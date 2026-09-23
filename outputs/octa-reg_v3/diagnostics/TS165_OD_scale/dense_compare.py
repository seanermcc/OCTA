"""Diagnostic-only similarity fits. Never applied to montage or calibration."""
from pathlib import Path
import json
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.optimize import minimize
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
paths=sorted((ROOT/'outputs/octa-reg_v1/prepared').glob('TS165_OD*.npz'))
review=json.loads((ROOT/'outputs/octa-reg_v2/all_samples/TS165_OD/human_review.json').read_text())
ims=[];poses=[];channels=[]
for p in paths:
    im=np.load(p)['enface'];lo,hi=np.nanpercentile(im,[2,98]);im=np.clip((im-lo)/(hi-lo),0,1)
    ims.append(im);poses.append(np.array(review['fields'][p.stem]['matrix_to_onh_pixels']))
    channels.append([gaussian_filter(im,1.5)-gaussian_filter(im,18),gaussian_filter(im,.8)-gaussian_filter(im,5)])
grid=np.indices((512,512))[:,::4,::4][::-1].reshape(2,-1).T
records=[]
for aa,bb in [(1,9),(2,9),(3,8),(3,9),(4,7),(5,7),(7,8),(8,9)]:
    a,b=aa-1,bb-1;manual=np.linalg.inv(poses[b])@poses[a]
    q=grid@manual[:2,:2].T+manual[:2,2]
    keep=(q.min(axis=1)>45)&(q.max(axis=1)<466)&(grid.min(axis=1)>15)&(grid.max(axis=1)<496)
    src=grid[keep];origin=src.mean(axis=0);target=origin@manual[:2,:2].T+manual[:2,2]
    theta=np.arctan2(manual[1,0],manual[0,0]);xx=src-origin
    def matrix(p):
        t=theta+p[0];scale=p[3] if len(p)>3 else 1.;rot=scale*np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
        m=np.eye(3);m[:2,:2]=rot;m[:2,2]=target+p[1:3]-origin@rot.T;return m
    def correlations(p,channel=0):
        m=matrix(p);dest=src@m[:2,:2].T+m[:2,2]
        good=(dest.min(axis=1)>5)&(dest.max(axis=1)<506)
        x=channels[a][channel][src[good,1],src[good,0]]
        y=map_coordinates(channels[b][channel],dest[good,::-1].T,order=1)
        return np.corrcoef(x,y)[0,1] if len(x)>100 else -1
    fits={}
    for mode in ('rigid','similarity'):
        bounds=[(-.18,.18),(-75,75),(-75,75)]+([(.75,1.35)] if mode=='similarity' else [])
        trials=[]
        for dx,dy in [(0,0),(-20,20),(20,-20)]:
            start=[0,dx,dy]+([1.] if mode=='similarity' else [])
            result=minimize(lambda p:-correlations(p),start,method='Powell',bounds=bounds,options={'maxiter':150,'xtol':1e-4,'ftol':1e-6})
            trials.append(result)
        best=min(trials,key=lambda r:r.fun)
        fits[mode]=dict(matrix=matrix(best.x).tolist(),scale=float(best.x[3]) if mode=='similarity' else 1.,correlation=float(-best.fun),fine_correlation=float(correlations(best.x,1)),sample_points=len(src),trials=[dict(scale=float(r.x[3]) if mode=='similarity' else 1.,corr=float(-r.fun)) for r in trials])
    record=dict(a=aa,b=bb,fits=fits);records.append(record)
    print(aa,bb,[(k,round(v['scale'],3),round(v['correlation'],3),round(v['fine_correlation'],3)) for k,v in fits.items()],flush=True)
    (OUT/'dense_fits.json').write_text(json.dumps(records,indent=2))
fig,axes=plt.subplots(4,3,figsize=(15,20))
full=np.indices((512,512))[::-1].reshape(2,-1).T
for row,(aa,bb) in enumerate([(1,9),(3,8),(4,7),(7,8)]):
    rec=next(r for r in records if r['a']==aa and r['b']==bb)
    for col,mode in enumerate(('rigid','similarity')):
        inv=np.linalg.inv(np.array(rec['fits'][mode]['matrix']));q=full@inv[:2,:2].T+inv[:2,2]
        w=map_coordinates(ims[aa-1],q[:,::-1].T,order=1,cval=np.nan).reshape(512,512)
        axes[row,col].imshow(w,cmap='gray',vmin=0,vmax=1);axes[row,col].set_title(f'Scan {aa} -> {bb}: {mode}, scale {rec["fits"][mode]["scale"]:.3f}')
    axes[row,2].imshow(ims[bb-1],cmap='gray',vmin=0,vmax=1);axes[row,2].set_title(f'Scan {bb}: native')
    for ax in axes[row]:ax.set_xticks(np.arange(0,513,64));ax.set_yticks(np.arange(0,513,64));ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(OUT/'diagnostic_fits.png',dpi=100)
