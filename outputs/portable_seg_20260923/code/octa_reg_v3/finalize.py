"""Post-search safety pass: supported poses depend only on supported observations."""
from pathlib import Path
import numpy as np
from octa_reg_v2.run import read,write,sha,apply
from octa_reg_v2.cohort_graph import components,fit_component,center
from .inputs import OUT

def finalize(root=OUT):
    for group in read(root/'run_plan.json')['groups']:
        folder=root/group;data=read(folder/'registration.json');graph=data['graph']
        if data['inherited_review']:
            write(folder/'review_registration.json',data);continue
        reference=graph['reference'];edges=graph['edges']
        # Demotions are monotonic. Repeat if a refit exposes a new ONH contradiction.
        while True:
            supported={int(i) for i,t in graph['tiers'].items() if t=='supported'}
            good=[e for e in edges if e['a'] in supported and e['b'] in supported]
            component=next((set(c) for c in components(supported,good) if reference in c),set())
            for i in supported-component:
                graph['tiers'][str(i)]='uncertain';graph['reasons'][str(i)].append('Support depends on a flagged field awaiting review')
            if component:
                poses,_,_,dropped=fit_component(component,good,reference,np.array(graph['poses'][str(reference)]))
                for i,m in poses.items():graph['poses'][str(i)]=m.tolist()
                for i in dropped:
                    graph['tiers'][str(i)]='uncertain';graph['reasons'][str(i)].append('Not connected after final supported-only refit')
            audits=[]
            if graph.get('origin_kind','unresolved')!='unresolved':
                for i,info in enumerate(data.get('scans',[])):
                    if str(i) not in graph['poses']:continue
                    c,kind=center(info)
                    if c is None:continue
                    error=float(np.linalg.norm(apply(c,np.array(graph['poses'][str(i)]))))
                    limit=70 if kind=='reviewed_onh' else 250;consistent=error<=limit
                    audits.append(dict(scan=i,center_kind=kind,distance_to_map_origin_px=error,limit_px=limit,consistent=consistent))
                    if not consistent and graph['tiers'][str(i)]=='supported':
                        graph['tiers'][str(i)]='uncertain';graph['reasons'][str(i)].append('Final fitted ONH center contradicts the reference')
            remaining={int(i) for i,t in graph['tiers'].items() if t=='supported'}
            if remaining==supported:break
        data['anatomy_audit']=dict(centers=audits)
        data['finalization']=dict(algorithm=str(Path(__file__)),sha256=sha(__file__),raw_registration_sha256=sha(folder/'registration.json'),
                                  policy='Recompute supported-only reachability and fit after large-change flags; preserve carried human decisions')
        write(folder/'review_registration.json',data)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);args=ap.parse_args();finalize(args.output)
