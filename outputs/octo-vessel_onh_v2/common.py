"""Isolated vessel/ONH experimental release. No human annotation writers."""
from pathlib import Path
import hashlib, json, os, shutil, datetime
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BATCH = ROOT / 'outputs/octa-vessel_seg_v1-batch'
LABELS = ROOT / 'outputs/octo-vessel_onh_v1/labels'
TARGETS = ['vessel', 'onh']

def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def object_hash(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True).encode()).hexdigest()

def disk_check(needed=5*1024**2):
    free=shutil.disk_usage(HERE).free
    if free < needed+16*1024**2:
        raise RuntimeError(f'Insufficient disk space: {free} bytes free; need {needed} plus 16 MiB reserve. Resume after freeing space.')

def write_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)
    disk_check(len(content.encode('utf-8')))
    tmp=path.with_name(path.name+'.writing')
    tmp.write_text(content,encoding='utf-8');tmp.replace(path)

def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def save_npz(path,**arrays):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    disk_check(sum(a.nbytes for a in arrays.values() if isinstance(a,np.ndarray)))
    tmp=path.with_name(path.stem+'.writing.npz')
    np.savez_compressed(tmp,**arrays);tmp.replace(path)

def scalar(z,key,default=''):
    return z[key].reshape(-1)[0].item() if key in z else default

def normalized(im):
    lo,hi=np.percentile(im,[1,99])
    return np.clip((im-lo)/max(hi-lo,1e-6),0,1).astype(np.float32)

def progress(stage,**kwargs):
    state=dict(updated=now(),stage=stage,**kwargs)
    write_json(HERE/'progress.json',state)
    print(json.dumps(state),flush=True)

def source_code_hash():
    return {n:digest(HERE/n) for n in ['common.py','audit.py','network.py','training.py']}

def count_roles(rows):
    out={}
    for a in sorted({r['animal'] for r in rows}):
        rs=[r for r in rows if r['animal']==a]
        out[a]=dict(scans=len(rs),vessel=sum(r['vessel_eligible'] for r in rs),
                    onh=sum(r['onh_eligible'] for r in rs),
                    onh_positive=sum(r['onh_eligible'] and r['onh_positive_pixels']>0 for r in rs),
                    onh_absent=sum(r['onh_eligible'] and r['onh_visibility']=='Outside image' for r in rs))
    return out
