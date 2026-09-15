"""Read-only recovery of completed inputs, independent of all inference writers."""
from common import *
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor, CancelledError
from collections import OrderedDict
import threading
from cnv_review_v1.gui import QtCore
from review_store import ReviewStore
from dataset import automatic_thickness

KEYS=[f'{e}_{s}' for e in 'BC' for s in (267,268,269)]

def array_hash(a):
    a=np.ascontiguousarray(a)
    return hashlib.sha256(str((a.shape,a.dtype.str)).encode()+a.tobytes()).hexdigest()

def available_memory():
    try:
        import psutil
        return psutil.virtual_memory().available
    except ImportError:
        return 4*1024**3

def load_data(sid,cancel=lambda:False):
    def check():
        if cancel():raise CancelledError()
    check();rec=read(HERE/'records'/f'{sid}.json')
    if rec['status']!='completed':raise ValueError(rec.get('reason','Predictions not completed'))
    r=next(r for r in selected() if r['scan_id']==sid)
    vp=Path(r['upstream_volume']);meta=read(HERE/'inputs'/f'{sid}.json')
    assert meta['scan_id']==sid and meta['native_shape']==[512,512,1024]
    assert meta['axis_order']=='B-scan,A-line' and meta['octa_channel']=='frame_OCTAAvg'
    assert Path(meta['source']['path']).resolve()==Path(r['source']).resolve()
    verify(meta['geometry']);verify(meta['optical_cache']);check()
    g=npz(meta['geometry']['path']);lo,hi=map(int,g['retina_band']);offset=int(g['label_offset'])
    assert tuple(g['native_shape'])==(512,512,1024)
    assert offset==(1024-hi if bool(g['vitreous_high']) else lo)==meta['canonical_crop_offset']
    assert [lo,hi]==meta['retinal_crop_original_depth']
    assert bool(g['vitreous_high'])==bool(meta['orientation_fresh_detected'])
    if meta.get('new_acquisition_upstream'):
        # This reads existing processed data only. No RAW reconstruction or inference.
        from octa.volio import ProcessedVolume
        from octa.segment import detect_orientation
        from eight_surface.segment import prepare_bscan
        if available_memory()<2*1024**3:raise MemoryError('Not enough free memory to recover this native acquisition; close other large applications and retry.')
        verify(meta['source']);check()
        with ProcessedVolume(r['source']) as volume:
            assert volume.struct.shape==volume.angio.shape==(512,512,1024)
            full=volume.read_volume()
        check();high=bool(detect_orientation(full.mean((0,1))))
        assert high==bool(g['vitreous_high'])
        images=np.empty((512,hi-lo,512),dtype=np.float32)
        for b in range(512):
            check();images[b]=prepare_bscan(full[b],high)[offset:offset+hi-lo]
        del full
        assert array_hash(images)==meta['images_array_sha256']
    else:
        p=read(vp/'prepared.json');nm=read(vp/'neural_complete.json')
        assert nm['scan_id']==sid and nm['n_bscans']==512
        assert Path(nm['source']['path']).resolve()==Path(r['source']).resolve()
        assert nm['orientation_detected']==bool(g['vitreous_high'])
        for key,fp in zip(('position_checkpoint','state_checkpoint'),read(HERE/'inventory.json')['upstream']):
            assert nm[key]['sha256']==fp['sha256']
        images=np.load(vp/'images.npy',mmap_mode='r')
    assert images.shape==(512,hi-lo,512);check()
    if meta.get('regenerated_neural'):
        verify(meta['regenerated_neural']);a=npz(meta['regenerated_neural']['path'])
        rows,prob=a['rows'],a['probabilities']
        if 'vessel' in a:g['vessel']=a['vessel']
    else:
        with np.load(vp/'measurements.npz',allow_pickle=False) as a:
            rows,prob=a['raw_position_branch'],a['probabilities']
    check();optical=npz(meta['optical_cache']['path'])['optical']
    assert optical.shape==(2,512,512) and np.isfinite(optical).all()
    calibration=ROOT/'outputs/octa-seg/octa-seg_v1/calibration/deployment_vessels.json'
    thick,reasons,endpoints=automatic_thickness(rows,prob,g,read(calibration)['thresholds'],hi-lo)
    assert np.isnan(thick[:,g['shadow']]).all();check()
    refs=reference_arrays(sid);audit=rec['annotation_audit']
    uncertain=np.zeros((512,512),bool);removed=uncertain.copy()
    for fp in audit.get('sources',[]):
        check();verify(fp)
        if fp['path'].endswith('_regions.json'):
            source=read(fp['path'])
            if source.get('scan_id')==sid and source.get('native_shape')==[512,512] and Path(source['source_volume']).resolve()==Path(r['source']).resolve():
                for region in source['regions']:
                    if region.get('decision')=='rejected':removed|=decode(region['runs'])
                    elif region.get('category')=='Other' or not region.get('classification_complete') or region.get('decision')=='unreviewed':uncertain|=decode(region['runs'])
    scan=SimpleNamespace(scan_id=sid,native_shape=(512,512),source_volume=Path(r['source']),
        structural_enface=optical[0],octa=optical[1],octa_metadata=meta,octa_error=None,
        images=images,thickness=thick,endpoints=endpoints,surface_names=tuple(SURFACES),px_um=1.12,
        shadow=g['shadow'],manual_mask=refs['target'],metadata=dict(visit=r,reference_review=dict(sources=audit.get('sources',[]))),
        thickness_metadata=dict(revision=sha(HERE/'inputs'/f'{sid}.json'),correction_fingerprints={}),
        input_provenance=meta,annotation_audit=audit,reference_uncertain=uncertain,reference_removed=removed)
    # Prohibit accidental mutation of reusable native inputs by the UI.
    for value in vars(scan).values():
        if isinstance(value,np.ndarray):value.flags.writeable=False
    return scan

def load_scan(sid,model='B_267',review_directory=None):
    scan=load_data(sid)
    return scan,ReviewStore(review_directory or REVIEW/'regions',scan,model)

def memory_bytes(scan):
    # Count memmaps conservatively at full size; their pages may become resident.
    return sum(v.nbytes for v in vars(scan).values() if isinstance(v,np.ndarray))

class SampleCache:
    """One worker, current plus two next samples, bounded bytes and cancellable queue.

    Running disk reads cannot be interrupted safely; cancellation is checked between
    recovery stages and native B-scans, and obsolete results are discarded.
    """
    def __init__(self,loader=load_data,max_bytes=1536*1024**2):
        self.loader=loader;self.max_bytes=max_bytes;self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='cnv-read')
        self.lock=threading.RLock();self.cache=OrderedDict();self.jobs={};self.desired=[];self.closed=False
        self.stats=dict(loads=0,hits=0,cancelled=0,evictions=0,errors=[])

    def plan(self,sids):
        with self.lock:
            self.desired=list(dict.fromkeys(sids))[:3]
            for sid,(future,token) in list(self.jobs.items()):
                if sid not in self.desired:
                    token.set();future.cancel();self.jobs.pop(sid);self.stats['cancelled']+=1
            for sid in list(self.cache):
                if sid not in self.desired:self.cache.pop(sid);self.stats['evictions']+=1

    def request(self,sid,prefetch=False):
        with self.lock:
            if self.closed:raise RuntimeError('Cache closed')
            if sid in self.cache:
                from concurrent.futures import Future
                self.stats['hits']+=1;f=Future();f.set_result(self.cache[sid]);return f
            if sid in self.jobs:return self.jobs[sid][0]
            if prefetch and (available_memory()<2*1024**3 or sum(memory_bytes(s) for s in self.cache.values())>=self.max_bytes):return None
            token=threading.Event()
            def work():
                t=time.perf_counter()
                try:
                    scan=self.loader(sid,token.is_set)
                    with self.lock:
                        if token.is_set() or self.closed or sid not in self.desired:raise CancelledError()
                        self.stats['loads']+=1;self.stats['last_load_seconds']=time.perf_counter()-t
                        needed=memory_bytes(scan)
                        while self.cache and sum(memory_bytes(s) for s in self.cache.values())+needed>self.max_bytes:
                            victims=[k for k in self.cache if k!=self.desired[0]]
                            if not victims:break
                            self.cache.pop(victims[-1]);self.stats['evictions']+=1
                        if sum(memory_bytes(s) for s in self.cache.values())+needed<=self.max_bytes:self.cache[sid]=scan
                    return scan
                except Exception as exc:
                    if not isinstance(exc,CancelledError):self.stats['errors'].append(dict(scan=sid,error=str(exc)))
                    raise
                finally:
                    with self.lock:
                        if self.jobs.get(sid,(None,None))[1] is token:self.jobs.pop(sid,None)
            future=self.pool.submit(work);self.jobs[sid]=(future,token);return future

    def close(self):
        with self.lock:
            self.closed=True
            for future,token in self.jobs.values():token.set();future.cancel()
            self.jobs.clear();self.cache.clear()
        self.pool.shutdown(wait=False,cancel_futures=True)

# Compatibility names required by the retained canvas base; the new Window uses SampleCache.
class Loader(QtCore.QThread):
    loaded=QtCore.Signal(object);failed=QtCore.Signal(str)
    def __init__(self,sid,model='B_267'):super().__init__();self.sid=sid;self.model=model
    def run(self):
        try:self.loaded.emit(load_scan(self.sid,self.model))
        except Exception as exc:self.failed.emit(str(exc))
OctaLoader=Loader
