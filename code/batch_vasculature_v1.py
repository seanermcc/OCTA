"""Resumable full-cohort export of the frozen September 9 major-vessel method."""
import csv
import json
import time
import traceback
from pathlib import Path

import numpy as np
from vasculature_baseline import (ROOT, file_hash, vessel_evidence, make_mask,
                                 display_image, plt, load_label, ProcessedVolume,
                                 _mean_db_dataset)
from vasculature_shape_gate import PARAMETERS, shape_gate
from eight_surface.vasculature_proposals import PROPOSAL_VERSION

OUT = ROOT / 'octa-vessel_seg_v1-batch'
OLD = ROOT / 'outputs/eight_surface/vasculature_proposals'
PILOTS = ROOT / 'outputs/vasculature_baseline'


def write_json(path, data):
    temp = path.with_suffix('.writing.json')
    temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temp.replace(path)


def main():
    OUT.mkdir(exist_ok=True)
    for name in ('proposals', 'previews', 'projections', 'records'):
        (OUT / name).mkdir(exist_ok=True)
    frozen = json.loads((PILOTS / '20260909_queue32/manifest.json').read_text())
    hashes = {n: file_hash(ROOT / 'code' / n) for n in
              ('vasculature_baseline.py', 'vasculature_shape_gate.py')}
    assert all(h == frozen['code_hashes'][n] for n, h in hashes.items()), 'Frozen code changed'
    assert PARAMETERS == frozen['parameters'] and frozen['threshold'] == .18
    rows = list(csv.DictReader((ROOT / 'outputs/scan_quality_metrics.csv').open(newline='')))
    assert len(rows) == 314 and len({r['scan_id'] for r in rows}) == 314
    index = list(csv.DictReader((ROOT / 'outputs/scan_index.csv').open(newline='')))
    assert sum(r['has_volumes'] == 'True' for r in index) == len(rows)
    assert all(r['status'] == 'ok' and Path(r['source']).is_file() for r in rows)
    write_json(OUT / 'inventory.json', rows)
    records = []
    for row in sorted(rows, key=lambda r: (not (OLD / (r['scan_id']+'_proposal.npz')).exists(), r['scan_id'])):
        start = time.monotonic()
        sid, source = row['scan_id'], row['source']
        band = np.array([int(row['retina_lo']), int(row['retina_hi'])])
        previous = OLD / f'{sid}_proposal.npz'
        old_mask = old_onh = None
        if previous.exists():
            with np.load(previous, allow_pickle=False) as z:
                assert Path(str(z['source_volume'][0])).resolve() == Path(source).resolve()
                band = z['retina_band'].copy()
                old_onh = z['human_onh_exclusion_mask'].copy()
                old_mask = z['predicted_vasculature_mask'].copy()
        stat = Path(source).stat()
        label_path = ROOT / 'outputs/cnv_labels' / f'{sid}_cnv.npz'
        label_hash = file_hash(label_path) if label_path.exists() and old_onh is None else None
        identity = dict(source=source, source_size=stat.st_size, source_mtime_ns=stat.st_mtime_ns,
                        retina_band=band.tolist(), code_hashes=hashes, threshold=.18,
                        parameters=PARAMETERS, onh_label_sha256=label_hash,
                        original_proposal_sha256=file_hash(previous) if previous.exists() else None)
        recpath = OUT / 'records' / f'{sid}.json'
        proposal = OUT / 'proposals' / f'{sid}_proposal.npz'
        preview = OUT / 'previews' / f'{sid}.png'
        rec = dict(scan_id=sid, identity=identity)
        try:
            if recpath.exists():
                saved = json.loads(recpath.read_text())
                if (saved.get('status') == 'complete' and saved['identity'] == identity
                        and proposal.exists() and preview.exists()
                        and file_hash(proposal) == saved['proposal_sha256']
                        and file_hash(preview) == saved['preview_sha256']):
                    records.append(saved)
                    continue
            im = None
            cache = OUT / 'projections' / f'{sid}.npz'
            for candidate in (cache, PILOTS / '20260909_major_vessels/projections' / f'{sid}.npz',
                              PILOTS / '20260909_queue32/projections' / f'{sid}.npz'):
                if candidate.exists():
                    with np.load(candidate, allow_pickle=False) as z:
                        if (str(z['source'][0]) == source and int(z['source_mtime_ns'][0]) == stat.st_mtime_ns
                                and np.array_equal(z['retina_band'], band)):
                            im = z['structural_enface'].copy()
                            break
            if im is None:
                print(f'Reading {sid}', flush=True)
                with ProcessedVolume(source) as volume:
                    assert 0 <= band[0] < band[1] <= volume.struct.shape[2]
                    im = _mean_db_dataset(volume.struct, slice(*band))
            np.savez_compressed(cache, structural_enface=im, source=np.array([source]),
                                source_mtime_ns=np.array([stat.st_mtime_ns]), retina_band=band)
            onh = old_onh if old_onh is not None else (
                load_label(label_path)['onh_mask'] if label_path.exists() else np.zeros(im.shape, bool))
            assert onh.shape == im.shape
            evidence, _, _ = vessel_evidence(im)
            before = make_mask(evidence, .18, onh)
            mask, audit = shape_gate(before, **PARAMETERS)
            assert mask.dtype == bool and mask.shape == im.shape
            assert not np.any(mask & ~before) and not np.any(mask & onh)
            if old_mask is not None:
                assert np.array_equal(mask, old_mask), 'Original queue mask did not reproduce'
            temp = proposal.with_suffix('.writing.npz')
            np.savez_compressed(temp, predicted_vasculature_mask=mask, evidence=evidence,
                scan_id=np.array([sid]), source_volume=np.array([source]), retina_band=band,
                native_shape=np.array(im.shape), axis_order=np.array(['B-scan,A-line']),
                proposal_format_version=np.array([PROPOSAL_VERSION]),
                projection_version=np.array(['1-retina-band-mean-db']), human_onh_exclusion_mask=onh,
                method=np.array(['major-vessel-shape-gate-v2']), threshold=np.array([.18]),
                parameters_json=np.array([json.dumps(PARAMETERS)]), code_hashes_json=np.array([json.dumps(hashes)]),
                human_reviewed=np.array([False]), provenance_json=np.array([json.dumps(identity)]))
            temp.replace(proposal)
            with np.load(proposal, allow_pickle=False) as check:
                assert np.array_equal(check['predicted_vasculature_mask'], mask)
            thumb = np.repeat(display_image(im)[..., None], 3, axis=2)
            thumb[mask] = thumb[mask]*.4 + np.array([.1, .65, 1.])*.6
            thumb[onh] = thumb[onh]*.4 + np.array([.2, 1., .4])*.6
            plt.imsave(preview, thumb)
            rec.update(status='complete', vessel_pixels=int(mask.sum()), native_shape=list(im.shape),
                       original_queue_exact_match=old_mask is not None, component_audit=audit,
                       proposal_sha256=file_hash(proposal), preview_sha256=file_hash(preview),
                       seconds=round(time.monotonic()-start, 2))
        except Exception:
            rec.update(status='failed', error=traceback.format_exc())
        write_json(recpath, rec)
        records.append(rec)
        complete = sum(r['status'] == 'complete' for r in records)
        write_json(OUT / 'status.json', dict(status='running', total=len(rows), complete=complete,
                    failed=sum(r['status']=='failed' for r in records), last_scan=sid))
        print(f'{len(records)}/{len(rows)} {sid}: {rec["status"]}', flush=True)
    failed = [r for r in records if r['status'] != 'complete']
    summary = dict(status='complete' if not failed else 'incomplete', total=len(rows),
                   complete=len(records)-len(failed), failed=len(failed),
                   original_queue_exact_matches=sum(r.get('original_queue_exact_match', False) for r in records),
                   threshold=.18, parameters=PARAMETERS, code_hashes=hashes, scans=records)
    write_json(OUT / 'manifest.json', summary)
    write_json(OUT / 'status.json', {k:v for k,v in summary.items() if k != 'scans'})
    entries = ''.join(f'<figure><a href="previews/{r["scan_id"]}.png"><img loading="lazy" src="previews/{r["scan_id"]}.png"></a><figcaption>{r["scan_id"]}</figcaption></figure>' for r in records if r['status']=='complete')
    (OUT / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>octa-vessel_seg_v1-batch</title><style>body{font:16px sans-serif;background:#171717;color:white}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}figure{margin:12px}img{width:100%}figcaption{font-size:12px}</style><h1>Major-vessel automatic proposals</h1><p>Frozen v1 batch. Blue: vessels. Green: existing human ONH exclusion. Automatic, unreviewed masks.</p><main>'+entries+'</main>', encoding='utf-8')
    if failed:
        raise RuntimeError(f'{len(failed)} scans failed; see manifest.json; rerun to retry')


if __name__ == '__main__':
    main()
