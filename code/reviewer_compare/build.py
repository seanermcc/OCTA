"""Read-only comparison of v3 reviewer journals on identical native B-scans.

No annotation serializers are imported. Output is a portable offline web viewer.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'code'))
sys.path.insert(0, str(PROJECT / 'outputs/octa-seg/octa-seg_v3/review/code'))
from octa_seg_v3.feedback import resolve, position_targets
from octa_seg_v3 import lesions as L
from eight_surface.config import SURFACE_NAMES

MODES = ('approved', 'drawn', 'geometry')
PX_UM = 1.12


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def safe(value):
    if isinstance(value, np.ndarray):
        return safe(value.tolist())
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def stats(delta):
    """Signed Shichu minus lead, in microns. No observations means missing, not zero."""
    d = np.asarray(delta, float)
    d = d[np.isfinite(d)]
    if not d.size:
        return dict(n=0, mae_um=None, median_um=None, p95_um=None, max_um=None,
                    bias_um=None, rmse_um=None, within_5um_pct=None)
    a = np.abs(d)
    return dict(n=int(d.size), mae_um=float(a.mean()), median_um=float(np.median(a)),
                p95_um=float(np.percentile(a, 95)), max_um=float(a.max()),
                bias_um=float(d.mean()), rmse_um=float(np.sqrt(np.mean(d*d))),
                within_5um_pct=float(100*np.mean(a <= 5)))


def paired(a, b, mode):
    za, zb = np.asarray(a['positions'], float), np.asarray(b['positions'], float)
    if za.shape != zb.shape:
        raise ValueError('Native position grid mismatch; resampling is forbidden')
    mask = np.asarray(a[mode], bool) & np.asarray(b[mode], bool)
    return np.where(mask, (zb-za)*PX_UM, np.nan)


def inventory(folder, reviewer):
    result = {}
    for path in sorted((folder / 'journals').glob('*.json')):
        j = read(path)
        if j['reviewer_id'] != reviewer:
            raise ValueError(f'Reviewer identity mismatch: {path}')
        key = f"{j['scan_id']}_b{int(j['bscan']):04d}"
        if path.stem != key or key in result:
            raise ValueError(f'Duplicate/misnamed journal: {path}')
        if not 0 <= j['cursor'] <= len(j['events']):
            raise ValueError(f'Invalid undo cursor: {path}')
        result[key] = (path, j, digest(path))
    if not result:
        raise ValueError(f'No journals in {folder}')
    orphan = sorted(p.name for p in (folder/'surface_labels').glob('*.npz') if p.stem not in result)
    if orphan:
        raise ValueError(f'Labels without authoritative journals: {orphan}')
    return result


def lesion_display(resolved, events):
    """Saved human annotations, not inferred lesion masks or retinal score targets."""
    lesion = resolved['lesions']
    has_events = any(e['action'] in L.ACTIONS for e in events)
    confirmed = resolved.get('lesion_confirmation') is not None
    return dict(region=lesion['cnv_region'].copy(),
                edge=lesion['cnv_edge'].copy(),
                edge_state=lesion['cnv_edge_state'].copy(),
                edge_unreliable=lesion['cnv_edge_unreliable'].copy(),
                confirmed=confirmed,
                status='CNV review confirmed' if confirmed else
                       'Saved CNV draft / unconfirmed' if has_events else
                       'No saved CNV annotations',
                definition=resolved.get('lesion_definition'))


def hyper_display(resolved, events):
    """Lossless native-image mask; counts are painted pixels, never inferred dot counts."""
    mask = resolved['lesions']['hyper_ref']
    yy, xx = np.nonzero(mask)
    confirmed = resolved.get('lesion_confirmation') is not None
    touched = any(e['action'] == 'hyper_ref' for e in events)
    return dict(runs=L.runs(mask.ravel()), shape=list(mask.shape),
                pixels=int(mask.sum()),
                bounds=[int(xx.min()), int(yy.min()), int(xx.max()+1), int(yy.max()+1)] if yy.size else None,
                status='Lesion review confirmed' if confirmed else
                       'Saved dot draft / unconfirmed' if touched else 'No saved dot annotations')


def load_review(item, provider, baseline, shadow, vessel, offset, shape):
    path, j, sha = item
    source = j['source']
    if j['coordinate_system'] != 'native A-line; full canonical depth':
        raise ValueError(f'Unsupported coordinate system: {path}')
    if j['boundary_names'] != SURFACE_NAMES:
        raise ValueError(f'Boundary anatomy mismatch: {path}')
    if source['provider_sha256'] != provider['sha']:
        raise ValueError(f'Frozen prediction hash mismatch: {path}')
    if list(source['image_shape']) != list(shape) or int(source['crop_offset']) != offset:
        raise ValueError(f'Native image geometry mismatch: {path}')
    if source['source_fingerprint']['sha256'] != provider['prep']['source']['sha256']:
        raise ValueError(f'Acquisition fingerprint mismatch: {path}')
    r = resolve(j['events'][:j['cursor']], baseline, offset, shape[1])
    c = r['confirmation']
    if c:
        for key in ('reviewer_id', 'scan_id', 'bscan', 'model_id', 'source'):
            if c.get(key) != j.get(key):
                raise ValueError(f'Confirmation identity mismatch: {path}: {key}')
        if c.get('boundary_names') != j['boundary_names']:
            raise ValueError(f'Confirmation boundary mismatch: {path}')
    t = position_targets(r, shadow, r['valid_geometry'], vessel)
    z = r['positions']
    # Diagnostic scope keeps denied/unreviewed finite saved curves, but never off-image values.
    geometry = np.isfinite(z) & (z >= offset) & (z <= offset + shape[1]-1)
    approved = t['approved_position'] if c else np.zeros(z.shape, bool)
    drawn = t['reliable_manual']
    out = dict(positions=z, approved=approved, drawn=drawn, geometry=geometry,
               status=r['review_status'], revision=j['revision'], seconds=j.get('active_seconds', 0),
               trace=r['trace'], reliability=r['reliability'], anatomy=r['anatomy'],
               excluded=r['excluded'], context_uncertain=t['context_uncertain'],
               notes=r['metadata'].get('notes', ''), source_path=str(path), sha256=sha,
               edited_points=int(r['drawn'].sum()), strokes=r['n_strokes'],
               cnv=lesion_display(r, j['events'][:j['cursor']]),
               hyper_ref=hyper_display(r, j['events'][:j['cursor']]))
    return out


def build(args):
    out = Path(args.output).resolve()
    roots = {'lead': Path(args.lead), 'shichu': Path(args.shichu)}
    # Never allow generated files inside any annotation tree.
    for root in roots.values():
        if out == root.resolve() or root.resolve() in out.parents:
            raise ValueError('Output must be outside reviewer annotations')
    inventories = {name: inventory(root, name) for name, root in roots.items()}
    out.mkdir(parents=True, exist_ok=True)
    (out/'images').mkdir(exist_ok=True)
    providers = {}
    for base in args.providers:
        for p in sorted(Path(base).glob('*/prepared.json')):
            sid = p.parent.name
            if sid in providers:
                raise ValueError(f'Ambiguous provider for {sid}')
            providers[sid] = p.parent
    cases, rows, hashes = [], [], []
    pooled = {mode: [] for mode in MODES}
    layer_pooled = {mode: [[] for _ in SURFACE_NAMES] for mode in MODES}
    case_maes = {mode: [] for mode in MODES}
    current_scan = None
    for key in sorted(set(inventories['lead']) | set(inventories['shichu'])):
        sample = next(inv[key][1] for inv in inventories.values() if key in inv)
        sid, row = sample['scan_id'], int(sample['bscan'])
        if sid != current_scan:
            p = providers[sid]
            prep = read(p/'prepared.json')
            if prep['scan_id'] != sid or not (prep.get('orientation_fresh') or 'canonical' in str(prep.get('orientation', ''))):
                raise ValueError(f'Missing verified canonical orientation for {sid}')
            images = np.load(p/'images.npy', mmap_mode='r', allow_pickle=False)
            with np.load(p/'measurements.npz', allow_pickle=False) as z:
                raw = z['raw_position_branch']; shadow = z['shadow']; vessel = z['vessel']; offset = int(z['label_offset'])
                if list(z['surface_names']) != SURFACE_NAMES:
                    raise ValueError('Provider boundary mismatch')
            with np.load(p/'geometry.npz', allow_pickle=False) as g:
                if int(g['label_offset']) != offset:
                    raise ValueError('Image crop offset disagreement')
            if (p/'context.npz').exists():
                with np.load(p/'context.npz', allow_pickle=False) as context:
                    vessel = vessel | context['vessel'].astype(bool)
            if raw.shape != (images.shape[0], len(SURFACE_NAMES), images.shape[2]):
                raise ValueError('Provider native grid mismatch')
            provider = dict(sha=digest(p/'measurements.npz'), prep=prep)
            hashes.append(dict(path=str(p/'measurements.npz'), sha256=provider['sha'], kind='provider'))
            current_scan = sid
        if not 0 <= row < len(images):
            raise ValueError('B-scan outside image grid')
        case = dict(id=key, scan_id=sid, bscan=row, offset=offset, depth=images.shape[1], width=images.shape[2],
                    image='images/'+key+'.png', reviewers={}, metrics={})
        for who, inv in inventories.items():
            if key in inv:
                review = load_review(inv[key], provider, raw[row], shadow[row], vessel[row], offset, images.shape)
                case['reviewers'][who] = review
                hashes.append(dict(path=review['source_path'], sha256=review['sha256'], kind='journal'))
        if len(case['reviewers']) == 2:
            for mode in MODES:
                d = paired(case['reviewers']['lead'], case['reviewers']['shichu'], mode)
                overall = stats(d)
                case['metrics'][mode] = overall
                pooled[mode].append(d.ravel())
                if overall['n']:
                    case_maes[mode].append(overall['mae_um'])
                for k, name in enumerate(SURFACE_NAMES):
                    layer_pooled[mode][k].append(d[k])
                    rows.append(dict(case=key, scan_id=sid, bscan=row, scope=mode, boundary=name,
                                     total_columns=case['width'], **stats(d[k])))
        im = np.asarray(images[row], float)
        finite = im[np.isfinite(im)]
        lo, hi = np.percentile(finite, [1, 99.5])
        gray = np.nan_to_num(np.clip((im-lo)/max(hi-lo, 1e-6), 0, 1))
        Image.fromarray((gray*255).astype(np.uint8)).save(out/case['image'])
        # Data URLs also keep canvas PNG export usable when index.html opens offline.
        case['image_data'] = 'data:image/png;base64,' + base64.b64encode((out/case['image']).read_bytes()).decode('ascii')
        cases.append(case)
        print(f"{len(cases):02d} {key} {','.join(case['reviewers'])}", flush=True)
    summary = dict(created=datetime.now(timezone.utc).isoformat(), axial_um_per_pixel=PX_UM,
                   counts={who:dict(saved=len(inv), states=dict(Counter(c['reviewers'][who]['status'] for c in cases if who in c['reviewers']))) for who, inv in inventories.items()},
                   matched=sum(len(c['reviewers']) == 2 for c in cases), union=len(cases), modes={}, per_boundary={})
    for mode in MODES:
        summary['modes'][mode] = stats(np.concatenate(pooled[mode]) if pooled[mode] else [])
        summary['modes'][mode]['equal_bscan_mae_um'] = float(np.mean(case_maes[mode])) if case_maes[mode] else None
        summary['per_boundary'][mode] = {name:stats(np.concatenate(layer_pooled[mode][k]) if layer_pooled[mode][k] else []) for k, name in enumerate(SURFACE_NAMES)}
    # Detect concurrent edits instead of publishing an internally stale snapshot.
    for item in hashes:
        if digest(item['path']) != item['sha256']:
            raise RuntimeError('Source changed during build; rebuild: '+item['path'])
    manifest = dict(sources=hashes, reviewer_roots={k:str(v.resolve()) for k,v in roots.items()},
                    replay_source=str(sys.modules[resolve.__module__].__file__),
                    replay_sha256=digest(sys.modules[resolve.__module__].__file__))
    payload = safe(dict(summary=summary, names=SURFACE_NAMES, cases=cases, provenance=manifest))
    (out/'data.js').write_text('window.COMPARISON = '+json.dumps(payload, separators=(',', ':'), allow_nan=False)+';\n', encoding='utf-8')
    (out/'index.html').write_text(Path(__file__).with_name('viewer.html').read_text(encoding='utf-8'), encoding='utf-8')
    (out/'cnv.js').write_text(Path(__file__).with_name('cnv.js').read_text(encoding='utf-8'), encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(safe(summary), indent=2), encoding='utf-8')
    (out/'source_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    fields = ['case','scan_id','bscan','scope','boundary','total_columns', *stats([])]
    with (out/'boundary_differences.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    with (out/'inventory.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f, fieldnames=['case','scan_id','bscan','lead','shichu'])
        writer.writeheader()
        writer.writerows(dict(case=c['id'],scan_id=c['scan_id'],bscan=c['bscan'], **{who:c['reviewers'].get(who,{}).get('status','Missing') for who in roots}) for c in cases)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lead', default='F:/octa/reviewers/lead')
    parser.add_argument('--shichu', default='F:/octa/reviewers/shichu')
    parser.add_argument('--providers', nargs='+', default=['F:/octa/For_Segmentation/Reviewed_Samples','F:/octa/For_Segmentation/More_Samples'])
    parser.add_argument('--output', default=str(PROJECT/'outputs/reviewer_comparison'))
    build(parser.parse_args())
