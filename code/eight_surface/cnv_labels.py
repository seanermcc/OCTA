"""Versioned en-face CNV, vasculature, and ONH labels.

The authoritative annotation is a boolean mask in the acquisition's native
``[B-scan, A-line]`` grid for each class.  Per-class review flags distinguish
"looked and absent" from "not labelled."  The file deliberately contains no
retinal surfaces and no segmentation-derived thickness values.  A source
segmentation path is stored only as provenance and as the bridge to later
lesion-centred review packs.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import numpy as np


CNV_LABEL_FORMAT_VERSION = "4-enface-vessel-proposals"
V3_CNV_LABEL_FORMAT_VERSION = "3-enface-multiclass-brush"
V2_CNV_LABEL_FORMAT_VERSION = "2-enface-footprint-onh-edge"
LEGACY_CNV_LABEL_FORMAT_VERSION = "1-enface-footprint"
PROJECTION_VERSION = "1-retina-band-mean-db"
LABEL_SUFFIX = "_cnv.npz"
FIELD_UM = 1460.0
ANNOTATION_NAMES = ("CNV", "VASCULATURE", "ONH")


def label_path(label_dir: str | Path, scan_id: str) -> Path:
    return Path(label_dir) / f"{scan_id}{LABEL_SUFFIX}"


def _scalar(data, key: str, conv, default=None):
    if key not in data.files:
        return default
    return conv(data[key][0])


def save_label(
    label_dir: str | Path,
    *,
    scan_id: str,
    cnv_mask: np.ndarray,
    vasculature_mask: np.ndarray | None = None,
    onh_mask: np.ndarray | None = None,
    onh_edge_mask: np.ndarray | None = None,
    source_volume: str | Path,
    source_segmentation: str | Path,
    retina_band: tuple[int, int] | list[int] | np.ndarray,
    vitreous_at_high_index: bool,
    animal: str = "",
    eye: str = "",
    day_label: str = "",
    days_post_laser: str = "",
    session_date: str = "",
    labeller: str = "",
    notes: str = "",
    reviewed: bool = True,
    reviewed_targets: np.ndarray | list[bool] | tuple[bool, ...] | None = None,
    field_um: float = FIELD_UM,
    vasculature_proposal_path: str = "",
    vasculature_proposal_sha256: str = "",
    vasculature_initial_mask: np.ndarray | None = None,
    vasculature_brush_touched: np.ndarray | None = None,
) -> Path:
    """Atomically write one multi-class en-face label.

    ``reviewed`` remains the CNV-review flag for compatibility with the lesion
    pack builder.  New callers should also pass ``reviewed_targets`` in
    ``ANNOTATION_NAMES`` order so that empty vessel/ONH masks are meaningful.
    """
    mask = np.asarray(cnv_mask, dtype=bool)
    if mask.ndim != 2 or min(mask.shape) < 1:
        raise ValueError("cnv_mask must be a non-empty [B-scan, A-line] array")

    def checked_mask(value, name):
        result = (np.zeros(mask.shape, dtype=bool) if value is None
                  else np.asarray(value, dtype=bool))
        if result.shape != mask.shape:
            raise ValueError(f"{name} must have the same shape as cnv_mask")
        return result

    vasculature = checked_mask(vasculature_mask, "vasculature_mask")
    initial_vessels = checked_mask(vasculature_initial_mask, "vasculature_initial_mask")
    touched_vessels = checked_mask(vasculature_brush_touched, "vasculature_brush_touched")
    if vasculature_proposal_path and (
            vasculature_initial_mask is None or len(vasculature_proposal_sha256) != 64
            or any(c not in "0123456789abcdef" for c in vasculature_proposal_sha256)):
        raise ValueError("An automatic vessel seed needs its initial mask and SHA-256 provenance")
    onh = checked_mask(onh_mask, "onh_mask")
    onh_edge = checked_mask(onh_edge_mask, "onh_edge_mask")
    if reviewed_targets is None:
        target_reviewed = np.array(
            [bool(reviewed), bool(vasculature.any()) and not vasculature_proposal_path,
             bool(onh.any() or onh_edge.any())], dtype=bool)
    else:
        target_reviewed = np.asarray(reviewed_targets, dtype=bool)
        if target_reviewed.shape != (len(ANNOTATION_NAMES),):
            raise ValueError(
                f"reviewed_targets must have {len(ANNOTATION_NAMES)} values in "
                "CNV, VASCULATURE, ONH order")
        # The historical scalar is still authoritative to old CNV consumers.
        reviewed = bool(target_reviewed[0])
    band = np.asarray(retina_band, dtype=np.int32)
    if band.shape != (2,) or int(band[1]) <= int(band[0]):
        raise ValueError("retina_band must be [lo, hi] with hi > lo")
    if not scan_id or any(char in scan_id for char in "\\/:"):
        raise ValueError("scan_id is empty or contains path separators")
    field_um = float(field_um)
    if not np.isfinite(field_um) or field_um <= 0:
        raise ValueError("field_um must be positive and finite")

    out = label_path(label_dir, scan_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    revision = 1
    if out.exists():
        try:
            with np.load(out, allow_pickle=False) as prior:
                revision = int(_scalar(prior, "revision", int, 0)) + 1
        except Exception:
            revision = 1

    # np.savez appends .npz unless the temporary name already ends with it.
    temp = out.with_name(out.stem + ".writing.npz")
    np.savez_compressed(
        temp,
        cnv_mask=mask,
        vasculature_mask=vasculature,
        vasculature_origin=np.array(["automatic_proposal" if vasculature_proposal_path else "manual"]),
        vasculature_proposal_path=np.array([str(vasculature_proposal_path)]),
        vasculature_proposal_sha256=np.array([str(vasculature_proposal_sha256)]),
        vasculature_initial_mask=initial_vessels,
        vasculature_brush_touched=touched_vessels,
        vasculature_edit_provenance=np.array(["brush footprint recorded from label format 4 onward"]),
        onh_mask=onh,
        onh_edge_mask=onh_edge,
        scan_id=np.array([scan_id]),
        animal=np.array([animal]),
        eye=np.array([eye]),
        day_label=np.array([day_label]),
        days_post_laser=np.array([days_post_laser]),
        session_date=np.array([session_date]),
        source_volume=np.array([str(Path(source_volume))]),
        source_segmentation=np.array([str(Path(source_segmentation))]),
        native_shape=np.asarray(mask.shape, dtype=np.int32),
        retina_band=band,
        vitreous_at_high_index=np.array([bool(vitreous_at_high_index)]),
        field_um=np.array([field_um], dtype=np.float32),
        bscan_um=np.array([field_um / mask.shape[0]], dtype=np.float32),
        aline_um=np.array([field_um / mask.shape[1]], dtype=np.float32),
        reviewed=np.array([bool(reviewed)]),
        annotation_names=np.array(ANNOTATION_NAMES),
        reviewed_targets=target_reviewed,
        lesion_present=np.array([bool(mask.any())]),
        lesion_pixel_count=np.array([int(mask.sum())], dtype=np.int64),
        vasculature_present=np.array([bool(vasculature.any())]),
        vasculature_pixel_count=np.array([int(vasculature.sum())], dtype=np.int64),
        onh_present=np.array([bool(onh.any())]),
        onh_pixel_count=np.array([int(onh.sum())], dtype=np.int64),
        onh_edge_present=np.array([bool(onh_edge.any())]),
        onh_edge_pixel_count=np.array([int(onh_edge.sum())], dtype=np.int64),
        labeller=np.array([labeller or os.environ.get("USERNAME") or
                           os.environ.get("USER") or ""]),
        notes=np.array([notes]),
        projection_version=np.array([PROJECTION_VERSION]),
        structural_projection=np.array(["mean dB across detected retina band"]),
        octa_projection=np.array(["mean dB across detected retina band"]),
        label_format_version=np.array([CNV_LABEL_FORMAT_VERSION]),
        revision=np.array([revision], dtype=np.int32),
        labelled_at=np.array([dt.datetime.now().isoformat(timespec="seconds")]),
    )
    temp.replace(out)
    return out


def load_label(path: str | Path) -> dict:
    path = Path(path)
    with np.load(path, allow_pickle=False) as data:
        version = _scalar(data, "label_format_version", str, "unknown")
        if version not in (
                CNV_LABEL_FORMAT_VERSION, V3_CNV_LABEL_FORMAT_VERSION, V2_CNV_LABEL_FORMAT_VERSION,
                LEGACY_CNV_LABEL_FORMAT_VERSION):
            raise ValueError(
                f"{path.name} has CNV label format {version!r}; expected "
                f"{CNV_LABEL_FORMAT_VERSION!r}")
        mask = np.asarray(data["cnv_mask"], dtype=bool)
        native = tuple(int(x) for x in data["native_shape"])
        if mask.ndim != 2 or mask.shape != native:
            raise ValueError(
                f"{path.name} mask shape {mask.shape} does not match native_shape {native}")
        if "onh_edge_mask" in data.files:
            onh_edge = np.asarray(data["onh_edge_mask"], dtype=bool)
            if onh_edge.shape != native:
                raise ValueError(
                    f"{path.name} ONH edge shape {onh_edge.shape} does not match "
                    f"native_shape {native}")
        else:
            # V1 had no ONH annotation. It remains fully usable and will be
            # upgraded only when the reviewer next saves it in the GUI.
            onh_edge = np.zeros(native, dtype=bool)
        vasculature = (np.asarray(data["vasculature_mask"], dtype=bool)
                       if "vasculature_mask" in data.files
                       else np.zeros(native, dtype=bool))
        onh = (np.asarray(data["onh_mask"], dtype=bool)
               if "onh_mask" in data.files else np.zeros(native, dtype=bool))
        for name, value in (("vasculature_mask", vasculature),
                            ("onh_mask", onh)):
            if value.shape != native:
                raise ValueError(
                    f"{path.name} {name} shape {value.shape} does not match "
                    f"native_shape {native}")
        vessel_provenance = {}
        for key in ("vasculature_initial_mask", "vasculature_brush_touched"):
            value = (np.asarray(data[key], dtype=bool) if key in data.files
                     else np.zeros(native, dtype=bool))
            if value.shape != native:
                raise ValueError(f"{path.name} has incompatible {key} shape")
            vessel_provenance[key] = value
        if "reviewed_targets" in data.files:
            names = ([str(x) for x in data["annotation_names"]]
                     if "annotation_names" in data.files else [])
            values = np.asarray(data["reviewed_targets"], dtype=bool)
            if names != list(ANNOTATION_NAMES) or values.shape != (
                    len(ANNOTATION_NAMES),):
                raise ValueError(
                    f"{path.name} has incompatible annotation review fields")
            reviewed_targets = values
        else:
            cnv_reviewed = _scalar(data, "reviewed", bool, False)
            # A legacy positive ONH edge is affirmative evidence that ONH was
            # inspected.  A missing/empty edge says nothing about absence.
            reviewed_targets = np.array(
                [cnv_reviewed, False, bool(onh_edge.any())], dtype=bool)
        out = {
            "path": path,
            "cnv_mask": mask,
            "vasculature_mask": vasculature,
            "onh_mask": onh,
            "onh_edge_mask": onh_edge,
            "annotation_names": ANNOTATION_NAMES,
            "reviewed_targets": reviewed_targets,
            "scan_id": _scalar(data, "scan_id", str, ""),
            "source_volume": _scalar(data, "source_volume", str, ""),
            "source_segmentation": _scalar(data, "source_segmentation", str, ""),
            "native_shape": native,
            "retina_band": tuple(int(x) for x in data["retina_band"]),
            "vitreous_at_high_index": _scalar(
                data, "vitreous_at_high_index", bool, False),
            "label_format_version": version,
            **vessel_provenance,
        }
        for key, conv, default in (
            ("animal", str, ""),
            ("eye", str, ""),
            ("day_label", str, ""),
            ("days_post_laser", str, ""),
            ("session_date", str, ""),
            ("field_um", float, FIELD_UM),
            ("bscan_um", float, FIELD_UM / mask.shape[0]),
            ("aline_um", float, FIELD_UM / mask.shape[1]),
            ("reviewed", bool, False),
            ("lesion_present", bool, bool(mask.any())),
            ("lesion_pixel_count", int, int(mask.sum())),
            ("vasculature_present", bool, bool(vasculature.any())),
            ("vasculature_pixel_count", int, int(vasculature.sum())),
            ("onh_present", bool, bool(onh.any())),
            ("onh_pixel_count", int, int(onh.sum())),
            ("onh_edge_present", bool, bool(onh_edge.any())),
            ("onh_edge_pixel_count", int, int(onh_edge.sum())),
            ("labeller", str, ""),
            ("notes", str, ""),
            ("projection_version", str, "unknown"),
            ("structural_projection", str, ""),
            ("octa_projection", str, ""),
            ("revision", int, 0),
            ("labelled_at", str, ""),
            ("vasculature_origin", str, "manual"),
            ("vasculature_proposal_path", str, ""),
            ("vasculature_proposal_sha256", str, ""),
            ("vasculature_edit_provenance", str, "unavailable in legacy label"),
        ):
            out[key] = _scalar(data, key, conv, default)
    if out["scan_id"] and label_path(path.parent, out["scan_id"]).name != path.name:
        raise ValueError(f"{path.name} does not match stored scan_id {out['scan_id']!r}")
    return out


def load_labels(label_dir: str | Path) -> list[dict]:
    records = []
    for path in sorted(Path(label_dir).glob(f"*{LABEL_SUFFIX}")):
        try:
            records.append(load_label(path))
        except Exception as exc:  # noqa: BLE001 - audit every incompatible file
            print(f"skipping unreadable/incompatible CNV label {path.name}: {exc}")
    return records
