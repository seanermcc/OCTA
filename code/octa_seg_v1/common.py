from pathlib import Path
import csv
import json
import os
import time
import numpy as np
from stage_a.common import fingerprint, digest, verify

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/octa-seg/octa-seg_v1"
PREVIOUS = ROOT / "outputs/stage_a/20260909_unet_review36_update"

def directory(path):
    path = Path(path).resolve()
    if not path.is_relative_to(OUT):
        raise ValueError(f"v1 artifacts must remain under {OUT}")
    if (OUT/"COMPLETE.json").exists() and not path.is_relative_to(OUT/"reviewer"):
        raise RuntimeError("octa-seg_v1 is complete and frozen. Use octa-seg_v2 for new scientific artifacts.")
    path.mkdir(parents=True, exist_ok=True)
    return path

def write_json(path, value):
    path = Path(path); directory(path.parent)
    def json_type(value):
        if isinstance(value,np.generic):return value.item()
        if isinstance(value,np.ndarray):return value.tolist()
        if isinstance(value,Path):return str(value)
        raise TypeError(f"Unsupported JSON value {type(value).__name__}")
    content = json.dumps(value, indent=2, allow_nan=False,default=json_type)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8"); tmp.replace(path)

def write_csv(path, rows):
    rows = list(rows); path = Path(path); directory(path.parent)
    if rows:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, sorted(set().union(*(r.keys() for r in rows))))
            w.writeheader(); w.writerows(rows)

def save_npz(path, **data):
    path = Path(path); directory(path.parent)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **data); tmp.replace(path)

def progress(stage, **details):
    write_json(OUT / "progress.json", dict(stage=stage, pid=os.getpid(), updated=time.strftime("%Y-%m-%dT%H:%M:%S"), **details))
    print(stage, details, flush=True)

def load_npz(path):
    with np.load(path, allow_pickle=False) as d:
        return {k: d[k] for k in d.files}
