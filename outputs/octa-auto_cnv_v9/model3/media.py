"""Native gallery providers and identical contrast across model views."""
from common import *
from PIL import Image
def png(path,array):
 p=dest(path);tmp=p.with_name(p.name+'.tmp');Image.fromarray(array).save(tmp,format='PNG');os.replace(tmp,p)
def gray(array,limits=None):
 lo,hi=np.percentile(array,[1,99.5]) if limits is None else limits
 return np.uint8(np.clip((array-lo)/max(float(hi-lo),1e-6),0,1)*255)
def rgba(mask,color):
 out=np.zeros((*mask.shape,4),np.uint8);out[mask,:3]=color;out[mask,3]=155;return out

def image_provider(sid,meta):
 if 'images' in meta:return meta['images']
 # The ten additional acquisitions retained display crops on demand. Recover
 # only the recorded processed-volume crop, and require exact upstream parity.
 out=HERE/'cache'/sid/'gallery_images.npy';jp=out.with_suffix('.json')
 if jp.exists():
  r=read(jp);verify(r['images']);return r['images']
 from octa.volio import ProcessedVolume
 from octa.segment import detect_orientation
 from eight_surface.segment import prepare_bscan
 verify(meta['source']);verify(meta['geometry'])
 print(json.dumps(dict(stage='Recover processed-volume display crop',scan_id=sid)),flush=True)
 with ProcessedVolume(meta['source']['path']) as volume:
  full=volume.read_volume()
 high=bool(detect_orientation(full.mean((0,1))))
 lo,hi=map(int,meta['retinal_crop_original_depth']);offset=full.shape[2]-hi if high else lo
 if high!=meta['orientation_fresh_detected'] or offset!=meta['canonical_crop_offset']:raise ValueError('Fresh display orientation differs from frozen upstream')
 images=np.stack([prepare_bscan(full[b],high)[offset:offset+hi-lo] for b in range(full.shape[0])]);del full
 h=hashlib.sha256(str((images.shape,images.dtype.str)).encode());h.update(memoryview(np.ascontiguousarray(images)))
 if h.hexdigest()!=meta['images_array_sha256']:raise ValueError('Recovered display crop differs from upstream array digest')
 tmp=dest(out).with_suffix('.tmp')
 with tmp.open('wb') as f:np.save(f,images);f.flush();os.fsync(f.fileno())
 os.replace(tmp,out);fp=fingerprint(out)
 write(jp,dict(images=fp,array_sha256=h.hexdigest(),source=meta['source'],fresh_vitreous_at_high_index=high,canonical_crop_offset=offset,role='display only; exact frozen upstream array parity'))
 return fp
def run():
 import msvcrt
 with dest(HERE/'media.lock').open('a+b') as lock:
  while True:
   lock.seek(0)
   try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);break
   except OSError:time.sleep(.5)
  try:_run()
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def _run():
 cases=read(HERE/'data/selection.json')['acquisitions'];records=[]
 for i,a in enumerate(cases):
  sid=a['scan_id'];out=HERE/'gallery/assets'/sid;jp=out/'media.json'
  if jp.exists():
   r=read(jp)
   for fp in r['outputs']:verify(fp)
   records.append(r);continue
  c=read(HERE/'cache'/sid/'manifest.json');meta=read(V6/'inputs'/(sid+'.json'));fp=image_provider(sid,meta)
  st=Path(fp['path']).stat()
  if st.st_size!=fp['bytes'] or st.st_mtime_ns!=fp['mtime_ns']:
   fresh=fingerprint(fp['path'])
   if fresh['bytes']!=fp['bytes'] or fresh['sha256']!=fp['sha256']:raise ValueError('Gallery image provider changed')
   fp=fresh
  images=np.load(fp['path'],mmap_mode='r');z=npz(HERE/'cache'/sid/'enface.npz');optical=z['optical']
  if images.shape!=(512,c['retinal_depth'],512):raise ValueError('Gallery B-scan grid')
  # Display-only provider check. Neural inputs were validated independently in
  # prepare_case. Reuse its frozen image identity instead of rereading an entire
  # volume twice just to make PNGs. Check native orientation/alignment at both
  # ends and three interior rows; expose this bounded scope in the manifest.
  check_rows=[0,127,255,383,511]
  sampled=images[check_rows]
  if not np.isfinite(sampled).all():raise ValueError('Nonfinite gallery provider rows')
  err=float(np.max(np.abs(sampled.mean(1)-optical[0,check_rows])))
  if err>.001:raise ValueError('B-scan/en-face alignment mismatch')
  # Finite cropped native providers preserve full lateral/slow axes, including 0 and 511.
  if not np.isfinite(images[0]).all() or not np.isfinite(images[511]).all():raise ValueError('Invalid boundary B-scans')
  contrast=np.percentile(images[::32,::8,::8],[1,99.5]).tolist()
  png(out/'structural.png',gray(optical[0]));png(out/'octa.png',gray(optical[1]));context=npz(HERE/'cache'/sid/'context.npz')['channels']
  png(out/'vessel.png',rgba(context[0]>0,(20,175,255)));png(out/'onh.png',rgba(context[1]>0,(38,235,127)))
  for row in (0,255,511):png(out/f'bscan_{row}.png',gray(images[row],contrast))
  r=dict(scan_id=sid,images=fp,axis_order='B-scan,depth,A-line',canonical_depth_zero='vitreous',canonical_crop_offset=c['canonical_crop_offset'],depth=images.shape[1],bscan_display_limits=contrast,structural_projection_max_error_db=err,projection_check_rows=check_rows,provider_verification='frozen upstream full digest with matching size/mtime; changed metadata triggers full rehash; five native rows checked for alignment',retained_native_rows=[0,511],outputs=[fingerprint(out/n) for n in ['structural.png','octa.png','vessel.png','onh.png','bscan_0.png','bscan_255.png','bscan_511.png']])
  write(jp,r);records.append(r);print(json.dumps(dict(stage='gallery media',completed=i+1,total=len(cases),scan_id=sid)),flush=True)
 write(HERE/'gallery/media_manifest.json',dict(records=records,selection_sha256=sha(HERE/'data/selection.json')))
if __name__=='__main__':run()
