"""Descriptor-free rotation/translation search on whole vessel curves."""
import numpy as np
from scipy import ndimage as ndi
from scipy.signal import fftconvolve
from .run import matrix, params, refine, score

def correlate(a,b):return fftconvolve(a,b[::-1,::-1],mode='full')

def coarse(a,b):
    scale=4
    aa=ndi.gaussian_filter(a['skel'].astype(float),2)[::scale,::scale]
    bb=ndi.gaussian_filter(b['skel'].astype(float),2)[::scale,::scale]
    va=a['valid'][::scale,::scale].astype(float);vb=b['valid'][::scale,::scale].astype(float)
    n=len(aa);center=np.array([63.5,63.5]);candidates=[]
    for degrees in range(-90,91,6):
        angle=np.deg2rad(degrees);r=matrix([angle,0,0])[:2,:2]
        # scipy uses y,x; R inverse becomes R again after swapping axes.
        rot=ndi.affine_transform(aa,r,center-r@center,order=1)
        mask=ndi.affine_transform(va,r,center-r@center,order=0)
        overlap=correlate(vb,mask)
        ab=correlate(bb,rot)
        norm=np.sqrt(np.maximum(correlate(bb*bb,mask)*correlate(vb,rot*rot),1e-12))
        quality=ab/norm
        quality[(overlap<.20*n*n)|(np.abs(np.indices(quality.shape)[0]-(n-1))>110)|(np.abs(np.indices(quality.shape)[1]-(n-1))>110)]=0
        for k in range(2):
            y,x=np.unravel_index(np.argmax(quality),quality.shape);value=quality[y,x]
            if value<=0:break
            translation=(np.array([x,y])-(n-1))*scale+scale*(center-r@center)
            candidates.append((float(value),matrix([angle,*translation])))
            quality[max(0,y-8):y+9,max(0,x-8):x+9]=0
    selected=[]
    for value,m in sorted(candidates,key=lambda x:-x[0]):
        p=params(m)
        if any(abs(p[0]-params(other)[0])<.16 and np.linalg.norm(p[1:]-params(other)[1:])<50 for _,other in selected):continue
        selected.append((value,m))
        if len(selected)==10:break
    return selected

def match(a,b):
    candidates=[]
    for q,m in coarse(a,b):
        refined=refine(a,b,m);s=score(a,b,refined)
        candidates.append(dict(**s,matrix=refined.tolist(),coarse_correlation=q))
    candidates.sort(key=lambda r:-r['score'])
    if not candidates:return dict(accepted=False,reason='no overlap candidate')
    best=candidates[0];p=params(np.array(best['matrix']))
    alternatives=[r for r in candidates[1:] if abs(params(np.array(r['matrix']))[0]-p[0])>.09 or np.linalg.norm(params(np.array(r['matrix']))[1:]-p[1:])>25]
    margin=best['score']-max((r['score'] for r in alternatives),default=0)
    return dict(best,method='whole-vessel curve rotation/translation search',alternative_margin=margin,
                accepted=bool(best['support']>=.64 and best['dice']>=.46 and best['corr']>=.20 and best['span_px']>=28 and margin>=.055),
                alternatives=candidates[1:4])
