"""Exercise already-frozen matching/export on one completed held-out fit; no tuning."""
from common import *
from candidates import extract,correspondence,metrics
protocol=read(HERE/'data/protocol.json');m=read(HERE/'data/supervision.json');fold=protocol['folds'][0];rows=[]
for r in m['records']:
 if r['animal'] not in fold['evaluation_animals']:continue
 sid=r['scan_id'];p=HERE/'fits/outer0_m1/predictions'/(sid+'.npz');doc=read(p.with_suffix('.json'));verify(doc['prediction']);assert r['animal'] not in doc['training_animals'];z=npz(p);labels,cs=extract(z['score'],npz(HERE/'cache'/sid/'context.npz')['channels']);truth=npz(r['target_file']['path']);correspondence(labels,cs,truth);metric=metrics(labels,cs,truth)
 assert sum(c['area_pixels'] for c in cs)==int(z['raw_mask'].sum())
 rows.append(dict(scan_id=sid,candidates=len(cs),finite_probability=bool(np.isfinite(z['score']).all()),geometry_preserved=True,matching_computed=True,metrics=metric))
write(HERE/'verification/FROZEN_EVALUATION_SMOKE.json',dict(passed=True,scoring_implementation_sha256=sha(HERE/'data/scoring_implementation.json'),policy_changed=False,records=rows))
print('Frozen candidate extraction/matching works on',len(rows),'held-out acquisitions')
