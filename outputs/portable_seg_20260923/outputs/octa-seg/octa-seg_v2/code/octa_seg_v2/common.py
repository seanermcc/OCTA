from pathlib import Path
import json
import csv
import numpy as np
from stage_a.common import fingerprint, verify, digest

OUT = Path(__file__).resolve().parents[2]
ROOT = OUT.parents[2]
V1 = OUT.parent / 'octa-seg_v1'
PILOT = OUT.parent / 'quality_pilot_20260910'
ROUND = OUT / 'round_000'
SCANS = ['TS165_OS_2025-04-29_WT_s02_121711','TS247_OD_2024-11-06_D21_s03_104157',
 'TS283_OD_2025-01-29_D7_s02_123712','TS325_OD_2026-05-26_6mo_s01_112940',
 'TS328_OD_2026-04-09_beforelaser_s01_130813','TS336_OD_2026-05-22_D21_s05_114507',
 'TS241_OD_2024-09-25_D42_s03_111600','TS247_OD_2024-10-30_D14_s05_105423',
 'TS250_OS_2026-03-23_D27_s03_115357','TS336_OD_2026-05-22_D21_s03_113534']

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def writable(path):
    path=Path(path).resolve()
    if not path.is_relative_to(OUT): raise ValueError('All v2 writes must stay in octa-seg_v2')
    for parent in [path.parent,*path.parents]:
        if parent==OUT: break
        if (parent/'COMPLETE.json').exists(): raise RuntimeError(f'Frozen release: {parent}')
    path.parent.mkdir(parents=True,exist_ok=True)
    return path

def write(path,obj):
    content=json.dumps(obj,indent=2,allow_nan=False,default=lambda o:o.tolist() if isinstance(o,np.ndarray) else o.item() if isinstance(o,np.generic) else str(o))
    path=Path(path)
    if path.exists() and path.read_text(encoding='utf-8')==content:return
    path=writable(path);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(content,encoding='utf-8');tmp.replace(path)

def save(path,**data):
    path=writable(path);tmp=path.with_suffix('.tmp.npz');np.savez_compressed(tmp,**data);tmp.replace(path)

def npz(path):
    with np.load(path,allow_pickle=False) as d:return {k:d[k] for k in d.files}

def table(path,rows):
    rows=list(rows);path=writable(path)
    with path.open('w',newline='',encoding='utf-8') as f:
        if rows:
            w=csv.DictWriter(f,sorted(set().union(*(r.keys() for r in rows))));w.writeheader();w.writerows(rows)

def initialize():
    dest=OUT/'manifest.json'
    if dest.exists():
        m=read(dest)
        for fp in m['checkpoints']:verify(fp)
        return m
    from eight_surface.cnv_labels import load_label
    import random
    with (ROOT/'outputs/scan_quality_metrics.csv').open(encoding='utf-8-sig') as f:q={r['scan_id']:r for r in csv.DictReader(f)}
    pool=[]
    for p in sorted((ROOT/'outputs/cnv_labels').glob('*_cnv.npz')):
        d=load_label(p);sid=d['scan_id']
        if sid not in q or sid in SCANS[:6] or not d['reviewed_targets'][0] or not d['cnv_mask'].any():continue
        import re
        match=re.search(r'_D(\d+)_',sid)
        if match and int(match[1])>0 and Path(q[sid]['source']).exists():pool.append(sid)
    rng=random.Random(20260910);animals=sorted({s.split('_')[0] for s in pool})
    selected=[rng.choice(sorted(s for s in pool if s.startswith(a+'_'))) for a in rng.sample(animals,4)]
    if set(selected)!=set(SCANS[6:]):raise ValueError(f'Selection pool changed: {selected}; fixed requested scans are retained; inspect pool')
    old=read(V1/'data/manifest.json')
    eligible=sorted({r['animal'] for r in old['records'] if sum(r.get('positions',[]))})
    m=dict(version='octa-seg_v2',round='round_000',scans=SCANS,selection_pool=pool,selection_seed=20260910,
      selection_rationale='four uniformly sampled animals, then one scan per animal, before viewing outputs',
      selected_in_rng_order=selected,checkpoints=[fingerprint(V1/'models/ALL_LABELLED'/n) for n in ('position.pt','states.pt')],
      calibration=fingerprint(V1/'calibration/deployment_vessels.json'),
      ancestry_manifest=fingerprint(V1/'data/manifest.json'),position_eligible_animals=eligible,
      claim='workflow/policy update using existing weights; no newly learned improvement; development results on seen ancestry',
      quality_ratings='independent assessment only, never imported as boundary training targets',
      policy='ilm_working_default; registered context preferred; neural_proposal fallback; unchanged other reporting thresholds')
    write(dest,m);return m
