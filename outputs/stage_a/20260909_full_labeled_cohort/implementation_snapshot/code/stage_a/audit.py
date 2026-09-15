"""Freeze completed first-round evidence. Never visits repeatability directories."""
import argparse
from collections import Counter, defaultdict
import datetime as dt
import json
from pathlib import Path

import numpy as np
from batch_segment import scan_id_for
from eight_surface.labels import load_label
from eight_surface.cnv_labels import load_label as load_footprint
from eight_surface.config import SURFACE_NAMES, CASCADE_VERSION
from octa.volio import ProcessedVolume
from .common import DEFAULT, OUT, fingerprint, write_json, write_csv, read_csv, output_dir, digest
from .eligibility import scope, supervision, BUFFER_UM


def audit(out):
    out = output_dir(out)
    if (out / "manifest.json").exists():
        raise FileExistsError("Dataset is frozen; use a new version directory")
    index = read_csv(OUT / "scan_index.csv")
    metadata = {scan_id_for(r): r for r in index}
    qc = {r["scan_id"]: r for r in read_csv(OUT / "scan_quality_metrics.csv")}
    groups = {r["scan_id"]: r["quality_group"] for r in read_csv(OUT / "eight_surface/qc_review_groups.csv")}
    inputs = {str(p.relative_to(OUT)): fingerprint(p) for p in [
        OUT / "scan_index.csv", OUT / "scan_quality_metrics.csv",
        OUT / "eight_surface/qc_review_groups.csv"]}
    packs = {}
    queued = set()
    for path in sorted((OUT / "eight_surface/review").glob("*_pack.npz")):
        fp = fingerprint(path)
        with np.load(path, allow_pickle=False) as p:
            sid = str(p["scan_id"][0])
            bs = p["bscan_index"].astype(int).tolist()
            packs[sid] = dict(fingerprint=fp, bscans=bs,
                              image_shape=list(p["images"].shape), shadow=p["shadow"].copy())
            queued.update((sid, b) for b in bs)
    sources, records, coverage, decisions = {}, [], [], []
    failures = []
    seen = set()
    # Deliberately non-recursive and restricted to the completed first round.
    for path in sorted((OUT / "eight_surface/labels").glob("*.npz")):
        try:
            fp = fingerprint(path)
            with np.load(path, allow_pickle=False) as raw:
                required = {"surface_edited", "surface_visible", "surface_reliable",
                            "surface_displaced", "region_excluded", "cascade_version"}
                if not required.issubset(raw.files):
                    raise ValueError("Explicit supervision flags missing; no permissive defaults")
            r = load_label(path)
            if fingerprint(path) != fp:
                raise RuntimeError("Label changed during snapshot")
            sid, b = r["scan_id"], r["bscan"]
            if (sid, b) not in queued or (sid, b) in seen:
                raise ValueError("Label outside standard queue or duplicate")
            seen.add((sid, b))
            if sid not in sources:
                md = metadata[sid]
                seg_path = OUT / "eight_surface/segmented" / f"{sid}.npz"
                with np.load(seg_path, allow_pickle=False) as seg:
                    source = Path(str(seg["source"][0]))
                    band = seg["retina_band"].astype(int).tolist()
                    stored_shape = seg["shape"].astype(int).tolist()
                source_fp = fingerprint(source, sampled=True)
                with ProcessedVolume(source) as v:
                    shape = list(v.shape)
                    dtype = str(v.struct.dtype)
                if shape != stored_shape or packs[sid]["image_shape"][1:] != [band[1]-band[0], shape[1]]:
                    raise ValueError("Source/pack/segmentation geometry mismatch")
                footprint_path = OUT / "cnv_labels" / f"{sid}_cnv.npz"
                foot = load_footprint(footprint_path) if footprint_path.exists() else None
                if foot and Path(foot["source_volume"]).resolve() != source.resolve():
                    raise ValueError("Footprint source mismatch")
                allowed, distance, status, biology = scope(md, foot, shape[:2])
                scope_path = output_dir(out / "scope") / f"{sid}.npz"
                np.savez_compressed(scope_path, allowed=allowed, signed_distance_um=distance)
                sources[sid] = dict(source=source_fp, segmentation=fingerprint(seg_path),
                    pack=packs[sid]["fingerprint"], native_shape=shape, source_dtype=dtype,
                    label_band=band, scope_path=str(scope_path), scope_hash=fingerprint(scope_path),
                    footprint=fingerprint(footprint_path) if foot else None,
                    footprint_reviewed=bool(foot and foot["reviewed"]),
                    footprint_positive=bool(foot and foot["cnv_mask"].any()),
                    footprint_revision=foot["revision"] if foot else None,
                    scope_status=status, biological_group=biology, metadata=md,
                    qc=qc.get(sid, {}), qc_group=groups.get(sid, "unknown"),
                    aline_um=foot["aline_um"] if foot else 1460.0/shape[1],
                    bscan_um=foot["bscan_um"] if foot else 1460.0/shape[0],
                    onh_edge_is_not_exclusion=True)
            src = sources[sid]
            with np.load(src["scope_path"], allow_pickle=False) as s:
                allowed = s["allowed"][b]
            pack = packs[sid]
            shadow = pack["shadow"][pack["bscans"].index(b)]
            valid, reason, bits = supervision(r, allowed, shadow)
            if r["surfaces"].shape != (8, src["native_shape"][1]):
                raise ValueError("Label/native width mismatch")
            off = valid & ((r["surfaces"] < 0) | (r["surfaces"] > pack["image_shape"][1]-1))
            bits["outside_review_image"] = 1024
            reason[off] |= bits["outside_review_image"]
            valid = reason == 0
            key = f"{sid}_b{b:04d}"
            target_path = output_dir(out / "targets") / f"{key}.npz"
            # Derived training evidence, never a human-label-format file.
            np.savez_compressed(target_path, rows_label=r["surfaces"].astype(np.float32),
                stored_auto=r["auto_surfaces"].astype(np.float32), valid=valid,
                reason_bits=reason, scope=allowed, shadow=shadow)
            counts = valid.sum(axis=1).astype(int).tolist()
            record = dict(key=key, scan_id=sid, bscan=b, animal=src["metadata"]["animal"],
                verdict=r["verdict"], label=fp, targets=str(target_path),
                targets_fingerprint=fingerprint(target_path), px_um=r["px_um"],
                eligible_columns_by_surface=counts, eligible=bool(valid.any()),
                qc_group=src["qc_group"], scope_status=src["scope_status"],
                biological_group=src["biological_group"],
                legacy_provenance="surface_wide_edit_only_local_strokes_unknown",
                reason_counts={name:int(((reason & bit) != 0).sum()) for name,bit in bits.items()},
                seconds_active=r.get("seconds_active"), n_strokes=r.get("n_strokes"))
            records.append(record)
            decisions.append({k:record[k] for k in ("key","animal","verdict","eligible","qc_group","scope_status","biological_group")})
            for s, count in zip(SURFACE_NAMES, counts):
                coverage.append(dict(animal=record["animal"], surface=s, qc_group=record["qc_group"],
                    biological_group=record["biological_group"], scope_status=record["scope_status"],
                    scan_id=sid, bscan=b, eligible_columns=count))
        except Exception as exc:
            failures.append(dict(path=str(path), error=f"{type(exc).__name__}: {exc}"))
    summary = dict(created=dt.datetime.now().astimezone().isoformat(),
        queued=len(queued), completed=len(records), verdicts=dict(Counter(r["verdict"] for r in records)),
        missing_decisions=[list(k) for k in sorted(queued-seen)], failures=failures,
        processed_scans=sum(r["has_volumes"] == "True" for r in index),
        corrected_by_animal=dict(Counter(r["animal"] for r in records if r["verdict"]=="corrected")),
        eligible_by_animal=dict(Counter(r["animal"] for r in records if r["eligible"])),
        eligible_by_scope=dict(Counter(r["scope_status"] for r in records if r["eligible"])),
        eligible_columns_by_surface={s:sum(r["eligible_columns_by_surface"][k] for r in records) for k,s in enumerate(SURFACE_NAMES)})
    manifest = dict(version="stage-a-20260908-v2", contract=CASCADE_VERSION,
        surface_names=SURFACE_NAMES, buffer_um=BUFFER_UM, inputs=inputs, sources=sources,
        records=records, reason_bits=bits, census=summary,
        source_hash_limit="Source MAT uses stat plus three 1MiB samples, not a full-file hash; consumed image tensors receive full content hashes.")
    manifest["dataset_id"] = digest(manifest)
    write_json(out / "manifest.json", manifest)
    write_json(out / "census.json", summary)
    write_csv(out / "decisions.csv", decisions)
    write_csv(out / "coverage_detail.csv", coverage)
    agg = defaultdict(lambda: [0,0])
    for c in coverage:
        key=tuple(c[k] for k in ("animal","surface","qc_group","biological_group","scope_status"))
        agg[key][0] += c["eligible_columns"]
        agg[key][1] += c["eligible_columns"] > 0
    write_csv(out / "coverage_by_animal_surface_qc.csv", [dict(zip(
        ("animal","surface","qc_group","biological_group","scope_status","eligible_columns","bscans_with_evidence"), (*k,*v))) for k,v in sorted(agg.items())])
    historical_path = OUT / "auto_seg_8layer_v2/unet/baseline_errors.csv"
    old = read_csv(historical_path)
    old_keys = {(r["scan_id"],int(r["bscan"])) for r in old}
    write_json(out / "historical_cohort.json", dict(source=fingerprint(historical_path),
        n_bscans=len(old_keys), keys=[list(k) for k in sorted(old_keys)],
        current_label_fingerprints=[r["label"] for r in records if (r["scan_id"],r["bscan"]) in old_keys],
        historical_rows=old, note="Historical scores frozen verbatim. Current label hashes are September 8 revisions; September 2 hashes were not recorded, so historical label identity cannot be certified."))
    print(json.dumps(summary, indent=2))
    if failures or summary["missing_decisions"]:
        raise RuntimeError("Audit incomplete; inspect census before training")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=DEFAULT)
    audit(p.parse_args().out)
