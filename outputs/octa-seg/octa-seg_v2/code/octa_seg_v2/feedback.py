"""Pure event resolution. This module never writes human feedback."""
import numpy as np

def resolve(events,shape=(8,512),model_id=None):
    k,w=shape;region=np.full(w,-1,np.int8);region_rev=np.full(w,-1,int)
    trace=np.full(shape,-1,np.int8);rel=np.full(shape,-1,np.int8);rel_rev=np.full(shape,-1,int)
    excluded=np.zeros(w,bool);positions=np.full(shape,np.nan,np.float32)
    manual=np.zeros(shape,bool);approved=np.zeros(shape,bool);provenance=np.full(shape,-1,int)
    for i,e in enumerate(events):
        lo,hi=e['lo'],e['hi']
        if not 0<=lo<hi<=w:raise ValueError('Invalid native interval')
        cols=np.arange(lo,hi);a=e['action'];ks=e.get('boundaries',list(range(k)))
        if a=='unreliable_region':
            region[cols]=0;region_rev[cols]=i;approved[:,cols]=False
        elif a=='clear_region':region[cols]=-1;region_rev[cols]=-1
        elif a=='exclude_image':excluded[cols]=True;approved[:,cols]=False;manual[:,cols]=False
        elif a=='clear_exclusion':excluded[cols]=False
        else:
            for b in ks:
                cc=np.array(e.get('columns',{}).get(str(b),cols),int)
                if len(cc)==0:continue
                if cc.min()<lo or cc.max()>=hi:raise ValueError('Event columns outside interval')
                provenance[b,cc]=i
                if a in ('not_traceable','clear_boundary','unreliable_boundary','correct','approve_position'):
                    approved[b,cc]=False
                if a=='not_traceable':trace[b,cc]=0;manual[b,cc]=False
                elif a=='clear_boundary':trace[b,cc]=-1;rel[b,cc]=-1;rel_rev[b,cc]=-1
                elif a=='unreliable_boundary':rel[b,cc]=0;rel_rev[b,cc]=i
                elif a in ('approve_shown','affirm_measurable'):
                    trace[b,cc]=1;rel[b,cc]=1;rel_rev[b,cc]=i
                elif a in ('correct','approve_position'):
                    yy=np.asarray(e['positions'][str(b)],np.float32)
                    if len(yy)!=len(cc) or not np.isfinite(yy).all():raise ValueError('Invalid explicit coordinates')
                    # Approvals are exact-position and model-specific. Manual strokes survive rounds.
                    if a=='approve_position' and model_id is not None and e['model_id']!=model_id:continue
                    positions[b,cc]=yy;trace[b,cc]=1
                    if a=='correct':manual[b,cc]=True;rel[b,cc]=0;rel_rev[b,cc]=i
                    else:approved[b,cc]=True
                else:raise ValueError(f'Unknown training action: {a}')
    use=(region[None]>=0)&(region_rev[None]>rel_rev)
    rel=np.where(use,region[None],rel).astype(np.int8)
    forbidden=(trace==0)|excluded[None]
    positions[forbidden]=np.nan;approved[forbidden]=False;manual[forbidden]=False
    # Manual drawn trace can remain uncertain for measurement and still teach position.
    valid=np.isfinite(positions)&~forbidden
    return dict(trace=trace,reliability=rel,excluded=excluded,positions=positions,
                manual=manual&valid,approved=approved&valid,region=region,provenance=provenance,
                reliability_provenance=np.where(use,region_rev[None],rel_rev))

def training_targets(events,shape=(8,512),model_id=None):
    d=resolve(events,shape,model_id)
    return dict(trace_target=d['trace'],reliability_target=d['reliability'],
       rows=d['positions'],manual_valid=d['manual'],approved_valid=d['approved'],
       excluded=d['excluded'],event_provenance=d['provenance'],reliability_event_provenance=d['reliability_provenance'])
