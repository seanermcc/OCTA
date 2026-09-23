"""Immutable Model 1 suggestions; only the GUI creates annotation decisions."""
from common import *
from scipy import ndimage as ndi

def model_arrays(a):
    fp=a['model1_provenance'];verify(fp);doc=read(fp['path'])
    if doc['scan_id']!=a['scan_id'] or doc['source_identity']!=a['source_identity']:
        raise ValueError('Model 1 source identity mismatch')
    verify(doc['prediction'])
    with np.load(doc['prediction']['path'],allow_pickle=False) as z:
        if str(z['scan_id'])!=a['scan_id'] or str(z['axis_order'])!='B-scan,A-line':
            raise ValueError('Model 1 native grid mismatch')
        arrays={k:z[k] for k in ('filtered_mask','raw_mask','score')}
    if any(v.shape!=(512,512) for v in arrays.values()):raise ValueError('Wrong proposal shape')
    return arrays,doc

def seed_gui_drafts(store):
    if store.path.exists():return 0
    arrays,doc=model_arrays(store.acquisition)
    labels,n=ndi.label(arrays['filtered_mask'],structure=np.ones((3,3)))
    regions=[]
    for i in range(1,n+1):
        regions.append(dict(id=f'm1-{i:04d}',state='draft',runs=encode(labels==i),
            origin=dict(kind='automatic_model1_proposal',component=i,
                prediction=doc['prediction'],checkpoint=doc['checkpoint'],threshold=doc['threshold'],
                mask='filtered_mask',human_confirmed=False),created_at=now()))
    # In-memory starting state, no automatic acceptance and no annotation file write.
    store.state['regions']=regions
    store.context['proposal_initialization']=dict(model='v8 Model 1 conservative',
        prediction=doc['prediction'],components=n,at=now())
    return n

def prepare():
    preview=V8/'data/preview.json';cases=read(preview)['cases']
    assert len(cases)==30 and len({c['scan_id'] for c in cases})==30
    acquisitions=[];stats=[]
    for c in cases:
        a=dict(c['acquisition'],preview_role=c['role'],model1_training_exposure=c['training_exposure'],
            model1_provenance=fingerprint(V8/'predictions/model1'/(c['scan_id']+'.json')))
        arrays,doc=model_arrays(a);labels,n=ndi.label(arrays['filtered_mask'],structure=np.ones((3,3)))
        acquisitions.append(a);stats.append(dict(scan_id=a['scan_id'],role=c['role'],proposals=n,
            proposed_pixels=int(arrays['filtered_mask'].sum()),confirmed=False))
    path=HERE/'queue/queue.json'
    queue=dict(acquisitions=acquisitions,preview=fingerprint(preview),model='v8 Model 1 conservative',
        calibration_um_per_pixel=1460/512,calibration_status='approximate project lateral calibration')
    if path.exists() and read(path)!=queue:raise ValueError('Existing frozen correction queue differs')
    atomic(path,queue)
    atomic(HERE/'reports/setup.json',dict(acquisitions=30,proposals=sum(s['proposals'] for s in stats),
        cases=stats,annotation_files_created=0,gui_sources={f:fingerprint(V7/f) for f in ('viewer.py','loader.py','review_store.py','common.py')}))
    print(json.dumps(dict(acquisitions=30,proposals=sum(s['proposals'] for s in stats))))

if __name__=='__main__':prepare()
