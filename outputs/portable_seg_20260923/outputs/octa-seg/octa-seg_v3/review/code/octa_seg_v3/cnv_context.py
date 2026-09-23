"""Read-only final v9 CNV context on the exact native en-face grid.

Live final-correction records supersede exports, including drafts and absence.
This display adapter never writes annotations or supplies layer training labels.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import numpy as np
from .common import ROOT, read, fingerprint

FINAL = ROOT / 'outputs/octa-auto_cnv_v9/final_correction'
GALLERY = FINAL.parent / 'model3/gallery/data.json'
PINK = '#ff80bd'


@lru_cache(maxsize=8)
def _indexed(path, stamp, key):
    document = read(path)
    rows = document[key]
    result = {r['scan_id']: r for r in rows}
    if len(rows) != len(result):
        raise ValueError('Duplicate acquisition in CNV context index')
    return document, result


def index(path, key):
    path = Path(path)
    st = path.stat()
    return _indexed(str(path), (st.st_mtime_ns, st.st_size), key)


def decode(runs, shape):
    mask = np.zeros(shape, bool)
    for run in runs:
        if len(run) != 3 or any(type(v) is not int for v in run):
            raise ValueError('CNV context requires integer native intervals')
        y, lo, hi = run
        if not (0 <= y < shape[0] and 0 <= lo < hi <= shape[1]):
            raise ValueError('CNV context interval outside native grid')
        mask[y, lo:hi] = True
    return mask


def signature_paths(sid):
    paths = [FINAL / 'dataset/manifest.json', GALLERY,
             FINAL / 'review/regions' / (sid + '.json')]
    if paths[0].exists():
        try:
            _, records = index(paths[0], 'records')
            target = records.get(sid, {}).get('targets')
            if target:
                from .data import local_path
                paths.append(local_path(target['path']))
        except (OSError, ValueError, KeyError):
            pass  # Refresh reports the invalid source; polling must keep running.
    return paths


def load_final_cnv(volume):
    manifest = FINAL / 'dataset/manifest.json'
    if not manifest.exists():
        return None
    doc, records = index(manifest, 'records')
    if doc.get('schema') != 'cnv-final-dataset-v1' or doc['summary'].get('synthetic', False):
        raise ValueError('Unsupported/synthetic final CNV dataset')
    sid, shape = volume.scan.scan_id, volume.scan.native_shape
    record = records.get(sid)
    if record is None:
        return None
    _, acquisitions = index(GALLERY, 'cases')
    source = acquisitions[sid]
    from .data import local_path
    if (source['source_identity'] != record['source_identity'] or
            source['native_shape'] != list(shape) or
            local_path(source['source']).resolve() != volume.scan.source_volume.resolve()):
        raise ValueError('Final CNV acquisition/source/native grid mismatch')
    path = FINAL / 'review/regions' / (sid + '.json')
    meta = dict(manifest=str(manifest), source_identity=record['source_identity'])
    if path.exists():
        live = read(path)
        if (live.get('schema') != 'cnv-final-correction-v9.1' or live.get('synthetic', True) or
                live['scan_id'] != sid or live['source_identity'] != record['source_identity'] or
                live['native_shape'] != list(shape) or live['axis_order'] != 'B-scan,A-line'):
            raise ValueError('Final CNV correction source/grid mismatch')
        state = live['state']
        mask, ignored = np.zeros(shape, bool), np.zeros(shape, bool)
        kept = np.zeros(shape, bool)
        has_draft = False
        for region in state['regions']:
            kind = region['state']
            if kind not in ('kept', 'draft', 'unsure', 'excluded', 'removed'):
                raise ValueError('Unknown final CNV region state')
            m = decode(region['runs'], shape)
            if kind in ('kept', 'draft'):
                mask |= m
                has_draft |= kind == 'draft' or not m.any()
            if kind == 'kept': kept |= m
            if kind in ('unsure', 'excluded'): ignored |= m
        mask &= ~ignored
        if not np.array_equal(kept & ~ignored, decode(live['masks']['positive'], shape)) or not np.array_equal(ignored, decode(live['masks']['ignored'], shape)):
            raise ValueError('Final CNV saved masks disagree with region state')
        digest = hashlib.sha256(json.dumps({k: state[k] for k in ('regions', 'absence')},
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        confirmation = state.get('confirmation') or {}
        confirmed = confirmation.get('whole_field_checked') and confirmation.get('annotation_sha256') == digest and not has_draft
        if state['absence'] and (mask.any() or ignored.any()):
            raise ValueError('Final CNV absence conflicts with saved regions')
        if state.get('defer_reason'):
            mask[:] = False
            status = 'final CNV: excluded/deferred (no footprint shown)'
        else:
            status = 'final CNV correction: ' + ('confirmed' if confirmed else 'saved draft; review pending')
            if state['absence']: status += ' · no CNV'
        meta.update(path=str(path), sha256=fingerprint(path), revision=live['revision'], status=status)
        return mask, meta
    status = record['status']
    if status in ('confirmed_positive', 'confirmed_negative'):
        target = record['targets']
        path = local_path(target['path'])
        if fingerprint(path) != target['sha256']:
            raise ValueError('Final CNV target changed since export')
        with np.load(path, allow_pickle=False) as z:
            if str(z['scan_id']) != sid or str(z['axis_order']) != 'B-scan,A-line':
                raise ValueError('Final CNV target identity/axis mismatch')
            arrays = [z[key] for key in ('target', 'known', 'ignored')]
            if any(a.shape != tuple(shape) or a.dtype != np.bool_ for a in arrays):
                raise ValueError('Final CNV target must be boolean on the native grid')
            mask, known, ignored = arrays
            if (mask & (~known | ignored)).any() or bool(mask.any()) != (status == 'confirmed_positive'):
                raise ValueError('Final CNV target conflicts with known/ignored/status')
        meta.update(path=str(path), sha256=target['sha256'], status='final CNV: ' + status.replace('_', ' '))
    elif status == 'correction_pending':
        # The exact selected assessment footprint is useful context, not a new label.
        ref = record['selected_reference']
        if ref['scan_id'] != sid or ref['source_identity'] != record['source_identity']:
            raise ValueError('Pending CNV reference identity mismatch')
        mask = decode(ref['runs'], shape)
        meta.update(path=str(manifest), sha256=fingerprint(manifest), status='final CNV: correction pending · selected assessment footprint')
    elif status in ('excluded_poor_image', 'excluded_deferred'):
        mask = np.zeros(shape, bool)
        meta.update(path=str(manifest), status='final CNV: excluded/poor image (no footprint shown)')
    else:
        raise ValueError('Unknown final CNV dataset status: ' + status)
    return mask, meta
