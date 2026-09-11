"""Read-only adapters for existing data and isolated region-review storage."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.ndimage import label as components

from eight_surface import cnv_labels as CL, labels as SL
from eight_surface.config import SURFACE_NAMES, CASCADE_VERSION
from eight_surface.vasculature_proposals import has_saved_vessel_work, load_proposal

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/cnv_review_v1"
COHORT = ROOT / "outputs/stage_a/20260909_full_labeled_cohort"
CATEGORIES = ("Unclassified", "Full Lesion", "Normal", "Other")


def scalar(data, key, default=None):
    return np.asarray(data[key]).reshape(-1)[0].item() if key in data else default


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def runs(mask):
    edges = np.flatnonzero(np.diff(np.r_[False, np.asarray(mask, bool), False]))
    return list(zip(edges[::2].tolist(), edges[1::2].tolist()))


def encode_mask(mask):
    return [[int(row), lo, hi] for row in range(mask.shape[0]) for lo, hi in runs(mask[row])]


def decode_mask(encoded, shape):
    mask = np.zeros(shape, bool)
    for row, lo, hi in encoded:
        if not (0 <= row < shape[0] and 0 <= lo < hi <= shape[1]):
            raise ValueError("Region footprint is outside the native image grid")
        mask[row, lo:hi] = True
    return mask


@dataclass
class Region:
    id: str
    mask: np.ndarray
    category: str = "Unclassified"
    notes: str = ""
    origin: str = "drawn in lesion review GUI"

    @property
    def complete(self):
        return self.category != "Unclassified" and (self.category != "Other" or bool(self.notes.strip()))

    def record(self):
        return dict(id=self.id, runs=encode_mask(self.mask), category=self.category,
                    notes=self.notes, origin=self.origin, classification_complete=self.complete,
                    bscan_indices=np.flatnonzero(self.mask.any(axis=1)).tolist())


class RegionStore:
    """Only called by GUI actions; opening an imported mask creates no labels."""
    def __init__(self, directory, scan, existing_mask, seed_path=""):
        self.path = Path(directory) / f"{scan.scan_id}_regions.json"
        self.scan = scan
        self.regions = []
        self.revision = 0
        self.seed_path = str(seed_path)
        self.seed_sha256 = fingerprint(seed_path) if seed_path else None
        self.disk_hash = fingerprint(self.path)
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (data.get("format") != "1-cnv-region-review" or data["scan_id"] != scan.scan_id
                    or tuple(data["native_shape"]) != scan.native_shape
                    or Path(data["source_volume"]).resolve() != scan.source_volume.resolve()):
                raise ValueError("Saved region review does not match this scan")
            self.revision = int(data["revision"])
            self.seed_path = data.get("seed_path", "")
            self.seed_sha256 = data.get("seed_sha256")
            for record in data["regions"]:
                if record["category"] not in CATEGORIES:
                    raise ValueError("Unknown saved lesion category")
                self.regions.append(Region(record["id"], decode_mask(record["runs"], scan.native_shape),
                                           record["category"], record["notes"], record["origin"]))
        else:
            labels, count = components(existing_mask)
            for i in range(1, count + 1):
                mask = labels == i
                # Deterministic identity across browsing sessions until first GUI save.
                uid = hashlib.sha256(scan.scan_id.encode() + mask.tobytes()).hexdigest()[:12]
                self.regions.append(Region(uid, mask, origin="existing CNV outline; category not assigned"))
        self.saved_signature = self.signature()

    def signature(self):
        return json.dumps([r.record() for r in self.regions], sort_keys=True)

    @property
    def dirty(self):
        return self.signature() != self.saved_signature

    def save(self, auto_source, surface_sources, vessel_source):
        if not self.dirty:
            return False
        if fingerprint(self.path) != self.disk_hash:
            raise RuntimeError("Region file changed in another window. Your edits remain in this window; close the other reviewer before resolving the conflict.")
        data = dict(format="1-cnv-region-review", scan_id=self.scan.scan_id,
                    source_volume=str(self.scan.source_volume.resolve()), native_shape=list(self.scan.native_shape),
                    axis_order="B-scan,A-line", category_names=list(CATEGORIES[1:]),
                    revision=self.revision + 1, saved_at=datetime.now(timezone.utc).isoformat(),
                    seed_path=self.seed_path, seed_sha256=self.seed_sha256,
                    auto_source=auto_source, surface_sources=surface_sources, vessel_source=vessel_source,
                    regions=[r.record() for r in self.regions])
        if self.path.exists():
            history = self.path.parent / "history" / f"{self.path.stem}_r{self.revision:04d}.json"
            if not history.exists():
                atomic_json(history, json.loads(self.path.read_text(encoding="utf-8")))
        atomic_json(self.path, data)
        self.revision += 1
        self.disk_hash = fingerprint(self.path)
        self.saved_signature = self.signature()
        return True


def load_enface(scan, label_dir, proposals_dir):
    path = CL.label_path(label_dir, scan.scan_id)
    record = CL.load_label(path) if path.exists() else None
    blank = np.zeros(scan.native_shape, bool)
    if record is not None:
        if (record["native_shape"] != scan.native_shape or record["scan_id"] != scan.scan_id
                or Path(record["source_volume"]).resolve() != scan.source_volume.resolve()):
            raise ValueError(f"En-face annotation source/grid mismatch: {path}")
    cnv = record["cnv_mask"] if record is not None else blank.copy()
    onh = record["onh_mask"] if record is not None else blank.copy()
    edge = record["onh_edge_mask"] if record is not None else blank.copy()
    if has_saved_vessel_work(record):
        vessel = record["vasculature_mask"]
        status = "saved vessel mask" + (" — reviewed" if record["reviewed_targets"][1] else " — draft, not fully reviewed")
        provenance = dict(path=str(path.resolve()), sha256=fingerprint(path), status=status,
                          origin=record.get("vasculature_origin", "manual"))
    else:
        proposal = load_proposal(proposals_dir, scan)
        vessel = proposal["mask"] if proposal else blank.copy()
        status = "automatic vessel proposal — unreviewed" if proposal else "no vessel mask available"
        provenance = dict(path=proposal["path"] if proposal else "", sha256=proposal["sha256"] if proposal else None, status=status)
    return cnv, vessel, onh, edge, provenance, str(path) if record is not None else ""


class SurfaceIndex:
    def __init__(self, roots):
        self.roots = [Path(p) for p in roots]
        self.records = {}

    def refresh(self, scan):
        records = {}
        for root in self.roots:
            for path in sorted(root.glob(f"{scan.scan_id}_b*.npz")):
                record = SL.load_label(path)
                row = int(record["bscan"])
                if (record["scan_id"] != scan.scan_id or tuple(record["surface_names"]) != scan.surface_names
                        or record.get("cascade_version") != CASCADE_VERSION
                        or record["surfaces"].shape != scan.surfaces.shape[1:]
                        or not 0 <= row < scan.native_shape[0]):
                    raise ValueError(f"Manual boundary file does not match this volume: {path}")
                # Explicit source precedence; do not infer precedence from copied mtimes.
                records.setdefault(row, (path, record))
        self.records = records

    def footprint(self, row, width):
        pair = self.records.get(row)
        if not pair:
            return np.zeros(width, bool)
        record = pair[1]
        if record.get("local_provenance_available"):
            return record["local_drawn"].any(axis=0)
        return np.zeros(width, bool)  # legacy drawing location is unknown


class AutoSource:
    """Priority-ordered providers; replacement failures never silently use old data."""
    def __init__(self, sources):
        self.sources = sources

    def load(self, scan):
        for source in self.sources:
            directory = Path(source["directory"])
            matches = [directory / f"{scan.scan_id}{suffix}" for suffix in ("_pack.npz", ".npz")]
            path = next((p for p in matches if p.exists()), None)
            if path is None:
                continue
            with np.load(path, allow_pickle=False) as d:
                if (scalar(d, "scan_id") != scan.scan_id
                        or tuple(str(n) for n in d["surface_names"]) != scan.surface_names
                        or scalar(d, "cascade_version") != CASCADE_VERSION):
                    raise ValueError(f"Automatic source ID/boundary contract mismatch: {path}")
                src = scalar(d, "source", scalar(d, "source_volume", ""))
                if not src or Path(src).resolve() != scan.source_volume.resolve():
                    raise ValueError(f"Automatic source volume mismatch: {path}")
                surfaces = np.array(d["surfaces"], dtype=np.float32)
                if surfaces.shape != scan.surfaces.shape:
                    raise ValueError(f"Automatic source must cover the full native volume: {path}")
                if "bscan_index" in d and not np.array_equal(d["bscan_index"], np.arange(scan.native_shape[0])):
                    raise ValueError(f"Automatic source B-scan rows are not in native order: {path}")
                if "retina_band" in d:
                    if tuple(d["retina_band"]) != scan.retina_band:
                        raise ValueError(f"Automatic crop differs from the displayed image: {path}")
                elif "label_offset" in d:
                    # Full-volume exports store the canonical full-depth start.
                    with np.load(scan.segmentation_path, allow_pickle=False) as base:
                        depth = int(base["shape"][2])
                    expected = depth - scan.retina_band[1] if scan.vitreous_at_high_index else scan.retina_band[0]
                    if int(scalar(d, "label_offset")) != expected:
                        raise ValueError(f"Automatic canonical crop offset mismatch: {path}")
                else:
                    raise ValueError(f"Automatic source needs retina_band or label_offset: {path}")
                confidence = (np.array(d["confidence"], dtype=np.float32) if "confidence" in d
                              else np.full_like(surfaces, np.nan))
                if confidence.shape != surfaces.shape:
                    raise ValueError(f"Automatic confidence grid mismatch: {path}")
                # These model confidence values are not the classical local-confidence scale.
                if "prediction_checkpoint" in d:
                    confidence[:] = np.nan
                meta = dict(name=source["name"], path=str(path.resolve()), bytes=path.stat().st_size,
                            mtime_ns=path.stat().st_mtime_ns,
                            checkpoint=str(scalar(d, "prediction_checkpoint", "")))
                return surfaces, confidence, meta
        raise FileNotFoundError(f"No compatible full-volume automatic boundaries for {scan.scan_id}")


def default_config():
    return dict(segmentations=str(ROOT / "outputs/eight_surface/segmented"),
                enface_labels=str(ROOT / "outputs/cnv_labels"),
                proposals=str(ROOT / "outputs/eight_surface/vasculature_proposals"),
                output=str(OUT),
                manual_sources=[str(COHORT / "manual_review_36/labels"), str(ROOT / "outputs/eight_surface/labels")],
                auto_sources=[dict(name="Full-cohort model • 2026-09-09 (experimental)", directory=str(COHORT / "full_volume_review/packs")),
                              dict(name="Eight-boundary cascade • existing fallback", directory=str(ROOT / "outputs/eight_surface/segmented"))])
