"""Repeated pair/graph trials in a fresh version; v2 human poses are immutable inputs."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,time,itertools,traceback,collections,json,copy
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from octa_reg_v2.cohort import load_group
from octa_reg_v2.cohort_graph import assemble,center,fit_component,components,CORNERS
from octa_reg_v2.run import read,write,sha,apply,matrix
from .inputs import OUT,V2,freeze
from .search import prepare,search_pair,distance,evaluate

VERSION='octa-reg_v3-1'

def graph_trials(scans,pairs):
    trials=[];accepted=[p for p in pairs if p['accepted']]
    for strategy in ('balanced','fine_detail','large_vessels'):
        edges=[]
        for p in accepted:
            e=dict(p)
            if strategy=='fine_detail':e['score']=.6*p['score']+.4*max(0,p['detail_corr'])
            if strategy=='large_vessels':e['score']=.6*p['score']+.4*p['large_vessel_score']
            e['balanced_score']=p['score'];edges.append(e)
        graph=assemble(scans,edges,pairs);poses={int(i):np.array(m) for i,m in graph['poses'].items()}
        agreement=0.;conflicts=0;onh_conflicts=0
        for p in accepted:
            if p['a'] not in poses or p['b'] not in poses:continue
            error=distance(poses[p['a']],poses[p['b']]@np.array(p['matrix']))
            agreement+=p['score']*np.exp(-(error/15)**2)
            conflicts+=error>30
        for i,m in poses.items():
            c,k=center(scans[i]['info'])
            if c is None or graph['origin_kind']=='unresolved':continue
            if np.linalg.norm(apply(c,m))>(70 if k=='reviewed_onh' else 250):onh_conflicts+=1
        objective=float(agreement-.15*conflicts-.6*onh_conflicts)
        trials.append(dict(strategy=strategy,objective=objective,agreement=agreement,conflicts=conflicts,onh_conflicts=onh_conflicts,graph=graph))
    best=max(trials,key=lambda r:r['objective']);graph=best['graph']
    for i,m in graph['poses'].items():
        c,k=center(scans[int(i)]['info'])
        if c is not None and graph['origin_kind']!='unresolved' and np.linalg.norm(apply(c,np.array(m)))>(70 if k=='reviewed_onh' else 250):
            graph['tiers'][i]='uncertain';graph['reasons'][i].append('ONH center conflicts with reference; proposal only')
    # A flagged bridge cannot certify a downstream field.
    supported={int(i) for i,t in graph['tiers'].items() if t=='supported'};root=graph['reference']
    ee=[e for e in graph['edges'] if e['a'] in supported and e['b'] in supported]
    backbone=next((set(c) for c in components(supported,ee) if root in c),set())
    for i in supported-backbone:
        graph['tiers'][str(i)]='uncertain';graph['reasons'][str(i)].append('Reference connection depends on a flagged field')
    # Refit only the supported component, so flagged fields cannot pull the final backbone.
    if backbone:
        origin=np.array(graph['poses'][str(root)])
        ps,good,bad,dropped=fit_component(backbone,ee,root,origin)
        for i,m in ps.items():graph['poses'][str(i)]=m.tolist()
        for i in dropped:
            graph['tiers'][str(i)]='uncertain';graph['reasons'][str(i)].append('Disconnected by supported-only refit')
    graph['selected_strategy']=best['strategy']
    return graph,[{k:v for k,v in t.items() if k!='graph'} for t in trials]

def group_run(group,root):
    root=Path(root);out=root/group;start=time.time()
    scans,context=load_group(group,out);manifest=read(root/'inputs/manifest.json')
    signature=dict(version=VERSION,inputs=sha(root/'inputs/manifest.json'),algorithms={str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in ('run.py','search.py','inputs.py')})
    if (out/'v3_cache_context.json').exists() and read(out/'v3_cache_context.json')!=signature:raise ValueError('V3 search code/input changed; preserve previous trials and use a new run folder')
    write(out/'v3_cache_context.json',signature)
    cnv_meta={r['scan_id']:r for r in manifest['cnvs']}
    for s in scans:
        if s['excluded'] or s.get('blocked'):continue
        sid=s['info']['scan_id']
        with np.load(root/'inputs'/(sid+'.npz')) as z:cnv=z['cnv'].copy();ignored=z['ignored'].copy()
        # Ambiguous CNV footprints are not positive/negative registration evidence.
        s['valid'] &= ~ignored
        prepare(s,cnv,cnv_meta[sid])
    baseline=read(V2/group/'review_registration.json');old=read(V2/group/'pair_evidence.json')
    old += [read(p) for p in (V2/group/'onh_pairs').glob('*.json')]
    by_pair=collections.defaultdict(list)
    for r in old:by_pair[r['a'],r['b']].append(r)
    nodes=[i for i,s in enumerate(scans) if not s['excluded'] and not s.get('blocked')]
    pairs=[];folder=out/'pairs';folder.mkdir(exist_ok=True)
    combinations=list(itertools.combinations(nodes,2))
    for n,(a,b) in enumerate(combinations):
        path=folder/f'{a:03d}_{b:03d}.json'
        if path.exists():r=read(path)
        else:
            poses=baseline['graph']['poses']
            relative=np.linalg.inv(np.array(poses[str(b)]))@np.array(poses[str(a)]) if str(a) in poses and str(b) in poses else None
            r=dict(a=a,b=b,**search_pair(scans[a],scans[b],by_pair[a,b],relative));write(path,r)
        pairs.append(r)
        if n%10==0:write(out/'progress.json',dict(stage='multiscale pair trials',completed=n+1,total=len(combinations),seconds=time.time()-start))
    graph,trials=graph_trials(scans,pairs)
    # Large changes need explicit review even if internal pair/graph scores increase.
    baseline_poses=baseline['graph']['poses'];ref=str(graph['reference'])
    gauge=np.array(baseline_poses[ref])@np.linalg.inv(np.array(graph['poses'][ref])) if ref in baseline_poses else np.eye(3)
    changes=[]
    for i,m in graph['poses'].items():
        if i not in baseline_poses:continue
        delta=distance(np.array(baseline_poses[i]),gauge@np.array(m));changes.append(dict(index=int(i),corner_rms_px=delta))
        if delta>50:
            graph['tiers'][i]='uncertain';graph['reasons'][i].append('Large change from v2 (>50 px corner RMS); requires manual review despite internal fit')
    automatic=copy.deepcopy(graph);review=manifest['placement_reviews'].get(group)
    diagnostic=[]
    if review:
        reference=graph['reference'];reference_human=review['records'][reference]['matrix_to_current_origin_pixels']
        v3_gauge=np.array(reference_human)@np.linalg.inv(np.array(graph['poses'][str(reference)]))
        old_reference=baseline['graph']['reference'];old_human=review['records'][old_reference]['matrix_to_current_origin_pixels']
        v2_gauge=np.array(old_human)@np.linalg.inv(np.array(baseline['graph']['poses'][str(old_reference)]))
        # Human placement/category decisions are preserved, including flagged confirmations.
        for i,s in enumerate(scans):
            rr=next(r for r in review['records'] if r['scan_id']==s['info']['scan_id'])
            hp=rr['matrix_to_current_origin_pixels'];ap=graph['poses'].get(str(i))
            if hp and ap:
                diagnostic.append(dict(scan_id=rr['scan_id'],review_tier=rr['review_tier'],confirmed=rr['placement_confirmed'],
                    v2_corner_rms_px=distance(np.array(hp),v2_gauge@np.array(baseline['graph']['poses'][str(i)])),
                    v3_corner_rms_px=distance(np.array(hp),v3_gauge@np.array(ap))))
            if hp:graph['poses'][str(i)]=hp
            else:graph['poses'].pop(str(i),None)
            graph['tiers'][str(i)]=rr['review_tier'];graph['reasons'][str(i)]=['Carried from saved v2 human review; '+('individual placement confirmed' if rr['placement_confirmed'] else 'draft placement')]
            if rr['notes']:graph['reasons'][str(i)].append(rr['notes'])
        if review['onh_override'] is not None:graph['origin_kind']='manual_onh'
        graph['edges']=[];graph['rejected']=[];graph['carried_review']=True
    data=dict(version=VERSION,group=group,scans=[dict(s['info'],cohort_blocked=s.get('blocked')) for s in scans],graph=graph,
        seconds=time.time()-start,trials=trials,cnv_sources=[cnv_meta[s['info']['scan_id']] for s in scans],
        inherited_review=review,development_comparison=diagnostic,changes_from_v2=changes)
    write(out/'registration.json',data);write(out/'review_registration.json',data)
    write(out/'automatic_trial_graph.json',automatic);write(out/'pair_evidence.json',pairs)
    result=dict(group=group,total=len(scans),counts=dict(collections.Counter(graph['tiers'].values())),
                pairs=len(pairs),trials=sum(p['trial_count'] for p in pairs),seconds=time.time()-start,carried_review=bool(review))
    write(out/'progress.json',dict(stage='complete',**result));print(json.dumps(result),flush=True)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--groups',nargs='*');ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    freeze(a.output);groups=a.groups or sorted(p.name for p in V2.glob('TS*') if (p/'montage.json').exists())
    write(a.output/'run_plan.json',dict(version=VERSION,groups=groups,workers=a.workers))
    results=[];failures=[]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        jobs={pool.submit(group_run,g,str(a.output)):g for g in groups}
        for f in as_completed(jobs):
            try:results.append(f.result())
            except Exception as e:
                error=dict(group=jobs[f],error=str(e),traceback=traceback.format_exc());failures.append(error);write(a.output/jobs[f]/'ERROR.json',error);print(error,flush=True)
            write(a.output/'batch_status.json',dict(completed=results,failed=failures,total_groups=len(groups)))
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
