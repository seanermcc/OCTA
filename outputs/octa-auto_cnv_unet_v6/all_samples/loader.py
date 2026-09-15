from common import *
from types import SimpleNamespace
from cnv_review_v1.gui import QtCore
from review_store import ReviewStore
from batch import recover_inputs

def load_scan(sid,model='B_267',review_directory=None):
    rec=read(HERE/'records'/f'{sid}.json')
    if rec['status']!='completed':raise ValueError(rec.get('reason','Scan predictions pending'))
    r=next(r for r in selected() if r['scan_id']==sid)
    d,meta,images=recover_inputs(r,verify_all=False)
    refs=reference_arrays(sid);audit=rec['annotation_audit']
    uncertain=np.zeros((512,512),bool);removed=uncertain.copy()
    for fp in audit.get('sources',[]):
        verify(fp)
        if fp['path'].endswith('_regions.json'):
            source=read(fp['path'])
            if source.get('scan_id')==sid and source.get('native_shape')==[512,512] and Path(source['source_volume']).resolve()==Path(r['source']).resolve():
                for region in source['regions']:
                    if region.get('decision')=='rejected':removed|=decode(region['runs'])
                    elif region.get('category')=='Other' or not region.get('classification_complete') or region.get('decision')=='unreviewed':uncertain|=decode(region['runs'])
    scan=SimpleNamespace(scan_id=sid,native_shape=(512,512),source_volume=Path(r['source']),
        structural_enface=d['optical'][0],octa=d['optical'][1],octa_metadata=meta,octa_error=None,
        images=images,thickness=d['thickness_um'],endpoints=d['endpoints_crop_px'],surface_names=tuple(SURFACES),px_um=1.12,
        shadow=d['shadow'],manual_mask=refs['target'],maps=d,metadata=dict(visit=r,reference_review=dict(sources=audit.get('sources',[]))),
        thickness_metadata=dict(revision=sha(HERE/'inputs'/f'{sid}.json'),correction_fingerprints={}),
        input_provenance=meta,annotation_audit=audit,reference_uncertain=uncertain,reference_removed=removed)
    store=ReviewStore(review_directory or HERE/'review/regions',scan,model)
    return scan,store

class Loader(QtCore.QThread):
    loaded=QtCore.Signal(object);failed=QtCore.Signal(str)
    def __init__(self,sid,model='B_267'):super().__init__();self.sid=sid;self.model=model
    def run(self):
        try:self.loaded.emit(load_scan(self.sid,self.model))
        except Exception as e:self.failed.emit(f'{type(e).__name__}: {e}')

class OctaLoader(QtCore.QThread):
    loaded=QtCore.Signal(object);failed=QtCore.Signal(str)
    def __init__(self,sid):super().__init__();self.sid=sid
    def run(self):
        try:
            d=npz(HERE/'inputs'/f'{self.sid}.npz');self.loaded.emit((d['optical'][1],read(HERE/'inputs'/f'{self.sid}.json')))
        except Exception as e:self.failed.emit(str(e))
