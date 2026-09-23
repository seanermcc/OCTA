"""Read-only providers, baseline channel parity, release-local context caches."""
from common import *
from legacy import automatic_thickness,tensor_inputs
from context import load_context
import shutil

def prepare_case(a):
 sid=a['scan_id'];out=HERE/'cache'/sid;mp=out/'manifest.json'
 if mp.exists():
  m=read(mp)
  for fp in m['outputs']:verify(fp)
  return m
 meta_path=V6/'inputs'/(sid+'.json');meta=read(meta_path);inputs=[fingerprint(meta_path)]
 if meta['scan_id']!=sid or meta['native_shape']!=[512,512,1024] or meta['axis_order']!='B-scan,A-line' or not meta['automatic_only'] or meta['octa_channel']!='frame_OCTAAvg':raise ValueError('Input grid/channel/policy mismatch')
 if Path(meta['source']['path']).resolve()!=Path(a['source']).resolve():raise ValueError('Input source mismatch')
 if meta['source']['sha256']!=a['source_fingerprint']['sha256']:raise ValueError('Source identity digest mismatch')
 for fp in [meta['source'],meta['geometry'],meta['optical_cache']]:verify(fp);inputs.append(fp)
 g=npz(meta['geometry']['path']);optical=npz(meta['optical_cache']['path'])['optical'];lo,hi=map(int,g['retina_band']);high=bool(g['vitreous_high']);offset=int(g['label_offset'])
 if high!=bool(meta['orientation_fresh_detected']) or offset!=(1024-hi if high else lo) or offset!=meta['canonical_crop_offset']:raise ValueError('Canonical orientation mismatch')
 if optical.shape!=(2,512,512) or not np.isfinite(optical).all():raise ValueError('Optical grid')
 old=V8/'cache'/sid/'enface_manifest.json'
 if old.exists():
  oldm=read(old);efp=next(fp for fp in oldm['outputs'] if Path(fp['path']).name=='enface.npz');verify(efp);inputs.extend([fingerprint(old),efp])
  z=npz(efp['path'])
  if not np.array_equal(z['optical'],optical):raise ValueError('Cached optical mismatch')
 else:
  rfp=meta.get('regenerated_neural') or meta.get('raw_neural_measurements');verify(rfp);inputs.append(rfp)
  raw=npz(rfp['path']);rows=raw.get('rows',raw.get('raw_position_branch'));cal=ROOT/'outputs/octa-seg/octa-seg_v1/calibration/deployment_vessels.json';inputs.append(fingerprint(cal))
  thick,reasons,end=automatic_thickness(rows,raw['probabilities'],g,read(cal)['thresholds'],hi-lo)
  z=dict(optical=optical,thickness_um=thick,availability=np.isfinite(thick),shadow=g['shadow'].astype(bool),reason_bits=reasons)
 if z['thickness_um'].shape!=(8,512,512) or not np.array_equal(z['availability'],np.isfinite(z['thickness_um'])) or not np.isnan(z['thickness_um'][:,z['shadow']]).all():raise ValueError('Baseline measurement availability mismatch')
 save(out/'enface.npz',**z)
 c,prov=load_context(a);save(out/'context.npz',channels=c)
 if prov['source']!='missing':
  r=next(r for r in read(EXPORT/'manifest.json')['records'] if r['scan_id']==sid)
  for p in [EXPORT/r['masks'],ROOT/'outputs'/r['source_path']]:
   fp=fingerprint(p);expected=r['masks_sha256'] if p==EXPORT/r['masks'] else r['source_sha256']
   if fp['sha256']!=expected:raise ValueError('Frozen context source changed')
   inputs.append(fp)
 write(out/'context.json',prov)
 # Frozen automatic predictions can only suggest hard reviewed-background locations.
 hp=V6/'predictions/C_267'/(sid+'.npz');hard=None
 if hp.exists():
  h=npz(hp)
  if str(h['scan_id'])!=sid or str(h['axis_order'])!='B-scan,A-line':raise ValueError('Hard-pool source mismatch')
  hard=h['mask'].astype(bool);inputs.append(fingerprint(hp))
 save(out/'hard.npz',mask=np.zeros((512,512),bool) if hard is None else hard)
 m=dict(scan_id=sid,inputs=inputs,source=meta['source'],orientation_detected=high,canonical_crop_offset=offset,retinal_depth=hi-lo,context=prov,hard_available=hard is not None,images=meta.get('images'),outputs=[fingerprint(out/n) for n in ('enface.npz','context.npz','context.json','hard.npz')])
 write(mp,m);return m

def normalization(records):
 stats={};vals=[npz(HERE/'cache'/r['scan_id']/'enface.npz') for r in records];missing=[]
 for name,n in [('optical',2),('thickness_um',8)]:
  centers=[];scales=[]
  for k in range(n):
   v=np.concatenate([x[name][k].ravel() for x in vals]);v=v[np.isfinite(v)]
   if not len(v):centers.append(0.);scales.append(1.);missing.append(f'{name}:{k}');continue
   q=np.percentile(v,[25,50,75]);centers.append(float(q[1]));scales.append(float(max((q[2]-q[0])/1.349,.001)))
  stats[name]=dict(center=centers,scale=scales)
 stats.update(training_scan_ids=sorted(r['scan_id'] for r in records),training_animals=sorted({r['animal'] for r in records}),entirely_unavailable_channels=missing,unavailable_fallback='center=0 scale=1, values zeroed by original availability policy')
 return stats
def input_tensor(sid,stats,model):
 x=tensor_inputs(npz(HERE/'cache'/sid/'enface.npz'),stats,'C')
 if model==2:x=np.concatenate([x,npz(HERE/'cache'/sid/'context.npz')['channels']])
 return x
def run():
 m=read(HERE/'data/supervision.json');sel=read(HERE/'data/selection.json');cases=[r['acquisition'] for r in m['records']]+sel['acquisitions']
 for i,a in enumerate(cases):
  prepare_case(a);progress('Validated native input preparation',completed=i+1,total=len(cases),scan=a['scan_id'])
if __name__=='__main__':
 with RunLock():run()
