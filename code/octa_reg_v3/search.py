"""Multiscale proposals; CNV can rank vessel-supported fits, never certify them."""
import warnings
import numpy as np
from scipy import ndimage as ndi
from scipy.optimize import least_squares
from skimage.filters import sato
from skimage.morphology import skeletonize,remove_small_objects
from skimage.feature import SIFT,match_descriptors
from skimage.exposure import equalize_adapthist
from skimage.measure import ransac
from skimage.transform import EuclideanTransform
from octa_reg_v2.run import matrix,params,apply,sample,inside,score
from octa_reg_v2.cohort_graph import center,CORNERS

GRID=np.array(np.meshgrid(np.arange(12,501,7),np.arange(12,501,7))).reshape(2,-1).T.astype(float)

def prepare(s,cnv,meta):
    im=s['image'];valid=s['valid']
    # Local normalization removes slow illumination while preserving fine detail.
    smooth=ndi.gaussian_filter(im,6)
    hp=(im-smooth)/np.maximum(ndi.gaussian_filter((im-smooth)**2,6)**.5,.025)
    hp=np.clip(hp,-3,3).astype('float32')
    ridge=sato(im,sigmas=[1,2,3],black_ridges=True).astype('float32')
    thick=ndi.distance_transform_edt(~s['skel'])<7
    area=valid&~thick&~ndi.binary_dilation(cnv,iterations=3)
    threshold=np.percentile(ridge[area],88) if area.any() else np.inf
    thin=remove_small_objects((ridge>max(threshold,.004))&area,min_size=22)
    sk=skeletonize(thin);sk[:12]=0;sk[-12:]=0;sk[:,:12]=0;sk[:,-12:]=0
    pts=np.argwhere(sk)[:,::-1].astype(float);pts=pts[::max(1,len(pts)//1000)]
    dt=ndi.distance_transform_edt(~sk).astype('float32');dt[~valid]=30
    s.update(detail=hp,thin_sk=sk,thin_pts=pts,thin_dt=dt,cnv=cnv,cnv_meta=meta)
    s['features']=[]
    for image in (equalize_adapthist(im,clip_limit=.02),(hp+3)/6):
        detector=SIFT(upsampling=1,c_dog=.006)
        try:
            detector.detect_and_extract(image)
            pts=detector.keypoints[:,::-1].astype(float)
            keep=inside(pts,12)&(sample(valid.astype(float),pts,0)>.5)
            s['features'].append((pts[keep],detector.descriptors[keep]))
        except RuntimeError:s['features'].append((np.empty((0,2)),np.empty((0,128),np.uint8)))
    labels,n=ndi.label(cnv);centers=[]
    for i in range(1,n+1):
        y,x=np.nonzero(labels==i)
        if len(x)>=30:centers.append([float(x.mean()),float(y.mean())])
    s['lesions']=np.array(centers[:15]).reshape(-1,2)

def distance(m,n):return float(np.sqrt(np.mean((apply(CORNERS,m)-apply(CORNERS,n))**2)))

def fine_metrics(a,b,m):
    q=apply(GRID,m)
    good=inside(q,12)&(sample(a['valid'].astype(float),GRID,0)>.5)&(sample(b['valid'].astype(float),q,0)>.5)
    x=sample(a['detail'],GRID[good]);y=sample(b['detail'],q[good])
    corr=float(np.corrcoef(x,y)[0,1]) if len(x)>50 and min(x.std(),y.std())>1e-6 else 0.
    supports=[];counts=[];matched=[]
    for source,target,mat in ((a,b,m),(b,a,np.linalg.inv(m))):
        pp=apply(source['thin_pts'],mat);ok=inside(pp,12)&(sample(target['valid'].astype(float),pp,0)>.5)
        dd=sample(target['thin_dt'],pp[ok],cval=30);counts.append(len(dd))
        supports.append(float((dd<3).mean()) if len(dd) else 0.)
        matched.extend(pp[ok][dd<3])
    available=min(counts,default=0)>=70
    support=min(supports) if available else None
    return dict(detail_corr=corr,small_support=support,small_points=min(counts,default=0))

def lesion_metrics(a,b,m):
    if not len(a['lesions']) or not len(b['lesions']):return dict(cnv_support=None,cnv_weight=0.)
    p=apply(a['lesions'],m);q=b['lesions']
    p=p[inside(p,0)];q=q[inside(apply(q,np.linalg.inv(m)),0)]
    if not len(p) or not len(q):return dict(cnv_support=None,cnv_weight=0.)
    ds=np.linalg.norm(p[:,None,:]-q[None,:,:],axis=2)
    same=a['info']['session_date']==b['info']['session_date']
    # Soft location agreement, not equal CNV shapes or a negative growth penalty.
    support=float((np.exp(-(ds.min(0)/(25 if same else 45))**2).mean()+np.exp(-(ds.min(1)/(25 if same else 45))**2).mean())/2)
    weight=min(a['cnv_meta']['weight'],b['cnv_meta']['weight'])*(.06 if same else .025)
    return dict(cnv_support=support,cnv_weight=weight)

def evaluate(a,b,m):
    r=score(a,b,m);r.update(fine_metrics(a,b,m));r.update(lesion_metrics(a,b,m))
    r['large_vessel_score']=r['score']
    small=r['small_support']
    # Feature similarity has greater leverage than predicted lesion coincidence.
    r['score']=float(.68*r['score']+.25*max(0,r['detail_corr'])+.07*(small or 0)+r['cnv_weight']*(r['cnv_support'] or 0))
    ca,ka=center(a['info']);cb,kb=center(b['info'])
    r['onh_error_px']=float(np.linalg.norm(apply(ca,m)-cb)) if ca is not None and cb is not None else None
    limit=70 if ka==kb=='reviewed_onh' else 250
    r['anatomy_ok']=r['onh_error_px'] is None or r['onh_error_px']<=limit
    # A straight large trunk without fine texture/spread does not pass.
    r['vessel_gate']=bool(r['overlap']>=.18 and r['support']>=.56 and r['dice']>=.4 and r['span_px']>=25
        and r['corr']>=.14 and r['detail_corr']>=.12 and r['anatomy_ok'])
    r['small_gate']=bool(small is not None and small>=.28 and r['detail_corr']>=.22
        and r['support']>=.42 and r['dice']>=.30 and r['span_px']>=28 and r['overlap']>=.22 and r['anatomy_ok'])
    return r

def refine_joint(a,b,m):
    """Local rigid trial using separately weighted trunk and small-vessel distances."""
    p0=params(m)
    def residual(p):
        mat=matrix(p);out=[]
        for source,target,transform in ((a,b,mat),(b,a,np.linalg.inv(mat))):
            for key,dt,weight in (('points','dt',1.),('thin_pts','thin_dt',.55)):
                pts=source[key][::2]
                if not len(pts):continue
                q=apply(pts,transform);d=sample(target[dt],q,cval=10)
                d[~inside(q)]=10
                out.append(np.minimum(d,12)*weight/np.sqrt(len(d)))
        return np.concatenate(out)
    fit=least_squares(residual,p0,bounds=(p0-[.08,16,16],p0+[.08,16,16]),
                       loss='soft_l1',f_scale=.08,diff_step=1e-3,max_nfev=26)
    return matrix(fit.x)

def feature_trials(a,b):
    for channel in range(2):
        pa,da=a['features'][channel];pb,db=b['features'][channel]
        if min(len(pa),len(pb))<7:continue
        for ratio,seed in ((.78,165),(.90,731)):
            matches=match_descriptors(da,db,cross_check=True,max_ratio=ratio)
            if len(matches)<6:continue
            p,q=pa[matches[:,0]],pb[matches[:,1]]
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                model,inliers=ransac((p,q),EuclideanTransform,min_samples=3,residual_threshold=5,
                    max_trials=1200,rng=np.random.default_rng(seed))
            if model is not None and inliers is not None and inliers.sum()>=5:
                yield model.params,dict(method='detail SIFT' if channel else 'all-field SIFT',ratio=ratio,seed=seed,inliers=int(inliers.sum()),matches=len(matches))

def search_pair(a,b,old,baseline):
    candidates=[]
    def add(m,meta):
        if not np.isfinite(m).all():return
        if any(distance(m,r[0])<1.5 for r in candidates):return
        candidates.append((m,meta))
    for r in old:
        if 'matrix' in r:add(np.array(r['matrix']),dict(method='v2 proposal',original_method=r.get('method'),inliers=r.get('inliers',0)))
        for alt in r.get('alternatives',[]):
            if 'matrix' in alt:add(np.array(alt['matrix']),dict(method='v2 alternative',inliers=0))
    if baseline is not None:add(baseline,dict(method='v2 graph relative pose',inliers=0))
    for m,meta in feature_trials(a,b):add(m,meta)
    # CNV centers propose starts only; vessel and texture gates still decide acceptance.
    if len(a['lesions']) and len(b['lesions']) and min(a['cnv_meta']['weight'],b['cnv_meta']['weight'])>=.35:
        angles=list(np.arange(-np.pi,np.pi,np.pi/6))
        angles+=list({round(params(m)[0],2) for m,_ in candidates})
        starts=[]
        for pa in a['lesions'][:5]:
            for pb in b['lesions'][:5]:
                for angle in angles:
                    m=matrix([angle,0,0]);m[:2,2]=pb-m[:2,:2]@pa
                    q=apply(a['points'][::5],m);valid=inside(q)
                    if valid.sum()<30:continue
                    val=float((sample(b['dt'],q[valid],cval=50)<5).mean())
                    starts.append((val,m))
        for val,m in sorted(starts,key=lambda r:-r[0])[:12]:
            if val>=.35:add(m,dict(method='CNV-location start',inliers=0))
    scored=[]
    for m,meta in candidates:
        scored.append(dict(evaluate(a,b,m),matrix=m.tolist(),**meta))
    scored.sort(key=lambda r:-r['score'])
    distinct=[]
    for r in scored:
        if all(distance(np.array(r['matrix']),np.array(q['matrix']))>10 for q in distinct):distinct.append(r)
        if len(distinct)>=3:break
    for r in distinct:
        m=refine_joint(a,b,np.array(r['matrix']))
        scored.append(dict(evaluate(a,b,m),matrix=m.tolist(),method=r['method']+' + multiscale refinement',inliers=r.get('inliers',0)))
    if not scored:return dict(accepted=False,method='exhausted multiscale trials',trial_count=0,alternatives=[])
    scored.sort(key=lambda r:-r['score'])
    plausible=[r for r in scored if r['vessel_gate'] or r['small_gate']]
    best=(plausible or scored)[0]
    rivals=[r for r in plausible if distance(np.array(r['matrix']),np.array(best['matrix']))>22]
    margin=best['score']-max((r['score'] for r in rivals),default=0.)
    return dict(best,accepted=bool(plausible and margin>=.025),alternative_margin=margin,
                trial_count=len(scored),alternatives=[r for r in scored if r is not best][:8],
                ambiguity=bool(plausible and margin<.025))
