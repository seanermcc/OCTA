"""Freeze manual-first vessel/ONH overlay exports without writing human labels."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parents[1]
BATCH = OUTPUTS / 'octa-vessel_seg_v1-batch'
LABELS = OUTPUTS / 'octo-vessel_onh_v1/labels'
CNV = OUTPUTS / 'octa-auto_cnv_v8'
AXES = 'B-scan,A-line'
COLORS = {'vessel': (20, 175, 255), 'onh': (38, 235, 127)}
MANUAL_ARRAYS = ('onh_edge_mask', 'vasculature_brush_touched', 'onh_brush_touched',
                 'vessel_region_excluded', 'onh_region_excluded', 'vessel_removed_by_onh')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar(z, key, default=None):
    return z[key].reshape(-1)[0].item() if key in z else default


def source_key(path):
    # Preserve acquisition identity across historical drive-letter relocations.
    text = str(path).replace('\\', '/').casefold()
    marker = '/octa_rawdata/'
    if marker not in text:
        raise ValueError('Unrecognized acquisition path: ' + text)
    return text.split(marker, 1)[1]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def build():
    check(not (HERE / 'manifest.json').exists(), 'Frozen export already exists; use --verify.')
    inventory = read(BATCH / 'inventory.json')
    ids = {r['scan_id'] for r in inventory}
    manual_ids = {p.name.removesuffix('_cnv.npz') for p in LABELS.glob('*_cnv.npz')}
    check(len(ids) == len(inventory), 'Duplicate inventory identities')
    check(manual_ids <= ids, 'Manual records outside the frozen cohort')
    exclusions = {r['scan_id']: r for r in read(HERE.parent / 'exclusions.json')}
    for folder in ('masks', 'png_masks', 'overlays'):
        (HERE / folder).mkdir(exist_ok=True)
    records = []
    for row in sorted(inventory, key=lambda r: r['scan_id']):
        sid = row['scan_id']
        manual = sid in manual_ids
        source = LABELS / (sid + '_cnv.npz') if manual else BATCH / 'proposals' / (sid + '_proposal.npz')
        source_hash = sha(source)
        with np.load(source, allow_pickle=False) as z:
            check(scalar(z, 'scan_id') == sid, sid + ': source ID')
            check(source_key(scalar(z, 'source_volume')) == source_key(row['source']), sid + ': source volume')
            check(tuple(z['native_shape']) == (512, 512), sid + ': source grid')
            if not manual:
                check(scalar(z, 'axis_order') == AXES, sid + ': source axes')
            vessel = z['vasculature_mask' if manual else 'predicted_vasculature_mask'].copy()
            onh = z['onh_mask' if manual else 'human_onh_exclusion_mask'].copy()
            for mask in (vessel, onh):
                check(mask.shape == (512, 512) and mask.dtype == bool, sid + ': mask grid/type')
            reviewed = z['reviewed_targets'][1:].astype(bool) if manual else np.zeros(2, bool)
            metadata = {k: z[k].tolist() for k in z.files if z[k].size <= 4} if manual else {}
            rec = dict(scan_id=sid, animal=row['animal'], eye=row['eye'], day_label=row['day_label'],
                       session_date=row['session_date'], source_volume=row['source'],
                       selection='saved_manual' if manual else 'frozen_v1',
                       source_path=source.relative_to(OUTPUTS).as_posix(), source_sha256=source_hash,
                       vessel_reviewed=bool(reviewed[0]), onh_reviewed=bool(reviewed[1]),
                       onh_visibility=scalar(z, 'onh_visibility', 'Not assessed'),
                       revision=scalar(z, 'revision'), labelled_at=scalar(z, 'labelled_at'),
                       notes=scalar(z, 'notes', ''), excluded_from_analysis=sid in exclusions,
                       exclusion_reason=exclusions.get(sid, {}).get('reason', ''),
                       vessel_pixels=int(vessel.sum()), onh_pixels=int(onh.sum()),
                       overlap_pixels=int((vessel & onh).sum()),
                       masks=f'masks/{sid}.npz', png_masks={}, overlays={})
            arrays = dict(vessel_mask=vessel, onh_mask=onh, scan_id=np.array(sid),
                          source_volume=np.array(row['source']), axis_order=np.array(AXES),
                          native_shape=np.array([512, 512]), source_selection=np.array(rec['selection']),
                          source_sha256=np.array(source_hash), reviewed_targets=reviewed,
                          annotation_names=np.array(['VASCULATURE', 'ONH']),
                          excluded_from_analysis=np.array(rec['excluded_from_analysis']),
                          onh_visibility=np.array(rec['onh_visibility']),
                          metadata_json=np.array(json.dumps(metadata, ensure_ascii=False)),
                          export_schema=np.array('vessel-onh-overlay-export-v1'))
            for key in MANUAL_ARRAYS:
                arrays[key] = z[key].copy() if manual and key in z else np.zeros((512, 512), bool)
            np.savez_compressed(HERE / rec['masks'], **arrays)
        check(sha(source) == source_hash, sid + ': source changed during export')
        rec['masks_sha256'] = sha(HERE / rec['masks'])
        for name, mask in (('vessel', vessel), ('onh', onh)):
            rec['png_masks'][name] = f'png_masks/{sid}_{name}.png'
            rec['overlays'][name] = f'overlays/{sid}_{name}.png'
            Image.fromarray(mask.astype(np.uint8) * 255).save(HERE / rec['png_masks'][name])
            rgba = np.zeros((512, 512, 4), np.uint8)
            rgba[mask, :3] = COLORS[name]
            rgba[mask, 3] = 155
            Image.fromarray(rgba).save(HERE / rec['overlays'][name])
        records.append(rec)
    manifest = dict(schema='vessel-onh-overlay-export-v1', created_at=datetime.now(timezone.utc).isoformat(),
                    selection_policy='Use both saved manual masks when a record exists, including drafts and empty masks; otherwise use frozen v1.',
                    axis_order=AXES, native_shape=[512, 512], transform='none',
                    purpose='Overlay export; not a new human-label or training release',
                    counts=dict(total=len(records), saved_manual=len(manual_ids), frozen_v1=len(records)-len(manual_ids),
                                excluded_from_analysis=sum(r['excluded_from_analysis'] for r in records)), records=records)
    write(HERE / 'manifest.json', manifest)
    fields = [k for k in records[0] if k not in ('png_masks', 'overlays')]
    with (HERE / 'inventory.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(records)
    print(json.dumps(manifest['counts']), flush=True)


def verify():
    manifest = read(HERE / 'manifest.json')
    rows = manifest['records']
    check(len(rows) == manifest['counts']['total'], 'Record count mismatch')
    for rec in rows:
        sid = rec['scan_id']; source = OUTPUTS / rec['source_path']
        check(sha(source) == rec['source_sha256'], sid + ': original source changed')
        check(sha(HERE / rec['masks']) == rec['masks_sha256'], sid + ': export hash mismatch')
        manual = rec['selection'] == 'saved_manual'
        check(manual == (LABELS / (sid + '_cnv.npz')).exists(), sid + ': manual precedence changed')
        with np.load(source, allow_pickle=False) as src, np.load(HERE / rec['masks'], allow_pickle=False) as out:
            for target, key in [('vessel', 'vasculature_mask' if manual else 'predicted_vasculature_mask'),
                                ('onh', 'onh_mask' if manual else 'human_onh_exclusion_mask')]:
                mask = out[target + '_mask']
                check(np.array_equal(mask, src[key]), sid + ': mask differs from source')
                check(np.array_equal(np.asarray(Image.open(HERE / rec['png_masks'][target])), mask.astype(np.uint8)*255), sid + ': PNG pixels')
                rgba = np.asarray(Image.open(HERE / rec['overlays'][target]))
                check(np.array_equal(rgba[:, :, 3], mask.astype(np.uint8)*155), sid + ': overlay coordinates/alpha')
                check(np.all(rgba[mask, :3] == COLORS[target]), sid + ': overlay color')
            if manual:
                check(np.array_equal(out['reviewed_targets'], src['reviewed_targets'][1:]), sid + ': review flags')
                for key in MANUAL_ARRAYS:
                    if key in src:
                        check(np.array_equal(out[key], src[key]), sid + ': provenance ' + key)
    by_id = {r['scan_id']: r for r in rows}
    preview_path = CNV / 'data/preview.json'
    matched = []; missing = []
    for case in read(preview_path)['cases']:
        sid = case['scan_id']; a = case['acquisition']
        if sid not in by_id:
            missing.append(sid); continue
        rec = by_id[sid]
        provider_path = Path(a['input_manifest']['path'])
        check(sha(provider_path) == a['input_manifest']['sha256'], sid + ': CNV provider hash')
        provider = read(provider_path)
        check(provider['scan_id'] == sid, sid + ': CNV identity')
        check(source_key(provider['source']['path']) == source_key(rec['source_volume']) == source_key(a['source']), sid + ': CNV source')
        check(provider['axis_order'] == AXES and provider['native_shape'][:2] == [512, 512], sid + ': CNV native grid')
        with np.load(CNV / 'cache' / sid / 'enface.npz', allow_pickle=False) as z:
            check(z['optical'].shape == (2, 512, 512), sid + ': CNV optical shape')
        with np.load(CNV / 'predictions/model1' / (sid + '.npz'), allow_pickle=False) as z:
            check(z['filtered_mask'].shape == (512, 512), sid + ': CNV prediction shape')
        matched.append(dict(scan_id=sid, masks=rec['masks'], selection=rec['selection'],
                            excluded_from_analysis=rec['excluded_from_analysis'], transform='none'))
    write(HERE / 'cnv_v8_mapping.json', dict(cnv_release=str(CNV), preview_sha256=sha(preview_path),
          matched=len(matched), missing=missing, axis_order=AXES, native_shape=[512, 512], cases=matched))
    report = dict(verified_at=datetime.now(timezone.utc).isoformat(), masks_verified=len(rows),
                  source_masks_equal=True, png_masks_equal=True, rgba_coordinates_equal=True,
                  source_files_unchanged=True, review_and_uncertainty_preserved=True,
                  cnv_v8_matches=len(matched), cnv_v8_missing=missing,
                  manifest_sha256=sha(HERE / 'manifest.json'))
    write(HERE / 'VERIFIED.json', report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if not args.verify:
        build()
    verify()
