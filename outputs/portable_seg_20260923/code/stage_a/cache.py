"""Fingerprint-verified N=1 cache, one bulk structural read per source volume."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from octa.volio import ProcessedVolume, find_retina_band
from eight_surface.segment import detect_orientation, prepare_bscan
from .common import DEFAULT, output_dir, write_json, fingerprint, verify, digest
from .geometry import PREPROCESS, preprocess, label_offset


def build(out):
    out = output_dir(out)
    manifest = json.loads((out/"manifest.json").read_text())
    if manifest["census"]["failures"]:
        raise ValueError("Incomplete audit")
    cache_dir = output_dir(out/"cache")
    registry_path = out/"cache_manifest.json"
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else dict(
        dataset_id=manifest["dataset_id"], preprocessing=PREPROCESS, entries={}, failures={})
    if registry["dataset_id"] != manifest["dataset_id"] or registry["preprocessing"] != PREPROCESS:
        raise ValueError("Cache identity mismatch")
    for sid, src in manifest["sources"].items():
        records = [r for r in manifest["records"] if r["scan_id"] == sid]
        try:
            verify(src["source"])
            for r in records:
                verify(r["targets_fingerprint"])
            existing = [registry["entries"].get(r["key"]) for r in records]
            if all(existing):
                for e in existing:
                    verify(e["file"])
                print(f"verified existing {sid}", flush=True)
                continue
            verify(src["pack"])
            print(f"bulk read {sid} ({len(records)} B-scans)", flush=True)
            with ProcessedVolume(src["source"]["path"]) as volume:
                full = volume.read_volume()
            if list(full.shape) != src["native_shape"]:
                raise ValueError("Source geometry changed")
            profile = full.mean(axis=(0,1))
            vhi = bool(detect_orientation(profile))
            lo,hi,_ = find_retina_band(profile)
            if [int(lo),int(hi)] != src["label_band"]:
                raise ValueError("Fresh retinal band differs from label geometry")
            offset = label_offset(src["label_band"],full.shape[2],vhi)
            with np.load(src["pack"]["path"],allow_pickle=False) as p:
                images = p["images"]
                picked = p["bscan_index"].astype(int).tolist()
            for r in records:
                raw = full[r["bscan"]]
                x,db,norm = preprocess(raw,vhi)
                check = prepare_bscan(raw[:,lo:hi],vhi)
                if not np.array_equal(check, images[picked.index(r["bscan"])]) or not np.array_equal(db[offset:offset+hi-lo],check):
                    raise ValueError("Fresh canonical source does not match human review image")
                with np.load(r["targets"],allow_pickle=False) as t:
                    rows = t["rows_label"]+offset
                    valid = t["valid"]
                if np.any(valid & ((rows<0)|(rows>x.shape[1]-1)|~np.isfinite(rows))):
                    raise ValueError("Target containment failure in native fallback")
                content_hash = hashlib.sha256(raw.tobytes()).hexdigest()
                identity = dict(source=src["source"], label=r["label"],
                    targets=r["targets_fingerprint"], preprocess=PREPROCESS,
                    source_shape=src["native_shape"], band=src["label_band"],
                    vitreous_high=vhi, bscan=r["bscan"], raw_bscan_sha256=content_hash)
                key = digest(identity)
                path = cache_dir/f"{r['key']}_{key[:16]}.npz"
                if not path.exists():
                    np.savez_compressed(path,x=x,rows=rows.astype(np.float32),valid=valid,
                        label_offset=np.array(offset),vitreous_high=np.array(vhi),
                        norm=np.array(norm),cache_key=np.array(key))
                registry["entries"][r["key"]] = dict(file=fingerprint(path),identity=identity,
                    cache_key=key,label_offset=offset,shape=list(x.shape),
                    pack_pixels_exact=True,eligible_targets_contained=True)
            del full
            verify(src["source"])
            registry["failures"].pop(sid,None)
        except Exception as exc:
            registry["failures"][sid] = f"{type(exc).__name__}: {exc}"
            print(f"CACHE FAILURE {sid}: {exc}",flush=True)
        write_json(registry_path,registry)
    registry["missing"] = [r["key"] for r in manifest["records"] if r["key"] not in registry["entries"]]
    write_json(registry_path,registry)
    print(f"Cache: {len(registry['entries'])} present; {len(registry['missing'])} missing",flush=True)
    if registry["failures"] or registry["missing"]:
        raise RuntimeError("Incomplete cache; no silent skipping")


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--data",type=Path,default=DEFAULT)
    build(p.parse_args().data)
