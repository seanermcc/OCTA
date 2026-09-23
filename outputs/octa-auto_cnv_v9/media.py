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
def run():
 cases=read(HERE/'data/selection.json')['acquisitions'];records=[]
 for i,a in enumerate(cases):
  sid=a['scan_id'];out=HERE/'gallery/assets'/sid;jp=out/'media.json'
  if jp.exists():
   r=read(jp)
   for fp in r['outputs']:verify(fp)
   records.append(r);continue
  c=read(HERE/'cache'/sid/'manifest.json');meta=read(V6/'inputs'/(sid+'.json'));fp=meta['images'];verify(fp);images=np.load(fp['path'],mmap_mode='r');z=npz(HERE/'cache'/sid/'enface.npz');optical=z['optical']
  if images.shape!=(512,c['retinal_depth'],512):raise ValueError('Gallery B-scan grid')
  err=float(np.max(np.abs(images.mean(1)-optical[0])))
  if err>.001:raise ValueError('B-scan/en-face alignment mismatch')
  # Finite cropped native providers preserve full lateral/slow axes, including 0 and 511.
  if not np.isfinite(images[0]).all() or not np.isfinite(images[511]).all():raise ValueError('Invalid boundary B-scans')
  contrast=np.percentile(images[::32,::8,::8],[1,99.5]).tolist()
  png(out/'structural.png',gray(optical[0]));png(out/'octa.png',gray(optical[1]));context=npz(HERE/'cache'/sid/'context.npz')['channels']
  png(out/'vessel.png',rgba(context[0]>0,(20,175,255)));png(out/'onh.png',rgba(context[1]>0,(38,235,127)))
  for row in (0,255,511):png(out/f'bscan_{row}.png',gray(images[row],contrast))
  r=dict(scan_id=sid,images=fp,axis_order='B-scan,depth,A-line',canonical_depth_zero='vitreous',canonical_crop_offset=c['canonical_crop_offset'],depth=images.shape[1],bscan_display_limits=contrast,structural_projection_max_error_db=err,retained_native_rows=[0,511],outputs=[fingerprint(out/n) for n in ['structural.png','octa.png','vessel.png','onh.png','bscan_0.png','bscan_255.png','bscan_511.png']])
  write(jp,r);records.append(r);print(json.dumps(dict(stage='gallery media',completed=i+1,total=len(cases),scan_id=sid)),flush=True)
 write(HERE/'gallery/media_manifest.json',dict(records=records,selection_sha256=sha(HERE/'data/selection.json')))
if __name__=='__main__':run()
