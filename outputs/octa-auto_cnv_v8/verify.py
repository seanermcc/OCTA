"""Acceptance contracts and small, discarded real-data training sanity fits."""
from common import *
from models import *
from legacy import tensor_inputs
from sampling import windows
from v6_model import infer
import torch

def contracts():
    results=[]
    for model,shape in [(1,(2,16,16)),(2,(2,256))]:
        z=torch.randn(shape,requires_grad=True);y=torch.zeros(shape);k=torch.ones(shape,dtype=torch.bool);k[...,::2]=False;y[...,1]=1
        base=masked_loss(z,y,k,model);base.backward();assert (z.grad[~k]==0).all()
        changed=z.detach().clone();changed[~k]=float('nan');yy=y.clone();yy[~k]=float('nan')
        assert torch.equal(base.detach(),masked_loss(changed,yy,k,model))
        assert masked_loss(changed,yy,torch.zeros_like(k),model)==0
        results.append(f'model{model}: unknown target/logit values have zero loss and gradient')
    assert neighbors(0).tolist()==[0,0,0,1,2] and neighbors(511).tolist()==[509,510,511,511,511]
    mask=np.zeros((64,64),bool);mask[10,10]=True;mask[20:40,20:40]=True;mask[30,40:55]=True;mask[45:50,45:50]=True
    out,reasons=filter_mask(mask)
    assert not out['filtered_mask'][10,10] and not out['filtered_mask'][30,50] and not out['filtered_mask'][47,47]
    assert out['filtered_mask'][25:35,25:35].all() and out['removal_reason'][47,47]==2
    irregular=np.zeros((64,64),bool);irregular[10:45,10:20]=True;irregular[35:45,10:48]=True
    filt,_=filter_mask(irregular);assert filt['filtered_mask'][38,35] and filt['filtered_mask'][15,15]
    assert all(r['pixels']==r['opening_pixels']+r['below_64_pixels'] for r in reasons)
    results.append('filter: tiny fragments/spurs removed; substantial irregular footprint retained; legitimate small footprints can be suppressed and remain inspectable')
    d=dict(optical=np.ones((2,512,512)),thickness_um=np.ones((8,512,512)),availability=np.ones((8,512,512),bool),shadow=np.zeros((512,512),bool))
    d['thickness_um'][:,0,0]=np.nan;d['availability'][:,0,0]=False
    stats={k:dict(center=[0]*n,scale=[1]*n) for k,n in [('optical',2),('thickness_um',8)]}
    before=tensor_inputs(d,stats,'C');d.update(target=np.ones((512,512)),ignored=np.ones((512,512)),human_reliability=np.zeros((512,512)))
    assert np.array_equal(before,tensor_inputs(d,stats,'C')) and before.shape==(19,512,512)
    assert np.isnan(d['thickness_um'][:,0,0]).all() and (before[11:,0,0]==0).all()
    results.append('Model1 input whitelist: annotations/exclusions/reliability cannot enter channels; measurement NaNs preserved')
    class Identity2D(torch.nn.Module):
        def forward(self,x):return x[:,0]
    field=np.linspace(-2,2,512*512,dtype=np.float32).reshape(512,512)
    actual=infer(Identity2D(),field[None],torch.device('cpu'))
    assert np.allclose(actual,1/(1+np.exp(-field)),atol=1e-6)
    class IdentityRow(torch.nn.Module):
        def forward(self,x):return x[:,2].mean(1)
    volume=np.broadcast_to(field[:,None,:],(512,8,512))
    actual=infer_structural(IdentityRow(),volume,dict(center=0,scale=1),torch.device('cpu'))
    assert np.allclose(actual,1/(1+np.exp(-field)),atol=1e-6)
    from inference_structural import infer_structural as batched_infer
    assert np.allclose(batched_infer(IdentityRow(),volume,dict(center=0,scale=1),torch.device('cpu')),actual,atol=1e-6)
    results.append('native en-face and central-row lateral stitching: full edge coverage, weighted identity reconstruction')
    a=np.zeros((512,512),bool);a[300,300]=True;pc=windows(a,256,256)
    assert pc[45,45]==1 and pc[44,44]==0
    results.append('sampling integrals: positive-free difficult backgrounds and native patch coordinates')
    from audit import v7_targets
    manifest=read(HERE/'data/manifest.json')
    for r in manifest['records']:
        verify(r['source']);verify(r['target_file'])
        if r['version']=='v7':v7_targets(read(r['source']['path']),r['acquisition'])
    ids={r['scan_id'] for r in manifest['records']};preview=read(HERE/'data/preview.json')['cases']
    assert len(preview)==30 and sum(p['training_exposure'] for p in preview)==10
    assert all((p['scan_id'] in ids)==p['training_exposure'] for p in preview)
    assert not ids.intersection(r['scan_id'] for r in manifest['blocked'])
    results.append('v7 confirmation hashes, exact saved masks, deferred blocking and 10/20 preview exposure contract')
    write(HERE/'verification/contracts.json',dict(passed=True,checks=results))
    print(json.dumps(results),flush=True)

def sanity():
    torch.set_num_threads(4);torch.manual_seed(267);device=torch.device('cuda')
    manifest=read(HERE/'data/manifest.json');record=next(r for r in manifest['records'] if r['positive_pixels'] and (HERE/'cache'/r['scan_id']/'manifest.json').exists())
    sid=record['scan_id'];z=npz(record['target_file']['path']);loc=np.argwhere(z['target']);row,x=loc[len(loc)//2];x=int(np.clip(x-128,0,256));top=int(np.clip(row-128,0,256))
    d=npz(HERE/'cache'/sid/'enface.npz');s={}
    for k in ['optical','thickness_um']:
        s[k]=dict(center=np.nanmedian(d[k],axis=(1,2)),scale=np.maximum(np.nanstd(d[k],axis=(1,2)),.01))
    volume=np.load(HERE/'cache'/sid/'structural.npy',mmap_mode='r');vals=volume[::32,::16,::16]
    ss=dict(center=float(vals.mean()),scale=max(float(vals.std()),.01));results=[]
    for model_id in [1,2]:
        torch.manual_seed(267);net=(UNet(19) if model_id==1 else StructuralCNN()).to(device)
        if model_id==1:image=tensor_inputs(d,s,'C')[:,top:top+256,x:x+256];target=z['target'][top:top+256,x:x+256];known=z['known'][top:top+256,x:x+256]
        else:image=structural_patch(volume,int(row),x,ss);target=z['target'][row,x:x+256];known=z['known'][row,x:x+256]
        xx=torch.from_numpy(image[None]).to(device);yy=torch.from_numpy(target[None]).to(device);kk=torch.from_numpy(known[None]).to(device)
        opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001);scaler=torch.amp.GradScaler('cuda',init_scale=1024);losses=[];t=time.time();torch.cuda.reset_peak_memory_stats()
        for i in range(8):
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type='cuda'):logits=net(xx);loss=masked_loss(logits,yy,kk,model_id)
            assert torch.isfinite(loss) and torch.isfinite(logits).all();scaler.scale(loss).backward();scaler.step(opt);scaler.update();losses.append(float(loss.detach()))
        assert min(losses[1:])<losses[0],losses
        if model_id==2:
            with torch.no_grad():_,maps=net(xx,return_attention=True)
            assert all(torch.allclose(a.sum(2),torch.ones_like(a.sum(2)),atol=1e-5) for a in maps)
            assert logits.shape==(1,256)
        results.append(dict(model=model_id,scan_id=sid,losses=losses,seconds=time.time()-t,peak_gpu_bytes=torch.cuda.max_memory_allocated(),weights_discarded=True,normalization='sanity-patch inputs only; not deployment normalization'))
        del net,opt,xx,yy,kk,logits,loss;torch.cuda.empty_cache()
    write(HERE/'verification/sanity.json',dict(passed=True,results=results));print(json.dumps(results),flush=True)
if __name__=='__main__':
    contracts()
    if '--sanity' in sys.argv:sanity()
