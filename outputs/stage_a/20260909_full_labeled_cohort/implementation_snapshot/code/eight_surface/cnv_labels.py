"""Versioned en-face CNV and ONH-edge labels, independent of surface labels.

The authoritative annotation is a boolean mask in the acquisition's native
``[B-scan, A-line]`` grid.  It deliberately contains no retinal surfaces and
no segmentation-derived thickness values.  A source segmentation path is
stored only as provenance and as the bridge to later lesion-centred review
packs.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import numpy as np


CNV_LABEL_FORMAT_VERSION = "2-enface-footprint-onh-edge"
LEGACY_CNV_LABEL_FORMAT_VERSION = "1-enface-footprint"
PROJECTION_VERSION = "1-retina-band-mean-db"
LABEL_SUFFIX = "_cnv.npz"
FIELD_UM = 1460.0


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
    field_um: float = FIELD_UM,
) -> Path:
    """Atomically write one reviewed en-face footprint label."""
    mask = np.asarray(cnv_mask, dtype=bool)
    if mask.ndim != 2 or min(mask.shape) < 1:
        raise ValueError("cnv_mask must be a non-empty [B-scan, A-line] array")
    if onh_edge_mask is None:
        onh_edge = np.zeros(mask.shape, dtype=bool)
    else:
        onh_edge = np.asarray(onh_edge_mask, dtype=bool)
        if onh_edge.shape != mask.shape:
            raise ValueError("onh_edge_mask must have the same shape as cnv_mask")
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
        lesion_present=np.array([bool(mask.any())]),
        lesion_pixel_count=np.array([int(mask.sum())], dtype=np.int64),
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
        if version not in (CNV_LABEL_FORMAT_VERSION, LEGACY_CNV_LABEL_FORMAT_VERSION):
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
            # V1 had no ONH annotation.  It remains fully usable and will be
            # upgraded to V2 only when the reviewer next saves it in the GUI.
            onh_edge = np.zeros(native, dtype=bool)
        out = {
            "path": path,
            "cnv_mask": mask,
            "onh_edge_mask": onh_edge,
            "scan_id": _scalar(data, "scan_id", str, ""),
            "source_volume": _scalar(data, "source_volume", str, ""),
            "source_segmentation": _scalar(data, "source_segmentation", str, ""),
            "native_shape": native,
            "retina_band": tuple(int(x) for x in data["retina_band"]),
            "vitreous_at_high_index": _scalar(
                data, "vitreous_at_high_index", bool, False),
            "label_format_version": version,
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
            ("onh_edge_present", bool, bool(onh_edge.any())),
            ("onh_edge_pixel_count", int, int(onh_edge.sum())),
            ("labeller", str, ""),
            ("notes", str, ""),
            ("projection_version", str, "unknown"),
            ("structural_projection", str, ""),
            ("octa_projection", str, ""),
            ("revision", int, 0),
            ("labelled_at", str, ""),
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
