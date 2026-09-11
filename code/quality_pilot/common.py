from pathlib import Path
import csv
import json
import numpy as np
from cnv_review_v1.data import atomic_json
from stage_a.common import fingerprint, verify

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / 'outputs/octa-seg/octa-seg_v1'
OUT = ROOT / 'outputs/octa-seg/quality_pilot_20260910'
SCANS = ['TS165_OS_2025-04-29_WT_s02_121711', 'TS247_OD_2024-11-06_D21_s03_104157',
         'TS283_OD_2025-01-29_D7_s02_123712', 'TS325_OD_2026-05-26_6mo_s01_112940',
         'TS328_OD_2026-04-09_beforelaser_s01_130813', 'TS336_OD_2026-05-22_D21_s05_114507']
NOTES = ['Decent; some solid segments appear to deserve dashed uncertainty.',
         'Great—almost perfect, particularly with good signal.',
         'Really solid; a few stray/misplaced labels near the ONH.',
         'OK, but needs more uncertain guesses through difficult stretches.', 'Not yet reviewed', 'Not yet reviewed']

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def npz(path):
    with np.load(path, allow_pickle=False) as d:
        return {k:d[k] for k in d.files}

def save(path, **data):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix('.tmp.npz'); np.savez_compressed(tmp, **data); tmp.replace(path)

def csvwrite(path, rows):
    rows=list(rows); path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        if rows:
            w=csv.DictWriter(f, sorted(set().union(*(r.keys() for r in rows))))
            w.writeheader(); w.writerows(rows)

def qc_rows():
    with (ROOT/'outputs/scan_quality_metrics.csv').open(encoding='utf-8-sig') as f:
        return {r['scan_id']:r for r in csv.DictReader(f) if r['scan_id'] in SCANS}

def initialize():
    path=OUT/'manifest.json'
    if path.exists():
        m=read(path)
        for fp in m['fixed_files']: verify(fp)
        return m
    files=[FROZEN/'models/ALL_LABELLED'/n for n in ('position.pt','states.pt')]
    files += [FROZEN/'calibration/deployment_vessels.json']
    files += [ROOT/'code'/p for p in ('octa_seg_v1/predict.py','octa_seg_v1/model.py',
              'octa_seg_v1/decisions.py','stage_a/geometry.py','stage_a/model.py')]
    m=dict(model='octa-seg_v1', scans=SCANS, fixed_files=[fingerprint(p) for p in files],
           automatic_before_human_overrides=True, axial_um=1.12,lateral_um=1460/512,
           warning_um=[10,20,40],median_window=9,strip_width=64,random_seed=20260910,
           qualitative_reviews=[dict(scan_id=s,note=n,source_task='01a08b8b-3eaa-75a1-9aed-4d84d0c8f8e5',
                kind='user full-volume observation; not regional ground truth') for s,n in zip(SCANS,NOTES)])
    atomic_json(path,m);return m
