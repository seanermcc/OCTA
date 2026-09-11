"""Descriptive diagnostics, never confidence labels or surface corrections."""
import numpy as np
from scipy.ndimage import median_filter,distance_transform_edt
from octa_seg_v1.decisions import runs
from eight_surface.config import SURFACE_NAMES,LAYER_DEFS

LAYERS=LAYER_DEFS+[('INNER_RETINA','ILM','IPL_INL')]

def stats(values):
    x=np.asarray(values); x=x[np.isfinite(x)]
    if not len(x):return dict(n=0,mean=None,median=None,std=None,iqr=None,p95=None,max=None)
    q=np.quantile(x,[.25,.5,.75,.95])
    return dict(n=int(x.size),mean=float(x.mean()),median=float(q[1]),std=float(x.std()),
                iqr=float(q[2]-q[0]),p95=float(q[3]),max=float(x.max()))

def roughness(rows, scale=1.12):
    """Last axis only. Jumps belong to their right endpoint; gaps stay NaN.

    Nine-column median uses nearest endpoint padding within each finite run.
    No values from the other side of a gap can affect either diagnostic.
    """
    z=np.asarray(rows)*scale
    jump=np.full(z.shape,np.nan,np.float32);dev=np.full_like(jump,np.nan)
    good=np.isfinite(z[...,1:])&np.isfinite(z[...,:-1])
    jump[...,1:]=np.where(good,np.abs(np.diff(z,axis=-1)),np.nan)
    for source,target in zip(z.reshape(-1,z.shape[-1]),dev.reshape(-1,z.shape[-1])):
        for lo,hi in runs(np.isfinite(source)):
            target[lo:hi]=np.abs(source[lo:hi]-median_filter(source[lo:hi],size=9,mode='nearest'))
    return jump,dev

def warnings(jump,dev):
    out={}
    for name,a in [('jump',jump),('spike',dev)]:
        out.update({f'{name}_{k}_um':v for k,v in stats(a).items() if k!='n'})
        n=int(np.isfinite(a).sum());out[name+'_eligible']=n
        for threshold in (10,20,40):
            out[f'{name}_gt{threshold}_fraction']=float(np.sum(a>threshold)/n) if n else None
    return out

def invalid_positions(rows,depth=1024):
    invalid=~np.isfinite(rows)|(rows<0)|(rows>depth-1)
    cross=np.isfinite(rows[:,:-1])&np.isfinite(rows[:,1:])&(rows[:,:-1]>=rows[:,1:])
    invalid[:,:-1]|=cross;invalid[:,1:]|=cross
    return invalid,cross

def diagnostic_thickness(rows,shadow,depth=1024):
    invalid,cross=invalid_positions(rows,depth)
    maps=[];failure=[]
    for _,top,bottom in LAYERS:
        a=SURFACE_NAMES.index(top);b=SURFACE_NAMES.index(bottom)
        delta=(rows[:,b]-rows[:,a])*1.12
        failed=invalid[:,a:b+1].any(axis=1)|(delta<=0)
        maps.append(np.where(~failed&~shadow,delta,np.nan));failure.append(failed)
    return np.stack(maps,1),np.stack(failure,1),invalid,cross

def onh_distance(sid,g):
    if sid.startswith('TS165_') and g['onh'].any():
        return distance_transform_edt(~g['onh'],sampling=1460/512).astype(np.float32),'distance to annotated ONH mask (inside=0)'
    if sid.startswith('TS283_') and g['onh_edge'].any():
        return distance_transform_edt(~g['onh_edge'],sampling=1460/512).astype(np.float32),'partial-edge proxy (not full ONH distance)'
    return np.full(g['shadow'].shape,np.nan,np.float32),'unknown; no location inferred'

def select_strips(sid,entropy,spike,seed):
    """Two uniform random tiles, one entropy and one spike tile; spatially separated."""
    rng=np.random.default_rng(seed);candidates=[]
    for b in range(entropy.shape[0]):
        for lo in range(0,entropy.shape[-1],64):
            e=entropy[b,:,lo:lo+64];s=spike[b,:,lo:lo+64]
            candidates.append(dict(scan_id=sid,bscan=b,lo=lo,hi=min(lo+64,entropy.shape[-1]),
                 entropy_p95=stats(e)['p95'],spike_p95_um=stats(s)['p95'] or 0,
                 spike_max_um=stats(s)['max'] or 0))
    chosen=[]
    def distant(c):
        return all(abs(c['bscan']-p['bscan'])>=24 or abs(c['lo']-p['lo'])>=128 for p in chosen)
    for idx in rng.permutation(len(candidates)):
        c=candidates[idx]
        if distant(c):chosen.append(dict(c,role='random',driver='random'))
        if len(chosen)==2:break
    for driver,key in [('entropy','entropy_p95'),('spike','spike_max_um')]:
        c=next(c for c in sorted(candidates,key=lambda x:-(x[key] or 0)) if distant(c))
        chosen.append(dict(c,role='targeted',driver=driver))
    return chosen
