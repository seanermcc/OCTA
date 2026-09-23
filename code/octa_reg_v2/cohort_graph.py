"""Eye-isolated pose graphs and explicitly uncertain anatomical placement."""
import itertools
import numpy as np
from scipy.optimize import least_squares
from .run import matrix,params,apply

CORNERS=np.array([[0,0],[511,0],[511,511],[0,511],[255.5,255.5]])

def center(info):
    spacing=np.array(info['spacing'])[::-1]
    v=info.get('visible_onh',{})
    if v.get('resolved'):
        return np.array(v['center_um'])/spacing,('reviewed_onh' if info.get('onh_assessable') else 'estimated_onh')
    c=info.get('convergence',{})
    if c.get('resolved') and c.get('center_um'):
        return np.array(c['center_um'])/spacing,'estimated_onh'
    # Robust line intersections, not the old all-branch LS fit that follows stripes.
    branches=[b for b in info.get('branches',[]) if b.get('accepted') and b.get('length_um',0)>=140]
    if len(branches)<3:return None,'unresolved'
    p=np.array([b['point'] for b in branches])/spacing
    v=np.array([b['direction'] for b in branches]);n=np.c_[-v[:,1],v[:,0]]
    rhs=(n*p).sum(1);hypotheses=[]
    for a,b in itertools.combinations(range(len(p)),2):
        if abs(np.linalg.det(n[[a,b]]))<.25:continue
        x=np.linalg.solve(n[[a,b]],rhs[[a,b]])
        if np.linalg.norm(x-[256,256])>1500:continue
        err=abs(n@x-rhs);take=err<18
        if take.sum()<3:continue
        if np.linalg.cond(n[take].T@n[take])>30:continue
        x=np.linalg.lstsq(n[take],rhs[take],rcond=None)[0]
        hypotheses.append((int(take.sum()),float(np.median(err[take])),x))
    if hypotheses:
        hypotheses.sort(key=lambda h:(-h[0],h[1]));best=hypotheses[0]
        rivals=[h for h in hypotheses[1:] if h[0]>=best[0] and np.linalg.norm(h[2]-best[2])>120]
        if not rivals:return best[2],'estimated_onh'
    return None,'unresolved'

def components(nodes,edges):
    sets={i:{i} for i in nodes}
    for e in edges:
        a,b=e['a'],e['b']
        if a not in sets or b not in sets:continue
        merged=sets[a]|sets[b]
        for i in merged:sets[i]=merged
    return sorted({tuple(sorted(s)) for s in sets.values()},key=lambda x:(-len(x),x))

def choose_root(nodes,scans):
    def key(i):
        c,kind=center(scans[i]['info']);v=scans[i]['info'].get('visible_onh',{})
        return (0 if kind=='reviewed_onh' and v.get('arc_deg',0)>=270 else 1 if kind=='reviewed_onh' else 2 if kind=='estimated_onh' else 3,i)
    return min(nodes,key=key)

def fit_component(nodes,edges,root,origin):
    ee=[dict(e) for e in edges if e['a'] in nodes and e['b'] in nodes]
    poses={root:origin};tree=[]
    while True:
        cross=[e for e in ee if (e['a'] in poses)!=(e['b'] in poses)]
        if not cross:break
        e=max(cross,key=lambda x:x['score']);a,b=e['a'],e['b'];m=np.array(e['matrix'])
        if a in poses:poses[b]=poses[a]@np.linalg.inv(m)
        else:poses[a]=poses[b]@m
        tree.append((a,b))
    for _ in range(5):
        changed=False
        for i in sorted(set(poses)-{root}):
            inc=[e for e in ee if i in (e['a'],e['b'])]
            proposals=[poses[e['b']]@np.array(e['matrix']) if e['a']==i else poses[e['a']]@np.linalg.inv(np.array(e['matrix'])) for e in inc]
            def votes(p):
                ds=[np.sqrt(np.mean((apply(CORNERS,p)-apply(CORNERS,q))**2)) for q in proposals]
                return sum(d<30 for d in ds),sum(e['score'] for e,d in zip(inc,ds) if d<30)
            if proposals:
                best=max(proposals,key=votes)
                if votes(best)[0]>=max(3,votes(poses[i])[0]+2):poses[i]=best;changed=True
        if not changed:break
    good=[];bad=[]
    for e in ee:
        delta=apply(CORNERS,poses[e['a']])-apply(apply(CORNERS,np.array(e['matrix'])),poses[e['b']])
        e['initial_loop_rms_px']=float(np.sqrt(np.mean(delta**2)))
        (good if e['initial_loop_rms_px']<=30 else bad).append(e)
    # Pruning can split the graph. Never fit unconstrained poses as supported.
    reachable=next(c for c in components(nodes,good) if root in c)
    dropped=set(nodes)-set(reachable)
    poses={i:p for i,p in poses.items() if i in reachable}
    good=[e for e in good if e['a'] in poses and e['b'] in poses]
    ids=sorted(set(poses)-{root})
    def unpack(x):return {root:origin,**{i:matrix(x[3*k:3*k+3]) for k,i in enumerate(ids)}}
    def residual(x):
        ps=unpack(x)
        return np.concatenate([(np.sqrt(e['score'])*(apply(CORNERS,ps[e['a']])-apply(apply(CORNERS,np.array(e['matrix'])),ps[e['b']]))).ravel() for e in good])
    if ids and good:
        x=np.concatenate([params(poses[i]) for i in ids]);fit=least_squares(residual,x,loss='soft_l1',f_scale=4,max_nfev=150)
        poses=unpack(fit.x)
    for e in good:
        delta=apply(CORNERS,poses[e['a']])-apply(apply(CORNERS,np.array(e['matrix'])),poses[e['b']])
        e['final_loop_rms_px']=float(np.sqrt(np.mean(delta**2)))
    return poses,good,bad,dropped

def assemble(scans,accepted,all_pairs):
    nodes=[i for i,s in enumerate(scans) if not s['excluded'] and not s.get('blocked')]
    if not nodes:return dict(poses={},tiers={},reasons={},edges=[],rejected=[],origin_kind='unresolved',reference=None,components=[])
    root=choose_root(nodes,scans);c,kind=center(scans[root]['info'])
    origin=matrix([0,*(-c if c is not None else np.zeros(2))]);comps=components(nodes,accepted)
    main=next(c for c in comps if root in c)
    poses,edges,bad,dropped=fit_component(main,accepted,root,origin)
    tiers={i:'supported' for i in poses};reasons={i:[] for i in nodes}
    # Flag underconstrained leaves and geometry-only recovery, even when placed.
    for i in poses:
        inc=[e for e in edges if i in (e['a'],e['b'])]
        if i!=root and len(inc)<2:
            best=max(inc,key=lambda e:e['score']) if inc else {}
            if best.get('inliers',0)<12 or best.get('support',0)<.7:
                tiers[i]='uncertain';reasons[i].append('Single overlap link with limited independent placement evidence')
        if inc and all(e.get('evidence_tier')=='geometry_consensus_low_contrast' for e in inc):
            tiers[i]='uncertain';reasons[i].append('Low contrast: multiple vessel overlaps and ONH direction; intensity gate waived')
        if inc and max(e['final_loop_rms_px'] for e in inc)>12:
            tiers[i]='uncertain';reasons[i].append('Residual disagreement among overlapping fields')
    unresolved=set(nodes)-set(poses);component_records=[]
    # Attach entire disconnected components as proposals. They never adjust the
    # supported backbone or contribute to its coverage statistic.
    remaining=[set(c) for c in components(unresolved,accepted)]
    while remaining:
        options=[]
        for comp in remaining:
            for e in all_pairs:
                if 'matrix' not in e or e.get('span_px',0)<10 or e.get('overlap',0)<.12 or e.get('support',0)<.20 or e.get('dice',0)<.20:continue
                if (e['a'] in comp and e['b'] in poses) or (e['b'] in comp and e['a'] in poses):
                    options.append((e.get('score',0),comp,e))
        if options:
            _,comp,e=max(options,key=lambda x:x[0]);a,b=e['a'],e['b'];r=a if a in comp else b
            m=np.array(e['matrix']);o=poses[b]@m if r==a else poses[a]@np.linalg.inv(m)
            ps,_,_,miss=fit_component(comp,accepted,r,o)
            for i in ps:tiers[i]='uncertain';reasons[i].append('Tentative overlap bridge; at least one registration acceptance gate failed')
            component_records.append(dict(members=sorted(ps),method='tentative_overlap',bridge=e))
        else:
            comp=remaining[0];r=choose_root(comp,scans);cc,ck=center(scans[r]['info'])
            if cc is not None and kind!='unresolved':
                o=matrix([0,*-cc]);ps,_,_,miss=fit_component(comp,accepted,r,o)
                for i in ps:tiers[i]='uncertain';reasons[i].append('ONH/convergence positioning only; relative rotation assumed from native display')
                component_records.append(dict(members=sorted(ps),method='onh_direction_only'))
            else:
                ps={};miss=set()
                for i in comp:tiers[i]='unlocalized';reasons[i].append('No defensible connection or ONH estimate after search; native field retained')
        poses.update(ps);remaining.remove(comp)
        for i in miss:
            if not any(i in c for c in remaining):remaining.append({i})
    for i,s in enumerate(scans):
        if s['excluded']:tiers[i]='excluded';reasons[i]=[s['info'].get('exclusion_reason') or 'Explicit existing exclusion']
        elif s.get('blocked'):tiers[i]='unlocalized';reasons[i]=[s['blocked']]
    return dict(poses={str(i):m.tolist() for i,m in poses.items()},tiers={str(i):t for i,t in tiers.items()},
                reasons={str(i):r for i,r in reasons.items()},edges=edges,rejected=bad,origin_kind=kind,
                reference=root,components=component_records)
