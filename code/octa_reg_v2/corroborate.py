"""Recover low-contrast fields only with agreement across established neighbors.

This is a separate, disclosed geometry-only evidence tier: intensity correlation
is not required, but three spatially informative overlaps and ONH direction are.
"""
import numpy as np
from .run import load,OUT,read,write,apply
from .assemble import solve,edges,CORNERS

def main():
    scans=load();base_edges=[e for e in edges() if e.get('evidence_tier')!='geometry_consensus_low_contrast']
    poses,_,_=solve(scans,base_edges);records=[]
    for i,s in enumerate(scans):
        if s['excluded'] or i in poses:continue
        candidates=[]
        for path in sorted((OUT/'curve_pairs').glob('*.json')):
            r=read(path);a,b=r['a'],r['b']
            if i not in (a,b) or r.get('accepted'):continue
            j=b if a==i else a
            if j not in poses or r.get('support',0)<.64 or r.get('dice',0)<.55 or r.get('overlap',0)<.30 or r.get('span_px',0)<28:continue
            m=np.array(r['matrix']);pose=poses[j]@(m if a==i else np.linalg.inv(m))
            candidates.append(dict(pair=r,path=str(path),pose=pose,neighbor=j))
        clusters=[]
        for c in candidates:
            agreeing=[d for d in candidates if np.sqrt(np.mean((apply(CORNERS,c['pose'])-apply(CORNERS,d['pose']))**2))<=12]
            clusters.append(agreeing)
        if not clusters:continue
        cluster=max(clusters,key=len)
        conv=s['info'].get('convergence',{});direction_ok=False;distance=None
        if conv.get('center_um') and conv.get('residual_um',999)<50:
            c=np.array(conv['center_um'])/np.array(s['info']['spacing'])[::-1]
            distance=float(np.median([np.linalg.norm(apply(c,r['pose'])) for r in cluster]))
            direction_ok=distance<=55
        accepted=len(cluster)>=3 and direction_ok
        record=dict(scan=i,neighbors=[c['neighbor'] for c in cluster],agreement_limit_px=12,
                    convergence_distance_px=distance,convergence_limit_px=55,accepted=accepted,
                    evidence='multiple informative vessel overlaps + consistent ONH convergence; intensity correlation waived')
        records.append(record)
        if accepted:
            for c in cluster:
                r=dict(c['pair'],accepted=True,method='corroborated vessel geometry + ONH convergence',
                       evidence_tier='geometry_consensus_low_contrast',corroboration=record)
                write(OUT/'consensus_pairs'/__import__('pathlib').Path(c['path']).name,r)
    write(OUT/'corroboration.json',records);print(records,flush=True)

if __name__=='__main__':main()
