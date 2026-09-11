"""Atomic artifacts, content-addressed stage resume, and strict batch adapter."""
from pathlib import Path
import csv
import hashlib
import json
import os
import re
import numpy as np
from . import LAYERS


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def fingerprint(path):
    p = Path(path).resolve()
    return dict(path=str(p), bytes=p.stat().st_size, sha256=sha(p))


def write(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    def encode(x):
        if isinstance(x, np.ndarray): return x.tolist()
        if isinstance(x, np.generic): return x.item()
        return str(x)
    tmp.write_text(json.dumps(value, indent=2, default=encode, allow_nan=False), encoding="utf-8")
    tmp.replace(p)


def save(path, **arrays):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp.npz")
    np.savez_compressed(tmp, **arrays); tmp.replace(p)


def npz(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def table(path, rows, fields=None):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r)) or ["status"]
    tmp = p.with_name(p.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    tmp.replace(p)


def require_verified(batch):
    p = Path(batch) / "FINAL_VERIFIED.json"
    if not p.exists():
        raise RuntimeError(f"Waiting for batch verification: {p}")
    proof = read(p)
    manifest = read(Path(batch) / "manifest.json")
    if (proof.get("passed") is not True or proof.get("scans") != len(manifest["scans"])
            or proof.get("all_native_grid_checks") is not True
            or proof.get("all_input_artifact_hashes_verified") is not True):
        raise ValueError("Batch final verification is unsuccessful or does not cover this manifest")
    for fp in proof.get("tables", []):
        if sha(fp["path"]) != fp["sha256"]:
            raise ValueError("Verified batch table changed: " + fp["path"])
    return manifest


def analysis_inputs(batch, skip_batch_audit=False):
    """A user-authorized cohort-audit skip never implies verified input status."""
    batch=Path(batch)
    if not skip_batch_audit:
        manifest=require_verified(batch)
        return manifest,dict(status="passed",verification=fingerprint(batch/"FINAL_VERIFIED.json"))
    manifest=read(batch/"manifest.json")
    if not manifest.get("scans"):raise ValueError("No acquisitions in the batch manifest")
    missing=[]
    for row in manifest["scans"]:
        sid=row["scan_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+",sid):raise ValueError("Unsafe scan id")
        volume=batch/"volumes"/sid
        required=[volume/name for name in ("complete.json","neural_complete.json","prepared.json",
                  "qc_complete.json","qc_masks.npz","geometry.npz","images.npy","measurements.npz")]
        export=batch/"thick/exports"/(sid+"_batch.npz")
        required += [export,export.with_suffix(".json")]
        missing.extend(str(p) for p in required if not p.is_file())
    if missing:raise ValueError("Required analysis inputs missing: "+"; ".join(missing))
    return manifest,dict(status="skipped_by_user",verification=None,
        authorization="Explicit --skip-batch-audit: proceed with full analysis without batch audit",
        acquisitions=len(manifest["scans"]),required_files_present=True,
        retained_checks="Export metadata, source fingerprints, stale corrections, native geometry and shadow NaNs")


def unique_scans(rows):
    """Paths/identities deduplicate; a sampled raw hash alone cannot prove identity."""
    keep, duplicates, ids, sources = [], [], {}, {}
    available_ids={r["scan_id"] for r in rows}
    for row in sorted(rows, key=lambda r: r["scan_id"]):
        sid = row["scan_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", sid): raise ValueError("Unsafe scan id")
        if row.get("source_variant_of"):
            if row["source_variant_of"] not in available_ids:
                raise ValueError("Alternate processing has no canonical acquisition: "+sid)
            duplicates.append(dict(scan_id=sid,canonical=row["source_variant_of"],
                                   reason="alternate processing of the same acquisition; canonical export used"))
            continue
        source = os.path.normcase(str(Path(row["source"]).resolve()))
        if sid in ids:
            if ids[sid] != source: raise ValueError("Conflicting acquisition identity: " + sid)
            duplicates.append(dict(scan_id=sid, canonical=sid, reason="duplicate manifest row")); continue
        ids[sid] = source
        if source in sources:
            duplicates.append(dict(scan_id=sid, canonical=sources[source], reason="same source path")); continue
        sources[source] = sid
        r = dict(row)
        match = re.search(r"T(?:S)?(\d+)", r["animal"])
        if not match or r.get("eye") not in ("OD", "OS") or not r.get("session_date"):
            raise ValueError("Unresolved animal, eye, or date: " + sid)
        r["animal"] = "TS" + match[1]
        keep.append(r)
    return keep, duplicates


class Stage:
    def __init__(self, root, name, signature):
        self.path = Path(root) / "logs" / (name + ".json")
        self.signature = signature

    def valid(self):
        if not self.path.exists(): return False
        old = read(self.path)
        return old.get("signature") == self.signature and all(
            Path(f["path"]).exists() and sha(f["path"]) == f["sha256"] for f in old["artifacts"])

    def finish(self, paths):
        write(self.path, dict(signature=self.signature, artifacts=[fingerprint(p) for p in paths]))


def source_paths(batch, row):
    b = Path(batch); v = b / "volumes" / row["scan_id"]
    exp = b / "thick/exports" / (row["scan_id"] + "_batch.npz")
    paths = [exp, exp.with_suffix(".json"), v/"geometry.npz", v/"qc_masks.npz",
             v/"prepared.json", v/"qc_complete.json"]
    prep = read(v/"prepared.json")
    if prep.get("enface_label"): paths.append(Path(prep["enface_label"]["path"]))
    meta = read(exp.with_suffix(".json"))
    paths += [Path(p) for p in meta.get("correction_fingerprints", {})]
    paths += region_paths(batch,row["scan_id"])
    if (b/"launch_config.json").exists():paths.append(b/"launch_config.json")
    # Raw source and hundreds of MB of images were verified by the upstream audit;
    # image file stat must still match its fingerprint, and it is read only.
    image_fp = prep["images_fingerprint"]; image_path = Path(image_fp["path"])
    stat = image_path.stat()
    if stat.st_size != image_fp["bytes"] or stat.st_mtime_ns != image_fp["mtime_ns"]:
        raise ValueError("Prepared structural image changed: " + str(image_path))
    return paths


def region_paths(batch,sid):
    config_path=Path(batch)/"launch_config.json"
    config=read(config_path) if config_path.exists() else {}
    roots=[Path(p) for p in config.get("region_sources",[])]
    if config.get("output"):roots.insert(0,Path(config["output"])/"regions")
    # Read all available outlines conservatively; saved normal regions never
    # erase another saved lesion without an explicit revised source annotation.
    return sorted({p/f"{sid}_regions.json" for p in roots if (p/f"{sid}_regions.json").exists()})


def load_scan(batch, row, config):
    from eight_surface.cnv_labels import load_label
    b = Path(batch); v = b/"volumes"/row["scan_id"]
    ep = b/"thick/exports"/(row["scan_id"]+"_batch.npz")
    if any(Path(str(p)+".stale.json").exists() for p in (ep, ep.with_suffix(".json"))):
        raise ValueError("Stale thickness export: " + str(ep))
    z = npz(ep); meta = read(ep.with_suffix(".json")); g = npz(v/"geometry.npz")
    if json.loads(str(z["metadata_json"].item())) != meta: raise ValueError("Export metadata differs")
    if (meta["scan_id"] != row["scan_id"] or meta["layers"] != LAYERS or meta["units"] != "um"
            or meta["axis_order"] != "layer,B-scan,A-line"
            or not meta["canonical_vitreous_at_depth_zero"]):
        raise ValueError("Incompatible thickness export")
    for name, expected in meta["source_fingerprints"].items():
        if sha(v/name) != expected: raise ValueError("Export source changed: " + name)
    for path, expected in meta.get("correction_fingerprints", {}).items():
        if sha(path) != expected: raise ValueError("Human correction changed; re-export first")
    arr = z["exclude_unreliable_um"].copy()
    shape = tuple(g["native_shape"][:2])
    if arr.shape != (8, *shape) or z["shadow"].shape != shape: raise ValueError("Grid mismatch")
    if np.isfinite(arr[:, z["shadow"].astype(bool)]).any(): raise ValueError("Shadow NaNs lost upstream")
    excluded = npz(v/"qc_masks.npz")["excluded"].astype(bool)
    if excluded.shape != shape: raise ValueError("Exclusion grid mismatch")
    arr[:, excluded] = np.nan
    if np.any(np.isfinite(arr) & (arr <= 0)): raise ValueError("Nonpositive thickness geometry")
    prep = read(v/"prepared.json"); label = None
    if prep.get("enface_label"):
        fp = prep["enface_label"]
        if sha(fp["path"]) != fp["sha256"]: raise ValueError("En-face annotation changed since batch")
        label = load_label(fp["path"])
        if (label["scan_id"] != row["scan_id"] or label["native_shape"] != shape
                or Path(label["source_volume"]).resolve() != Path(row["source"]).resolve()):
            raise ValueError("En-face annotation coordinate mismatch")
    sy, sx = config["field_um"]/shape[0], config["field_um"]/shape[1]
    calibration = "approximate 1460 um field fallback"
    if label:
        sy, sx = label["bscan_um"], label["aline_um"]; calibration = "saved en-face physical calibration"
    if row["scan_id"] in config["calibration_overrides"]:
        sy, sx = config["calibration_overrides"][row["scan_id"]]; calibration = "configured (B-scan,A-line) um/pixel"
    if not np.isfinite([sy, sx]).all() or min(sy, sx) <= 0: raise ValueError("Invalid calibration")
    images = np.load(v/"images.npy", mmap_mode="r")
    enface = np.empty(shape, np.float32)
    for lo in range(0, shape[0], 32): enface[lo:lo+32] = images[lo:lo+32].mean(axis=1)
    data = dict(thickness=arr, shadow=z["shadow"], human_excluded=excluded, enface=enface,
                vessel=g["vessel"], cnv_human=g["cnv"], onh=g["onh"], onh_edge=g["onh_edge"],
                spacing=np.array([sy, sx]), endpoints=z["reported_endpoints_crop_px"],
                endpoint_sources=z["reported_endpoint_sources"], endpoint_reason=z["endpoint_reason"])
    regions=[]
    from cnv_review_v1.data import decode_mask
    for path in region_paths(batch,row["scan_id"]):
        saved=read(path)
        if (saved["scan_id"]!=row["scan_id"] or tuple(saved["native_shape"])!=shape
                or Path(saved["source_volume"]).resolve()!=Path(row["source"]).resolve()):
            raise ValueError("Region outline coordinate mismatch: "+str(path))
        for region in saved["regions"]:
            mask=decode_mask(region["runs"],shape)
            if region["category"] in ("Full Lesion","Unclassified"):
                data["cnv_human"]|=mask
            regions.append(dict(path=str(path),id=region["id"],category=region["category"],
                                origin=region.get("origin","unknown"),pixels=int(mask.sum())))
    info = dict(row, shape=list(shape), spacing=[sy, sx], calibration=calibration,
                export_metadata=meta, vessel_provenance=prep["footprints"],
                annotation_reviewed=label["reviewed_targets"].tolist() if label else [False]*3,
                enface_label=prep.get("enface_label"),region_annotations=regions)
    return data, info
