"""TS247 OD pilot. All transforms are rigid, native pixel x-right/y-down.

No source masks or human labels are modified. Vessel agreement is an internal
fit score, not independent accuracy. Acquisition dates remain in provenance.
"""
from pathlib import Path
import json, time, warnings, itertools, argparse
import numpy as np
from scipy import ndimage as ndi
from scipy.optimize import least_squares
from skimage.feature import SIFT, match_descriptors
from skimage.exposure import equalize_adapthist
from skimage.measure import ransac
from skimage.transform import EuclideanTransform
from skimage.morphology import skeletonize
from octa_reg_v1.io import ROOT, read, write, sha

BASE=ROOT/'outputs/octa-reg_v1'
OUT=ROOT/'outputs/octa-reg_v2/TS247_OD'
SEED=247

def matrix(p):
    c,s=np.cos(p[0]),np.sin(p[0])
    return np.array([[c,-s,p[1]],[s,c,p[2]],[0,0,1.]])

def params(m): return np.array([np.arctan2(m[1,0],m[0,0]),m[0,2],m[1,2]])

def apply(p,m): return np.asarray(p)@m[:2,:2].T+m[:2,2]

def sample(im,p,order=1,cval=0):
    return ndi.map_coordinates(im,np.asarray(p)[:,::-1].T,order=order,mode='constant',cval=cval)

def inside(p,margin=8): return (p[:,0]>=margin)&(p[:,0]<512-margin)&(p[:,1]>=margin)&(p[:,1]<512-margin)

def load():
    scans=[]; hashes={}
    release=OUT/'RELEASE.json'
    if release.exists():
        pinned=read(release)
        for path,expected in pinned['code_hashes'].items():
            if sha(path)!=expected:raise ValueError('Released pilot code changed: use a new version/output directory, '+path)
    for path in sorted((BASE/'prepared').glob('TS247_OD_*.json')):
        info=read(path); sid=info['scan_id']
        hashes[str(path)]=sha(path)
        if info.get('excluded_from_analysis') or info.get('status')!='prepared' or 'prepared_sha256' not in info:
            scans.append(dict(info=info,excluded=True)); continue
        for source,expected in info['input_hashes'].items():
            actual=sha(source)
            if actual!=expected: raise ValueError('Changed baseline input: '+source)
            hashes[source]=actual
        zpath=path.with_suffix('.npz'); actual=sha(zpath)
        if actual!=info['prepared_sha256']: raise ValueError('Changed prepared scan: '+sid)
        hashes[str(zpath)]=actual;hashes[str(path)]=sha(path)
        z=np.load(zpath); im=z['enface'].copy(); valid=np.isfinite(im)&~z['registration_blocked']
        if im.shape!=(512,512) or not np.allclose(z['spacing'],[1460/512]*2):
            raise ValueError('This bounded pilot requires its calibrated 512 x 512 native grid')
        lo,hi=np.percentile(im[np.isfinite(im)],[2,98]); im=np.clip((np.nan_to_num(im,nan=lo)-lo)/(hi-lo),0,1)
        vessel=z['vessel']&valid
        sk=skeletonize(vessel);sk[:8]=False;sk[-8:]=False;sk[:,:8]=False;sk[:,-8:]=False
        pts=np.argwhere(sk)[:,::-1].astype(float)
        # Modest uniform subsampling preserves all trunks rather than selecting junctions.
        pts=pts[::max(1,len(pts)//1500)]
        dt=ndi.distance_transform_edt(~sk).astype('float32')
        dt[~valid]=30
        scans.append(dict(info=info,excluded=False,image=im.astype('float32'),valid=valid,vessel=vessel,
                          skel=sk,points=pts,dt=dt,zpath=str(zpath)))
    if release.exists():
        if [s['info']['scan_id'] for s in scans]!=pinned['scan_ids']:
            raise ValueError('Released pilot inventory changed; use a new output version')
        for path,expected in pinned['source_hashes'].items():
            if sha(path)!=expected:raise ValueError('Released pilot source changed; stale caches forbidden: '+path)
    OUT.mkdir(parents=True,exist_ok=True);write(OUT/'source_hashes.json',hashes)
    return scans

def features(scans):
    folder=OUT/'features';folder.mkdir(exist_ok=True)
    for n,s in enumerate(scans):
        if s['excluded']:continue
        path=folder/(s['info']['scan_id']+'.npz')
        if path.exists():
            z=np.load(path);s['kp']=z['points'];s['desc']=z['descriptors'];continue
        image=equalize_adapthist(s['image'],clip_limit=.015)
        detector=SIFT(upsampling=1,c_dog=.008)
        detector.detect_and_extract(image)
        pts=detector.keypoints[:,::-1].astype(float)
        # Keep structural descriptors near trunks; avoid disc interiors and excluded pixels.
        near=ndi.distance_transform_edt(~s['vessel'])<18
        take=(sample(near.astype(float),pts,0)>.5)&(sample(s['valid'].astype(float),pts,0)>.5)&inside(pts,12)
        s['kp']=pts[take];s['desc']=detector.descriptors[take]
        np.savez_compressed(path,points=s['kp'],descriptors=s['desc'])
        print('features',n,len(s['kp']),flush=True)

def candidate(a,b):
    matches=match_descriptors(a['desc'],b['desc'],cross_check=True,max_ratio=.85)
    if len(matches)<5:return None,dict(matches=len(matches),inliers=0)
    p,q=a['kp'][matches[:,0]],b['kp'][matches[:,1]]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        model,inliers=ransac((p,q),EuclideanTransform,min_samples=3,residual_threshold=7,
                             max_trials=2000,rng=np.random.default_rng(SEED))
    if not model or inliers is None:return None,dict(matches=len(matches),inliers=0)
    return model.params,dict(matches=len(matches),inliers=int(inliers.sum()),
                            inlier_points_a=p[inliers].tolist(),inlier_points_b=q[inliers].tolist())

def refine(a,b,m):
    # Symmetric centerline chamfer, robust against missing labels and image artifacts.
    pa,pb=a['points'],b['points']; p0=params(m)
    def residual(p):
        mat=matrix(p); qa=apply(pa,mat);qb=apply(pb,np.linalg.inv(mat))
        da=sample(b['dt'],qa,cval=10);db=sample(a['dt'],qb,cval=10)
        da[~inside(qa)]=10;db[~inside(qb)]=10
        return np.r_[da,db]
    fit=least_squares(residual,p0,loss='soft_l1',f_scale=2,
        bounds=(p0-np.array([.10,22,22]),p0+np.array([.10,22,22])),diff_step=1e-3,max_nfev=45)
    return matrix(fit.x)

def score(a,b,m):
    pa,pb=a['points'],b['points'];qa=apply(pa,m);qb=apply(pb,np.linalg.inv(m))
    ia=inside(qa)&(sample(b['valid'].astype(float),qa,0)>.5)
    ib=inside(qb)&(sample(a['valid'].astype(float),qb,0)>.5)
    da=sample(b['dt'],qa[ia],cval=50);db=sample(a['dt'],qb[ib],cval=50)
    if min(len(da),len(db))<40:return dict(score=0.,support=0.,median_px=999.,overlap=0.,dice=0.,corr=0.,span_px=0.)
    support=min(float((da<5).mean()),float((db<5).mean()))
    # Intensity and vessel area are evaluated only in observed common tissue.
    y,x=np.mgrid[8:504:3,8:504:3];grid=np.c_[x.ravel(),y.ravel()].astype(float);target=apply(grid,m)
    valid=inside(target)&(sample(a['valid'].astype(float),grid,0)>.5)&(sample(b['valid'].astype(float),target,0)>.5)
    overlap=float(valid.mean());grid=grid[valid];target=target[valid]
    va=sample(a['vessel'].astype(float),grid,0)>.5;vb=sample(b['vessel'].astype(float),target,0)>.5
    dice=float(2*(va&vb).sum()/max(1,va.sum()+vb.sum()))
    aa=sample(a['image'],grid);bb=sample(b['image'],target)
    corr=float(np.corrcoef(aa,bb)[0,1]) if len(aa)>10 and min(aa.std(),bb.std())>1e-6 else 0.
    matched=qa[ia][da<5];span=float(np.linalg.svd(matched-matched.mean(0),compute_uv=False)[1]/np.sqrt(len(matched))) if len(matched)>3 else 0.
    return dict(score=float(.50*support+.30*dice+.20*max(0,corr)),support=support,
                median_px=float(np.median(np.r_[da,db])),overlap=overlap,dice=dice,corr=corr,span_px=span)

def pairs(scans):
    results=[];folder=OUT/'pairs';folder.mkdir(exist_ok=True)
    for i,j in itertools.combinations(range(len(scans)),2):
        a,b=scans[i],scans[j]
        if a['excluded'] or b['excluded']:continue
        path=folder/f'{i:02d}_{j:02d}.json'
        if path.exists():results.append(read(path));continue
        m,evidence=candidate(a,b);r=dict(a=i,b=j,method='vessel-anchored SIFT + symmetric centerline refinement',**evidence)
        if m is not None and evidence['inliers']>=5:
            original=score(a,b,m);refined=refine(a,b,m);s=score(a,b,refined)
            if s['score']<original['score']:s=original
            else:m=refined
            r.update(s,matrix=m.tolist())
            r['accepted']=bool(evidence['inliers']>=7 and s['overlap']>=.18 and s['support']>=.57 and s['dice']>=.42 and s['span_px']>=23 and s['corr']>=.18)
        else:r['accepted']=False
        write(path,r);results.append(r)
        if r['accepted']:print('pair',i,j,'inliers',r['inliers'],'score',round(r['score'],3),flush=True)
    write(OUT/'pairs.json',results)
    return results

def main():
    t=time.perf_counter();scans=load();features(scans);result=pairs(scans)
    print('DONE pairs',len(result),'accepted',sum(r['accepted'] for r in result),'seconds',time.perf_counter()-t,flush=True)

if __name__=='__main__':main()
