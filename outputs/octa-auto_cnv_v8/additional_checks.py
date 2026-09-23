"""Audit coverage, exposure, source precedence and fixed-policy diagnostics."""
from common import *
from models import filter_mask
from collections import Counter
def run():
    m=read(HERE/'data/manifest.json');preview=read(HERE/'data/preview.json')['cases'];train={r['scan_id'] for r in m['records']}
    historical=read(V7/'reports/historical_labels.json')['records']
    historic_ids={r['scan_id'] for r in historical}
    assert not historic_ids.intersection(c['scan_id'] for c in preview if not c['training_exposure'])
    assert len({r['source_identity'] for r in m['records']})==len(m['records'])
    for r in m['records']:
        if r['version']=='v7':
            d=read(r['source']['path']);ids=[x['id'] for x in d['state']['regions']]
            assert len(set(ids))==len(ids)
        target=npz(r['target_file']['path'])
        if not r['audit']['complete']:assert np.array_equal(target['known'],target['target'])
        assert int(target['target'].sum())==r['positive_pixels']
    stats=read(HERE/'data/normalization_enface.json')
    assert set(stats['training_scan_ids'])==train
    count=Counter(c['acquisition']['animal'] for c in preview);assert len(count)==10 and set(count.values())=={3}
    impact=[]
    for r in m['records']:
        truth=npz(r['target_file']['path'])['target'];filtered,removed=filter_mask(truth)
        impact.append(dict(scan_id=r['scan_id'],training_positive_pixels=int(truth.sum()),hypothetical_suppressed_pixels=int((truth&~filtered['filtered_mask']).sum())))
    model1=read(HERE/'model1/complete.json');s=model1['sampling_counts']
    assert s['requested:positive']==6400 and s['requested:background']==3200 and s['requested:hard']==3200
    assert sum(v for k,v in s.items() if k.startswith('animal:'))==12800
    assert not any(k.removeprefix('scan:') not in train for k in s if k.startswith('scan:'))
    write(HERE/'verification/additional_checks.json',dict(passed=True,older_source_counts=dict(Counter(r['version'] for r in m['records'])),training_acquisitions=len(train),historical_comparison_disjoint=True,unique_native_acquisitions=True,partial_background_always_unknown=True,training_only_normalization=True,preview_per_animal=dict(count),model1_sampling_counts=s,display_policy_training_impact=impact))
    print(json.dumps(dict(passed=True,positive_training_pixels=sum(r['training_positive_pixels'] for r in impact),hypothetically_suppressed_pixels=sum(r['hypothetical_suppressed_pixels'] for r in impact),hard_fallback=s.get('hard_fallback',0),actual_hard=s.get('actual:hard',0),animal_counts={k:v for k,v in s.items() if k.startswith('animal:')})),flush=True)
if __name__=='__main__':run()
