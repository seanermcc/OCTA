"""Validate all generated comparisons against the saved source manifest."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from build import PROJECT, MODES, digest, paired, stats, L

out=PROJECT/'outputs/reviewer_comparison'
text=(out/'data.js').read_text(encoding='utf-8')
data=json.loads(text.removeprefix('window.COMPARISON = ').rstrip().removesuffix(';'))
assert len(data['cases']) == data['summary']['union']
checked=0
for source in data['provenance']['sources']:
    assert digest(source['path'])==source['sha256'], source['path']
    checked+=1
pools={mode:[] for mode in MODES}
stale=[]
for case in data['cases']:
    with Image.open(out/case['image']) as im:
        assert im.size==(case['width'],case['depth'])
    for who,r in case['reviewers'].items():
        p=Path(r['source_path']).parent.parent/'surface_labels'/(case['id']+'.npz')
        with np.load(p,allow_pickle=False) as z:
            assert np.isclose(float(z['px_um'].item()),1.12)
            # Compatibility surfaces are crop-relative; the journals are full canonical depth.
            expected=np.asarray(r['positions'],float)-case['offset']
            diff=np.nanmax(np.abs(z['surfaces'].astype(float)-expected))
            if diff>1e-3:stale.append(dict(case=case['id'],reviewer=who,max_px=float(diff)))
        assert np.asarray(r['positions']).shape==(8,case['width'])
        assert not np.any(np.asarray(r['approved']) & ~np.asarray(r['geometry']))
        if r['status']!='Confirmed':assert not np.any(r['approved'])
        journal=json.loads(Path(r['source_path']).read_text(encoding='utf-8'))
        lesion=L.empty(case['width'],case['depth'])
        for event in journal['events'][:journal['cursor']]:
            if event['action'] in L.ACTIONS:
                L.apply(lesion,event,case['offset'])
        for field,key in [('region','cnv_region'),('edge','cnv_edge'),
                          ('edge_state','cnv_edge_state'),('edge_unreliable','cnv_edge_unreliable')]:
            np.testing.assert_allclose(np.asarray(r['cnv'][field],float),lesion[key],equal_nan=True)
        hyper=r['hyper_ref']
        assert hyper['shape']==list(lesion['hyper_ref'].shape)
        decoded=np.zeros(case['depth']*case['width'],bool)
        for lo,hi in hyper['runs']:
            assert 0<=lo<hi<=decoded.size
            decoded[lo:hi]=True
        np.testing.assert_array_equal(decoded.reshape(hyper['shape']),lesion['hyper_ref'])
        assert hyper['pixels']==int(decoded.sum())
    if len(case['reviewers'])<2:
        assert not case['metrics']
        continue
    for mode in MODES:
        a,b=case['reviewers']['lead'],case['reviewers']['shichu']
        delta=paired(a,b,mode)
        q=stats(delta)
        assert q['n']==case['metrics'][mode]['n']
        if q['n']:
            assert np.isclose(q['mae_um'],case['metrics'][mode]['mae_um'],atol=1e-5)
        np.testing.assert_allclose(delta,-paired(b,a,mode),atol=1e-8,equal_nan=True)
        pools[mode].append(delta.ravel())
for mode in MODES:
    q=stats(np.concatenate(pools[mode]))
    assert q['n']==data['summary']['modes'][mode]['n']
    assert np.isclose(q['mae_um'],data['summary']['modes'][mode]['mae_um'],atol=1e-5)
report=dict(cases=len(data['cases']),matched=data['summary']['matched'],source_hashes_verified=checked,
            all_images_native_size=True,all_scopes_recomputed=True,reviewer_swap_invariance=True,
            missing_not_scored=True,unconfirmed_not_approved=True,
            cnv_replayed_from_each_saved_cursor=True,
            hyper_ref_replayed_from_each_saved_cursor=True,
            hyper_ref_reviews_with_paint={who:sum(bool(c['reviewers'].get(who,{}).get('hyper_ref',{}).get('pixels',0)) for c in data['cases']) for who in ['lead','shichu']},
            compatibility_geometry_differences=stale)
(out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
