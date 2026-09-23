"""Export one current target per acquisition, with explicit pending/excluded states."""
from common import *
from review_store import Store, targets, completion_kind
from collections import Counter

def run(directory=None, output=None, synthetic=False):
    directory=Path(directory or HERE/'review/regions')
    output=Path(output or HERE/'dataset')
    if synthetic and not output.resolve().is_relative_to(HERE/'verification'):
        raise ValueError('Synthetic exports must stay in verification')
    queue=read(HERE/'queue/queue.json');cohort=read(HERE/'queue/cohort.json')
    verify(cohort['acceptance']);acquisitions={a['scan_id']:a for a in queue['acquisitions']}
    for path,h in queue['source_hashes'].items():
        if sha(path)!=h:raise ValueError('Frozen source changed; reconcile before exporting: '+path)
    rows=[]
    for base in cohort['records']:
        r=dict(base);sid=r['scan_id']
        if r['status']=='correction_pending':
            a=acquisitions[sid]; path=directory/(sid+'.json')
            if path.exists():
                store=Store(a,directory,synthetic=synthetic);kind=completion_kind(store.state,store.shape)
                r.update(correction=fingerprint(path),revision=store.revision)
                if kind in ('positive','negative'):
                    p,b,ig,_,_=targets(store.state,store.shape,True)
                    instances=np.array([decode(x['runs'])&~ig for x in store.state['regions'] if x['state']=='kept' and (decode(x['runs'])&~ig).any()],bool)
                    if not len(instances):instances=np.zeros((0,512,512),bool)
                    out=destination(output/'targets'/(sid+'_'+r['correction']['sha256'][:16]+'.npz'))
                    if not out.exists():
                        temp=out.with_suffix('.tmp')
                        with temp.open('wb') as f:np.savez_compressed(f,target=p,known=p|b,ignored=ig,instances=instances,
                            scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'))
                        os.replace(temp,out)
                    r.update(status='confirmed_'+kind,targets=fingerprint(out),acceptance='Whole-image confirmation in final correction GUI')
                elif kind=='deferred':r.update(status='excluded_deferred',reason=store.state['defer_reason'])
                else:r['status']='correction_pending'
                verify(r['correction'])
        if 'targets' in r:
            verify(r['targets'])
            with np.load(r['targets']['path'],allow_pickle=False) as z:
                assert str(z['scan_id'])==sid and str(z['axis_order'])=='B-scan,A-line'
                p=z['target'];k=z['known'];ig=z['ignored'];instances=z['instances']
                assert p.shape==k.shape==ig.shape==(512,512)
                assert np.array_equal(k,~ig) and not (p&ig).any() and np.array_equal(instances.any(0),p)
                assert bool(p.any())==(r['status']=='confirmed_positive')
                r.update(positive_pixels=int(p.sum()),ignored_pixels=int(ig.sum()),regions=len(instances))
        rows.append(r)
    counts=dict(Counter(r['status'] for r in rows));pending=counts.get('correction_pending',0)
    assert len(rows)==len({r['source_identity'] for r in rows})==324
    summary=dict(at=now(),counts=counts,total_acquisitions=324,remaining_corrections=pending,
        assessable_dataset_complete=pending==0,all_324_have_definitive_labels=all(r['status'].startswith('confirmed_') for r in rows),
        synthetic=synthetic,policy='One record per acquisition. Train only from confirmed records and their target paths; ignored pixels and excluded images are not negatives. Source training exposure remains part of provenance; this is not an independent test set.')
    manifest=dict(schema='cnv-final-dataset-v1',summary=summary,acceptance=cohort['acceptance'],records=rows)
    atomic(output/'manifest.json',manifest);atomic(output/'summary.json',summary)
    return summary

if __name__=='__main__':print(json.dumps(run(),indent=2))
