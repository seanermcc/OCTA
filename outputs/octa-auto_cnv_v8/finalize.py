"""Deliver only after both final checkpoints, all 30 pairs and native navigation pass."""
from common import *
from predict import summarize
from scipy import ndimage as ndi
import torch,platform,csv

def run():
    summarize();manifest=read(HERE/'data/manifest.json');preview=read(HERE/'data/preview.json');results=read(HERE/'reports/comparison.json')
    assert all(read(HERE/f'verification/{name}.json')['passed'] for name in ('contracts','sanity','additional_checks','structural_isolation'))
    models=[read(HERE/f'model{i}/complete.json') for i in (1,2)]
    for m in models:
        assert m['completed_epochs']==100 and m['optimizer_steps']==3200;verify(m['checkpoint'])
        assert m['config']['manifest_sha256']==sha(HERE/'data/manifest.json')
        assert m['config']['model_code_sha256']==sha(HERE/'models.py')
        structural=m['config']['model_id']==2
        assert m['config']['sampler_code_sha256']==sha(HERE/('sampling_structural.py' if structural else 'sampling.py'))
        assert m['config']['training_code_sha256']==sha(HERE/('train_structural.py' if structural else 'train.py'))
        stats='normalization_structural.json' if structural else 'normalization_enface.json'
        assert m['config']['normalization_sha256']==sha(HERE/'data'/stats)
        counts=m['sampling_counts'];assert counts['actual:positive']==6400
        assert counts['actual:background']==(6400 if structural else 3200)
        if not structural:assert counts['actual:hard']==3200
        assert sum(v for k,v in counts.items() if k.startswith('animal:'))==12800
    checks=[];allfps=[]
    inputs=read(HERE/'data/inputs.json')['cases']
    assert len(inputs)==87 and len({r['source_full']['sha256'] for r in inputs})==87
    for c in preview['cases']:
        sid=c['scan_id'];cache=HERE/'cache'/sid;cm=read(cache/'manifest.json')
        assert cm['scan_id']==sid and cm['native_shape']==[512,1024,512] and cm['structural_enface_max_error_db']<.001
        vol=np.load(cache/'structural.npy',mmap_mode='r');assert vol.shape==(512,1024,512)
        assert all(np.isfinite(vol[r]).all() for r in (0,256,511))
        for model in (1,2):
            p=HERE/f'predictions/model{model}'/(sid+'.npz');d=npz(p);meta=read(p.with_suffix('.json'));verify(meta['prediction']);allfps.append(meta['prediction'])
            assert meta['checkpoint']['sha256']==models[model-1]['checkpoint']['sha256']
            assert meta['source_identity']==c['acquisition']['source_identity'] and meta['role']==c['role']
            assert str(d['scan_id'])==sid and d['score'].shape==(512,512) and np.isfinite(d['score']).all()
            assert d['unknown_mask'].shape==(512,512)
            assert np.array_equal(np.isnan(d['unknown_score']),~d['unknown_mask'])
            assert np.array_equal(d['unknown_score'][d['unknown_mask']],d['score'][d['unknown_mask']])
            if model==1:
                assert np.array_equal(d['raw_mask'],d['filtered_mask']|(d['removal_reason']>0))
            else:assert np.array_equal(d['raw_mask'],d['score']>=.5)
        v6=read(cache/'v6_provenance.json');assert v6['scan_id']==sid;assert sha(cache/'v6.npz')==v6['prediction']['sha256']
        unknown_file=HERE/'predictions/frozen_v6'/(sid+'_unknown.npz');unknown=npz(unknown_file)
        assert np.array_equal(unknown['unknown_mask'],d['unknown_mask'])
        assert np.array_equal(np.isnan(unknown['unknown_score']),~unknown['unknown_mask'])
        allfps.append(fingerprint(unknown_file))
        checks.append(dict(scan_id=sid,identity_grid_orientation=True,full_depth_navigation_rows=[0,256,511],both_predictions=True,frozen_v6=True,training_exposure=c['training_exposure']))
    for fp in manifest['annotation_sources']:verify(fp)
    for record in manifest['records']:verify(record['target_file'])
    for model in (1,2):
        predicted=sum(r[f'model{model}']['raw_pixels'] for r in results if r['role']=='training/reference')
        if predicted==0:raise RuntimeError(f'Model {model} has no foreground on any training reference; stop for review without changing fixed thresholds')
        if all(r[f'model{model}']['raw_pixels']==512*512 for r in results if r['role']=='training/reference'):
            raise RuntimeError(f'Model {model} predicts the entire field on every training reference; stop for review')
    preservation=read(HERE/'verification/preservation_after.json');assert preservation['unchanged']
    write(HERE/'verification/comparison_checks.json',dict(passed=True,cases=checks))
    write(HERE/'environment.json',dict(python=sys.version,torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),platform=platform.platform()))
    rows=[]
    for r in results:
        for key,values in r.get('training_case_comparisons',{}).items():rows.append(dict(scan_id=r['scan_id'],model=key,**values))
    with dest(HERE/'reports/training_case_comparisons.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    impact=read(HERE/'reports/display_policy_training_impact.json')['cases'];positive=sum(r['training_positive_pixels'] for r in impact);removed=sum(r['pixels_hypothetically_removed'] for r in impact)
    from collections import Counter
    sources=Counter(r['version'] for r in manifest['records'])
    logs={i:[json.loads(line) for line in (HERE/f'model{i}/training.jsonl').read_text().splitlines()] for i in (1,2)}
    for entries in logs.values():
        assert [e['epoch'] for e in entries]==list(range(1,101))
        assert all(np.isfinite(e['mean_fit_loss']) for e in entries)
    lines=[
        '# CNV v8 exploratory comparison',
        '',
        'Open `OPEN_OCTA_AUTO_CNV_V8.cmd` for the read-only, shared 30-acquisition viewer. This release predicts native en-face CNV footprints, not axial lesion volumes.',
        '',
        '**Scope:** 10 training/reference acquisitions and 20 acquisitions excluded from fitting and historical CNV-label sources. All ten non-WT animals have training exposure. There is no cross-validation, held-out validation study, cohort-wide new inference, improved-accuracy claim, or new-animal generalization claim.',
        '',
        f'Frozen supervision: {len(manifest["records"])} native acquisitions; selected source counts {dict(sources)}. The v7 contribution is 30 confirmed positives and seven confirmed negatives; four deferred acquisitions block fallback and are excluded. Two v7 Unsure areas remain unknown. Older incomplete fields provide confirmed positive pixels only. Source documents, hashes, revisions, eye, animal and visit are retained in data/manifest.json and data/sources/.',
        '',
        'Precedence selects one source per acquisition: valid v7 > valid v5 > v4 > v3 > reviewed original. V7 draft/deferred records block older fallback. Disagreements are not silently unioned. V6 predictions and ratings never supply target labels. Actual sampling chooses animals uniformly, then uniformly among acquisitions eligible for the requested patch category; each model complete.json includes realized per-animal and per-acquisition counts.',
        '',
        'The historical v6 release trained A/B/C configurations at seeds 267/268/269 using within-TS267 visit partitions and validation-selected checkpoints/thresholds. V8 uses the frozen C/267 output as comparison context and trains two fresh models at seed 267 on the expanded manual dataset. C/267 is the requested context, not a best-seed claim.',
        '',
        '| Property | Frozen v6 | V8 Model 1 | V8 Model 2 |',
        '|---|---|---|---|',
        '| Training evidence | Nine labeled training acquisitions, all TS267; visit-based validation/checkpoint selection | Expanded multi-animal audited manual evidence, including v7 whole-field confirmations | Same audited evidence and animal balancing |',
        '| Input | C: structural OCT, actual OCTA, automatic availability/shadow and thickness | Same 19-channel C recipe; fresh weights | Five adjacent native structural B-scans only; fresh weights |',
        '| Network | Compact U-Net 16/32/64/128/256, GroupNorm | Same compact U-Net | Distinct four-stage 16/32/64/128 CNN, GroupNorm, SiLU, stagewise axial attention pooling and 1D head |',
        '| Selection | Validation-selected checkpoint and threshold | Scheduled epoch 100; provisional threshold 0.70 | Scheduled epoch 100; threshold 0.50 |',
        '| Display | Frozen C/267 context | One-pixel disk opening, then remove 8-connected components below 64 pixels | No component size/shape filter |',
        '',
        'Both models used seed 267, AdamW (learning rate 0.001, weight decay 0.0001), 100 epochs, 32 optimizer steps per epoch and effective batch size four. Mixed precision uses microbatch one and four-step accumulation. Checkpoints retain optimizer, scaler and Python/NumPy/PyTorch/CUDA/sampler RNG states. The final scheduled checkpoint is used; there was no early stopping or preview-based threshold tuning.',
        '',
        'Model 1 uses masked BCE with positive weight 1 and negative weight 2, plus 0.5 masked Dice on positive patches. Requested patch proportions are 50% positive, 25% ordinary reviewed background and 25% frozen-v6 difficult reviewed background. Difficult patches contain no confirmed positives; unavailable difficult pools fall back to ordinary background. V6 supplies sampling locations only.',
        '',
        'Model 2 uses masked BCE plus masked Dice, equal positive/background patch sampling, lateral flips, neighbor-order reversal and modest intensity changes. No axial flips or rotations are augmentations. Canonical orientation comes from established detect_orientation/prepare_bscan functions. Full depth and original axial resolution are retained; no RPE flattening or layer-based crop is applied. Its input tensors contain no en-face projections, OCTA, thickness, retinal surfaces, v6 predictions, or handcrafted candidates.',
        '',
        'Automatic measurements retain NaNs. Model 1 alone fills unavailable normalized thickness with neutral zero and supplies availability channels. Exclusion masks affect the loss only. Both normalizations were fitted only to training inputs; structural normalization uses a fixed regular subsample of full-depth training volumes.',
        '',
        f'The fixed Model 1 display policy would remove {removed:,} of {positive:,} known positive training pixels ({removed/max(1,positive):.2%}) if applied to those footprints. This is a diagnostic: human targets were never filtered. Per-acquisition effects are in reports/display_policy_training_impact.json. Legitimate small or irregular lesions can be suppressed. Unusual shape alone is not proof of a false detection. Scores, pre-filter threshold masks, removed-pixel reason maps and removed components remain available.',
        '',
        'The intended structural evidence includes RPE disruption/displacement, nearby hyperreflective dots and continuity across B-scans. These are learned only through manual footprint supervision; no separate feature annotations exist. No independently validated RPE-disruption or dot detector is claimed. Attention is an explanatory aid, not axial segmentation or proof of reasoning.',
        '',
        f'Fit diagnostics only: Model 1 mean patch loss changed from {logs[1][0]["mean_fit_loss"]:.4f} to {logs[1][-1]["mean_fit_loss"]:.4f}; Model 2 from {logs[2][0]["mean_fit_loss"]:.4f} to {logs[2][-1]["mean_fit_loss"]:.4f}. These values are not validation metrics or directly comparable across loss definitions.',
        '',
        'Training-case Dice/IoU, missed/extra components and false-positive area are recorded for the ten reference acquisitions in reports/training_case_comparisons.csv and the viewer. Scoring is restricted to reviewed coverage. Component matching uses 8-connectivity and any reviewed-pixel overlap; it does not adjudicate biological lesion identity. The twenty unlabeled acquisitions have prediction descriptions and optional reviewer observations only, never accuracy metrics.',
        '',
        'The viewer links native B-scan navigation to all footprints and lateral bands. Manual truth is read-only. Ignored areas are hatched as unknown; predictions inside them are retained in unknown_score arrays. Browser-local comparison notes are separate and can be exported as JSON; they do not change labels or trigger retraining.',
        '',
        'Acceptance evidence: verification/contracts.json, sanity.json, comparison_checks.json, preservation_after.json and viewer_checks.json. All old CNV release files were checked for unchanged size/mtime; old text/code/original annotations and consumed prediction/checkpoint inputs additionally have cryptographic checks. Each consumed processed source has a full SHA256 in its native cache manifest, in addition to inherited sampled source identity. New cache and predictions live only in v8; no RAW reconstruction occurred.',
        '',
        'Next decision belongs to human review: revise a model, collect feature-specific B-scan labels, or begin formal animal-grouped validation. This release stops at the shared comparison set.'
    ]
    overview=['', 'Training-case comparison summary: arithmetic means over the ten training/reference acquisitions only. These are descriptive fit comparisons, not validation results.', '', '| Footprint | Mean Dice | Mean extra components | Mean false-positive pixels in reviewed coverage |', '|---|---:|---:|---:|']
    for key in ('v6','model1_raw','model1_filtered','model2'):
        values=[r['training_case_comparisons'][key] for r in results if 'training_case_comparisons' in r]
        assert len(values)==10
        overview.append(f'| {key} | {np.mean([v["dice"] for v in values]):.3f} | {np.mean([v["extra_components"] for v in values]):.1f} | {np.mean([v["false_positive_area_pixels"] for v in values]):.1f} |')
    overview += ['', 'The structural model produces many additional fragments within reviewed training coverage at its fixed 0.50 threshold. This is a material limitation of this initial fit and a priority for human review. Its raw behavior is preserved; these observations did not alter training, thresholds or postprocessing. The twenty unlabeled acquisitions are excluded from this table and have no accuracy scores.', '']
    lines[-2:-2]=overview
    dest(HERE/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    write(HERE/'artifact_manifest.json',dict(predictions=allfps,models=models,dataset=fingerprint(HERE/'data/manifest.json'),preview=fingerprint(HERE/'data/preview.json')))
    write(HERE/'source_manifest.json',[fingerprint(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.html','.cmd')])
    write(HERE/'upstream_code_provenance.json',[fingerprint(p) for p in [ROOT/'outputs/octa-auto_cnv_unet_v6/model.py',ROOT/'outputs/octa-auto_cnv_unet_v6/dataset.py',ROOT/'code/octa/volio.py',ROOT/'code/octa/segment.py',ROOT/'code/eight_surface/segment.py']])
    write(HERE/'COMPUTE_COMPLETE.json',dict(models=2,epochs_each=100,optimizer_steps_each=3200,comparison_cases=30,training_references=10,unlabeled_acquisitions=20,viewer_verification_required=True))
    progress('Both models and frozen comparison computed; viewer QA pending')
if __name__=='__main__':run()
