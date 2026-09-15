"""Release integrity checks; incomplete runs are reported without promotion."""
import io,zipfile
import numpy as np
from PIL import Image
from common import *
from network import native_prob,resolved_masks

def main(require_complete=True):
    audit=read_json(HERE/'audit_manifest.json');inventory=read_json(HERE/'inventory.json');protocol=read_json(HERE/'protocol.json')
    assert protocol['training_code_hashes']==source_code_hash()
    assert digest(HERE/'audit_manifest.json')==protocol['audit_sha256']
    assert digest(HERE/'inventory.json')==audit['inventory_sha256']
    assert digest(BATCH/'manifest.json')==audit['frozen_manifest_sha256']
    archive=HERE/'data/source_annotations_snapshot.zip';assert digest(archive)==audit['snapshot_sha256']
    with zipfile.ZipFile(archive) as zf:
        for row in audit['annotations']:
            blob=zf.read(Path(row['source_path']).name)
            assert hashlib.sha256(blob).hexdigest()==row['source_sha256']
            assert digest(HERE/row['supervision_file'])==row['supervision_sha256']
            with np.load(HERE/row['supervision_file'],allow_pickle=False) as s:
                assert not (s['positive']&s['negative']).any()
                assert np.array_equal(s['ignored'],~(s['positive']|s['negative']))
                if row['excluded']:assert s['ignored'].all()
    annotation_by_sid={r['scan_id']:r for r in audit['annotations']}
    ph=digest(HERE/'protocol.json')
    for f in protocol['folds']:
        groups={k:{annotation_by_sid[s]['animal'] for s in ids} for k,ids in f['scans'].items()}
        assert not groups['train']&groups['evaluation'] and not groups['train']&groups['calibration'] and not groups['calibration']&groups['evaluation']
        assert groups['evaluation']=={f['evaluation_animal']}
        assert groups['calibration']=={f['calibration_animal']}
        trained=read_json(HERE/'models'/f['name']/'trained.json')
        assert trained['protocol_sha256']==ph and trained['checkpoint_sha256']==digest(HERE/'models'/f['name']/'best.pt')
        result=read_json(HERE/'evaluation'/f'{f["name"]}.json')
        assert result['checkpoint_sha256']==trained['checkpoint_sha256']
        for row in result['scans']:
            assert digest(HERE/row['prediction_file'])==row['prediction_sha256']
            with np.load(HERE/row['prediction_file'],allow_pickle=False) as z:
                mask=resolved_masks(native_prob(z['probability_model_grid']),result['thresholds'],result['min_onh_area'])
                assert np.array_equal(mask[0],z['vessel_mask']) and np.array_equal(mask[1],z['onh_mask'])
                assert not (z['vessel_mask']&z['onh_mask']).any()
    final=read_json(HERE/'final_settings.json');modelhash=digest(HERE/'models/all_eligible/best.pt')
    complete=excluded=failed=missing=0
    for i,row in enumerate(inventory):
        sid=row['scan_id'];rp=HERE/'records'/f'{sid}.json'
        assert digest(row['proposal_path'])==row['proposal_sha256'],'Frozen proposal changed'
        assert digest(row['projection_path'])==row['projection_sha256'],'Frozen projection changed'
        if row['excluded']:
            excluded+=1;assert not (HERE/'predictions'/f'{sid}.npz').exists()
            if rp.exists():assert read_json(rp)['status']=='excluded'
            continue
        if not rp.exists():missing+=1;continue
        r=read_json(rp)
        if r['status']!='complete':failed+=1;continue
        pp=HERE/r['prediction_file'];assert digest(pp)==r['prediction_sha256']
        assert r['identity']['model_sha256']==modelhash
        with np.load(pp,allow_pickle=False) as z:
            assert str(scalar(z,'scan_id'))==sid and str(scalar(z,'source_volume'))==row['source_volume']
            assert z['vessel_mask'].shape==tuple(row['native_shape']) and z['vessel_mask'].dtype==bool
            assert z['onh_mask'].shape==tuple(row['native_shape']) and z['onh_mask'].dtype==bool
            assert not (z['vessel_mask']&z['onh_mask']).any()
            assert not bool(scalar(z,'human_corrected')) and not bool(scalar(z,'independent_evaluation'))
            assert np.isfinite(z['probability_model_grid']).all()
            mask=resolved_masks(native_prob(z['probability_model_grid']),final['thresholds'],final['min_onh_area'])
            assert np.array_equal(mask[0],z['vessel_mask']) and np.array_equal(mask[1],z['onh_mask'])
        complete+=1
    gallery_ok=False
    if (HERE/'gallery_inventory.json').exists() and (HERE/'index.html').exists():
        gallery=read_json(HERE/'gallery_inventory.json')
        assert {r['scan_id'] for r in gallery}=={r['scan_id'] for r in inventory}
        for r in gallery:
            with Image.open(HERE/r['original']) as im:assert im.size==(512,512);im.verify()
            for mode in ['frozen','final','human','held']:
                if r[mode]:
                    for path in r[mode].values():
                        with Image.open(HERE/path) as im:assert im.size==(512,512);im.verify()
        gallery_ok=True
    result=dict(status='complete' if complete+excluded==314 and not failed and not missing and gallery_ok else 'incomplete',verified_at=now(),
                complete_predictions=complete,excluded_scans=excluded,failed_records=failed,missing_records=missing,total=314,gallery_verified=gallery_ok,
                source_projections_and_frozen_proposals_unchanged=True,annotation_snapshot_verified=True,animal_partition_integrity=True,
                evaluation_predictions_reproduced=True,native_prediction_masks_reproduced=True,overlap_pixels=0,
                model_sha256=modelhash,protocol_sha256=ph,remaining_free_bytes=shutil.disk_usage(HERE).free,
                limitation='Integrity verification is not scientific validation. ONH fails held-out absence specificity; vessel accuracy is conditional on sparse edited support.')
    write_json(HERE/'FINAL_VERIFIED.json',result)
    print(json.dumps(result,indent=2),flush=True)
    if require_complete and result['status']!='complete':raise RuntimeError('Release incomplete; see FINAL_VERIFIED.json')
    return result

if __name__=='__main__':
    import sys
    main('--partial' not in sys.argv)
