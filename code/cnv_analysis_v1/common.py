from pathlib import Path
import csv
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[2]
LAYERS = ['Full retina', 'RNFL', 'GCL', 'IPL', 'INL', 'OPL',
          'Photoreceptor composite', 'RPE band']
POLICY = 'pilot-use-available-exclude-explicit-unreliable-v2'
ORIENTATION = 'Provisional image N/S/E/W = D*/V*/N*/T*; anatomical orientation unconfirmed.'

def provisional_sector(dx,dy):
    return ('N*' if dx>0 else 'T*') if abs(dx)>abs(dy) else ('V*' if dy>0 else 'D*')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def fingerprint(path):
    p = Path(path).resolve()
    return dict(path=str(p), sha256=sha(p), bytes=p.stat().st_size)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

def write(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix(p.suffix + '.tmp')
    t.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    t.replace(p)

def csvwrite(path, rows, fields=None):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r)) or ['status']
    t = p.with_suffix('.tmp.csv')
    with t.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fields); w.writeheader(); w.writerows(rows)
    t.replace(p)

def csvread(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def npz(path):
    import numpy as np
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}

def save(path, **arrays):
    import numpy as np
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix('.tmp.npz'); np.savez_compressed(t, **arrays); t.replace(p)

def default_config(release='v1', source='manual'):
    batch = ROOT/'outputs/octa-seg_v1_batch'
    return dict(version=1, release=release, annotation_source=source,
        output=str(ROOT/'outputs/octa-seg/octa-seg_v1'/f'cnv_analysis_{release}'),
        batch=str(batch), gate=str(batch/'FINAL_VERIFIED.json'),
        auto_gate=str(ROOT/'outputs/octa-auto_cnv_v1/FINAL_VERIFIED.json'),
        enface_labels=str(ROOT/'outputs/cnv_labels'),
        region_sources=[str(batch/'reviewer/regions'),str(ROOT/'outputs/cnv_review_v1/regions')],
        auto_proposals=str(ROOT/'outputs/octa-auto_cnv_v1/proposals'),
        thickness_reference=str(ROOT/'outputs/octa-seg/octa-seg_v1/cnv_analysis_v1'),
        field_um_yx=[1460., 1460.], absolute_edges_um=[0,100,200,300,400,500,600],
        normalized_edges=[0,.5,1,1.5,2,2.5,3], bootstrap_samples=2000,
        random_seed=417, complete_band_fraction=.98,
        registration=dict(min_inliers=16, min_inlier_fraction=.45, max_residual_um=12.,
                          min_overlap=.30, min_correlation=.45, max_rotation_deg=35.),
        experimental=True, policy=POLICY)

def validate_config(c):
    if c['release'] not in ('v1','v2'):
        raise ValueError('Release must be v1 or v2')
    allowed = ('manual',) if c['release']=='v1' else ('automatic_core','automatic_footprint')
    if c['annotation_source'] not in allowed:
        raise ValueError(f"{c['release']} requires annotation source in {allowed}")
    p = Path(c['output']).resolve()
    expected = f"cnv_analysis_{c['release']}"
    if p.name != expected or not p.is_relative_to((ROOT/'outputs').resolve()):
        raise ValueError('Output must be a dedicated cnv_analysis_v1/v2 folder under outputs')
    if c['policy'] != POLICY or c['normalized_edges'] != [0,.5,1,1.5,2,2.5,3]:
        raise ValueError('Unsupported thickness policy or normalized bands')
    if len(c['field_um_yx'])!=2 or min(c['field_um_yx'])<=0:
        raise ValueError('Physical calibration must be positive')
    e = c['absolute_edges_um']
    if len(e)!=7 or e[0]!=0 or any(b<=a for a,b in zip(e,e[1:])):
        raise ValueError('Six strictly increasing absolute distance bands required')
    return p

def gate(c):
    marker = Path(c['gate'])
    waiver=c.get('batch_audit_override')
    if waiver:
        if not isinstance(waiver,dict) or waiver.get('authorized_by')!='user' or not waiver.get('instruction'):
            raise RuntimeError('Batch audit override requires recorded user authorization')
        scans=read(Path(c['batch'])/'manifest.json')['scans']
        required=('complete.json','neural_complete.json','geometry.npz','measurements.npz','images.npy','human_overrides_provenance.json','qc_complete.json')
        missing=[f'{r["scan_id"]}/{name}' for r in scans for name in required
                 if not (Path(c['batch'])/'volumes'/r['scan_id']/name).exists()]
        if missing: raise RuntimeError('Scan-level outputs are incomplete: '+', '.join(missing[:10]))
        proof=dict(batch_audit_performed=False,authorization=waiver,scans=len(scans),
                   required_scan_artifacts_present=True,batch_manifest=fingerprint(Path(c['batch'])/'manifest.json'))
    elif not marker.exists() or read(marker).get('passed') is not True:
        raise RuntimeError(f'Final measurement is gated: upstream audit absent or not passed: {marker}')
    else:
        data = read(marker)
        scans = read(Path(c['batch'])/'manifest.json')['scans']
        if data.get('scans') != len(scans):
            raise RuntimeError('Final audit scan count does not match batch inventory')
        for fp in data.get('tables', []):
            if sha(fp['path']) != fp['sha256']:
                raise RuntimeError('Upstream audit table changed: '+fp['path'])
        proof=fingerprint(marker)
    if c['release']=='v2':
        a = Path(c['auto_gate'])
        if not a.exists() or read(a).get('passed') is not True:
            raise RuntimeError(f'Automatic release gate is not passed: {a}')
        if not (Path(c['thickness_reference'])/'frozen_inputs.json').exists():
            raise RuntimeError('v2 requires the frozen v1 thickness inputs')
    return proof

def day_info(r):
    import math
    import re
    label = r.get('day_label','')
    kind = r.get('timepoint_kind','').lower()
    pre = kind in ('prelaser','pre_laser','before_laser','before laser','before') or 'before laser' in label.lower()
    actual = r.get('days_post_laser','')
    try:
        day = float(actual)
        if not math.isfinite(day): raise ValueError()
        basis = 'actual'
    except (ValueError, TypeError):
        match = re.fullmatch(r'D(-?\d+(?:\.\d+)?)', label, re.I)
        day = float(match[1]) if match else None
        basis = 'nominal' if match else 'categorical'
    pre = pre or (day is not None and day<0)
    # Unresolved month visits remain categorical but are known post-D0 visits.
    post_category=bool(re.fullmatch(r'\d+(?:\.\d+)?\s*(?:mo|months?)',label,re.I))
    return dict(day=day, day_basis=basis, day_label=label,
                prelaser=pre, post_d0=bool(not pre and ((day is not None and day>0) or post_category)),
                visit_id=r['session_date'])
