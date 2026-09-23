"""Independent diagnostic fits, including branch-only scores and broad starts."""
from pathlib import Path
import json
import numpy as np
from scipy.ndimage import gaussian_filter,map_coordinates,binary_dilation
from scipy.optimize import minimize,OptimizeResult
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
paths=sorted((ROOT/'outputs/octa-reg_v1/prepared').glob('TS165_OD*.npz'))
review=json.loads((ROOT/'outputs/octa-reg_v2/all_samples/TS165_OD/human_review.json').read_text())
previous=json.loads((OUT/'dense_fits.json').read_text());sift=json.loads((OUT/'pair_fits.json').read_text())
ims=[];poses=[];channels=[];masks=[]
for p in paths:
    z=np.load(p);im=z['enface'];lo,hi=np.nanpercentile(im,[2,98]);im=np.clip((im-lo)/(hi-lo),0,1)
    ims.append(im);poses.append(np.array(review['fields'][p.stem]['matrix_to_onh_pixels']))
    channels.append([gaussian_filter(im,1.5)-gaussian_filter(im,18),gaussian_filter(im,.8)-gaussian_filter(im,5)])
    masks.append(binary_dilation(z['vessel'],iterations=5))
def prev(a,b):return np.array(next(r for r in previous if r['a']==a and r['b']==b)['fits']['similarity']['matrix'])
records=[]
for aa,bb in [(7,8),(8,9),(3,8),(4,7),(5,7),(1,9),(3,9)]:
    a,b=aa-1,bb-1;manual=np.linalg.inv(poses[b])@poses[a]
    seeds=[manual,prev(aa,bb)]
    sf=next((r for r in sift['pairs'] if r['a']==aa and r['b']==bb),None)
    if sf and 'SimilarityTransform' in sf['fits']:seeds.append(np.array(sf['fits']['SimilarityTransform']['matrix']))
    if aa==3 and bb==8:seeds.append(np.linalg.inv(prev(8,9))@prev(3,9))
    if aa==7 and bb==8:seeds.append(np.array([[1.,0.,-125],[0.,1.,25],[0.,0.,1.]]))
    grid=np.indices((512,512))[:,::3,::3][::-1].reshape(2,-1).T
    theta=np.arctan2(manual[1,0],manual[0,0]);origin=np.array([255.5,255.5]);xx=grid-origin
    def matrix(p):
        t=p[0];rot=p[3]*np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
        m=np.eye(3);m[:2,:2]=rot;m[:2,2]=p[1:3]-origin@rot.T;return m
    def correlations(p):
        m=matrix(p);dest=grid@m[:2,:2].T+m[:2,2]
        good=(dest.min(axis=1)>15)&(dest.max(axis=1)<496)&(grid.min(axis=1)>15)&(grid.max(axis=1)<496)
        src=grid[good];dst=dest[good]
        if len(src)<1500:return -1,-1,-1
        vals=[]
        fine=(~masks[a][src[:,1],src[:,0]])&(map_coordinates(masks[b].astype(float),dst[:,::-1].T,order=0)<.5)
        for c,sel in [(0,np.ones(len(src),bool)),(1,np.ones(len(src),bool)),(1,fine)]:
            x=channels[a][c][src[sel,1],src[sel,0]];y=map_coordinates(channels[b][c],dst[sel,::-1].T,order=1)
            vals.append(np.corrcoef(x,y)[0,1] if len(x)>500 else -1)
        return vals
    def objective(p):
        c=correlations(p);return -(.35*c[0]+.25*c[1]+.40*c[2])
    trials=[]
    for seed in seeds:
        t=np.arctan2(seed[1,0],seed[0,0]);s=np.linalg.norm(seed[:2,0]);dest=origin@seed[:2,:2].T+seed[:2,2]
        if not(.55<s<1.8):continue
        for factor in (1.,1.2):
            x=[t,*dest,min(s*factor,1.7)]
            bounds=[(t-.20,t+.20),(dest[0]-110,dest[0]+110),(dest[1]-110,dest[1]+110),(.55,1.8)]
            trials.append(OptimizeResult(x=np.array(x),fun=objective(x)))
            simplex=np.tile(x,(5,1)).astype(float)
            for j,step in enumerate([.02,5.,5.,.02]):simplex[j+1,j]+=step
            r=minimize(objective,x,method='Nelder-Mead',bounds=bounds,options={'maxiter':450,'xatol':.002,'fatol':1e-5,'initial_simplex':simplex})
            trials.append(r)
    best=min(trials,key=lambda r:r.fun);m=matrix(best.x)
    rec=dict(a=aa,b=bb,matrix=m.tolist(),scale=float(best.x[3]),scores=list(correlations(best.x)),trials=[dict(scale=float(r.x[3]),scores=list(correlations(r.x))) for r in trials])
    records.append(rec);print(aa,bb,round(rec['scale'],4),np.round(rec['scores'],3),flush=True)
    (OUT/'refined_fits.json').write_text(json.dumps(records,indent=2))
fig,axes=plt.subplots(len(records),2,figsize=(12,len(records)*6))
full=np.indices((512,512))[::-1].reshape(2,-1).T
for row,rec in enumerate(records):
    inv=np.linalg.inv(rec['matrix']);q=full@inv[:2,:2].T+inv[:2,2]
    w=map_coordinates(ims[rec['a']-1],q[:,::-1].T,order=1,cval=np.nan).reshape(512,512)
    axes[row,0].imshow(w,cmap='gray',vmin=0,vmax=1);axes[row,0].set_title(f'Scan {rec["a"]} at diagnostic scale {rec["scale"]:.3f}')
    axes[row,1].imshow(ims[rec['b']-1],cmap='gray',vmin=0,vmax=1);axes[row,1].set_title(f'Scan {rec["b"]} native')
    for ax in axes[row]:ax.set_xticks(np.arange(0,513,64));ax.set_yticks(np.arange(0,513,64));ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(OUT/'refined_fits.png',dpi=100)
