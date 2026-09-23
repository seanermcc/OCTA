"""Native optical provider; only cache writes are v7 destinations."""
from common import *
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import threading

def arrays(path):
    with np.load(path,allow_pickle=False) as z:return {k:z[k] for k in z.files}

def load_scan(acquisition):
    a=acquisition;verify(a['input_manifest']);meta=read(a['input_manifest']['path'])
    if meta['scan_id']!=a['scan_id'] or Path(meta['source']['path']).resolve()!=Path(a['source']).resolve():raise ValueError('Provider identity mismatch')
    if meta['native_shape']!=[512,512,1024] or meta['axis_order']!='B-scan,A-line' or meta['octa_channel']!='frame_OCTAAvg':raise ValueError('Provider native grid/channel mismatch')
    verify(meta['source']);verify(meta['geometry']);verify(meta['optical_cache'])
    g=arrays(meta['geometry']['path']);lo,hi=map(int,g['retina_band']);offset=int(g['label_offset']);high=bool(g['vitreous_high'])
    if offset!=(1024-hi if high else lo) or high!=bool(meta['orientation_fresh_detected']) or offset!=meta['canonical_crop_offset']:raise ValueError('Orientation/crop mismatch')
    if [lo,hi]!=meta['retinal_crop_original_depth']:raise ValueError('Retinal crop mismatch')
    if meta.get('new_acquisition_upstream'):
        cache=HERE/'cache/native'/(a['scan_id']+'.npy');side=cache.with_suffix('.json')
        old_cache=V7/'cache/native'/(a['scan_id']+'.npy')
        if old_cache.exists() and old_cache.with_suffix('.json').exists():
            old_meta=read(old_cache.with_suffix('.json'))
            if old_meta['input_manifest_sha256']==a['input_manifest']['sha256']:
                cache=old_cache;side=cache.with_suffix('.json')
        if cache.exists() and side.exists() and read(side)['input_manifest_sha256']==a['input_manifest']['sha256']:
            verify(read(side)['images']);images=np.load(cache,mmap_mode='r')
        else:
            # Established read/preparation functions only; no upstream writer imports.
            sys.path.insert(0,str(ROOT/'code'))
            from octa.volio import ProcessedVolume
            from octa.segment import detect_orientation
            from eight_surface.segment import prepare_bscan
            with ProcessedVolume(a['source']) as volume:full=volume.read_volume()
            detected=bool(detect_orientation(full.mean((0,1))))
            if detected!=high:raise ValueError('Fresh orientation disagrees with provider')
            images=np.empty((512,hi-lo,512),np.float32)
            for b in range(512):images[b]=prepare_bscan(full[b],detected)[offset:offset+hi-lo]
            del full
            array_sha=hashlib.sha256(str((images.shape,images.dtype.str)).encode()+images.tobytes()).hexdigest()
            if array_sha!=meta['images_array_sha256']:raise ValueError('Recovered images differ from frozen input')
            destination(cache);tmp=cache.with_name(cache.name+'.'+uuid.uuid4().hex+'.tmp')
            try:
                with tmp.open('wb') as f:np.save(f,images);f.flush();os.fsync(f.fileno())
                os.replace(tmp,cache)
            finally:tmp.unlink(missing_ok=True)
            atomic(side,dict(images=fingerprint(cache),input_manifest_sha256=a['input_manifest']['sha256'],orientation_fresh_detected=detected))
            images=np.load(cache,mmap_mode='r')
    else:
        verify(meta['images']);images=np.load(meta['images']['path'],mmap_mode='r')
    if images.shape!=(512,hi-lo,512):raise ValueError('Native structural grid mismatch')
    optical=arrays(meta['optical_cache']['path'])['optical']
    if optical.shape!=(2,512,512) or not np.isfinite(optical).all():raise ValueError('Invalid optical provider')
    # Compare actual memmap projection to frozen structural en face, not just dimensions.
    err=float(np.max(np.abs(images.mean(axis=1)-optical[0])))
    if err>0.001:raise ValueError(f'Native image/en-face disagreement {err:g} dB')
    return SimpleNamespace(acquisition=a,images=images,structural=optical[0],octa=optical[1],metadata=meta,
        alignment_max_error_db=err,loaded_at=now())

def context_overlays(a,kind):
    sid=a['scan_id'];result=[]
    if kind=='prediction':
        from proposals import model_arrays
        z,doc=model_arrays(a)
        return [dict(mask=z['raw_mask'].astype(bool),color='#e3bc57',label='Model 1 before filtering',
            source=dict(kind='model1_raw_reference',record=doc))]
    if kind=='legacy_prediction':
        path=V6/'predictions/provenance'/(sid+'.json');doc=read(path)['models']['C_267']
        if doc['scan_id']!=sid or doc['native_shape']!=[512,512] or doc['axis_order']!='B-scan,A-line':raise ValueError('Prediction provenance grid/identity mismatch')
        verify(doc['prediction'])
        # Native mask is immutable; provenance includes model, threshold and checkpoint.
        p=V6/'predictions/C_267'/(sid+'.npz');z=arrays(p)
        if Path(doc['prediction']['path']).resolve()!=p.resolve() or str(z['scan_id'])!=sid or str(z['axis_order'])!='B-scan,A-line':raise ValueError('Prediction array identity mismatch')
        if str(z['checkpoint_sha256'])!=doc['checkpoint']['sha256']:raise ValueError('Prediction checkpoint mismatch')
        mask=z['mask'].astype(bool)
        if mask.shape!=(512,512):raise ValueError('Prediction shape mismatch')
        result.append(dict(mask=mask,color='#e3bc57',label='Unreviewed v6 C / seed 267',
            source=dict(kind=kind,path=str(p),sha256=sha(p),provenance=fingerprint(path),model='C_267',record=doc)))
    else:
        history=read(V7/'reports/historical_labels.json')['records']
        matching=[r for r in history if r['scan_id']==sid and r['identity_matches']]
        ranked=sorted([r for r in matching if r['version'] in ('v5','v4','v3','original')],key=lambda r:['v5','v4','v3','original'].index(r['version']))
        if not ranked:return result
        h=ranked[0];verify(h['source']);src=dict(kind='historical',version=h['version'],revision=h.get('revision'),**h['source'])
        if h['version']=='original':
            z=arrays(h['source']['path']);mask=z['cnv_mask'].astype(bool)
            # Later explicit classifications can exclude inherited original outlines.
            for review in matching:
                if review['version']=='original_classification':
                    for r in review.get('regions',[]):
                        if r.get('classification_complete') and r.get('category') in ('Normal','Other'):mask &= ~decode(r['runs'])
            result.append(dict(mask=mask,color='#46dbea',label='Historical original footprint (partial)',source=src))
        else:
            for r in h['regions']:
                if r.get('decision')=='rejected':continue
                uncertain=r.get('category')=='Other' or r.get('decision')!='approved' or not r.get('classification_complete')
                if r.get('category')=='Normal' and r.get('classification_complete'):continue
                result.append(dict(mask=decode(r['runs']),color='#b4a1df' if uncertain else '#46dbea',
                    label='Historical '+h['version']+(' unsure/draft' if uncertain else ' CNV'),source=dict(src,region_id=r['id'])))
    return result

class Cache:
    """One reader; current + next at most 1.5 GiB; no annotation access."""
    def __init__(self,loader=load_scan,max_bytes=1536*1024**2):
        self.loader=loader;self.max_bytes=max_bytes;self.pool=ThreadPoolExecutor(max_workers=1)
        self.values=OrderedDict();self.jobs={};self.lock=threading.RLock();self.desired=[];self.closed=False

    def plan(self,acquisitions):
        with self.lock:
            self.desired=[r['scan_id'] for r in acquisitions][:2]
            for sid in list(self.values):
                if sid not in self.desired:del self.values[sid]
            for sid,future in list(self.jobs.items()):
                if sid not in self.desired:future.cancel()

    def request(self,a):
        sid=a['scan_id']
        with self.lock:
            if sid in self.values:
                from concurrent.futures import Future
                f=Future();f.set_result(self.values[sid]);return f
            if sid in self.jobs and not self.jobs[sid].cancelled():return self.jobs[sid]
            def work():
                scan=self.loader(a);size=scan.images.nbytes+scan.structural.nbytes+scan.octa.nbytes
                with self.lock:
                    if not self.closed and sid in self.desired:
                        used=sum(s.images.nbytes+s.structural.nbytes+s.octa.nbytes for s in self.values.values())
                        if used+size<=self.max_bytes:self.values[sid]=scan
                return scan
            f=self.pool.submit(work);self.jobs[sid]=f
            return f

    def release_done(self):
        with self.lock:
            for sid in list(self.jobs):
                if self.jobs[sid].done():del self.jobs[sid]

    def close(self):
        self.closed=True
        for f in self.jobs.values():f.cancel()
        self.values.clear();self.pool.shutdown(wait=False,cancel_futures=True)
