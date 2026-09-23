"""Measurement contract. No estimator can fill a not-traceable location."""
import numpy as np
from scipy.ndimage import shift as ndshift
from skimage.registration import phase_cross_correlation
from eight_surface.config import SURFACE_NAMES, LAYER_DEFS

RELIABLE, NOT_TRACEABLE, UNCERTAIN = 1,2,3
REASONS={1:"learned evidence passed (experimental)",2:"learned not-traceable decision",
    3:"learned evidence below reporting thresholds",4:"vessel-derived unreliable default",
    5:"explicit human not-traceable",6:"explicit human unreliable",7:"image excluded",
    8:"rejected B-scan review",9:"insufficient boundary calibration evidence",
    10:"nonfinite, outside image or crossing position",11:"explicit positive human state; image check passed"}

def decide(rows, probabilities, calibration, vessel, *, trace=None, reliability=None,
           excluded=None, rejected=False, depth=1024, use_vessels=True):
    """Inputs [8,W], probabilities [8,2,W]; output measurements never estimates."""
    rows=np.asarray(rows);p=np.asarray(probabilities)
    state=np.full(rows.shape,UNCERTAIN,np.uint8);reason=np.full(rows.shape,3,np.uint8)
    for k,c in enumerate(calibration):
        no=p[k,0]<=c["not_traceable_cutoff"]
        state[k,no]=NOT_TRACEABLE;reason[k,no]=2
        good=(p[k,0]>=c["trace_cutoff"]) & (p[k,1]>=c["reliability_cutoff"]) & ~no
        state[k,good]=RELIABLE;reason[k,good]=1
        if not c["supported"]:
            state[k]=UNCERTAIN;reason[k]=9
    tr=np.full(rows.shape,-1) if trace is None else np.asarray(trace)
    rel=np.full(rows.shape,-1) if reliability is None else np.asarray(reliability)
    # Explicit traceable does not automatically mean reliable, or vice versa.
    state[((tr==1)|(rel==1))&(state==NOT_TRACEABLE)]=UNCERTAIN
    reason[((tr==1)|(rel==1))&(reason==2)]=3
    if use_vessels:
        default=np.broadcast_to(vessel,rows.shape).copy();default[0]=False
        default &= rel!=1
        take=default & (state!=NOT_TRACEABLE)
        state[take]=UNCERTAIN;reason[take]=4
    unreliable=rel==0
    state[unreliable]=UNCERTAIN
    reason[unreliable]=6
    denied=tr==0
    state[denied]=NOT_TRACEABLE;reason[denied]=5
    # Manual reliability is not positional truth. A positive state permits a
    # report only after the calibrated image check, never by itself.
    reason[(tr==1)&(rel==1)&(state==RELIABLE)]=11
    invalid=~np.isfinite(rows)|(rows<0)|(rows>depth-1)
    crossing=rows[:-1]>=rows[1:]
    invalid[:-1]|=crossing;invalid[1:]|=crossing
    take=invalid & (state!=NOT_TRACEABLE)
    state[take]=UNCERTAIN;reason[take]=10
    if excluded is not None:
        take=np.broadcast_to(excluded,rows.shape)&(state!=NOT_TRACEABLE)
        state[take]=UNCERTAIN;reason[take]=7
    if rejected:
        take=state!=NOT_TRACEABLE;state[take]=UNCERTAIN;reason[take]=8
    reported=np.where(state==RELIABLE,rows,np.nan).astype(np.float32)
    return reported,state,reason

def thickness(reported, shadow):
    reported=np.asarray(reported)
    result=[]
    for _,top,bottom in LAYER_DEFS+[("INNER_RETINA","ILM","IPL_INL")]:
        a=SURFACE_NAMES.index(top);b=SURFACE_NAMES.index(bottom)
        delta=(reported[...,b,:]-reported[...,a,:])*1.12
        delta=np.where((delta>=0)&~shadow,delta,np.nan)
        result.append(delta)
    return np.stack(result,axis=-2).astype(np.float32)

def runs(mask):
    edges=np.flatnonzero(np.diff(np.r_[False,np.asarray(mask,bool),False]))
    return list(zip(edges[::2],edges[1::2]))

def alignment(images):
    """Register adjacent canonical images; never assume same x after motion.

    One native-pixel translation, correlation check, and bounded shift. Local
    boundary patches undergo an additional check before a candidate is allowed.
    """
    shifts=np.zeros((len(images)-1,2),np.float32)
    scores=np.zeros(len(images)-1,np.float32)
    for b in range(len(images)-1):
        a=images[b].astype(float);c=images[b+1].astype(float)
        a=(a-np.mean(a))/(np.std(a)+1e-6);c=(c-np.mean(c))/(np.std(c)+1e-6)
        delta,_,_=phase_cross_correlation(a,c,upsample_factor=1,normalization=None)
        shifts[b]=delta
        if abs(delta[0])>12 or abs(delta[1])>6:continue
        shifted=ndshift(c,delta,order=1,mode="constant",cval=np.nan)
        ok=np.isfinite(shifted)
        scores[b]=np.corrcoef(a[ok],shifted[ok])[0,1]
    return shifts,scores

def estimate_context(rows, reported, states, reasons, images, shifts, scores,
                     offset=0, max_gap=128, min_correlation=.65):
    """Both lateral anchors + registered immediate slices on BOTH sides.

    All three slices need measured lateral anchors. Inside the gap, neighboring
    positional proposals may be uncertain: they supply contextual shape, never
    measurement truth. No generated estimate is reused, no propagation occurs,
    and no not-traceable/excluded corridor is bridged.
    """
    estimates=np.full_like(rows,np.nan,dtype=np.float32)
    context_reason=np.full(rows.shape,1,np.uint8) # insufficient anchors/context
    records=[]
    for b in range(1,len(rows)-1):
        if min(scores[b-1],scores[b])<min_correlation:continue
        for k in range(8):
            for lo,hi in runs(states[b,k]==UNCERTAIN):
                if lo==0 or hi==rows.shape[-1] or hi-lo>max_gap:continue
                if not np.isfinite(reported[b,k,[lo-1,hi]]).all():continue
                if np.isin(reasons[b,k,lo:hi],[7,8,9,10]).any():continue
                candidates=[];corrs=[]
                for neighbor,delta in ((b-1,-shifts[b-1]),(b+1,shifts[b])):
                    zshift,xshift=delta
                    xx=np.arange(lo-1,hi+1);native=np.rint(xx-xshift).astype(int)
                    if native.min()<0 or native.max()>=rows.shape[-1]:break
                    if not np.all(states[neighbor,k,native[[0,-1]]]==RELIABLE):break
                    if np.isin(reasons[neighbor,k,native],[7,8,9,10]).any():break
                    # Conservative no-not-traceable corridor, including native x.
                    low=min(lo-1,int(native.min()));high=max(hi+1,int(native.max())+1)
                    if (states[neighbor,k,low:high]==NOT_TRACEABLE).any() or (states[b,k,low:high]==NOT_TRACEABLE).any():break
                    curve=rows[neighbor,k,native]+zshift
                    if not np.isfinite(curve).all():break
                    anchors=reported[b,k,[lo-1,hi]]
                    curve+=np.linspace(anchors[0]-curve[0],anchors[1]-curve[-1],len(curve))
                    z=int(np.nanmedian(rows[b,k,lo:hi])-offset)
                    zlo=max(0,z-24);zhi=min(images.shape[1],z+25)
                    nzlo=int(zlo-zshift);nzhi=int(zhi-zshift)
                    if nzlo<0 or nzhi>images.shape[1] or zhi-zlo<16:break
                    patch=images[b,zlo:zhi,lo-1:hi+1]
                    other=images[neighbor,nzlo:nzhi][:,native]
                    if patch.shape!=other.shape or np.std(other)<1e-5:break
                    corr=float(np.corrcoef(patch.ravel(),other.ravel())[0,1])
                    if not np.isfinite(corr) or corr<.45:break
                    candidates.append(curve[1:-1]);corrs.append(corr)
                if len(candidates)!=2:continue
                if np.max(np.abs(candidates[0]-candidates[1]))>12:continue
                candidate=np.mean(candidates,axis=0)
                if np.max(np.abs(candidate-rows[b,k,lo:hi]))>16:continue
                # Boundaries are never moved to enforce ordering; fail closed.
                if k and np.any(candidate<=rows[b,k-1,lo:hi]):continue
                if k<7 and np.any(candidate>=rows[b,k+1,lo:hi]):continue
                estimates[b,k,lo:hi]=candidate;context_reason[b,k,lo:hi]=0
                records.append(dict(bscan=b,boundary=SURFACE_NAMES[k],lo=int(lo),hi=int(hi),length=int(hi-lo),
                    min_local_correlation=min(corrs),max_neighbor_disagreement_px=float(np.max(np.abs(candidates[0]-candidates[1])))))
    if np.isfinite(estimates[states==NOT_TRACEABLE]).any():raise AssertionError("Forbidden estimate")
    return estimates,context_reason,records
