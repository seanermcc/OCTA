"""V8 release-local writes and immutable input provenance."""
from pathlib import Path
import os, sys, json, hashlib, time, uuid
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import numpy as np
HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('OCTA_PROJECT', r'G:\OCT_TreeShrew\octa'))
V7 = ROOT/'outputs/octa-auto_cnv_v7'
V6 = ROOT/'outputs/octa-auto_cnv_unet_v6/all_samples'
sys.path.insert(0, str(ROOT/'code'))
LAYERS = [('Full retina',0,7),('RNFL',0,1),('GCL',1,2),('IPL',2,3),('INL',3,4),('OPL',4,5),('Photoreceptor composite',5,6),('RPE band',6,7)]
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dest(p):
    p=Path(p).resolve()
    if not p.is_relative_to(HERE): raise ValueError('Write outside v8: '+str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
def json_type(x):
    if isinstance(x,np.ndarray): return x.tolist()
    if isinstance(x,np.generic): return x.item()
    if isinstance(x,Path): return str(x)
    raise TypeError(type(x).__name__)
def write(p,d):
    p=dest(p); t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
    t.write_text(json.dumps(d,indent=2,allow_nan=False,default=json_type),encoding='utf8'); t.replace(p)
def save(p,**a):
    p=dest(p); t=p.with_name(p.name+'.tmp.npz'); np.savez_compressed(t,**a); t.replace(p)
def npz(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def fingerprint(p,sampled=False):
    p=Path(p).resolve(); st=p.stat(); h=hashlib.sha256()
    with p.open('rb') as f:
        if sampled:
            for off in sorted({0,max(0,st.st_size//2-524288),max(0,st.st_size-1048576)}):
                f.seek(off); h.update(f.read(1048576))
        else:
            for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    if p.stat().st_mtime_ns!=st.st_mtime_ns:raise RuntimeError('Source changed during hashing')
    return dict(path=str(p),bytes=st.st_size,mtime_ns=st.st_mtime_ns,sha256=h.hexdigest(),hash_scope='three_1MiB_samples' if sampled else 'full_file')
def sha(p):return fingerprint(p)['sha256']
def verify(fp):
    got=fingerprint(fp['path'],fp.get('hash_scope')=='three_1MiB_samples')
    if got['bytes']!=fp['bytes'] or got['sha256']!=fp['sha256']:raise RuntimeError('Frozen source changed: '+fp['path'])
def digest(d):return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def decode(runs,shape=(512,512)):
    out=np.zeros(shape,bool)
    for y,a,b in runs:
        if any(type(t)!=int for t in (y,a,b)) or not(0<=y<shape[0] and 0<=a<b<=shape[1]):raise ValueError('Invalid native run')
        if out[y,a:b].any():raise ValueError('Overlapping runs')
        out[y,a:b]=True
    return out
def progress(stage,**kw):
    d=dict(stage=stage,time=time.strftime('%Y-%m-%dT%H:%M:%S'),pid=os.getpid(),**kw)
    write(HERE/'progress.json',d);print(json.dumps(d,default=json_type),flush=True)
