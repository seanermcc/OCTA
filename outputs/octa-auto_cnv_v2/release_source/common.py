"""Isolated experimental CNV workflow; upstream files are read-only."""
from pathlib import Path
import hashlib
import json
import os
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LONG = ROOT / 'outputs/longitudinal_assessment'
sys.path.insert(0, str(ROOT / 'code'))
sys.path.insert(0, str(ROOT / 'outputs/octa-thick_v1'))
sys.path.insert(0, str(HERE))
# The activated environment must be retained in desktop child processes.
_handles = []
if os.name == 'nt' and os.environ.get('CONDA_PREFIX'):
    dll = Path(os.environ['CONDA_PREFIX']) / 'Library/bin'
    os.environ['PATH'] = str(dll) + os.pathsep + os.environ.get('PATH', '')
    _handles.append(os.add_dll_directory(str(dll)))
import numpy as np

VERSION = 'octa-auto_cnv_v2'
PIXEL_UM = 1460.0 / 512
PIXEL_MM2 = (PIXEL_UM / 1000) ** 2

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def destination(path):
    path = Path(path).resolve()
    if not path.is_relative_to(HERE):
        raise ValueError('All writes must stay inside octa-auto_cnv_v2')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def write(path, data):
    path = destination(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False, default=str), encoding='utf-8')
    tmp.replace(path)

def save_npz(path, **data):
    path = destination(path)
    tmp = path.with_suffix('.tmp')
    with tmp.open('wb') as f:
        np.savez_compressed(f, **data)
    tmp.replace(path)

def npz(path):
    with np.load(path, allow_pickle=False) as d:
        return {k: d[k] for k in d.files}

def selected():
    return [r for r in read(LONG/'manifest.json')['visits'] if r['animal'] == 'TS267']

def volume_path(sid):
    return LONG/'v2/round_000/volumes'/sid

def volume(sid):
    import engine
    # Prevent the old viewer's stale-export bookkeeping from writing upstream.
    engine.HERE = HERE/'viewer_cache'
    return engine.Volume(volume_path(sid), read(LONG/'v2/launch_config.json'))


