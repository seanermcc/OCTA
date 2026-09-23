"""Identical fresh compact U-Nets; deterministic, animal-balanced fixed-budget fits."""
from common import *
from models import UNet,masked_loss
from prepare import normalization,input_tensor
from collections import defaultdict,Counter
import torch,random,shutil,gc

def windows(mask):
 v=np.pad(mask.astype('int32'),((1,0),(1,0))).cumsum(0).cumsum(1)
 return v[256:,256:]-v[:-256,256:]-v[256:,:-256]+v[:-256,:-256]
class Sampler:
 def __init__(self,records,stats,model):
  self.data={};self.pools=defaultdict(lambda:defaultdict(list));self.counts=Counter();self.audit=[]
  for r in records:
   sid=r['scan_id'];z=npz(r['target_file']['path']);p=z['target'];k=z['known'];pc=windows(p);bc=windows(k&~p);hc=windows(npz(HERE/'cache'/sid/'hard.npz')['mask']&k&~p)
   coords=dict(positive=np.argwhere(pc>0),background=np.argwhere((pc==0)&(bc>0)),hard=np.argwhere((pc==0)&(bc>0)&(hc>0)),assessed=np.argwhere(windows(k)>0))
   self.data[sid]=dict(input=input_tensor(sid,stats,model),target=p,known=k,coords=coords)
   for kind,c in coords.items():
    if len(c):self.pools[r['animal']][kind].append(sid)
   self.audit.append(dict(scan_id=sid,animal=r['animal'],pools={k:len(v) for k,v in coords.items()}))
  self.animals=sorted(self.pools)
  if not self.animals:raise ValueError('Empty sampling cohort')
 def sample(self,rng,requested):
  animal=str(rng.choice(self.animals));kind=requested
  # Preserve animal balance. Missing positives do not drop negative-only animals.
  fallbacks={'positive':['positive','background','assessed'],'background':['background','assessed'],'hard':['hard','background','assessed']}
  kind=next(k for k in fallbacks[requested] if self.pools[animal][k])
  if kind!=requested:self.counts[f'fallback:{requested}->{kind}']+=1
  sid=str(rng.choice(self.pools[animal][kind]));e=self.data[sid];coords=e['coords'][kind];y,x=coords[rng.integers(len(coords))]
  image=e['input'][:,y:y+256,x:x+256].copy();target=e['target'][y:y+256,x:x+256].copy();known=e['known'][y:y+256,x:x+256].copy()
  if rng.random()<.5:image=image[:,:,::-1].copy();target=target[:,::-1].copy();known=known[:,::-1].copy()
  if kind in ('background','hard') and target.any():raise AssertionError('Background patch contains truth')
  for key in ['animal:'+animal,'scan:'+sid,'actual:'+kind,'requested:'+requested]:self.counts[key]+=1
  return image,target.astype('float32'),known.astype('float32')

def train(name,model,animals):
 folder=HERE/'fits'/name;done=folder/'complete.json';protocol=read(HERE/'data/protocol.json');manifest=read(HERE/'data/supervision.json');records=[r for r in manifest['records'] if r['animal'] in animals]
 source_files=['training.py','models.py','v6_model.py','legacy.py','prepare.py','context.py','common.py']
 code={n:sha(HERE/n) for n in source_files}
 if done.exists():
  d=read(done);verify(d['checkpoint'])
  if d['contract']['code']!=code or d['contract']['protocol_sha256']!=sha(HERE/'data/protocol.json'):raise RuntimeError('Completed training code/contract changed')
  return d
 torch.set_num_threads(4);torch.manual_seed(267);torch.cuda.manual_seed_all(267);np.random.seed(267);random.seed(267)
 torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 if not torch.cuda.is_available():raise RuntimeError('CUDA required for baseline mixed-precision schedule')
 stats=normalization(records);sp=folder/'normalization.json'
 if sp.exists() and read(sp)!=stats:raise ValueError('Normalization changed on resume')
 if not sp.exists():write(sp,stats)
 contract=dict(name=name,model=model,training_animals=sorted(animals),training_scan_ids=stats['training_scan_ids'],protocol_sha256=sha(HERE/'data/protocol.json'),supervision_sha256=sha(HERE/'data/supervision.json'),normalization_sha256=sha(sp),code=code,channels=19 if model==1 else 30,seed=267,epochs=100,steps_per_epoch=32,effective_batch=4,microbatch=4,loss='v8 model1 weighted BCE (background x2) plus 0.5 positive-tile Dice for BOTH models',fresh_weights=True)
 write(folder/'config.json',contract);net=UNet(contract['channels']).cuda();opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001);scaler=torch.amp.GradScaler('cuda',init_scale=1024);rng=np.random.default_rng(267);sampler=Sampler(records,stats,model)
 write(folder/'sampling_pools.json',dict(records=sampler.audit,policy='animal uniformly first; positive->background->assessed, hard->background->assessed, background->assessed; then scan/window uniformly; all fallbacks counted'))
 last=folder/'latest.pt';start=0
 if last.exists():
  cp=torch.load(last,map_location='cpu',weights_only=False)
  if cp['contract']!=contract:raise RuntimeError('Resume contract changed')
  net.load_state_dict(cp['model']);opt.load_state_dict(cp['optimizer']);scaler.load_state_dict(cp['scaler']);start=cp['epoch'];torch.set_rng_state(cp['torch_rng']);torch.cuda.set_rng_state_all(cp['cuda_rng']);np.random.set_state(cp['numpy_rng']);random.setstate(cp['python_rng']);rng.bit_generator.state=cp['sampler_rng'];sampler.counts.update(cp['sampling_counts'])
 progress('Training',fit=name,epoch=start,total=100,animals=animals)
 for epoch in range(start,100):
  net.train();losses=[];t=time.time()
  for step in range(32):
   opt.zero_grad(set_to_none=True)
   batch=[sampler.sample(rng,kind) for kind in ('positive','positive','background','hard')]
   x,y,k=[torch.from_numpy(np.stack([sample[j] for sample in batch])).cuda() for j in range(3)]
   with torch.autocast('cuda',dtype=torch.float16):z=net(x);loss=masked_loss(z,y,k,1)
   if not torch.isfinite(z).all() or not torch.isfinite(loss):raise FloatingPointError('Nonfinite fit')
   scaler.scale(loss).backward();losses.append(float(loss.detach()))
   scaler.unscale_(opt)
   if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in net.parameters()):raise FloatingPointError('Nonfinite gradients')
   scaler.step(opt);scaler.update()
  cp=dict(epoch=epoch+1,optimizer_steps=(epoch+1)*32,model=net.state_dict(),optimizer=opt.state_dict(),scaler=scaler.state_dict(),torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all(),numpy_rng=np.random.get_state(),python_rng=random.getstate(),sampler_rng=rng.bit_generator.state,sampling_counts=dict(sampler.counts),contract=contract)
  tmp=dest(last.with_suffix('.tmp'));torch.save(cp,tmp);os.replace(tmp,last)
  record=dict(epoch=epoch+1,optimizer_steps=(epoch+1)*32,mean_fit_loss=float(np.mean(losses)),seconds=time.time()-t)
  write(folder/'epochs'/f'{epoch+1:03d}.json',record)
  if (epoch+1)%5==0:progress('Training',fit=name,**record)
 final=dest(folder/'final.pt');tmp=final.with_suffix('.tmp');torch.save(dict(model=net.state_dict(),contract=contract,epoch=100),tmp);os.replace(tmp,final)
 d=dict(contract=contract,checkpoint=fingerprint(final),completed_epochs=100,optimizer_steps=3200,sampling_counts=dict(sampler.counts));write(done,d)
 del net,opt,sampler;gc.collect();torch.cuda.empty_cache();return d

def predict(name,acquisitions):
 from v6_model import infer
 folder=HERE/'fits'/name;d=read(folder/'complete.json');verify(d['checkpoint']);cp=torch.load(d['checkpoint']['path'],map_location='cpu',weights_only=False);contract=cp['contract'];stats=read(folder/'normalization.json');device=torch.device('cuda');net=UNet(contract['channels']).to(device);net.load_state_dict(cp['model']);net.eval();torch.set_num_threads(4)
 for a in acquisitions:
  sid=a['scan_id'];out=folder/'predictions'/(sid+'.npz');jp=out.with_suffix('.json')
  if jp.exists():
   doc=read(jp);verify(doc['prediction'])
   if doc['checkpoint']['sha256']!=d['checkpoint']['sha256']:raise ValueError('Prediction checkpoint changed')
   continue
  score=infer(net,input_tensor(sid,stats,contract['model']),device,batch_size=4)
  if score.shape!=(512,512) or not np.isfinite(score).all() or score.min()<0 or score.max()>1:raise ValueError('Invalid predictions')
  save(out,score=score,raw_mask=score>=.7,scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'))
  write(jp,dict(scan_id=sid,animal=a['animal'],source_identity=a['source_identity'],prediction=fingerprint(out),checkpoint=d['checkpoint'],training_animals=contract['training_animals'],animal_out_of_sample=a['animal'] not in contract['training_animals'],raw_threshold=.7,input_manifest_sha256=sha(HERE/'cache'/sid/'manifest.json')))
 del net;gc.collect();torch.cuda.empty_cache()
