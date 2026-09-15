import json, sys, shutil
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path.cwd() / 'code'))
from cnv_review_v1.data import default_config, atomic_json
root = Path.cwd()
run = root / 'outputs/stage_a/20260909_unet_review36_update'
out = run / 'cnv_gui'
providers = out / 'automatic'
queue = out / 'scan_queue'
providers.mkdir(parents=True, exist_ok=True)
queue.mkdir(parents=True, exist_ok=True)
results = []
for folder in sorted((run / 'review_queue').glob('TS*')):
    job_record = json.loads((folder / 'job.json').read_text())
    job = job_record['job']
    summary = json.loads((folder / 'volume_summary.json').read_text())
    sid = job['scan_id']
    base_path = Path(job['segmentation']['path'])
    with np.load(base_path, allow_pickle=False) as base:
        band = base['retina_band'].copy()
        names = base['surface_names'].copy()
        version = base['cascade_version'].copy()
        depth = int(base['shape'][2])
        expected_shape = base['surfaces'].shape
    offset = depth - int(band[1]) if summary['orientation_detected'] else int(band[0])
    assert offset == summary['label_offset']
    rows = []
    for b in range(summary['n_bscans']):
        with np.load(folder / 'predictions' / f'b{b:04d}.npz', allow_pickle=False) as pred:
            assert str(pred['job_id']) == job_record['job_id']
            rows.append(pred['candidate_rows'].copy() - offset)
    surfaces = np.stack(rows).astype(np.float32)
    assert surfaces.shape == expected_shape == (512, 8, 512)
    with np.load(run / 'review_queue/packs' / f'{sid}_pack.npz', allow_pickle=False) as pack:
        np.testing.assert_allclose(surfaces[pack['bscan_index']], pack['surfaces'], rtol=0, atol=0)
    np.savez_compressed(providers / f'{sid}.npz', surfaces=surfaces, scan_id=np.array([sid]),
        source=np.array([job['source']['path']]), surface_names=names, cascade_version=version,
        retina_band=band, bscan_index=np.arange(512), prediction_checkpoint=np.array(job['checkpoint']['path']),
        prediction_checkpoint_sha256=np.array(job['checkpoint']['sha256']),
        unreliable_layers=np.array(summary['unreliable_layers']))
    shutil.copy2(base_path, queue / base_path.name)
    results.append(dict(scan_id=sid, shape=list(surfaces.shape), selected_rows_match=True, checkpoint=job['checkpoint']))
config_path = root / 'outputs/cnv_review_v1/settings.json'
config = json.loads(config_path.read_text()) if config_path.exists() else default_config()
if config_path.exists():
    shutil.copy2(config_path, out / 'previous_settings.json')
config['segmentations'] = str(queue)
config['auto_sources'] = [dict(name='Updated U-Net - review-36 update (experimental)', directory=str(providers))]
config['compare_latest_auto'] = True
atomic_json(config_path, config)
atomic_json(out / 'export_verification.json', results)
print(json.dumps(results, indent=2))
