"""Read-only native-grid thickness engine. No Qt, inference, or label writes."""
from pathlib import Path
from types import SimpleNamespace
import csv
import hashlib
import json
import sys
import os
# Some desktop hosts supply duplicate PATH/Path entries. Keep the activated
# environment's DLL search directory explicit for NumPy's delayed MKL loads.
_dll_handles = []
if os.name == 'nt' and os.environ.get('CONDA_PREFIX'):
    _dll_bin = Path(os.environ['CONDA_PREFIX'])/'Library/bin'
    os.environ['PATH'] = str(_dll_bin) + os.pathsep + os.environ.get('PATH', '')
    if _dll_bin.is_dir(): _dll_handles.append(os.add_dll_directory(str(_dll_bin)))
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from cnv_review_v1.data import SurfaceIndex
from eight_surface import provenance as P
from eight_surface.config import SURFACE_NAMES
from octa_seg_v1.decisions import REASONS

LAYERS = [('Full retina', 0, 7), ('RNFL', 0, 1), ('GCL', 1, 2),
          ('IPL', 2, 3), ('INL', 3, 4), ('OPL', 4, 5),
          ('Photoreceptor composite', 5, 6), ('RPE band', 6, 7)]
SOURCES = ['missing', 'automatic segmentation', 'human stroke',
           'approved automatic position', 'contextual estimate', 'pending human stroke',
           'saved U-Net position']
POLICY = 'pilot-use-available-exclude-explicit-unreliable-v2'
UM = 1.12
WHY = {**REASONS, 20: 'human stroke pending explicit approval', 21: 'explicitly approved position',
       22: 'human unreliable; preview only if eligible', 23: 'human not traceable, image exclusion, or rejected B-scan',
       24: 'context invalidated by changed supporting row or neighbor'}

def sha(path):
    path = Path(path)
    if not path.exists(): return None
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def read_npz(path):
    with np.load(path, allow_pickle=False) as d: return {k: d[k] for k in d.files}

def pixel(x, y, shape):
    return (int(np.clip(np.floor(y + .5), 0, shape[0]-1)),
            int(np.clip(np.floor(x + .5), 0, shape[1]-1)))

def approved_positions(label, events):
    mask = np.zeros_like(label['surfaces'], bool)
    for event in events:
        k = list(label['surface_names']).index(event['boundary'])
        cols = np.asarray(event['columns'], int)
        if np.any((cols < 0) | (cols >= mask.shape[1])): raise ValueError('Invalid approval columns')
        mask[k, cols] = False
        if event['action'] == 'approved_for_future_positions':
            mask[k, cols] = np.isclose(label['surfaces'][k, cols], event['positions_crop_px'], atol=1e-4, rtol=0)
    return (mask & (P.record_visibility(label) == P.MARK_YES)
            & (P.record_reliability(label) == P.MARK_YES)
            & ~label['local_displaced'] & ~label['local_taper']
            & ~label['region_excluded'][None] & (label['verdict'] != 'rejected'))

def measure(endpoints, sources, shadow, unreliable=None):
    """Both modes share this exact calculation; missing stays NaN."""
    values, estimated = [], []
    for _, a, b in LAYERS:
        delta = (endpoints[:, b] - endpoints[:, a]) * UM
        valid = np.isfinite(delta) & (delta > 0) & ~shadow
        values.append(np.where(valid, delta, np.nan))
        estimated.append(valid & ((unreliable[:, a] | unreliable[:, b]) if unreliable is not None else ((sources[:, a] >= 4) | (sources[:, b] >= 4))))
    return np.stack(values), np.stack(estimated)

class Volume:
    def __init__(self, directory, config):
        self.path = Path(directory).resolve(); self.scan_id = self.path.name
        self.config = config
        for name in ('complete.json', 'neural_complete.json', 'geometry.npz', 'measurements.npz', 'images.npy', 'human_overrides_provenance.json'):
            if not (self.path/name).exists(): raise ValueError(f'Incomplete volume: missing {name} in {self.path}')
        self.complete = json.loads((self.path/'complete.json').read_text())
        self.neural = json.loads((self.path/'neural_complete.json').read_text())
        if any(d['scan_id'] != self.scan_id for d in (self.complete, self.neural)):
            raise ValueError('Scan identity mismatch')
        self.g = read_npz(self.path/'geometry.npz'); self.d = read_npz(self.path/'measurements.npz')
        self.images = np.load(self.path/'images.npy', mmap_mode='r')
        self.offset = int(self.g['label_offset']); n, w, depth = map(int, self.g['native_shape'])
        lo, hi = map(int, self.g['retina_band']); high = bool(self.g['vitreous_high'])
        self.shape = (n, w); expected = (n, 8, w)
        if (list(self.d['surface_names']) != SURFACE_NAMES or self.images.shape != (n, hi-lo, w)
            or not 0 <= lo < hi <= depth or self.offset != (depth-hi if high else lo)
            or int(self.d['label_offset']) != self.offset
            or self.neural['orientation_detected'] != high or self.neural['label_offset'] != self.offset
            or 'vitreous 0' not in self.neural['axis_order']):
            raise ValueError('Incompatible native grid, boundary names, crop, or orientation')
        for key in ('reported_positions', 'uncertain_estimates', 'raw_position_branch', 'state', 'reason'):
            if self.d[key].shape != expected: raise ValueError(f'Invalid {key} dimensions')
        if self.g['shadow'].shape != self.shape or not np.array_equal(self.g['shadow'], self.d['shadow']):
            raise ValueError('Shadow grid mismatch')
        self.source_hashes = {name: sha(self.path/name) for name in ('measurements.npz', 'geometry.npz', 'neural_complete.json', 'complete.json')}
        frozen = self.complete.get('measurements', {})
        if frozen.get('sha256') and frozen.get('hash_scope') == 'full_file' and frozen['sha256'] != self.source_hashes['measurements.npz']:
            raise ValueError('Completed measurement fingerprint mismatch')
        self.enface = np.mean(self.images, axis=1)
        self.scan = SimpleNamespace(scan_id=self.scan_id, surface_names=tuple(SURFACE_NAMES),
                    surfaces=self.d['reported_positions'], native_shape=self.shape)
        self.index = SurfaceIndex([Path(config['output'])/'surface_labels', *config['manual_sources']])
        self.limits = {}; self.exported = []; self.reload()

    def reload(self):
        self.index.refresh(self.scan)
        rep = self.d['reported_positions'].copy() - self.offset
        preview = self.d['uncertain_estimates'].copy() - self.offset
        src = np.where(np.isfinite(rep), 1, 0).astype('uint8')
        psrc = np.where(np.isfinite(preview), 4, 0).astype('uint8')
        reason = self.d['reason']
        # Frozen image guards are retained conservatively, even after removing a label.
        blocked = (self.d['state'] == 2) | np.isin(reason, [7, 8]) | self.g['shadow'][:, None, :]
        unreliable = reason == 6  # explicit human unreliability, not model uncertainty
        self.messages = reason.copy()
        fingerprints = {}; changed_rows = set()
        frozen = json.loads((self.path/'human_overrides_provenance.json').read_text())
        baseline = {str(Path(f['path']).resolve()): f['sha256'] for f in frozen}
        for path, old_hash in baseline.items():
            if sha(path) != old_hash: changed_rows.add(int(Path(path).stem.rsplit('_b', 1)[1]))
        self.events = {}
        for row, (path, rec) in self.index.records.items():
            digest = sha(path); fingerprints[str(path)] = digest
            if digest != baseline.get(str(path.resolve())): changed_rows.add(row)
            context_path = path.parent.parent/'surface_context'/f'{path.stem}.json'
            if context_path.exists():
                context = json.loads(context_path.read_text())
                if (context['scan_id'] != self.scan_id or context['bscan'] != row
                    or list(context['retina_band']) != self.g['retina_band'].tolist()
                    or not context['canonical_vitreous_at_depth_zero']
                    or Path(context['source_volume']).resolve() != Path(self.neural['source']['path']).resolve()):
                    raise ValueError(f'Correction coordinate frame mismatch: {context_path}')
                fingerprints[str(context_path)] = sha(context_path)
            if rec.get('local_provenance_available'):
                drawn = rec['local_drawn'] & ~rec['local_displaced'] & ~rec['local_taper']
            else: drawn = np.zeros_like(rep[row], bool)
            event_path = Path(self.config['output'])/'estimate_feedback'/f'{self.scan_id}_b{row:04d}.json'
            events = []
            if event_path.exists():
                data = json.loads(event_path.read_text())
                if data['scan_id'] != self.scan_id or data['bscan'] != row: raise ValueError('Feedback identity mismatch')
                events = data['events']; fingerprints[str(event_path)] = sha(event_path); changed_rows.add(row)
            self.events[row] = events
            vis = P.record_visibility(rec); rel = P.record_reliability(rec)
            hard = (vis == P.MARK_NO) | rec['region_excluded'][None]
            if rec['verdict'] == 'rejected': hard[:] = True
            approved = approved_positions(rec, events)
            # Exact human strokes with explicit positive reliability can be reported.
            approved |= drawn & (vis == P.MARK_YES) & (rel == P.MARK_YES)
            blocked[row] |= hard
            unreliable[row] |= rel == P.MARK_NO
            unreliable[row][rel == P.MARK_YES] = False
            rep[row, drawn | approved] = np.nan
            take = approved & ~hard
            rep[row, take] = rec['surfaces'][take]
            src[row, take] = np.where(drawn[take], 2, 3)
            preview[row, drawn] = rec['surfaces'][drawn]; psrc[row, drawn] = 5
            self.messages[row, drawn] = 20
            self.messages[row, take] = 21
            self.messages[row, rel == P.MARK_NO] = 22
            self.messages[row, hard] = 23
        # Conservative dependency invalidation: entire changed row and immediate neighbors.
        self.stale_context_rows = sorted({b for r in changed_rows for b in (r-1, r, r+1) if 0 <= b < self.shape[0]})
        for b in self.stale_context_rows:
            stale = psrc[b] == 4
            preview[b, stale] = np.nan
            self.messages[b, stale] = 24
        raw = self.d['raw_position_branch'] - self.offset
        take = ~np.isfinite(preview)
        preview[take] = raw[take]; psrc[take] = 6
        psrc[np.isfinite(rep)] = src[np.isfinite(rep)]
        preview[np.isfinite(rep)] = rep[np.isfinite(rep)]
        # Direct saved strokes take precedence even without a training approval.
        for row, (_, rec) in self.index.records.items():
            if rec.get('local_provenance_available'):
                drawn = rec['local_drawn'] & ~rec['local_displaced'] & ~rec['local_taper']
                preview[row, drawn] = rec['surfaces'][drawn]
                psrc[row, drawn] = 2
        preview[blocked | (preview < 0) | (preview > self.images.shape[1]-1)] = np.nan
        rep = preview.copy(); rep[unreliable] = np.nan; src = psrc.copy()
        # Reject endpoints that cross any other finite endpoint in the same mode.
        for arr in (rep, preview):
            invalid = np.zeros(arr.shape, bool)
            for a in range(8):
                for b in range(a+1, 8):
                    crossing = np.isfinite(arr[:, a]) & np.isfinite(arr[:, b]) & (arr[:, a] >= arr[:, b])
                    invalid[:, a] |= crossing; invalid[:, b] |= crossing
            arr[invalid] = np.nan
        src[~np.isfinite(rep)] = 0; psrc[~np.isfinite(preview)] = 0
        self.endpoints = (rep, preview); self.sources = (src, psrc)
        self.unreliable = unreliable
        self.maps = [measure(a, s, self.g['shadow'], unreliable) for a, s in zip(self.endpoints, self.sources)]
        for k in range(8):
            if k not in self.limits:
                vals = self.maps[0][0][k]; vals = vals[np.isfinite(vals)]
                if not len(vals): vals = self.maps[1][0][k]; vals = vals[np.isfinite(vals)]
                limits = np.percentile(vals, [2, 98]) if len(vals) else np.array([0., 300.])
                if limits[1] <= limits[0]: limits[1] = limits[0]+1
                self.limits[k] = list(map(float, limits))
        self.correction_hashes = fingerprints
        revision = POLICY + sha(self.path/'measurements.npz') + json.dumps(fingerprints, sort_keys=True) + str(self.stale_context_rows)
        self.revision = hashlib.sha256(revision.encode()).hexdigest()
        for path, revision in self.exported:
            if revision != self.revision:
                Path(str(path)+'.stale.json').write_text(json.dumps({'stale': True, 'reason': 'Corrections changed; export again', 'current_revision': self.revision}, indent=2))
        # Also detect old exports after closing and reopening the viewer.
        for path in (HERE/'exports').glob(f'{self.scan_id}_*.json'):
            if path.name.endswith('.stale.json'): continue
            old = json.loads(path.read_text())
            if old.get('revision') and old['revision'] != self.revision:
                for suffix in ('.json', '.npz', '.png', '.csv'):
                    artifact = path.with_suffix(suffix)
                    if artifact.exists() and (artifact,old['revision']) not in self.exported:
                        self.exported.append((artifact,old['revision']))
                        Path(str(artifact)+'.stale.json').write_text(json.dumps({'stale':True,'reason':'Corrections changed; export again','current_revision':self.revision}))

    def point(self, row, col, mode):
        result = []
        for k, (name, a, b) in enumerate(LAYERS):
            val = float(self.maps[mode][0][k, row, col]); estimated = bool(self.maps[mode][1][k, row, col])
            ends = self.endpoints[mode][row, [a, b], col]
            source = self.sources[mode][row, [a, b], col]
            missing = []
            for j, s in zip((a, b), source):
                if not s:
                    why = 'shadow' if self.g['shadow'][row, col] else WHY.get(int(self.messages[row, j, col]), 'withheld')
                    if self.unreliable[row,j,col]: why = 'explicitly marked unreliable; enable Include unreliable measurements'
                    missing.append(f'{SURFACE_NAMES[j]}: {why}; missing or invalid endpoint')
            result.append(dict(scan_id=self.scan_id, bscan=row, aline=col, layer=name,
                mode=('exclude_unreliable', 'include_unreliable')[mode], thickness_um=val if np.isfinite(val) else None,
                estimated=estimated, top_boundary=SURFACE_NAMES[a], bottom_boundary=SURFACE_NAMES[b],
                top_crop_px=float(ends[0]) if np.isfinite(ends[0]) else None,
                bottom_crop_px=float(ends[1]) if np.isfinite(ends[1]) else None,
                top_full_px=float(ends[0]+self.offset) if np.isfinite(ends[0]) else None,
                bottom_full_px=float(ends[1]+self.offset) if np.isfinite(ends[1]) else None,
                top_source=SOURCES[source[0]], bottom_source=SOURCES[source[1]],
                top_state=('unreliable' if self.unreliable[row,a,col] else 'missing' if source[0]==0 else 'usable for pilot'),
                bottom_state=('unreliable' if self.unreliable[row,b,col] else 'missing' if source[1]==0 else 'usable for pilot'),
                missing_reason='; '.join(missing), revision=self.revision, experimental=True))
        return result

    def metadata(self):
        return dict(format='octa-thick_v1', scan_id=self.scan_id, units='um', axial_um_per_px=UM,
            axis_order='layer,B-scan,A-line', endpoint_axis_order='B-scan,boundary,A-line',
            canonical_vitreous_at_depth_zero=True, crop_offset=self.offset, raw_vitreous_high=bool(self.g['vitreous_high']),
            layers=[(n, SURFACE_NAMES[a], SURFACE_NAMES[b]) for n,a,b in LAYERS], source_codes=SOURCES,
            endpoint_reason_codes=WHY,
            model_version='octa-seg_v1', experimental=True, analysis_policy=POLICY,
            policy_note='Available positions assumed usable for this pilot; this does not change model validation or human ground truth. Toggle affects explicit human unreliability only.',
            source_fingerprints=self.source_hashes,
            source_volume=self.neural['source'], position_checkpoint=self.neural['position_checkpoint'],
            correction_fingerprints=self.correction_hashes, revision=self.revision,
            stale_context_rows=self.stale_context_rows, color_limits=self.limits,
            note='Photoreceptor composite includes ONL; isolated ONL unavailable. Frozen denials retained conservatively.')

    def export(self, path):
        reported = self.maps[0][0]; preview, estimated = self.maps[1]
        np.savez_compressed(path, reported_um=reported, estimated_um=np.where(estimated, preview, np.nan),
            exclude_unreliable_um=reported, include_unreliable_um=preview, unreliable_measurement_mask=estimated,
            unreliable_endpoint_mask=self.unreliable,
            preview_um=preview, reported_mask=np.isfinite(reported), estimated_mask=estimated,
            shadow=self.g['shadow'], reported_endpoints_crop_px=self.endpoints[0],
            preview_endpoints_crop_px=self.endpoints[1], reported_endpoint_sources=self.sources[0],
            preview_endpoint_sources=self.sources[1], endpoint_reason=self.messages,
            metadata_json=np.array(json.dumps(self.metadata())))
        self.exported.append((Path(path), self.revision))

    def save_point(self, path, row, col, mode):
        records = self.point(row, col, mode); path = Path(path)
        exists = path.exists()
        with path.open('a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            if not exists: writer.writeheader()
            writer.writerows(records)
        path.with_suffix('.json').write_text(json.dumps(self.metadata(), indent=2))
        self.exported.append((path, self.revision))
