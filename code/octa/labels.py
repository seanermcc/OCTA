"""
Human surface labels: the file format, and the maths that turns a drawn stroke
into a corrected surface.

Separate from the GUI on purpose. `refit`, any future training code, and the QC
scripts all need to read labels, and none of them should have to import a Qt
application to do it.

What a label is
---------------
One `.npz` per reviewed B-scan, holding both what the human ended up with and
what the automatic pipeline had proposed. Keeping the automatic surfaces
alongside the corrected ones is what makes the labels measurable rather than
merely usable: the difference between them is the only direct evidence we have
of how wrong the pipeline actually is, and it is how `refit` knows which
surfaces a human genuinely touched.

A surface nobody corrected carries no human information. Its "label" is the
automatic output fed back, and training or refitting on it would launder the
prior into evidence for itself. `surface_edited` marks the difference, and
every consumer is expected to honour it.

There is a third case between those two, and it is the one that would quietly
poison a training set. Correcting one surface can shove another: the ordering
constraint only ever pushes a deeper surface further out, so dragging the ILM
past the RNFL/GCL boundary moves that boundary too. Its value then differs from
the automatic result without a human ever having drawn it. `surface_displaced`
records exactly that, so the three states stay separable:

    edited      a human drew this surface
    displaced   the ordering constraint moved it to accommodate an edit
    neither     it is the automatic output, unexamined

Only `edited` surfaces are evidence. `displaced` ones are a side effect worth
seeing -- a lot of displacement usually means the whole stack was wrong and the
human is fixing it top-down -- but they are not labels.

Verdicts
--------
    accepted   the automatic surfaces were already right; no strokes drawn
    corrected  at least one surface was redrawn
    rejected   the image is unusable (too shadowed, artefacted, off-retina).
               Not a training example, and not a pipeline failure either --
               rejected B-scans are excluded from both.

`surface_visible` is a separate axis from all of that: it records whether the
human could actually *see* a given boundary in this B-scan. An invisible
surface has no correct answer to learn, which is a different statement from the
automatic answer being wrong. This is the measurement that should decide
whether a boundary belongs in the cascade at all -- the question the retired
IPL sublaminae were argued about without it.

`region_excluded` is a fourth axis, and a different shape from the other three:
it is per-A-line rather than per-surface, because it answers a question that
does not distinguish between surfaces at all -- *is the image itself usable
here*, regardless of which boundary you're looking for. A shadow band, a
scan-edge artefact, or a genuinely signal-free stretch makes every surface in
that column range equally unreliable, and marking it once is both faster than
and different from marking ten surfaces not-visible individually. It is a human
override of the same kind of judgement the automatic `shadow` mask makes
algorithmically, for the cases that mask misses.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import numpy as np

LABEL_SUFFIX = ".npz"
VERDICTS = ("accepted", "corrected", "rejected")


# --------------------------------------------------------------------------
# stroke -> surface
# --------------------------------------------------------------------------

def apply_stroke(base: np.ndarray, xs, ys, taper: float = 30.0) -> np.ndarray:
    """
    Splice a freehand stroke into one surface.

    `xs`/`ys` are the A-line and depth coordinates the cursor passed through.
    Inside the stroke the surface becomes exactly what was drawn. Outside it,
    the *offset* at the nearest stroke end is faded to zero over `taper`
    A-lines, so the correction joins the untouched automatic surface smoothly
    instead of stepping off it.

    Fading the offset rather than the position is the whole point. A human
    correcting a 40-A-line stretch of a 512-A-line B-scan is saying "this bit
    is wrong", not "the rest is right at exactly the value it already has" --
    and a hard splice would leave two discontinuities of a kind no
    dynamic-programme surface could ever produce, which would then be learned
    as if they were anatomy.
    """
    base = np.asarray(base, dtype=float)
    n = base.size
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if xs.size == 0:
        return base.copy()

    # One depth per A-line: a drag revisits the same column many times, and a
    # fast diagonal drag skips columns entirely, so collapse to one value per
    # visited column and interpolate across the gaps.
    col = np.clip(np.round(xs).astype(int), 0, n - 1)
    ux, inv = np.unique(col, return_inverse=True)
    uy = np.bincount(inv, weights=ys) / np.bincount(inv)

    x0, x1 = int(ux[0]), int(ux[-1])
    grid = np.arange(n)
    drawn = np.interp(np.arange(x0, x1 + 1), ux, uy)

    off = np.zeros(n)
    off[x0:x1 + 1] = drawn - base[x0:x1 + 1]

    if taper > 0 and (x0 > 0 or x1 < n - 1):
        dist = np.maximum(np.clip(x0 - grid, 0, None), np.clip(grid - x1, 0, None))
        w = np.clip(1.0 - dist / float(taper), 0.0, 1.0)
        edge = np.where(grid < x0, off[x0], off[x1])
        outside = (grid < x0) | (grid > x1)
        off = np.where(outside, edge * w, off)

    return base + off


def stroke_support(n: int, xs, taper: float = 30.0):
    """Which A-lines a stroke actually drew, and which it only tapered into.

    The exact companion of :func:`apply_stroke`: same column rounding, same
    span, same taper ramp. It answers the question the surface array cannot --
    *did a human draw here* -- so a consumer never has to infer stroke support
    from how far the corrected surface happens to sit from the automatic one.
    Two columns can differ by zero because the automatic line was already
    right, and a column can differ by a lot because the taper moved it.

    Returns ``(drawn, tapered)``, both ``[n]`` bool and disjoint. Keep this
    function and :func:`apply_stroke` edited together.
    """
    drawn = np.zeros(int(n), dtype=bool)
    tapered = np.zeros(int(n), dtype=bool)
    xs = np.asarray(xs, dtype=float)
    if xs.size == 0:
        return drawn, tapered

    col = np.clip(np.round(xs).astype(int), 0, int(n) - 1)
    x0, x1 = int(col.min()), int(col.max())
    drawn[x0:x1 + 1] = True

    if taper > 0 and (x0 > 0 or x1 < n - 1):
        grid = np.arange(int(n))
        dist = np.maximum(np.clip(x0 - grid, 0, None), np.clip(grid - x1, 0, None))
        w = np.clip(1.0 - dist / float(taper), 0.0, 1.0)
        tapered = ((grid < x0) | (grid > x1)) & (w > 0)
    return drawn, tapered


def enforce_order(surf: np.ndarray, min_gap: float = 1.0) -> np.ndarray:
    """
    Keep surfaces in anatomical order after an edit.

    Same rule the cascade uses: a cumulative maximum from the vitreous side,
    which only ever pushes a violating deeper surface further out, so one bad
    surface cannot drag the rest of the stack with it.
    """
    out = np.asarray(surf, dtype=float).copy()
    for i in range(1, out.shape[0]):
        out[i] = np.maximum(out[i], out[i - 1] + min_gap)
    return out


# --------------------------------------------------------------------------
# file i/o
# --------------------------------------------------------------------------

def label_path(label_dir, scan_id: str, bscan: int) -> Path:
    return Path(label_dir) / f"{scan_id}_b{int(bscan):04d}{LABEL_SUFFIX}"


def save_label(label_dir, *, scan_id: str, bscan: int, verdict: str,
               surfaces: np.ndarray, auto_surfaces: np.ndarray,
               surface_names, surface_edited, surface_visible,
               px_um: float, cascade_version: str,
               surface_displaced=None, region_excluded=None,
               seconds_active: float = 0.0, n_strokes: int = 0,
               is_control: bool = False, labeller: str = "",
               source_pack: str = "", notes: str = "") -> Path:
    """Write one reviewed B-scan. Overwrites any earlier label for it."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}, got {verdict!r}")
    surfaces = np.asarray(surfaces, dtype=np.float32)
    auto_surfaces = np.asarray(auto_surfaces, dtype=np.float32)
    if surfaces.shape != auto_surfaces.shape:
        raise ValueError("surfaces and auto_surfaces must have the same shape")

    # Recorded per surface so a later reader can weight or filter on how large
    # a correction was without recomputing it from the two arrays.
    d = surfaces.astype(float) - auto_surfaces.astype(float)
    rms_shift = np.sqrt(np.nanmean(d ** 2, axis=1))
    max_shift = np.nanmax(np.abs(d), axis=1)

    # Fall back to inferring displacement from the arrays if the caller did not
    # track it: a surface that moved without being edited was displaced. The
    # caller's own record is preferred because it knows the difference between
    # a surface the ordering constraint shoved and one that a later edit
    # happened to return to its original place.
    surface_edited = np.asarray(surface_edited, dtype=bool)
    if surface_displaced is None:
        surface_displaced = (~surface_edited) & (max_shift > 1e-6)
    surface_displaced = np.asarray(surface_displaced, dtype=bool)
    if region_excluded is None:
        region_excluded = np.zeros(surfaces.shape[1], dtype=bool)
    region_excluded = np.asarray(region_excluded, dtype=bool)

    p = label_path(label_dir, scan_id, bscan)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        p,
        surfaces=surfaces,
        auto_surfaces=auto_surfaces,
        surface_names=np.array([str(x) for x in surface_names]),
        surface_edited=surface_edited,
        surface_displaced=surface_displaced,
        surface_visible=np.asarray(surface_visible, dtype=bool),
        region_excluded=region_excluded,
        rms_shift_px=rms_shift.astype(np.float32),
        max_shift_px=max_shift.astype(np.float32),
        verdict=np.array([verdict]),
        scan_id=np.array([scan_id]),
        bscan=np.array([int(bscan)], dtype=np.int32),
        is_control=np.array([bool(is_control)]),
        px_um=np.array([float(px_um)], dtype=np.float32),
        cascade_version=np.array([cascade_version]),
        seconds_active=np.array([float(seconds_active)], dtype=np.float32),
        n_strokes=np.array([int(n_strokes)], dtype=np.int32),
        labeller=np.array([labeller]),
        source_pack=np.array([source_pack]),
        notes=np.array([notes]),
        labelled_at=np.array([_dt.datetime.now().isoformat(timespec="seconds")]),
    )
    return p


def load_label(path) -> dict:
    """Read one label file into plain Python types."""
    d = np.load(path, allow_pickle=False)
    out = {
        "path": Path(path),
        "surfaces": d["surfaces"].astype(float),
        "auto_surfaces": d["auto_surfaces"].astype(float),
        "surface_names": [str(x) for x in d["surface_names"]],
        "surface_edited": d["surface_edited"].astype(bool),
        "verdict": str(d["verdict"][0]),
        "scan_id": str(d["scan_id"][0]),
        "bscan": int(d["bscan"][0]),
        "px_um": float(d["px_um"][0]),
    }
    # Fields added after the first labels were written. Absent is not an error;
    # it means that label predates the field.
    opt = {"surface_visible": lambda v: v.astype(bool),
           "surface_displaced": lambda v: v.astype(bool),
           "region_excluded": lambda v: v.astype(bool),
           "rms_shift_px": lambda v: v.astype(float),
           "max_shift_px": lambda v: v.astype(float),
           "is_control": lambda v: bool(v[0]),
           "cascade_version": lambda v: str(v[0]),
           "seconds_active": lambda v: float(v[0]),
           "n_strokes": lambda v: int(v[0]),
           "labeller": lambda v: str(v[0]),
           "source_pack": lambda v: str(v[0]),
           "notes": lambda v: str(v[0]),
           "labelled_at": lambda v: str(v[0])}
    for k, conv in opt.items():
        if k in d.files:
            out[k] = conv(d[k])
    out.setdefault("surface_visible",
                   np.ones(len(out["surface_names"]), dtype=bool))
    out.setdefault("surface_displaced",
                   np.zeros(len(out["surface_names"]), dtype=bool))
    out.setdefault("region_excluded",
                   np.zeros(out["surfaces"].shape[1], dtype=bool))
    out.setdefault("cascade_version", "unknown")
    out.setdefault("seconds_active", float("nan"))
    out.setdefault("n_strokes", -1)
    return out


def load_labels(label_dir) -> list[dict]:
    """Every label in a directory, sorted by scan then B-scan."""
    out = []
    for f in sorted(Path(label_dir).glob(f"*{LABEL_SUFFIX}")):
        try:
            out.append(load_label(f))
        except Exception as e:                      # noqa: BLE001
            print(f"  skipping unreadable label {f.name}: {e}")
    out.sort(key=lambda r: (r["scan_id"], r["bscan"]))
    return out
