"""Pilot utilities. All writes are confined to this release, never human labels."""
from pathlib import Path
import csv
import hashlib
import json
import os
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'code'))
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import numpy as np

LONG = ROOT / 'outputs/longitudinal_assessment'
V5 = ROOT / 'outputs/octa-auto_cnv_v5'
V3 = ROOT / 'outputs/octa-auto_cnv_v3'
UM = 1460 / 512
SURFACES = ['ILM','RNFL_GCL','GCL_IPL','IPL_INL','INL_OPL','OPL_ONL','PR_RPE','RPE']
LAYERS = [('Full retina',0,7),('RNFL',0,1),('GCL',1,2),('IPL',2,3),('INL',3,4),('OPL',4,5),('Photoreceptor composite',5,6),('RPE band',6,7)]

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def dest(path):
    path = Path(path).resolve()
    if not path.is_relative_to(HERE):
        raise ValueError('Writes must stay inside octa-auto_cnv_unet_v6')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def json_type(v):
    if isinstance(v, np.ndarray): return v.tolist()
    if isinstance(v, np.generic): return v.item()
    if isinstance(v, Path): return str(v)
    raise TypeError(type(v).__name__)

def write(path, data):
    p=dest(path); tmp=p.with_suffix(p.suffix+f'.{os.getpid()}.{time.time_ns()}.tmp')
    tmp.write_text(json.dumps(data,indent=2,allow_nan=False,default=json_type),encoding='utf-8')
    tmp.replace(p)

def csv_write(path, rows):
    rows=list(rows)
    p=dest(path);tmp=p.with_suffix(p.suffix+f'.{os.getpid()}.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        if rows:
            w=csv.DictWriter(f,sorted(set().union(*(r.keys() for r in rows))))
            w.writeheader(); w.writerows(rows)
    tmp.replace(p)

def npz(path):
    with np.load(path,allow_pickle=False) as a: return {k:a[k] for k in a.files}

def save(path, **arrays):
    p=dest(path); tmp=p.with_suffix('.tmp.npz')
    np.savez_compressed(tmp,**arrays); tmp.replace(p)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''): h.update(block)
    return h.hexdigest()

def fingerprint(path, sampled=False):
    from stage_a.common import fingerprint as fp
    return fp(path,sampled)

def verify(fp):
    actual=fingerprint(fp['path'],fp.get('hash_scope')=='three_1MiB_samples')
    if actual['sha256'] != fp['sha256'] or actual['bytes'] != fp['bytes']:
        raise ValueError('Source content changed: '+fp['path'])

def volume_path(sid): return LONG/'v2/round_000/volumes'/sid

def progress(stage, **kw):
    d=dict(stage=stage,updated=time.strftime('%Y-%m-%dT%H:%M:%S'),pid=os.getpid(),**kw)
    write(HERE/'progress.json',d); print(json.dumps(d),flush=True)

def decode(runs,shape=(512,512)):
    mask=np.zeros(shape,bool)
    for r in runs:
        if len(r)!=3 or any(isinstance(x,bool) or not isinstance(x,int) for x in r): raise ValueError('Noninteger native run')
        y,a,b=r
        if not (0<=y<shape[0] and 0<=a<b<=shape[1]): raise ValueError('Out-of-bounds native run')
        if mask[y,a:b].any(): raise ValueError('Duplicate/overlapping run encoding')
        mask[y,a:b]=True
    return mask

def encode(mask):
    result=[]
    for y,row in enumerate(mask):
        edges=np.flatnonzero(np.diff(np.r_[False,row,False]))
        result.extend([[y,int(a),int(b)] for a,b in zip(edges[::2],edges[1::2])])
    return result

# GUI compatibility constants. These resolve only to the isolated v6 batch.
VERSION='octa-auto_cnv_unet_v6_all_samples'
DATA=HERE
PIXEL_UM=UM
PIXEL_MM2=(UM/1000)**2
destination=dest
def selected():
    return read(HERE/'inventory.json')['scans'] if (HERE/'inventory.json').exists() else []

def prediction_provenance(root,model,sid,missing_ok=False):
    packed=Path(root)/'provenance'/f'{sid}.json'
    if packed.exists():
        value=read(packed)['models'].get(model)
        if value is not None:return value
    legacy=Path(root)/model/f'{sid}.json'
    if legacy.exists():return read(legacy)
    if missing_ok:return None
    raise FileNotFoundError(f'Missing prediction provenance: {sid} / {model}')

def save_prediction_provenance(root,model,sid,value):
    p=Path(root)/'provenance'/f'{sid}.json'
    data=read(p) if p.exists() else dict(format='six-model-native-prediction-provenance',scan_id=sid,models={})
    data['models'][model]=value;write(p,data)

def reference_arrays(sid):
    p=HERE/'references'/f'{sid}.npz'
    if p.exists():return npz(p)
    import io,zipfile
    with zipfile.ZipFile(HERE/'references.zip') as z:
        data=z.read(f'{sid}.npz')
    with np.load(io.BytesIO(data),allow_pickle=False) as a:return {k:a[k] for k in a.files}

