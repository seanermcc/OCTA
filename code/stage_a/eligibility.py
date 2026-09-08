"""Conservative legacy supervision and physically measured footprint exclusion."""
import numpy as np
from scipy.ndimage import distance_transform_edt
from eight_surface.config import N_SURFACES, CASCADE_VERSION

BUFFER_UM = 250.0  # provisional candidate from the staged specification


def biological_group(metadata):
    label = metadata.get("day_label", "").strip().lower().replace(" ", "")
    if label == "wt" and metadata.get("animal") == "TS165":
        return "WT"
    try:
        day = float(metadata.get("days_post_laser", ""))
    except (TypeError, ValueError):
        day = float("nan")
    if day < 0 or label == "beforelaser":
        return "confirmed_pre_laser"
    if day > 0:
        return "post_laser_verified_timing"
    # Explicit CNV session description plus positive nominal day establishes
    # post-laser context only; it does NOT establish an exact elapsed interval.
    if ("cnv" in metadata.get("session_folder", "").lower()
            and label.startswith("d") and label[1:].isdigit() and int(label[1:]) > 0):
        return "post_laser_nominal_timing"
    return "timing_unknown"


def scope(metadata, footprint, shape, buffer_um=BUFFER_UM):
    group = biological_group(metadata)
    distance = np.full(shape, np.nan, np.float32)
    if footprint is not None and footprint["reviewed"]:
        mask = footprint["cnv_mask"]
        if mask.shape != tuple(shape):
            raise ValueError("Footprint/native geometry mismatch")
        if mask.any():
            sampling = (footprint["bscan_um"], footprint["aline_um"])
            if not all(np.isfinite(s) and s > 0 for s in sampling):
                raise ValueError("Invalid footprint physical sampling")
            distance = (distance_transform_edt(~mask, sampling=sampling)
                        - distance_transform_edt(mask, sampling=sampling)).astype(np.float32)
            return distance > buffer_um, distance, "positive_scan_remote", group
        return np.ones(shape, bool), distance, (
            "control_footprint_negative" if group in ("WT", "confirmed_pre_laser")
            else "footprint_negative_post_laser" if group.startswith("post_laser")
            else "footprint_negative_timing_unknown"), group
    if group in ("WT", "confirmed_pre_laser"):
        return np.ones(shape, bool), distance, "independent_control_metadata", group
    return np.zeros(shape, bool), distance, "unknown_missing_or_unreviewed_footprint", group


def supervision(record, allowed, shadow=None):
    rows = np.asarray(record["surfaces"])
    width = rows.shape[1]
    if rows.shape != (N_SURFACES, width) or np.shape(allowed) != (width,):
        raise ValueError("Supervision geometry mismatch")
    reason = np.zeros(rows.shape, np.uint16)
    bits = {"not_corrected": 1, "unedited": 2, "not_visible": 4,
            "unreliable": 8, "displaced": 16, "image_excluded": 32,
            "outside_stage_a_scope": 64, "nonfinite_target": 128,
            "shadow": 256, "wrong_contract": 512}
    if record["verdict"] != "corrected":
        reason |= bits["not_corrected"]
    if record.get("cascade_version") != CASCADE_VERSION:
        reason |= bits["wrong_contract"]
    for key, name, positive in [("surface_edited", "unedited", False),
                                ("surface_visible", "not_visible", False),
                                ("surface_reliable", "unreliable", False),
                                ("surface_displaced", "displaced", True)]:
        flags = np.asarray(record[key], bool)
        if flags.shape != (N_SURFACES,):
            raise ValueError(f"Unexpected {key} shape")
        reason[flags if positive else ~flags] |= bits[name]
    reason[:, np.asarray(record["region_excluded"], bool)] |= bits["image_excluded"]
    reason[:, ~allowed] |= bits["outside_stage_a_scope"]
    reason[~np.isfinite(rows)] |= bits["nonfinite_target"]
    if shadow is not None:
        reason[:, np.asarray(shadow, bool)] |= bits["shadow"]
    return reason == 0, reason, bits


def region_targets(rows, valid, height):
    """Seven closed bands only. No invented vitreous/sub-RPE targets."""
    rows, valid = np.asarray(rows), np.asarray(valid, bool)
    target = np.full((height, rows.shape[1]), -100, np.int64)
    depth = np.arange(height)[:, None]
    for k in range(7):
        good = valid[k] & valid[k + 1] & (rows[k + 1] >= rows[k])
        region = good[None] & (depth >= rows[k]) & (depth < rows[k + 1])
        target[region] = k
    return target
