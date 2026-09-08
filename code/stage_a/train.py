"""Reproducible animal-balanced training, resumable checkpoints and train-only smoke."""
import argparse
from collections import defaultdict
import json
import random
import time
from pathlib import Path
import numpy as np
import torch
from .common import DEFAULT,output_dir,write_json,fingerprint,digest
from .data import Dataset
from .model import BoundaryUNet,losses,decode


def code_identity():
    return digest({p.name:p.read_text(encoding="utf-8") for p in sorted(Path(__file__).parent.glob("*.py"))})


def save_checkpoint(path,model,optimizer,identity,config,step,epoch,best,rng):
    state=dict(model=model.state_dict(),optimizer=optimizer.state_dict(),identity=identity,
        config=config,step=step,epoch=epoch,best_validation=best,
        rng=rng.getstate(),torch_rng=torch.get_rng_state(),
        cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
        code_identity=code_identity(),experimental=True,validated=False)
    temp=Path(path).with_suffix(".tmp")
    torch.save(state,temp)
    temp.replace(path)


def load_checkpoint(path,device="cpu"):
    ck=torch.load(path,map_location="cpu",weights_only=True)
    model=BoundaryUNet(ck["config"]["base"]).to(device)
    model.load_state_dict(ck["model"])
    return model,ck


def validation_loss(model,data,device,region_weight):
    by=defaultdict(list)
    model.eval()
    with torch.no_grad():
        for i,r in enumerate(data.records):
            x,rows,valid,region=data.sample(i,device)
            a,b=model(x)
            loss,_=losses(a,b,rows,valid,region,region_weight)
            by[r["animal"]].append(float(loss))
    return float(np.mean([np.mean(v) for v in by.values()]))


def run(args):
    torch.set_num_threads(4)
    device=args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    data=Dataset(args.data,"train")
    # Smoke does not even instantiate validation or test datasets.
    val=None if args.smoke_steps else Dataset(args.data,"validation")
    out=output_dir(args.out)
    if (out/"last.pt").exists() and not args.resume:
        raise FileExistsError("Existing run; explicitly resume or choose a new directory")
    config=dict(base=args.base,lr=args.lr,region_weight=args.region_weight,seed=args.seed,
                sampling="uniform_animal_then_uniform_eligible_bscan",augmentation="horizontal_flip_only",
                steps_per_epoch=args.steps_per_epoch or len(data),smoke=bool(args.smoke_steps))
    rng=random.Random(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark=False
    torch.use_deterministic_algorithms(True,warn_only=True)
    model=BoundaryUNet(args.base).to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=1e-4)
    step,epoch,best=0,0,None
    if args.resume:
        model,ck=load_checkpoint(args.resume,device)
        if ck["identity"]!=data.identity or ck["config"]!=config or ck["code_identity"]!=code_identity():
            raise ValueError("Checkpoint data/config/code mismatch")
        opt=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=1e-4)
        opt.load_state_dict(ck["optimizer"])
        rng.setstate(ck["rng"])
        torch.set_rng_state(ck["torch_rng"])
        if ck["cuda_rng"]:
            torch.cuda.set_rng_state_all(ck["cuda_rng"])
        step,epoch,best=ck["step"],ck["epoch"],ck["best_validation"]
    start=time.monotonic(); events=[]
    groups={a:[i for i,r in enumerate(data.records) if r["animal"]==a] for a in data.animals}
    target_steps=step+args.smoke_steps if args.smoke_steps else args.epochs*config["steps_per_epoch"]
    while step<target_steps:
        model.train()
        animal=rng.choice(data.animals)
        index=rng.choice(groups[animal])
        x,rows,valid,region=data.sample(index,device,flip=rng.random()<.5)
        opt.zero_grad(set_to_none=True)
        a,b=model(x)
        loss,detail=losses(a,b,rows,valid,region,args.region_weight)
        if not torch.isfinite(loss):
            raise FloatingPointError("Non-finite training loss")
        loss.backward()
        grads=[p.grad for p in model.parameters() if p.grad is not None]
        if not all(torch.isfinite(g).all() for g in grads):
            raise FloatingPointError("Non-finite gradients")
        grad=float(torch.nn.utils.clip_grad_norm_(model.parameters(),5.0))
        if grad<=0:
            raise RuntimeError("Zero gradients")
        opt.step(); step+=1
        event=dict(step=step,key=data.records[index]["key"],animal=animal,
                   loss=float(loss.detach()),gradient_norm=grad,**detail)
        events.append(event)
        print(json.dumps(event),flush=True)
        if step%config["steps_per_epoch"]==0 or step==target_steps:
            epoch=step//config["steps_per_epoch"]
            if val is not None:
                v=validation_loss(model,val,device,args.region_weight)
                event["animal_macro_validation_loss"]=v
                if best is None or v<best:
                    best=v
                    save_checkpoint(out/"best.pt",model,opt,data.identity,config,step,epoch,best,rng)
            save_checkpoint(out/"last.pt",model,opt,data.identity,config,step,epoch,best,rng)
    # Checkpoint round-trip uses an unaugmented training sample only.
    x,*_=data.sample(0,device)
    model.eval()
    with torch.no_grad():
        expected=model(x)[0]
        restored,ck=load_checkpoint(out/"last.pt",device)
        restored.eval()
        actual=restored(x)[0]
        if not torch.equal(expected,actual):
            raise AssertionError("Checkpoint inference differs")
        pred,entropy=decode(actual)
        if pred.shape!=(1,8,x.shape[-1]) or not torch.isfinite(pred).all():
            raise AssertionError("Invalid prediction shape/values")
    write_json(out/f"run_step_{step:06d}.json",dict(config=config,identity=data.identity,
        code_identity=code_identity(),device=device,torch=torch.__version__,cuda=torch.version.cuda,
        parameters=sum(p.numel() for p in model.parameters()),events=events,
        elapsed_s=time.monotonic()-start,checkpoint_reload_exact=True,prediction_shape=list(pred.shape),
        smoke_train_only=bool(args.smoke_steps),test_accessed=False,
        peak_cuda_memory_bytes=torch.cuda.max_memory_allocated() if device.startswith("cuda") else None,
        promotion="experimental_software_smoke_only" if args.smoke_steps else "experimental_requires_scientific_acceptance"))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,default=DEFAULT)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--device")
    p.add_argument("--base",type=int,default=8)
    p.add_argument("--lr",type=float,default=3e-4)
    p.add_argument("--region-weight",type=float,default=.1)
    p.add_argument("--seed",type=int,default=20260908)
    p.add_argument("--epochs",type=int,default=40)
    p.add_argument("--steps-per-epoch",type=int)
    p.add_argument("--smoke-steps",type=int,default=0)
    p.add_argument("--resume",type=Path)
    run(p.parse_args())
