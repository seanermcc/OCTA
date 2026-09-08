#!/usr/bin/env python3
"""Build lesion-centred eight-boundary review packs from en-face CNV masks.

Run from ``code`` after CNV footprint labels have been saved::

    python eight_surface/cnv_review.py

The output packs remain compatible with ``eight_surface/label_gui.py`` and add
explicit zone arrays and selection roles.  They never alter the independent
CNV masks or existing surface labels.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from octa.volio import ProcessedVolume  # noqa: E402

from eight_surface import cnv_labels as CL  # noqa: E402
from eight_surface.config import CASCADE_VERSION, SURFACE_NAMES  # noqa: E402
from eight_surface.segment import prepare_bscan  # noqa: E402


ZONE_NAMES = ("remote", "nearby", "rim", "core")
ZONE_REMOTE, ZONE_NEARBY, ZONE_RIM, ZONE_CORE = range(4)
DEFAULT_CNV_LABELS = Path("../outputs/cnv_labels")
DEFAULT_SEGMENTED = Path("../outputs/eight_surface/segmented")
DEFAULT_OUT = Path("../outputs/eight_surface/cnv_review")


def lesion_zones(mask: np.ndarray, bscan_um: float, aline_um: float,
                 rim_um: float = 75.0,
                 nearby_um: float = 250.0) -> tuple[np.ndarray, dict]:
    """Classify every native pixel as core, rim, nearby, or remote.

    The inner rim adapts to small lesions so a real footprint never loses its
    core entirely.  Outside distances retain the requested physical widths.
    """
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("CNV mask must be [B-scan, A-line]")
    if rim_um <= 0 or nearby_um <= rim_um:
        raise ValueError("require 0 < rim_um < nearby_um")
    if bscan_um <= 0 or aline_um <= 0:
        raise ValueError("pixel spacing must be positive")
    zones = np.full(mask.shape, ZONE_REMOTE, dtype=np.uint8)
    if not mask.any():
        return zones, {"inner_rim_um": 0.0, "max_inside_um": 0.0}

    sampling = (float(bscan_um), float(aline_um))
    inside = distance_transform_edt(mask, sampling=sampling)
    outside = distance_transform_edt(~mask, sampling=sampling)
    max_inside = float(inside.max())
    # Preserve a meaningful core for lesions narrower than 2*rim_um.
    inner_rim = min(float(rim_um), max_inside * 0.5)

    zones[(~mask) & (outside <= nearby_um)] = ZONE_NEARBY
    zones[(~mask) & (outside <= rim_um)] = ZONE_RIM
    zones[mask] = ZONE_RIM
    zones[mask & (inside > inner_rim)] = ZONE_CORE
    return zones, {"inner_rim_um": inner_rim,
                   "max_inside_um": max_inside}


def _spread_pick(candidates: np.ndarray, scores: np.ndarray, n: int,
                 min_sep: int, used: set[int]) -> list[int]:
    candidates = np.asarray(candidates, dtype=int)
    if n <= 0 or candidates.size == 0:
        return []
    order = candidates[np.argsort(-np.asarray(scores, dtype=float))]
    picked: list[int] = []
    for row in order:
        row = int(row)
        if row in used or any(abs(row - old) < min_sep for old in picked):
            continue
        picked.append(row)
        if len(picked) == n:
            break
    # Preserve requested coverage when the volume/zone cannot satisfy the
    # within-role separation. Cross-role proximity is intentional at a rim.
    for row in order:
        row = int(row)
        if row not in used and row not in picked:
            picked.append(row)
        if len(picked) == n:
            break
    used.update(picked)
    return picked


def select_bscans(mask: np.ndarray, zones: np.ndarray, *,
                  bscan_um: float, aline_um: float,
                  n_core: int = 3, n_rim: int = 2,
                  n_nearby: int = 2, n_remote: int = 2,
                  min_sep: int = 12) -> list[tuple[int, str]]:
    """Choose spatially distinct lesion-centred cross-sections."""
    mask = np.asarray(mask, dtype=bool)
    zones = np.asarray(zones, dtype=np.uint8)
    if mask.shape != zones.shape:
        raise ValueError("mask and zones must have the same shape")
    if not mask.any():
        return []
    sampling = (float(bscan_um), float(aline_um))
    inside = distance_transform_edt(mask, sampling=sampling)
    outside = distance_transform_edt(~mask, sampling=sampling)
    used: set[int] = set()
    result: list[tuple[int, str]] = []

    core_candidates = np.flatnonzero(np.any(zones == ZONE_CORE, axis=1))
    if not core_candidates.size:
        core_candidates = np.flatnonzero(mask.any(axis=1))
    core_scores = inside[core_candidates].max(axis=1)
    for row in _spread_pick(core_candidates, core_scores, n_core, min_sep, used):
        result.append((row, "core"))

    lesion_rows = np.flatnonzero(mask.any(axis=1))
    # Narrow cross-sections sit nearest the leading/trailing footprint rim.
    rim_scores = -mask[lesion_rows].sum(axis=1).astype(float)
    for row in _spread_pick(lesion_rows, rim_scores, n_rim, min_sep, used):
        result.append((row, "rim"))

    nonlesion = ~mask.any(axis=1)
    nearby_candidates = np.flatnonzero(
        nonlesion & np.any((zones == ZONE_NEARBY) | (zones == ZONE_RIM), axis=1))
    near_dist = outside[nearby_candidates].min(axis=1)
    for row in _spread_pick(
            nearby_candidates, -near_dist, n_nearby, min_sep, used):
        result.append((row, "nearby"))

    remote_candidates = np.flatnonzero(
        nonlesion & (np.mean(zones == ZONE_REMOTE, axis=1) >= 0.90))
    remote_dist = outside[remote_candidates].min(axis=1)
    for row in _spread_pick(
            remote_candidates, remote_dist, n_remote, min_sep, used):
        result.append((row, "remote"))

    return sorted(result)


def _load_segmentation(path: Path, cnv: dict) -> dict:
    with np.load(path, allow_pickle=False) as data:
        names = [str(x) for x in data["surface_names"]]
        version = str(data["cascade_version"][0])
        if names != SURFACE_NAMES or version != CASCADE_VERSION:
            raise ValueError(
                f"{path.name} is not the current {CASCADE_VERSION} eight-boundary output")
        scan_id = str(data["scan_id"][0])
        if scan_id != cnv["scan_id"]:
            raise ValueError(f"scan ID mismatch: label={cnv['scan_id']} segmentation={scan_id}")
        surfaces = data["surfaces"].astype(np.float32)
        confidence = (data["confidence"].astype(np.float32)
                      if "confidence" in data.files
                      else np.full(surfaces.shape, np.nan, dtype=np.float32))
        shadow = data["shadow"].astype(bool)
        source = Path(str(data["source"][0]))
        stored_band = (tuple(int(x) for x in data["retina_band"])
                       if "retina_band" in data.files else None)
        px_um = float(data["px_um"][0]) if "px_um" in data.files else 1.12
    if surfaces.shape[0:1] + surfaces.shape[2:3] != cnv["native_shape"]:
        raise ValueError(
            f"segmentation grid {(surfaces.shape[0], surfaces.shape[2])} does not "
            f"match CNV mask {cnv['native_shape']}")
    if stored_band is not None and stored_band != cnv["retina_band"]:
        raise ValueError(
            f"retina-band mismatch: label={cnv['retina_band']} segmentation={stored_band}")
    if not source.is_file():
        raise FileNotFoundError(f"source volume not found: {source}")
    return {"surfaces": surfaces, "confidence": confidence, "shadow": shadow,
            "source": source, "px_um": px_um}


def write_pack(cnv: dict, segmentation_path: Path, out_dir: Path, args) -> tuple[Path, list[dict]]:
    zones, zone_info = lesion_zones(
        cnv["cnv_mask"], cnv["bscan_um"], cnv["aline_um"],
        rim_um=args.rim_um, nearby_um=args.nearby_um)
    selected = select_bscans(
        cnv["cnv_mask"], zones,
        bscan_um=cnv["bscan_um"], aline_um=cnv["aline_um"],
        n_core=args.n_core, n_rim=args.n_rim, n_nearby=args.n_nearby,
        n_remote=args.n_remote, min_sep=args.min_sep)
    if not selected:
        raise ValueError("reviewed label contains no CNV footprint")
    seg = _load_segmentation(segmentation_path, cnv)
    picked = np.array([row for row, _role in selected], dtype=np.int32)
    roles = np.array([role for _row, role in selected])
    lo, hi = cnv["retina_band"]
    # One bulk crop read: never fetch selected B-scans in a loop from HDF5.
    with ProcessedVolume(seg["source"]) as volume:
        structural = volume.read_volume(
            channel="struct", depth_slice=slice(lo, hi))
    images = np.stack([
        prepare_bscan(structural[int(row)], cnv["vitreous_at_high_index"])
        for row in picked
    ]).astype(np.float32)

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{cnv['scan_id']}_cnv_pack.npz"
    if out.exists() and not args.overwrite:
        raise FileExistsError(f"{out} already exists; use --overwrite to replace it")
    np.savez_compressed(
        out,
        images=images,
        surfaces=seg["surfaces"][picked].astype(np.float32),
        confidence=seg["confidence"][picked].astype(np.float16),
        shadow=seg["shadow"][picked].astype(bool),
        picked=picked,
        bscan_index=picked,
        is_control=(roles == "remote"),
        suspect_score=np.full(picked.size, np.nan, dtype=np.float32),
        surface_names=np.array(SURFACE_NAMES),
        cascade_version=np.array([CASCADE_VERSION]),
        scan_id=np.array([cnv["scan_id"]]),
        px_um=np.array([seg["px_um"]], dtype=np.float32),
        selection_role=roles,
        lesion_zone=zones[picked].astype(np.uint8),
        zone_names=np.array(ZONE_NAMES),
        cnv_mask_rows=cnv["cnv_mask"][picked].astype(bool),
        source_cnv_label=np.array([str(cnv["path"])]),
        cnv_label_format_version=np.array([cnv["label_format_version"]]),
        rim_um=np.array([args.rim_um], dtype=np.float32),
        effective_inner_rim_um=np.array(
            [zone_info["inner_rim_um"]], dtype=np.float32),
        nearby_um=np.array([args.nearby_um], dtype=np.float32),
        bscan_um=np.array([cnv["bscan_um"]], dtype=np.float32),
        aline_um=np.array([cnv["aline_um"]], dtype=np.float32),
    )
    manifest = []
    for item, role in selected:
        counts = {name: int(np.sum(zones[item] == code))
                  for code, name in enumerate(ZONE_NAMES)}
        manifest.append({
            "scan_id": cnv["scan_id"], "bscan": item,
            "selection_role": role, "pack_file": out.name,
            "core_alines": counts["core"], "rim_alines": counts["rim"],
            "nearby_alines": counts["nearby"],
            "remote_alines": counts["remote"],
            "cnv_label_file": cnv["path"].name,
        })
    return out, manifest


def _segmentation_for(cnv: dict, segmented_dir: Path) -> Path:
    stored = Path(cnv.get("source_segmentation") or "")
    if stored.is_file():
        return stored
    candidate = segmented_dir / f"{cnv['scan_id']}.npz"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(
        f"no eight-boundary segmentation for {cnv['scan_id']} in {segmented_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cnv-labels", default=str(DEFAULT_CNV_LABELS))
    parser.add_argument("--segmented", default=str(DEFAULT_SEGMENTED))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--scan-id", action="append", default=[])
    parser.add_argument("--n-core", type=int, default=3)
    parser.add_argument("--n-rim", type=int, default=2)
    parser.add_argument("--n-nearby", type=int, default=2)
    parser.add_argument("--n-remote", type=int, default=2)
    parser.add_argument("--rim-um", type=float, default=75.0)
    parser.add_argument("--nearby-um", type=float, default=250.0)
    parser.add_argument("--min-sep", type=int, default=12)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if min(args.n_core, args.n_rim, args.n_nearby, args.n_remote) < 0:
        parser.error("selection counts cannot be negative")
    if args.min_sep < 1:
        parser.error("--min-sep must be positive")

    records = CL.load_labels(args.cnv_labels)
    if args.scan_id:
        wanted = {item.lower() for item in args.scan_id}
        records = [record for record in records
                   if record["scan_id"].lower() in wanted]
    if not records:
        print(f"no compatible CNV labels in {args.cnv_labels}")
        return 1

    out_dir = Path(args.out_dir)
    all_manifest: list[dict] = []
    written = skipped = failed = 0
    for number, cnv in enumerate(records, 1):
        print(f"[{number}/{len(records)}] {cnv['scan_id']}")
        if not cnv["reviewed"]:
            print("  skipped: footprint has not been marked reviewed")
            skipped += 1
            continue
        if not cnv["lesion_present"] or not cnv["cnv_mask"].any():
            print("  skipped: reviewed as no CNV footprint")
            skipped += 1
            continue
        try:
            seg_path = _segmentation_for(cnv, Path(args.segmented))
            path, rows = write_pack(cnv, seg_path, out_dir, args)
            all_manifest.extend(rows)
            written += 1
            counts = {role: sum(row["selection_role"] == role for row in rows)
                      for role in ZONE_NAMES[::-1]}
            print(f"  {len(rows)} B-scans {counts} -> {path.name}")
        except FileExistsError as exc:
            print(f"  skipped: {exc}")
            skipped += 1
        except Exception as exc:  # noqa: BLE001 - continue auditing other scans
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            failed += 1

    if all_manifest:
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = out_dir / "cnv_review_manifest.csv"
        fields = ["scan_id", "bscan", "selection_role", "pack_file",
                  "core_alines", "rim_alines", "nearby_alines",
                  "remote_alines", "cnv_label_file"]
        with manifest_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_manifest)
        print(f"manifest: {manifest_path}")
    print(f"done: {written} pack(s) written, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

