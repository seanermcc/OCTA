from common import *
from collections import Counter
import torch, shutil

pilot=read(HERE.parent/'data/manifest.json')
batch=ROOT/'outputs/octa-seg_v1_batch'
manifest=read(batch/'manifest.json')
rows=[]
for r in manifest['scans']:
    sid=r['scan_id'];vp=batch/'volumes'/sid
    p=read(vp/'prepared.json');g=npz(vp/'geometry.npz')
    rows.append(dict(scan_id=sid,vessel_status=p['footprints']['status'],onh_pixels=int(g['onh'].sum()),neural_files=len(list((vp/'neural').glob('*.npz'))),images_exists=(vp/'images.npy').exists()))
write(HERE/'verification/input_preflight.json',rows)
print('ENV',sys.executable,os.environ.get('CONDA_PREFIX'),torch.__version__,torch.cuda.is_available(),shutil.disk_usage(HERE).free,flush=True)
print('UPSTREAM',Counter(r['vessel_status'] for r in rows),'ONH',sum(r['onh_pixels']>0 for r in rows),'NEURAL',Counter(r['neural_files'] for r in rows),flush=True)
print('PILOT model hashes',[(r['scan_id'],[(f['path'],f['sha256']) for f in r['fingerprints'] if f['path'].endswith('position.pt') or f['path'].endswith('states.pt')]) for r in pilot['scans'][:1]],flush=True)
for ex in 'BC':
    for seed in (267,268,269):
        p=HERE.parent/f'experiment_{ex}'
        if seed!=267:p=p/f'seed_{seed}'
        ck=torch.load(p/'best.pt',map_location='cpu',weights_only=False)
        print(ex,seed,sha(p/'best.pt'),ck.keys(),ck['config'],read(p/'threshold.json')['selected'],flush=True)
