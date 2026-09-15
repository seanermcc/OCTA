"""Matched deterministic sampling, resumable learning and validation-only selection."""
from common import *
from dataset import tensor_inputs
from model import UNet, masked_loss, infer
import argparse
import random
import torch
from scipy import ndimage as ndi

CHANNELS={'A':2,'B':11,'C':19}
DEFAULT=dict(seed=267,epochs=100,batches=32,batch_size=4,learning_rate=.001,weight_decay=.0001,patience=15,tile=256,stride=128)

def configure(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True

class Sampler:
    def __init__(self,scans,seed):
        self.scans=scans;self.rng=np.random.default_rng(seed)
        self.positive=[i for i,d in enumerate(scans) if d['target'].any()]
        self.background=[i for i,d in enumerate(scans) if (d['known']&~d['target']).any()]
        self.choices={}
        # Acquisition is chosen uniformly before tile origin; training-only grid.
        for i,d in enumerate(scans):
            choices={True:[],False:[]}
            for y in range(0,257,16):
                for x in range(0,257,16):
                    t=d['target'][y:y+256,x:x+256];k=d['known'][y:y+256,x:x+256]
                    if k.any(): choices[bool(t.any())].append((y,x))
            self.choices[i]=choices
        self.background=[i for i in self.background if self.choices[i][False]]
        if not self.positive or not self.background: raise ValueError('Need positive and known-negative tile support')

    def tile(self,positive,augment=True):
        rng=self.rng;pool=self.positive if positive else self.background
        i=int(rng.choice(pool));d=self.scans[i]
        y,x=self.choices[i][positive][rng.integers(len(self.choices[i][positive]))]
        # Spatial jitter translates the crop in native space; no artificial edge padding.
        if augment:
            yy=int(np.clip(y+rng.integers(-12,13),0,256));xx=int(np.clip(x+rng.integers(-12,13),0,256))
            if bool(d['target'][yy:yy+256,xx:xx+256].any())==positive and d['known'][yy:yy+256,xx:xx+256].any(): y,x=yy,xx
        a=d['input'][:,y:y+256,x:x+256].copy();t=d['target'][y:y+256,x:x+256].copy();k=d['known'][y:y+256,x:x+256].copy()
        if augment:
            for axis in (0,1):
                if rng.random()<.5: a=np.flip(a,axis+1);t=np.flip(t,axis);k=np.flip(k,axis)
            a=a.copy()
            for c in range(2): a[c]=a[c]*rng.uniform(.9,1.1)+rng.uniform(-.1,.1)
        return np.ascontiguousarray(a),np.ascontiguousarray(t),np.ascontiguousarray(k),(i,y,x,positive)

    def batch(self,n):
        rows=[self.tile(i%2==0) for i in range(n)]
        return [np.stack([r[k] for r in rows]) for k in range(3)], [r[3] for r in rows]

def load_scans(experiment):
    m=read(HERE/'data/manifest.json');stats=read(HERE/'data/normalization.json');records=[]
    for r in m['scans']:
        d=npz(HERE/'data'/f"{r['scan_id']}.npz");d['input']=tensor_inputs(d,stats,experiment);d['record']=r;records.append(d)
    return records

def save_checkpoint(path,**data):
    p=dest(path);tmp=p.with_suffix('.tmp.pt');torch.save(data,tmp);tmp.replace(p)

def run(experiment,config=None):
    config=dict(DEFAULT,**(config or {}));out=HERE/f'experiment_{experiment}'
    if config['seed']!=267:out=out/f"seed_{config['seed']}"
    config.update(experiment=experiment,channels=CHANNELS[experiment],architecture='UNet 16,32,64,128,256; GroupNorm; random initialization',
                  manifest_sha256=sha(HERE/'data/manifest.json'),normalization_sha256=sha(HERE/'data/normalization.json'),
                  checkpoint_selection='Minimum full-field known-pixel validation loss on D49 only',
                  threshold_selection='D49 validation only after checkpoint selection',
                  model_code_sha256=sha(HERE/'model.py'),training_code_sha256=sha(Path(__file__)))
    if (out/'config.json').exists() and read(out/'config.json')!=config: raise ValueError('Configuration changed; preserve existing experiment')
    write(out/'config.json',config)
    if (out/'complete.json').exists():progress('Training already complete',experiment=experiment);return
    configure(config['seed']);device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    scans=load_scans(experiment);training=[d for d in scans if d['record']['split']=='train' and d['known'].any()]
    validation=[d for d in scans if d['record']['split']=='validation' and d['known'].any()]
    sampler=Sampler(training,config['seed']);net=UNet(CHANNELS[experiment]).to(device)
    optimizer=torch.optim.AdamW(net.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
    scaler=torch.amp.GradScaler('cuda',enabled=device.type=='cuda');history=[];best=float('inf');stale=0;start_epoch=0
    sampling_digest=hashlib.sha256();elapsed_prior=0
    if (out/'last.pt').exists():
        ck=torch.load(out/'last.pt',map_location=device,weights_only=False)
        assert ck['config']==config
        net.load_state_dict(ck['model']);optimizer.load_state_dict(ck['optimizer']);scaler.load_state_dict(ck['scaler'])
        history=ck['history'];best=ck['best'];stale=ck['stale'];start_epoch=ck['epoch']+1
        sampler.rng.bit_generator.state=ck['sampler_rng'];torch.set_rng_state(ck['torch_rng'].cpu())
        if device.type=='cuda':torch.cuda.set_rng_state_all([s.cpu() for s in ck['cuda_rng']])
        elapsed_prior=ck['elapsed_seconds']
    begin=time.monotonic()
    for epoch in range(start_epoch,config['epochs']):
        if stale>=config['patience']:break
        net.train();losses=[];epoch_start=time.monotonic();samples=[]
        for step in range(config['batches']):
            batch,coords=sampler.batch(config['batch_size']);samples.extend(coords)
            x,y,k=[torch.from_numpy(a).to(device) for a in batch]
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type,enabled=device.type=='cuda'):
                loss=masked_loss(net(x),y,k)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
            scaler.scale(loss).backward();scaler.unscale_(optimizer);torch.nn.utils.clip_grad_norm_(net.parameters(),5)
            scaler.step(optimizer);scaler.update();losses.append(float(loss.detach()))
        vals=[]
        for d in validation:
            p=infer(net,d['input'],device,config['batch_size'])
            logits=torch.from_numpy(np.log(np.clip(p,1e-6,1-1e-6)/np.clip(1-p,1e-6,1)))[None]
            vals.append(float(masked_loss(logits,torch.from_numpy(d['target'])[None],torch.from_numpy(d['known'])[None])))
        val=float(np.mean(vals));improved=val<best-1e-5
        if improved:best=val;stale=0
        else:stale+=1
        row=dict(epoch=epoch+1,training_loss=float(np.mean(losses)),validation_loss=val,seconds=time.monotonic()-epoch_start,
                 sampling_sha256=hashlib.sha256(json.dumps(samples).encode()).hexdigest(),best=improved)
        history.append(row)
        payload=dict(model=net.state_dict(),optimizer=optimizer.state_dict(),scaler=scaler.state_dict(),config=config,
            history=history,best=best,stale=stale,epoch=epoch,sampler_rng=sampler.rng.bit_generator.state,
            torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all() if device.type=='cuda' else [],
            elapsed_seconds=elapsed_prior+time.monotonic()-begin)
        save_checkpoint(out/'last.pt',**payload)
        if improved:save_checkpoint(out/'best.pt',**payload)
        csv_write(out/'history.csv',history)
        progress('Training',experiment=experiment,seed=config['seed'],**row,stale_epochs=stale)
    write(out/'complete.json',dict(epochs=len(history),best_epoch=min(history,key=lambda h:h['validation_loss'])['epoch'],
        best_validation_loss=best,elapsed_seconds=elapsed_prior+time.monotonic()-begin,device=str(device),
        gpu=torch.cuda.get_device_name(0) if device.type=='cuda' else None,best_checkpoint=fingerprint(out/'best.pt'),
        stopping='patience' if stale>=config['patience'] else 'epoch budget',config=config))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--experiment',choices=['A','B','C','all'],default='all');p.add_argument('--seed',type=int,default=267)
    args=p.parse_args()
    for ex in ('ABC' if args.experiment=='all' else args.experiment):run(ex,dict(seed=args.seed))
