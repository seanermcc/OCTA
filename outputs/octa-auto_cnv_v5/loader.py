"""Read-only native scan loading. Map endpoints also drive the B-scan lines."""
from common import *
from types import SimpleNamespace
from cnv_review_v1.gui import QtCore
from review_store import ReviewStore
from thickness import load_thickness
from octa_projection import projection

def load_scan(sid):
    a=npz(DATA/'scans'/sid/'maps.npz');meta=json.loads(str(a['metadata_json']))
    out=volume_path(sid)
    for name in ('geometry.npz','measurements.npz'):
        if meta['audit']['input_hashes'][str(out/name)]!=sha(out/name):raise ValueError('The saved segmentation changed. Reconcile its export before reusing these proposals.')
    values,endpoints,thickness_meta=load_thickness(sid)
    g=npz(out/'geometry.npz');images=np.load(out/'images.npy',mmap_mode='r')
    scan=SimpleNamespace(scan_id=sid,native_shape=tuple(a['enface'].shape),source_volume=Path(meta['visit']['source']),
        structural_enface=a['enface'],images=images,thickness=values,endpoints=endpoints,
        surface_names=tuple(a['surface_names']),px_um=1.12,shadow=g['shadow'],
        manual_mask=a['manual_cnv'],maps=a,metadata=meta,thickness_metadata=thickness_meta,
        octa=None,octa_metadata=None,octa_error=None)
    manual_path=ROOT/'outputs/cnv_labels'/f'{sid}_cnv.npz'
    if manual_path.exists():
        from eight_surface.cnv_labels import load_label
        manual=load_label(manual_path)
        if manual['scan_id']!=sid or tuple(manual['native_shape'])!=scan.native_shape or Path(manual['source_volume']).resolve()!=scan.source_volume.resolve():
            raise ValueError('Saved manual annotation does not match this native acquisition')
        scan.manual_mask=manual['cnv_mask'].copy()
        scan.metadata['reference_review']={'sources':[{'path':str(manual_path),'sha256':sha(manual_path)}]}
    seed=DATA/'proposals'/f'{sid}.npz'
    store=ReviewStore(HERE/'review/regions',scan,a['core'],str(seed))
    return scan,store

class Loader(QtCore.QThread):
    loaded=QtCore.Signal(object);failed=QtCore.Signal(str)
    def __init__(self,sid):super().__init__();self.sid=sid
    def run(self):
        try:self.loaded.emit(load_scan(self.sid))
        except Exception as exc:self.failed.emit(f'{type(exc).__name__}: {exc}')

class OctaLoader(QtCore.QThread):
    loaded=QtCore.Signal(object);failed=QtCore.Signal(str)
    def __init__(self,sid):super().__init__();self.sid=sid
    def run(self):
        try:self.loaded.emit(projection(self.sid))
        except Exception as exc:self.failed.emit(str(exc))
