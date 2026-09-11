"""Fixed-budget animal-separated training, resumable at every 100 steps."""
import argparse
import json
import random
import time
import numpy as np
import torch
from stage_a.model import BoundaryUNet, losses
from .model import StateNet, evidence, state_loss
from .common import *

def protocol():
    m=json.loads((OUT/"data/manifest.json").read_text())
    animals=sorted({r["animal"] for r in m["records"]})
    evaluated=["TS165","TS247","TS283","TS325"]
    folds=[dict(name=a, evaluation=[a], calibration=[evaluated[(i+1)%4]],
        training=sorted(set(animals)-{a,evaluated[(i+1)%4]}),initialization="random",steps=1800) for i,a in enumerate(evaluated)]
    folds.append(dict(name="ALL_LABELLED",evaluation=[],calibration=[],training=animals,
        initialization=str(PREVIOUS/"models/ALL_LABELLED/last.pt"),steps=600))
    correction=json.loads((OUT/"data/state_semantics_correction.json").read_text()) if (OUT/"data/state_semantics_correction.json").exists() else {}
    return dict(dataset_id=m["dataset_id"], position_parent_protocol_id=correction.get("parent_position_protocol_id"), folds=folds, base=8, lr=.0003,
        state_steps=900, state_seed=610, position_seed=609, lateral_crop=128,
        position_targets="exact local manual strokes only", selection="fixed budget, no early stopping on calibration/evaluation",
        state_ablation="paired state models with identical initialization/sampling, vessel context and defaults both omitted in ablation",
        final_test=False, experimental=True),m

def atomic_torch(path,data):
    directory(path.parent); tmp=path.with_suffix(".tmp.pt");torch.save(data,tmp);tmp.replace(path)

def load_position(path,device="cuda"):
    ck=torch.load(path,map_location="cpu",weights_only=True)
    net=BoundaryUNet(8).to(device);net.load_state_dict(ck["model"]);net.eval()
    return net,ck

def train_position(fold, records, data, pid):
    out=directory(OUT/"models"/fold["name"]); path=out/"position.pt"
    torch.manual_seed(609);rng=random.Random(609)
    net=BoundaryUNet(8).cuda();opt=torch.optim.AdamW(net.parameters(),lr=.0003)
    step=0;history=[]
    if path.exists():
        ck=torch.load(path,map_location="cpu",weights_only=True)
        allowed={pid,json.loads((OUT/"models/protocol.json").read_text()).get("position_parent_protocol_id")}
        if ck["protocol_id"] not in allowed: raise ValueError("Resume protocol changed")
        if ck["step"]>=fold["steps"]:return
        net.load_state_dict(ck["model"]);opt.load_state_dict(ck["optimizer"])
        rng.setstate(ck["rng"]);torch.set_rng_state(ck["torch_rng"])
        torch.cuda.set_rng_state_all(ck["cuda_rng"])
        step=ck["step"];history=ck["history"]
    elif fold["initialization"]!="random":
        ck=torch.load(fold["initialization"],map_location="cpu",weights_only=True)
        if fold["evaluation"] or fold["calibration"]: raise ValueError("All-label weights forbidden in excluded folds")
        net.load_state_dict(ck["model"])
    eligible=[r for r in records if r["animal"] in fold["training"] and data[r["key"]]["valid"].any()]
    groups={a:[r for r in eligible if r["animal"]==a] for a in sorted({r["animal"] for r in eligible})}
    start=time.monotonic();values=[]
    net.train()
    while step<fold["steps"]:
        a=rng.choice(list(groups));r=rng.choice(groups[a]);d=data[r["key"]]
        # Pick a crop with actual manual targets; no synthetic positions.
        cols=np.flatnonzero(d["valid"].any(0));center=int(rng.choice(cols.tolist()))
        lo=max(0,min(center-rng.randrange(128),d["x"].shape[-1]-128));sl=slice(lo,lo+128)
        x=torch.from_numpy(d["x"][None,...,sl].copy()).cuda()
        rows=torch.from_numpy(d["rows"][None,...,sl].copy()).cuda()
        valid=torch.from_numpy(d["valid"][None,...,sl].copy()).cuda()
        if rng.random()<.5:x=x.flip(-1);rows=rows.flip(-1);valid=valid.flip(-1)
        region=torch.full(x.shape[:1]+x.shape[2:],-100,dtype=torch.long,device="cuda")
        opt.zero_grad(set_to_none=True)
        with torch.autocast("cuda",dtype=torch.bfloat16):logits,regions=net(x)
        loss,_=losses(logits.float(),regions.float(),rows,valid,region,region_weight=0)
        if not torch.isfinite(loss):raise FloatingPointError("Nonfinite position loss")
        loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5.)
        if not torch.isfinite(norm):raise FloatingPointError("Nonfinite gradient")
        opt.step();step+=1;values.append(float(loss.detach()))
        if step%100==0 or step==fold["steps"]:
            history.append(dict(step=step,loss=float(np.mean(values)),elapsed_this_invocation_s=time.monotonic()-start));values=[]
            atomic_torch(path,dict(model=net.state_dict(),optimizer=opt.state_dict(),step=step,
                rng=rng.getstate(),torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all(),
                history=history,fold=fold,protocol_id=pid,position_targets="strict"))
            write_csv(out/"position_history.csv",history)
            progress("position training",fold=fold["name"],step=step,total=fold["steps"])

def feature_cache(fold,records,data,pid):
    if (OUT/"features"/fold["name"]/"complete.json").exists():return
    net,ck=load_position(OUT/"models"/fold["name"]/"position.pt")
    path=directory(OUT/"features"/fold["name"])
    start=time.monotonic()
    for i,r in enumerate(records):
        dst=path/f"{r['key']}.npz"
        if dst.exists():continue
        with torch.no_grad(),torch.autocast("cuda",dtype=torch.bfloat16):
            x=torch.from_numpy(data[r["key"]]["x"][None]).cuda();logits,_=net(x)
            f,rows,entropy=evidence(logits,x)
        save_npz(dst,features=f[0].cpu().numpy(),rows=rows[0].cpu().numpy(),entropy=entropy[0].cpu().numpy())
        if i%40==0:progress("state evidence cache",fold=fold["name"],completed=i+1,total=len(records))
    del net;torch.cuda.empty_cache()
    write_json(path/"complete.json",dict(protocol_id=pid,seconds=time.monotonic()-start))

def train_states(fold,records,data,pid,steps):
    eligible=[r for r in records if r["animal"] in fold["training"] and
        ((data[r["key"]]["trace_target"]>=0).any() or (data[r["key"]]["reliability_target"]>=0).any())]
    # State-only rejected records survive independently of position eligibility.
    groups={a:[r for r in eligible if r["animal"]==a] for a in sorted({r["animal"] for r in eligible})}
    features={r["key"]:load_npz(OUT/"features"/fold["name"]/f"{r['key']}.npz")["features"] for r in eligible}
    for vessel in (True,False):
        path=OUT/"models"/fold["name"]/("states.pt" if vessel else "states_no_vessels.pt")
        torch.manual_seed(610);rng=random.Random(610);net=StateNet().cuda();opt=torch.optim.AdamW(net.parameters(),lr=.001)
        step=0;history=[]
        if path.exists():
            ck=torch.load(path,map_location="cpu",weights_only=True)
            if ck["protocol_id"]!=pid:raise ValueError("State resume protocol changed")
            if ck["step"]>=steps:continue
            net.load_state_dict(ck["model"]);opt.load_state_dict(ck["optimizer"]);step=ck["step"]
            rng.setstate(ck["rng"]);history=ck["history"]
        start=time.monotonic();values=[]
        while step<steps:
            batch=[rng.choice(groups[rng.choice(list(groups))]) for _ in range(4)]
            f=torch.from_numpy(np.stack([features[r["key"]] for r in batch])).cuda()
            arrays=[torch.from_numpy(np.stack([data[r["key"]][key] for r in batch])).cuda() for key in ("trace_target","reliability_target","vessel")]
            if rng.random()<.5:f=f.flip(-1);arrays=[a.flip(-1) for a in arrays]
            t,rel,v=arrays
            opt.zero_grad(set_to_none=True);loss=state_loss(net(f,v,vessel),t,rel,v,vessel)
            loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5.)
            if not torch.isfinite(norm):raise FloatingPointError("Nonfinite state gradient")
            opt.step();step+=1;values.append(float(loss.detach()))
            if step%100==0 or step==steps:
                history.append(dict(step=step,loss=float(np.mean(values)),elapsed_this_invocation_s=time.monotonic()-start));values=[]
                atomic_torch(path,dict(model=net.state_dict(),optimizer=opt.state_dict(),step=step,rng=rng.getstate(),
                    history=history,fold=fold,protocol_id=pid,use_vessels=vessel))
                progress("state training",fold=fold["name"],vessels=vessel,step=step,total=steps)

def run(only=None):
    torch.set_num_threads(4);torch.backends.cudnn.benchmark=False
    torch.use_deterministic_algorithms(True,warn_only=True)
    p,m=protocol();pid=digest(p)
    if (OUT/"models/protocol.json").exists() and json.loads((OUT/"models/protocol.json").read_text())!=p:
        raise ValueError("Frozen protocol changed")
    write_json(OUT/"models/protocol.json",p)
    data={r["key"]:load_npz(r["cache"]["path"]) for r in m["records"]}
    for fold in p["folds"]:
        if only and fold["name"]!=only:continue
        start=time.monotonic()
        train_position(fold,m["records"],data,pid)
        feature_cache(fold,m["records"],data,pid)
        train_states(fold,m["records"],data,pid,p["state_steps"])
        marker=OUT/"models"/fold["name"]/"complete.json"
        if not marker.exists():write_json(marker,dict(protocol_id=pid,seconds=time.monotonic()-start,fold=fold))
    progress("training invocation complete")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--fold");run(p.parse_args().fold)
