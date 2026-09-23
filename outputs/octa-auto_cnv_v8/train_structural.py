"""Fixed schedule, fresh initialization, resumable epoch-boundary state."""
from common import *
from models import UNet,StructuralCNN,masked_loss
from sampling_structural import Sampler
import torch,random,argparse

def run(model_id,resume=True):
    torch.set_num_threads(4);torch.manual_seed(267);torch.cuda.manual_seed_all(267);np.random.seed(267);random.seed(267)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    if not torch.cuda.is_available():raise RuntimeError('CUDA mixed precision required')
    device=torch.device('cuda');m=read(HERE/'data/manifest.json');stats_path=HERE/'data'/('normalization_enface.json' if model_id==1 else 'normalization_structural.json');stats=read(stats_path)
    contract=dict(seed=267,epochs=100,steps_per_epoch=32,effective_batch_size=4,microbatch=1,gradient_accumulation=4,lr=.001,weight_decay=.0001,model_id=model_id,selection='final scheduled epoch 100; no validation or early stopping',manifest_sha256=sha(HERE/'data/manifest.json'),normalization_sha256=sha(stats_path),model_code_sha256=sha(HERE/'models.py'),sampler_code_sha256=sha(HERE/'sampling_structural.py'),training_code_sha256=sha(__file__))
    folder=HERE/f'model{model_id}';write(folder/'config.json',contract)
    net=(UNet(19) if model_id==1 else StructuralCNN()).to(device);optimizer=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001)
    scaler=torch.amp.GradScaler('cuda',init_scale=1024);rng=np.random.default_rng(267);start=0
    sampler=Sampler(m,stats,model_id);last=folder/'checkpoints/latest.pt'
    if resume and last.exists():
        checkpoint=torch.load(last,map_location='cpu',weights_only=False)
        if checkpoint['config']!=contract:raise RuntimeError('Resume contract changed')
        net.load_state_dict(checkpoint['model']);optimizer.load_state_dict(checkpoint['optimizer']);scaler.load_state_dict(checkpoint['scaler']);start=checkpoint['epoch']
        torch.set_rng_state(checkpoint['torch_rng']);torch.cuda.set_rng_state_all(checkpoint['cuda_rng']);np.random.set_state(checkpoint['numpy_rng']);random.setstate(checkpoint['python_rng']);rng.bit_generator.state=checkpoint['sampler_rng'];sampler.counts.update(checkpoint['sampling_counts'])
    schedule=['positive','positive','background','hard'] if model_id==1 else ['positive','positive','background','background']
    for epoch in range(start,100):
        net.train();losses=[];t0=time.time()
        for step in range(32):
            optimizer.zero_grad(set_to_none=True)
            for kind in schedule:
                image,target,known=sampler.sample(rng,kind)
                x=torch.from_numpy(image[None]).to(device);y=torch.from_numpy(target[None]).to(device);k=torch.from_numpy(known[None]).to(device)
                with torch.autocast(device_type='cuda',dtype=torch.float16):logits=net(x);loss=masked_loss(logits,y,k,model_id)
                if not torch.isfinite(logits).all() or not torch.isfinite(loss):raise FloatingPointError(f'Model {model_id}: nonfinite epoch {epoch+1} step {step}')
                scaler.scale(loss/4).backward();losses.append(float(loss.detach()))
            scaler.unscale_(optimizer)
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in net.parameters()):raise FloatingPointError('Nonfinite gradients; run stopped')
            scaler.step(optimizer);scaler.update()
        record=dict(epoch=epoch+1,optimizer_steps=(epoch+1)*32,mean_fit_loss=float(np.mean(losses)),seconds=time.time()-t0,peak_gpu_bytes=torch.cuda.max_memory_allocated(),interpretation='training fit diagnostic only')
        with dest(folder/'training.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(record)+'\n')
        cp=dict(epoch=epoch+1,model=net.state_dict(),optimizer=optimizer.state_dict(),scaler=scaler.state_dict(),torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all(),numpy_rng=np.random.get_state(),python_rng=random.getstate(),sampler_rng=rng.bit_generator.state,config=contract,sampling_counts=dict(sampler.counts))
        tmp=dest(last.with_suffix('.tmp'));torch.save(cp,tmp);tmp.replace(last)
        if (epoch+1)%10==0:
            import shutil
            shutil.copyfile(last,dest(folder/f'checkpoints/epoch_{epoch+1:03d}.pt'))
        progress('Training fixed schedule',model=model_id,**record)
    import shutil
    shutil.copyfile(last,dest(folder/'checkpoints/final.pt'))
    write(folder/'complete.json',dict(config=contract,checkpoint=fingerprint(folder/'checkpoints/final.pt'),sampling_counts=dict(sampler.counts),completed_epochs=100,optimizer_steps=3200))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--model',type=int,choices=[2],required=True);args=parser.parse_args()
    try:run(args.model)
    except Exception as e:
        write(HERE/f'model{args.model}/FAILED.json',dict(error=repr(e),time=time.time()));raise

