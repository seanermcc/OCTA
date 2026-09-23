"""Atomic products and read-only source selection. Never invoke upstream loaders."""
from pathlib import Path
import hashlib
import json
import os
import re
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / 'outputs/octa-reg_v1'
DEFAULT_INVENTORY = ROOT / 'outputs/octa-auto_cnv_unet_v6/all_samples/inventory.json'
DEFAULT_EXPORT = ROOT / 'outputs/octo-vessel_onh_v2/final_output_v1'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()

def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(tmp, path)

def save(path, **arrays):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('wb') as f: np.savez_compressed(f, **arrays)
    os.replace(tmp, path)

def identity(path):
    return str(path).replace('\\', '/').casefold().split('/octa_rawdata/', 1)[-1]

def checked(path, expected):
    actual = sha(path)
    if not expected or actual != expected: raise ValueError('hash mismatch: ' + str(path))
    return actual

def boolean(array, shape, name):
    if array.shape != tuple(shape) or array.dtype != bool:
        raise ValueError('Boolean native grid mismatch: ' + name)
    return array.copy()

def assessable_onh(record):
    return bool(record.get('onh_reviewed') and record.get('onh_visibility', '').startswith(('Visible', 'Partially visible')))

def select_masks(row, sidecar, shape, records, export):
    """Presence in primary export is authoritative, including empty/invalid/draft."""
    sid = row['scan_id']; rec = records.get(sid)
    if rec is not None:
        for key in ('animal', 'eye', 'session_date'):
            if rec[key] != row[key]: raise ValueError('Export identity mismatch: ' + key)
        if identity(rec['source_volume']) != identity(row['source']):
            raise ValueError('Export source identity mismatch')
        path = Path(export) / rec['masks']; h = checked(path, rec['masks_sha256'])
        with np.load(path, allow_pickle=False) as z:
            data = {k: z[k].copy() for k in z.files}
        if str(data['scan_id']) != sid or identity(str(data['source_volume'])) != identity(row['source']):
            raise ValueError('Mask embedded identity mismatch')
        if str(data['axis_order']) != 'B-scan,A-line' or list(data['native_shape']) != list(shape):
            raise ValueError('Mask axis/grid mismatch; resizing forbidden')
        for key in ('vessel_mask', 'onh_mask'):
            boolean(data[key], shape, key)
        for key, value in data.items():
            if value.ndim == 2: boolean(value, shape, key)
        if bool(data['excluded_from_analysis']) != bool(rec['excluded_from_analysis']):
            raise ValueError('Exclusion flag mismatch')
        provenance = dict(rec, mask_source='primary_export', mask_path=str(path), mask_hash=h,
                          onh_available=True, onh_assessable=assessable_onh(rec))
        return data, provenance
    # Only absent acquisitions may use legacy geometry. Read exactly the vessel field.
    geo = sidecar['geometry']; path = Path(geo['path']); h = checked(path, geo['sha256'])
    if path.parent.name != sid: raise ValueError('Fallback acquisition path identity mismatch')
    with np.load(path, allow_pickle=False) as z:
        if list(z['native_shape'][:2]) != list(shape): raise ValueError('Fallback native grid mismatch')
        vessel = boolean(z['vessel'], shape, 'legacy vessel')
    return {'vessel_mask': vessel}, dict(mask_source='legacy_geometry_fallback', selection='automatic/unreviewed',
        mask_path=str(path), mask_hash=h, vessel_reviewed=False, onh_reviewed=False,
        onh_available=False, onh_assessable=False, onh_visibility='unavailable',
        excluded_from_analysis=False, exclusion_reason='', geometry_identity_basis='verified sidecar + scan-named directory + pinned hash')

def load_scan(row, inventory, records, export):
    sid = row['scan_id']; sidepath = Path(inventory).parent / 'inputs' / (sid + '.json')
    side = read(sidepath)
    if side['scan_id'] != sid or identity(side['source']['path']) != identity(row['source']):
        raise ValueError('Optical sidecar acquisition identity mismatch')
    if side['axis_order'] != 'B-scan,A-line': raise ValueError('Optical axis mismatch')
    if not side.get('orientation_fresh_detected'): raise ValueError('Fresh orientation provenance unavailable')
    path = sidepath.with_suffix('.npz'); h = checked(path, side['optical_cache']['sha256'])
    with np.load(path, allow_pickle=False) as z: optical = z['optical'].copy()
    shape = tuple(side['native_shape'][:2])
    if optical.shape != (2, *shape): raise ValueError('Optical native grid mismatch')
    # Newly discovered acquisitions legitimately omit the legacy index dimensions.
    # The cache and fresh-source sidecar still independently agree on the native grid.
    if row.get('n_slow') and int(row['n_slow']) != shape[0]: raise ValueError('Inventory grid mismatch')
    if row.get('n_fast') and int(row['n_fast']) != shape[1]: raise ValueError('Inventory grid mismatch')
    masks, prov = select_masks(row, side, shape, records, export)
    spacing = [1460. / shape[0], 1460. / shape[1]]
    calibration = dict(status='approximate', provenance='1460 um field / actual native grid; X500um is galvo amplitude')
    cal = side.get('lateral_calibration', {})
    if cal.get('validated') is True:
        spacing = [float(cal['bscan_um']), float(cal['aline_um'])]
        if not np.all(np.isfinite(spacing)) or min(spacing) <= 0: raise ValueError('Invalid validated calibration')
        calibration = dict(status='validated', provenance=cal)
    blocked = ~np.isfinite(optical[0]); available = []
    for key in ('image_excluded', 'region_excluded', 'vessel_region_excluded', 'onh_region_excluded',
                'uncertain_mask', 'vessel_uncertain', 'onh_uncertain'):
        if key in masks:
            blocked |= boolean(masks[key], shape, key); available.append(key)
    if prov['onh_assessable']: blocked |= masks['onh_mask']
    arrays = dict(enface=optical[0], octa=optical[1], vessel=masks['vessel_mask'],
                  registration_blocked=blocked, spacing=np.asarray(spacing))
    arrays.update({'selected_' + k: v for k, v in masks.items()})
    info = dict(row, **{k:v for k,v in prov.items() if k not in row}, shape=list(shape), spacing=spacing,
                calibration=calibration, grid_provenance='cache + fresh-source sidecar' + (' + inventory dimensions' if row.get('n_slow') and row.get('n_fast') else '; optional inventory dimensions absent'), orientation_provenance={k:side.get(k) for k in
                    ('orientation_fresh_detected', 'orientation_evidence', 'direct_source_rechecked', 'canonical_crop_offset')},
                source_identity=side['source'], optical_path=str(path), optical_hash=h,
                sidecar_path=str(sidepath), sidecar_hash=sha(sidepath),
                explicit_exclusion_fields=available, absent_exclusion_information='unknown',
                exclusion_policy='No CNV, lesion, thickness, low-signal or vessel-shadow exclusions',
                mask_metadata={k:v.tolist() for k,v in masks.items() if v.ndim != 2},
                input_hashes={str(path):h, str(sidepath):sha(sidepath), prov['mask_path']:prov['mask_hash']})
    # Never allow a similarly named upstream inventory field to override mask policy.
    info.update(prov)
    return arrays, info

def input_rows(inventory):
    rows = read(inventory)['scans']; ids=set(); sources=set()
    for row in rows:
        row['animal'] = 'TS' + re.fullmatch(r'TS?(\d+)[MF]?', row['animal']).group(1)
        if row['eye'] not in ('OD', 'OS'): raise ValueError('Unknown eye')
        if not row['scan_id'].startswith(row['animal']+'_'+row['eye']+'_'+row['session_date']):
            raise ValueError('Scan ID identity mismatch')
        if row['scan_id'] in ids or identity(row['source']) in sources: raise ValueError('Duplicate acquisition')
        ids.add(row['scan_id']); sources.add(identity(row['source']))
    return sorted(rows, key=lambda r:r['scan_id'])
