"""Model 3 correction-only destinations. Earlier releases are read-only inputs."""
from pathlib import Path
import hashlib, json, os, sys, time, uuid
import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MODEL3 = HERE.parent
V7 = ROOT / 'outputs/octa-auto_cnv_v7'
V6 = ROOT / 'outputs/octa-auto_cnv_unet_v6/all_samples'
SCHEMA = 'cnv-model3-correction-v9.1'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def destination(path):
    p = Path(path).resolve()
    if not p.is_relative_to(HERE):
        raise ValueError('All correction writes must stay inside ' + str(HERE))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def atomic(path, data):
    p = destination(path)
    tmp = p.with_name(p.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, allow_nan=False)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        tmp.unlink(missing_ok=True)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''): h.update(b)
    return h.hexdigest()

def fingerprint(path, sampled=False):
    p = Path(path).resolve(); st = p.stat(); h = hashlib.sha256()
    with p.open('rb') as f:
        if sampled:
            for off in sorted({0, max(0, st.st_size//2-524288), max(0, st.st_size-1048576)}):
                f.seek(off); h.update(f.read(1048576))
        else:
            for b in iter(lambda: f.read(4*1024*1024), b''): h.update(b)
    if p.stat().st_mtime_ns != st.st_mtime_ns: raise RuntimeError('Input changed during read')
    return dict(path=str(p), bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                sha256=h.hexdigest(), hash_scope='three_1MiB_samples' if sampled else 'full_file')

def verify(fp):
    got = fingerprint(fp['path'], fp.get('hash_scope') == 'three_1MiB_samples')
    if got['sha256'] != fp['sha256'] or got['bytes'] != fp['bytes']:
        raise ValueError('Input changed: ' + fp['path'])

def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def intervals(row):
    edge = np.flatnonzero(np.diff(np.r_[False, row, False]))
    return [(int(a), int(b)) for a,b in zip(edge[::2], edge[1::2])]

def encode(mask):
    return [[y,a,b] for y,row in enumerate(mask) for a,b in intervals(row)]

def decode(runs, shape=(512,512)):
    out = np.zeros(shape, bool)
    for run in runs:
        if len(run)!=3 or any(type(x) is not int for x in run): raise ValueError('Noninteger native run')
        y,a,b = run
        if not (0<=y<shape[0] and 0<=a<b<=shape[1]): raise ValueError('Invalid native coordinates')
        if out[y,a:b].any(): raise ValueError('Overlapping run encoding')
        out[y,a:b] = True
    return out

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


