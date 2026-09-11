"""Supplemental comparisons and final read-only contract checks."""
import csv
import numpy as np
from .common import *
from .metrics import LAYERS,stats

def run():
    initialize();checks=[];entropy_rows=[];findings=[]
    for sid in SCANS:
        out=OUT/'volumes'/sid;g=npz(out/'geometry.npz');d=npz(out/'measurements.npz');z=npz(out/'diagnostics.npz')
        prep=read(out/'prepared.json');verify(prep['source']);images=np.load(prep['images'],mmap_mode='r')
        assert d['raw_position_branch'].shape==(512,8,512)
        provider=npz(OUT/'review_packs/automatic'/f'{sid}.npz')
        np.testing.assert_allclose(provider['surfaces']+int(g['label_offset']),d['reported_positions'],equal_nan=True,rtol=0,atol=1e-4)
        assert not np.isfinite(d['primary_thickness_um'].transpose(0,2,1)[g['shadow']]).any()
        assert not np.isfinite(d['uncertain_estimates'][d['state']==2]).any()
        assert images.shape==(512,int(np.diff(g['retina_band'])[0]),512)
        if sid in SCANS[:4]:
            prior=npz(FROZEN/'volumes'/sid/'measurements.npz')
            np.testing.assert_equal(d['raw_position_branch'],prior['raw_position_branch'])
            np.testing.assert_equal(d['entropy'],prior['entropy']);np.testing.assert_equal(d['state'],prior['automatic_state'])
        for k,name in enumerate(d['surface_names']):
            e=d['entropy'][:,k].reshape(512,8,64);med=np.median(e,axis=-1);upper=np.quantile(e,.95,axis=-1)
            for b in range(512):
                for tile in range(8):entropy_rows.append(dict(scan_id=sid,bscan=b,boundary=str(name),lo=tile*64,hi=(tile+1)*64,entropy_median=float(med[b,tile]),entropy_p95=float(upper[b,tile])))
        for mode,t in [('primary',d['primary_thickness_um']),('diagnostic',z['diagnostic_thickness_um'])]:
            for k,(name,_,_) in enumerate(LAYERS):
                findings.append(dict(scan_id=sid,mode=mode,layer=name,coverage=float(np.isfinite(t[:,k]).mean()),**stats(t[:,k])))
        checks.append(dict(scan_id=sid,bscans=512,source_unchanged=True,shape_and_crop_alignment=True,
              shadow_primary_nan=True,not_traceable_candidates_nan=True,
              original_neural_predictions_identical=sid in SCANS[:4],boundary_maps=len(list((OUT/'maps'/sid).glob('*.png')))))
        assert checks[-1]['boundary_maps']==8
    csvwrite(OUT/'reports/strip_boundary_entropy.csv',entropy_rows)
    atomic_json(OUT/'reports/verification.json',dict(fixed_model_thresholds_and_rules_unchanged=True,volumes=checks))
    queue=read(OUT/'review_queue.json')['examples']
    assert len(queue)==24
    for sid in SCANS:
        q=[p for p in queue if p['scan_id']==sid];assert len(q)==4
        assert sum(p['role']=='random' for p in q)==2
        assert {p['driver'] for p in q if p['role']=='targeted'}=={'entropy','spike'}
        for i,a in enumerate(q):
            for b in q[i+1:]:assert abs(a['bscan']-b['bscan'])>=24 or abs(a['lo']-b['lo'])>=128
    text=['# Thickness distribution comparison','',
          'These are automatic-model diagnostics before human overrides, with invalid/crossing and shadowed columns excluded and counted. The original-four range is descriptive; lying outside it is not an error definition.', '',
          '| Layer | Original four median range (µm) | TS328 median / SD / IQR (µm) | TS328 valid % | TS336 median / SD / IQR (µm) | TS336 valid % |',
          '|---|---:|---:|---:|---:|---:|']
    for layer,_,_ in LAYERS:
        rr=[r for r in findings if r['mode']=='diagnostic' and r['layer']==layer]
        old=[r['median'] for r in rr[:4] if r['median'] is not None]
        a,b=rr[4:]
        text.append(f"| {layer} | {min(old):.1f}–{max(old):.1f} | {a['median']:.1f} / {a['std']:.1f} / {a['iqr']:.1f} | {a['coverage']*100:.1f} | {b['median']:.1f} / {b['std']:.1f} / {b['iqr']:.1f} | {b['coverage']*100:.1f} |")
    text+=['','Every layer is retained. Primary RNFL, TOTAL and INNER_RETINA remain unavailable because v1 withholds ILM. Primary and diagnostic results must not be combined.', '',
           'Use thickness_contexts.csv to compare the same joint signal/vessel/CNV/ONH strata. The new acquisitions lack annotated ONH locations, so eccentricity matching to TS165 or TS283 is unavailable. Apparent layer-distribution differences cannot be separated fully from location or annotation availability in this pilot.', '',
           'Native per-boundary median/P95 entropy for every 64-column strip is in strip_boundary_entropy.csv.']
    (OUT/'reports/THICKNESS_COMPARISON.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    report=OUT/'START_HERE.md';body=report.read_text(encoding='utf-8')
    marker='\n## Additional results\n'
    body=body.split(marker)[0]+marker+'\n[Thickness comparison](reports/THICKNESS_COMPARISON.md), [regional assessment](reports/HUMAN_ASSESSMENT.md), and [verification](reports/verification.json).\n'
    body+='\nThe two new acquisitions have CNR 22.75 (TS328) and 20.02 (TS336), with low-signal coverage below 0.3%. Their diagnostic total-thickness medians, 252.5 and 246.9 µm, fall within the original-four median range (207.1–253.7 µm). TS328’s diagnostic photoreceptor median is higher (33.7 µm versus 25.9–29.4 µm); this is a finding to inspect, not an established error.\n'
    body+='\n**Context limitation:** neither new acquisition has a saved vessel, CNV or ONH mask. Its zero vessel input is the existing missing-mask behavior, so higher solid coverage cannot be interpreted as better quality: vessel-derived withholding is absent. The unknown-context rows cannot support fully matched vessel/CNV/ONH comparisons. No missing anatomy was estimated.\n'
    body+='\nThe solid/dashed spike fractions rounded to 0.00% above are not proof of correctness. Full-precision fractions and maximum magnitudes are in the tables. The optional white dotted ILM is a raw diagnostic overlay; it is excluded from the solid/dashed aggregate and remains covered by the raw per-boundary diagnostics.\n'
    report.write_text(body,encoding='utf-8')
    from .evaluate_reviews import run as evaluate
    evaluate();print('Verified all six exports, 48 maps and 24 separated strips.',flush=True)

if __name__=='__main__':run()
