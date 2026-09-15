"""Versioned working measurement policy; never produces training truth."""
import numpy as np
from octa_seg_v1.decisions import decide,RELIABLE,UNCERTAIN,NOT_TRACEABLE,thickness

POLICY_REASONS={12:'ilm_working_default',13:'neural_proposal',14:'explicit measurable exception',15:'v2 regional unreliability',16:'human position candidate'}
POLICY_REVISION='v2-working-2'

def geometry_valid(rows,offset,depth):
    valid=np.isfinite(rows)&(rows>=offset)&(rows<offset+depth)
    # Compare every finite available boundary, including across missing neighbors.
    for k in range(rows.shape[-2]):
        for j in range(k):
            crossing=np.isfinite(rows[...,j,:])&np.isfinite(rows[...,k,:])&(rows[...,j,:]>=rows[...,k,:])
            valid[...,j,:]&=~crossing;valid[...,k,:]&=~crossing
    return valid

def apply(rows,prob,cal,vessel,offset,depth,guard=None,feedback=None,context=None):
    guard={} if guard is None else guard
    rep,state,reason=decide(rows,prob,cal,vessel,depth=1024,**guard)
    original_reason=reason.copy();z=rows.copy()
    trace=np.array(guard.get('trace',np.full(rows.shape,-1)),copy=True)
    rel=np.array(guard.get('reliability',np.full(rows.shape,-1)),copy=True)
    excluded=np.broadcast_to(guard.get('excluded',False),rows.shape).copy()
    human_position=np.zeros(rows.shape,bool)
    if feedback is not None:
        f=feedback
        trace=np.where(f['trace']>=0,f['trace'],trace);rel=np.where(f['reliability']>=0,f['reliability'],rel)
        excluded|=f['excluded'][None];human_position=np.isfinite(f['positions']);z[human_position]=f['positions'][human_position]
        # Explicit visible manual strokes can supersede automatic trace denials.
        state[human_position&(trace==1)]=UNCERTAIN
        yes=(f['reliability']==1)&(trace==1)
        state[yes]=RELIABLE;reason[yes]=14
    # V1's guard application let a reliability denial replace a trace denial.
    # Reliability alone is never permission to generate a continuation.
    auto_denied=decide(rows,prob,cal,vessel,depth=1024)[1]==NOT_TRACEABLE
    retain_denial=auto_denied&(trace!=1)
    state[retain_denial]=NOT_TRACEABLE;reason[retain_denial]=2
    # ILM default bypasses missing positive calibration, not actual automatic trace denial.
    ilm=(trace[0]!=0)&(rel[0]!=0)&(state[0]!=NOT_TRACEABLE)
    state[0,ilm]=RELIABLE;reason[0,ilm & (reason[0]!=14)]=12
    bad=rel==0
    state[bad & (state!=NOT_TRACEABLE)]=UNCERTAIN;reason[bad & (state!=NOT_TRACEABLE)]=6
    if feedback is not None:
        regional=(feedback['region'][None]==0)&(feedback['reliability']==0)
        reason[regional & (state!=NOT_TRACEABLE)]=15
    state[trace==0]=NOT_TRACEABLE;reason[trace==0]=5
    valid=geometry_valid(z,offset,depth)
    invalid=~valid&(state!=NOT_TRACEABLE);state[invalid]=UNCERTAIN;reason[invalid]=10
    state[excluded]=np.where(state[excluded]==NOT_TRACEABLE,NOT_TRACEABLE,UNCERTAIN)
    reason[excluded]=7
    if guard.get('rejected',False):state[state!=NOT_TRACEABLE]=UNCERTAIN;reason[:]=8
    rep=np.where(state==RELIABLE,z,np.nan).astype(np.float32)
    candidate=np.full_like(z,np.nan);source=np.zeros(z.shape,np.uint8)
    allowed=(state==UNCERTAIN)&valid&~excluded&(reason!=8)
    if context is not None:
        ok=allowed&geometry_valid(np.where(np.isfinite(context),context,z),offset,depth)&np.isfinite(context)
        candidate[ok]=context[ok];source[ok]=1
    fallback=allowed&~np.isfinite(candidate);candidate[fallback]=z[fallback];source[fallback]=2
    take=allowed&human_position;candidate[take]=z[take];source[take]=3
    return dict(reported_positions=rep,uncertain_estimates=candidate,state=state,reason=reason,
                original_reason=original_reason,candidate_source=source,working_positions=z)
