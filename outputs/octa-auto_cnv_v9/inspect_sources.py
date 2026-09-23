import sys, json, shutil
from pathlib import Path
sys.dont_write_bytecode = True
import numpy as np
import torch
R=Path(__file__).resolve().parents[2]
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
print('COMPUTE',torch.__version__,torch.cuda.is_available(),torch.cuda.get_device_properties(0),shutil.disk_usage(R))
q=read(R/'outputs/octa-auto_cnv_v8/manual_review/queue/queue.json')['acquisitions']
for a in q:
 d=read(R/'outputs/octa-auto_cnv_v8/manual_review/review/regions'/(a['scan_id']+'.json'))
 print('LABEL',a['scan_id'],d['kind'],d['revision'],sum(r['state']=='kept' for r in d['state']['regions']))
m=read(R/'outputs/octo-vessel_onh_v2/final_output_v1/manifest.json')
for sel in ('saved_manual','frozen_v1'):
 a=next(r for r in m['records'] if r['selection']==sel)
 with np.load(R/'outputs/octo-vessel_onh_v2/final_output_v1'/a['masks']) as z:
  print('CONTEXT',sel,a,{k:(str(z[k]) if z[k].size<5 else [str(z[k].shape),str(z[k].dtype)]) for k in z.files})
print('INVENTORY KEYS',read(R/'outputs/octa-auto_cnv_v7/queue/inventory.json').keys())
a=q[0]
print('INPUT',read(R/'outputs/octa-auto_cnv_unet_v6/all_samples/inputs'/(a['scan_id']+'.json')))
print('PROVIDER',np.load(a['image_provider'],mmap_mode='r').shape)
