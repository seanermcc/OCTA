"""Eight-boundary label format with per-A-line annotation provenance.

Format ``3-local-provenance`` adds six ``[8, A-line]`` arrays beside the
existing ``[8]`` flags -- where a human stroke actually landed, where the
software tapered it, where the ordering constraint moved it, where a human
explicitly reviewed the automatic line, and tri-state local visibility and
reliability.  See :mod:`eight_surface.provenance` for what each one means.

Backward compatibility is one-way on purpose.  ``load_label`` reads every older
eight-boundary label unchanged and reports ``local_provenance_available=False``
for it; nothing here ever rewrites an existing file, and no migration invents a
stroke history that was never recorded.  The whole-surface ``surface_edited`` /
``surface_visible`` / ``surface_reliable`` flags are still written, still mean
what they always meant, and are still what an older reader will find.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np

from octa.labels import (  # shared, tested geometry
    apply_stroke, enforce_order, stroke_support,
)

from . import provenance as P

from .config import (
    CASCADE_VERSION,
    LABEL_FORMAT_VERSION,
    READABLE_LABEL_FORMAT_VERSIONS,
    LAYER_NAMES,
    N_SURFACES,
    SURFACE_NAMES,
    layer_reliability,
)


LABEL_SUFFIX = ".npz"
VERDICTS = ("accepted", "corrected", "rejected")


def label_path(label_dir, scan_id: str, bscan: int) -> Path:
    return Path(label_dir) / f"{scan_id}_b{int(bscan):04d}{LABEL_SUFFIX}"


def save_label(
    label_dir,
    *,
    scan_id: str,
    bscan: int,
    verdict: str,
    surfaces: np.ndarray,
    auto_surfaces: np.ndarray,
    surface_names,
    surface_edited,
    surface_visible,
    surface_reliable,
    px_um: float,
    cascade_version: str = CASCADE_VERSION,
    surface_displaced=None,
    region_excluded=None,
    seconds_active: float = 0.0,
    n_strokes: int = 0,
    is_control: bool = False,
    labeller: str = "",
    source_pack: str = "",
    notes: str = "",
    local=None,
) -> Path:
    """Write one reviewed B-scan in format ``3-local-provenance``.

    ``local`` is the six-array dict from :func:`eight_surface.provenance.empty_local`,
    kept per B-scan by the GUI.  Omitting it writes a file whose local arrays
    say, truthfully, that no column was drawn, tapered, displaced, reviewed or
    judged -- which is what a caller that does not track strokes actually knows.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    names = [str(x) for x in surface_names]
    if names != SURFACE_NAMES:
        raise ValueError("eight-boundary labels require the exact current surface order")
    surfaces = np.asarray(surfaces, np.float32)
    auto = np.asarray(auto_surfaces, np.float32)
    if surfaces.shape != auto.shape or surfaces.shape[0] != N_SURFACES:
        raise ValueError("surfaces and auto_surfaces must both be [8, A-line]")

    edited = np.asarray(surface_edited, bool)
    visible = np.asarray(surface_visible, bool)
    reliable = np.asarray(surface_reliable, bool)
    if any(x.shape != (N_SURFACES,) for x in (edited, visible, reliable)):
        raise ValueError("surface flags must all have shape (8,)")
    delta = surfaces.astype(float) - auto.astype(float)
    rms = np.sqrt(np.nanmean(delta ** 2, axis=1))
    maximum = np.nanmax(np.abs(delta), axis=1)
    displaced = ((~edited) & (maximum > 1e-6) if surface_displaced is None
                 else np.asarray(surface_displaced, bool))
    excluded = (np.zeros(surfaces.shape[1], bool) if region_excluded is None
                else np.asarray(region_excluded, bool))
    if excluded.shape != (surfaces.shape[1],):
        raise ValueError("region_excluded must have one value per A-line")
    layer_rel_map = layer_reliability(reliable)
    layer_rel = np.array([bool(layer_rel_map[name]) for name in LAYER_NAMES])

    n_col = surfaces.shape[1]
    store = P.empty_local(n_col)
    if local is not None:
        for key in P.LOCAL_KEYS:
            if key not in local:
                raise ValueError(f"local provenance is missing {key}")
            value = np.asarray(local[key])
            if value.shape != (N_SURFACES, n_col):
                raise ValueError(
                    f"{key} must be [{N_SURFACES}, {n_col}], got {value.shape}")
            store[key] = value.astype(store[key].dtype)
    for key in ("local_visibility", "local_reliability"):
        bad = ~np.isin(store[key], [P.MARK_UNKNOWN, P.MARK_YES, P.MARK_NO])
        if bad.any():
            raise ValueError(f"{key} contains a value that is not a tri-state mark")

    path = label_path(label_dir, scan_id, bscan)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        surfaces=surfaces,
        auto_surfaces=auto,
        surface_names=np.array(names),
        surface_edited=edited,
        surface_displaced=displaced,
        surface_visible=visible,
        surface_reliable=reliable,
        layer_names=np.array(LAYER_NAMES),
        layer_reliable=layer_rel,
        region_excluded=excluded,
        local_drawn=store["local_drawn"],
        local_taper=store["local_taper"],
        local_displaced=store["local_displaced"],
        local_reviewed=store["local_reviewed"],
        local_visibility=store["local_visibility"],
        local_reliability=store["local_reliability"],
        rms_shift_px=rms.astype(np.float32),
        max_shift_px=maximum.astype(np.float32),
        verdict=np.array([verdict]),
        scan_id=np.array([scan_id]),
        bscan=np.array([int(bscan)], np.int32),
        is_control=np.array([bool(is_control)]),
        px_um=np.array([float(px_um)], np.float32),
        cascade_version=np.array([cascade_version]),
        label_format_version=np.array([LABEL_FORMAT_VERSION]),
        seconds_active=np.array([float(seconds_active)], np.float32),
        n_strokes=np.array([int(n_strokes)], np.int32),
        labeller=np.array([labeller]),
        source_pack=np.array([source_pack]),
        notes=np.array([notes]),
        labelled_at=np.array([dt.datetime.now().isoformat(timespec="seconds")]),
    )
    return path


def load_label(path) -> dict:
    with np.load(path, allow_pickle=False) as data:
        names = [str(x) for x in data["surface_names"]]
        if names != SURFACE_NAMES:
            raise ValueError("label belongs to a different surface cascade")
        present = set(data.files)
        out = {
            "path": Path(path),
            "surfaces": data["surfaces"].astype(float),
            "auto_surfaces": data["auto_surfaces"].astype(float),
            "surface_names": names,
            "surface_edited": data["surface_edited"].astype(bool),
            "surface_displaced": data["surface_displaced"].astype(bool),
            "surface_visible": data["surface_visible"].astype(bool),
            "surface_reliable": (data["surface_reliable"].astype(bool)
                                 if "surface_reliable" in data.files
                                 else np.ones(N_SURFACES, bool)),
            "region_excluded": (data["region_excluded"].astype(bool)
                                if "region_excluded" in data.files
                                else np.zeros(data["surfaces"].shape[1], bool)),
            "verdict": str(data["verdict"][0]),
            "scan_id": str(data["scan_id"][0]),
            "bscan": int(data["bscan"][0]),
            "px_um": float(data["px_um"][0]),
        }
        for key in ("local_drawn", "local_taper", "local_displaced",
                    "local_reviewed"):
            if key in present:
                out[key] = data[key].astype(bool)
        for key in ("local_visibility", "local_reliability"):
            if key in present:
                out[key] = data[key].astype(np.uint8)
        for key, conv in {
            "rms_shift_px": lambda x: x.astype(float),
            "max_shift_px": lambda x: x.astype(float),
            "is_control": lambda x: bool(x[0]),
            "cascade_version": lambda x: str(x[0]),
            "label_format_version": lambda x: str(x[0]),
            "seconds_active": lambda x: float(x[0]),
            "n_strokes": lambda x: int(x[0]),
            "labeller": lambda x: str(x[0]),
            "source_pack": lambda x: str(x[0]),
            "notes": lambda x: str(x[0]),
            "labelled_at": lambda x: str(x[0]),
        }.items():
            if key in data.files:
                out[key] = conv(data[key])
    derived = layer_reliability(out["surface_reliable"])
    out["layer_names"] = list(LAYER_NAMES)
    out["layer_reliable"] = np.array([derived[name] for name in LAYER_NAMES])
    out.setdefault("cascade_version", "unknown")
    out.setdefault("label_format_version", "1")
    if out["label_format_version"] not in READABLE_LABEL_FORMAT_VERSIONS:
        raise ValueError(
            f"{Path(path).name} is label format "
            f"{out['label_format_version']!r}, which this code does not know how "
            f"to read. Refusing to guess at its fields.")
    out.setdefault("seconds_active", float("nan"))
    out.setdefault("n_strokes", -1)
    _attach_local(out, present)
    return out


def _attach_local(out: dict, present: set) -> None:
    """Attach the per-A-line arrays, or say honestly that the file has none.

    A file written before format ``3-local-provenance`` is left exactly as it
    is on disk.  ``local_provenance_available`` is False for it, its
    ``provenance_code`` is ``PROV_UNAVAILABLE`` wherever the whole-surface flags
    say something happened and ``PROV_AUTO`` where they say nothing did, and its
    local visibility/reliability stay ``MARK_UNKNOWN`` unless the whole-surface
    flag was switched off.  Nothing is reconstructed from ``surfaces`` minus
    ``auto_surfaces``; that difference cannot recover intent.
    """
    if set(P.LOCAL_KEYS) <= present:
        out["local_provenance_available"] = True
        out["provenance_code"] = P.provenance_code(
            out["local_drawn"], out["local_taper"],
            out["local_displaced"], out["local_reviewed"])
        return
    if present & set(P.LOCAL_KEYS):
        raise ValueError(
            "label has only part of the local provenance arrays: "
            + ", ".join(sorted(present & set(P.LOCAL_KEYS))))
    out.update(P.legacy_local(out))


def local_arrays(record) -> dict:
    """The six stored planes for ``record``, empty ones for a legacy file."""
    n_col = np.asarray(record["surfaces"]).shape[1]
    blank = P.empty_local(n_col)
    return {key: np.asarray(record.get(key, blank[key])).copy()
            for key in P.LOCAL_KEYS}


def load_labels(label_dir) -> list[dict]:
    records = []
    for path in sorted(Path(label_dir).glob(f"*{LABEL_SUFFIX}")):
        try:
            records.append(load_label(path))
        except Exception as exc:  # noqa: BLE001
            print(f"  skipping unreadable/incompatible label {path.name}: {exc}")
    return sorted(records, key=lambda r: (r["scan_id"], r["bscan"]))

