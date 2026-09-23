"""Independent ONH-consistency pass over cohort registration proposals.

The raw search results stay intact. Reviewed disc centers add anatomical
constraints; estimated centers only veto gross contradictions, never certify a
placement. Original photometric and centerline metrics remain separately stored.
"""
from pathlib import Path
import argparse,itertools,json,inspect,hashlib
import numpy as np
from .cohort import DEFAULT_OUT,load_group,unique_accepted
from .run import read,write,sha,matrix,apply,params,score,refine
from .cohort_graph import center,assemble,CORNERS

def reviewed(info):return bool(info.get('onh_assessable') and info.get('visible_onh',{}).get('resolved'))

def anchored_match(a,b):
    ca,_=center(a['info']);cb,_=center(b['info']);starts=[]
    for angle in np.deg2rad(np.arange(-180,180,3)):
        m=matrix([angle,0,0]);m[:2,2]=cb-m[:2,:2]@ca;s=score(a,b,m);starts.append((s['score'],m))
    candidates=[];angles=[]
    for _,m in sorted(starts,key=lambda r:-r[0]):
        theta=params(m)[0]
        if any(abs(np.arctan2(np.sin(theta-t),np.cos(theta-t)))<.15 for t in angles):continue
        angles.append(theta);refined=refine(a,b,m)
        error=float(np.linalg.norm(apply(ca,refined)-cb))
        if error<=35:m=refined
        s=score(a,b,m);candidates.append(dict(**s,matrix=m.tolist(),onh_error_px=float(np.linalg.norm(apply(ca,m)-cb))))
        if len(candidates)>=8:break
    candidates.sort(key=lambda r:-r['score']);best=candidates[0]
    return dict(best,accepted=bool(best['support']>=.50 and best['dice']>=.40 and best['span_px']>=23 and best['overlap']>=.18),
                method='reviewed ONH centers + vessel-pattern rotation search',anatomical_anchor=True,alternatives=candidates[1:4])

def process(group,root):
    folder=root/group;raw=read(folder/'registration.json');scans,context=load_group(group,folder)
    anchor_context=dict(algorithm_sha256=hashlib.sha256(inspect.getsource(anchored_match).encode()).hexdigest(),sources=context['sources'])
    context_path=folder/'onh_cache_context.json'
    if context_path.exists() and read(context_path)!=anchor_context:
        raise ValueError('ONH search inputs or algorithm changed; use a fresh output version')
    write(context_path,anchor_context)
    allpairs=read(folder/'pair_evidence.json');accepted=unique_accepted(allpairs);rejections=[];filtered=[]
    for e in accepted:
        a,b=e['a'],e['b'];ca,ka=center(scans[a]['info']);cb,kb=center(scans[b]['info'])
        if ca is not None and cb is not None:
            error=float(np.linalg.norm(apply(ca,np.array(e['matrix']))-cb))
            limit=70 if ka==kb=='reviewed_onh' else 250
            if error>limit:
                rejections.append(dict(e,anatomy_reason='Pair implies incompatible ONH locations',onh_error_px=error,limit_px=limit));continue
        filtered.append(e)
    anchors=[i for i,s in enumerate(scans) if not s['excluded'] and not s.get('blocked') and reviewed(s['info'])]
    folder.joinpath('onh_pairs').mkdir(exist_ok=True);extra=[]
    for a,b in itertools.combinations(anchors,2):
        path=folder/'onh_pairs'/f'{a:03d}_{b:03d}.json'
        r=read(path) if path.exists() else dict(a=a,b=b,**anchored_match(scans[a],scans[b]))
        if not path.exists():write(path,r)
        extra.append(r)
        if r['accepted']:
            # Two reviewed disc observations add a separate priority/pose weight;
            # score is restored to its actual overlap metric in the saved graph.
            filtered=[e for e in filtered if (e['a'],e['b'])!=(a,b)]
            filtered.append(dict(r,overlap_score=r['score'],score=2+r['score'],pose_weight=2+r['score']))
    graph=assemble(scans,filtered,allpairs+extra)
    for e in graph['edges']+graph['rejected']:
        if 'overlap_score' in e:e['score']=e['overlap_score']
    # If an overlap-failed disc view still has a reviewed center, its best
    # ONH-constrained angle is a better proposal than a contradictory weak bridge.
    root_index=graph['reference']
    for r in extra:
        if root_index not in (r['a'],r['b']):continue
        i=r['b'] if r['a']==root_index else r['a'];c,_=center(scans[i]['info'])
        existing=graph['poses'].get(str(i));error=np.linalg.norm(apply(c,np.array(existing))) if existing is not None else float('inf')
        if error>70 and str(root_index) in graph['poses']:
            m=np.array(r['matrix']);base=np.array(graph['poses'][str(root_index)])
            pose=base@np.linalg.inv(m) if r['a']==root_index else base@m
            graph['poses'][str(i)]=pose.tolist();graph['tiers'][str(i)]='uncertain'
            graph['reasons'][str(i)].append('Best reviewed-ONH anchored placement; vessel alignment remains uncertain')
    audits=[]
    for i,s in enumerate(scans):
        if str(i) not in graph['poses']:continue
        c,k=center(s['info'])
        if c is None or graph['origin_kind']=='unresolved':continue
        error=float(np.linalg.norm(apply(c,np.array(graph['poses'][str(i)]))))
        limit=70 if k=='reviewed_onh' else 250
        if error>limit:
            graph['tiers'][str(i)]='uncertain'
            graph['reasons'][str(i)].append('ONH location contradicts the map origin; retain only as an uncertain proposal')
        audits.append(dict(scan=i,center_kind=k,distance_to_map_origin_px=error,limit_px=limit,consistent=error<=limit))
    # Fields connected through a flagged single link can inherit its uncertainty.
    # Only high-confidence backbone reachability is reported as supported.
    supported={int(i) for i,t in graph['tiers'].items() if t=='supported'};seen={root_index} if root_index in supported else set()
    while True:
        new=set(seen)
        for e in graph['edges']:
            a,b=e['a'],e['b']
            if a in supported and b in supported:
                if a in seen:new.add(b)
                if b in seen:new.add(a)
        if new==seen:break
        seen=new
    for i in supported-seen:
        graph['tiers'][str(i)]='uncertain';graph['reasons'][str(i)].append('Connection to reference depends on a flagged field')
    raw['graph']=graph;raw['anatomy_audit']=dict(reviewed_onh_indices=anchors,anchor_pairs=extra,rejected_edges=rejections,centers=audits)
    write(folder/'review_registration.json',raw)
    result=dict(group=group,anchors=len(anchors),onh_pairs=len(extra),rejected_onh_edges=len(rejections),
        counts={k:list(graph['tiers'].values()).count(k) for k in ['supported','uncertain','unlocalized','excluded']})
    write(folder/'anatomy_audit.json',result);print(json.dumps(result),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=DEFAULT_OUT);ap.add_argument('--groups',nargs='*');args=ap.parse_args()
    groups=args.groups or read(args.output/'run_plan.json')['groups']
    for g in groups:
        if (args.output/g/'registration.json').exists():process(g,args.output)
    write(args.output/'anatomy_code_hashes.json',{str(p):sha(p) for p in [Path(__file__)]})

if __name__=='__main__':main()
