"""Targets and loss masks built from human labels only.

Supervision is per boundary **and per A-line**.  A stroke over 40 columns of a
512-column B-scan supervises 40 columns; the rest of that boundary is not
evidence and gets zero weight.  Which columns those are comes from the label's
recorded stroke provenance, never from where the corrected line happens to sit
relative to the automatic one -- a column can differ by nothing because the
automatic answer was already right, and differ by a lot because the software
taper moved it.

What counts as boundary-position evidence
-----------------------------------------
``PROV_DRAWN``                a human stroke covered this column.  The only
                              thing supervised on.
``PROV_TAPER``                software join fading a stroke back onto the
                              automatic line.  Not evidence.
``PROV_DISPLACED``            the ordering constraint moved it.  Not evidence.
``PROV_DRAWN_DISPLACED``      drawn, then shoved by ordering.  The history is
                              kept; the position is no longer what the human
                              drew, so it is not evidence either.
``PROV_REVIEWED``             a human explicitly reviewed the automatic line
                              and left it.  Real information -- it is a
                              visibility and measurability label -- but it is
                              *not* a boundary-position target, or the model
                              would be trained on its predecessor's output.
``PROV_AUTO``                 untouched.  Not evidence.
``PROV_UNAVAILABLE``          a label written before this format; see
                              ``provenance.LEGACY_POLICIES``.

On top of that a column must not be inside a whole-image exclusion, and the
human must not have marked the boundary locally unidentifiable or locally
unreliable there.  A region is supervised in a column only when **both** of its
bounding surfaces are, evaluated column by column.

Visibility supervision uses a different mask again: the tri-state local
visibility, with ``MARK_UNKNOWN`` columns carrying zero weight.  Unknown is not
"not visible", and training it as though it were would teach the model to
abstain wherever nobody happened to look.
"""

from __future__ import annotations

import numpy as np

from eight_surface import provenance as P
from eight_surface.config import ANALYSIS_LAYER_DEFS, N_SURFACES, SURFACE_NAMES

IDX = {name: i for i, name in enumerate(SURFACE_NAMES)}

# One region per band the eight surfaces delimit, plus the two open-ended ones.
REGION_NAMES = [
    "VITREOUS", "RNFL", "GCL", "IPL", "INL", "OPL", "PHOTORECEPTOR", "RPE",
    "SUB_RPE",
]
N_REGIONS = len(REGION_NAMES)
assert N_REGIONS == N_SURFACES + 1

# region i lies between surface i-1 above and surface i below; the first has no
# surface above it and the last none below.
REGION_BOUNDS = [(None, 0)] + [(i - 1, i) for i in range(1, N_SURFACES)] + [
    (N_SURFACES - 1, None)]

BOUNDARY_SIGMA_PX = 2.0


def supervised_records(records) -> list:
    """Only ``corrected`` B-scans are evidence."""
    return [r for r in records if r["verdict"] == "corrected"]


DEFAULT_LEGACY_POLICY = P.DEFAULT_LEGACY_POLICY


def column_valid(record, legacy_policy: str = DEFAULT_LEGACY_POLICY) -> np.ndarray:
    """``[8, A-line]`` bool -- columns that are direct human boundary evidence.

    This is the mask everything else in this module is built from.  For a label
    in format ``3-local-provenance`` it is exact.  For an older label it is
    whatever ``legacy_policy`` allows: ``"surface_flag"`` reproduces the old
    whole-boundary behaviour so historical numbers stay reproducible, and
    ``"strict"`` supplies nothing at all.  Neither ever writes to the label.
    """
    valid = P.local_position_valid(record, legacy_policy)
    if valid.shape[0] != N_SURFACES:
        raise AssertionError(
            f"provenance must be [{N_SURFACES}, A-line], got {valid.shape}")
    return valid


def surface_supervised(record, legacy_policy: str = DEFAULT_LEGACY_POLICY
                       ) -> np.ndarray:
    """``[8]`` -- boundaries with human evidence in at least one column.

    Retained because callers use it to decide whether a boundary appears in a
    sample at all.  It is a summary of :func:`column_valid`, never a substitute
    for it: a True here does **not** mean the whole boundary is supervised.
    """
    flags = column_valid(record, legacy_policy).any(axis=1)
    if flags.shape != (N_SURFACES,):
        raise AssertionError(f"surface flags must be [{N_SURFACES}], got {flags.shape}")
    return flags


def reviewed_only(record, legacy_policy: str = DEFAULT_LEGACY_POLICY) -> np.ndarray:
    """``[8, A-line]`` -- explicitly reviewed automatic line, not drawn.

    Kept separate and returned separately so a caller can count it, report it,
    or feed it to a measurability head -- but never mistake it for a drawn
    position target.
    """
    if not record.get("local_provenance_available", False):
        return np.zeros(np.asarray(record["surfaces"]).shape, bool)
    return np.asarray(record["provenance_code"], np.uint8) == P.PROV_REVIEWED


def column_supervised(record) -> np.ndarray:
    """``[A-line]`` -- A-lines the human did not exclude."""
    excluded = np.asarray(record["region_excluded"], bool)
    n_col = np.asarray(record["surfaces"]).shape[1]
    if excluded.shape != (n_col,):
        raise AssertionError(
            f"region_excluded must be [{n_col}], got {excluded.shape}")
    return ~excluded


def boundary_weight(record, rows=None, height=None,
                    legacy_policy: str = DEFAULT_LEGACY_POLICY) -> np.ndarray:
    """``[8, A-line]`` loss weight for the boundary head.

    Zero wherever the human gave no answer *in that column*.  When
    ``rows``/``height`` are given, a supervised column whose human row falls
    outside the image is also zeroed: a target that does not exist in the
    tensor cannot be learned.
    """
    weight = column_valid(record, legacy_policy).astype(np.float32)
    rows = np.asarray(record["surfaces"] if rows is None else rows, float)
    weight[~np.isfinite(rows)] = 0.0
    if height is not None:
        inside = (rows >= 0) & (rows <= height - 1)
        weight[~inside] = 0.0
    return weight


def region_supervised(record, legacy_policy: str = DEFAULT_LEGACY_POLICY
                      ) -> np.ndarray:
    """``[9]`` -- regions with both bounding surfaces supervised somewhere."""
    surf = surface_supervised(record, legacy_policy)
    out = np.empty(N_REGIONS, bool)
    for r, (above, below) in enumerate(REGION_BOUNDS):
        parts = [surf[i] for i in (above, below) if i is not None]
        out[r] = bool(np.all(parts))
    return out


def region_column_supervised(record, legacy_policy: str = DEFAULT_LEGACY_POLICY
                             ) -> np.ndarray:
    """``[9, A-line]`` -- a region is supervised in a column only when both of
    its bounding surfaces are valid **in that same column**.

    The open-ended vitreous and sub-RPE regions have one bounding surface each
    and inherit its validity.  Getting this per-column is what stops a lesion
    core, where the outer boundary is unidentifiable, from being supervised as
    a confidently-measured RPE band because the same boundary was drawn 200
    A-lines away.
    """
    valid = column_valid(record, legacy_policy)
    out = np.empty((N_REGIONS, valid.shape[1]), bool)
    for r, (above, below) in enumerate(REGION_BOUNDS):
        parts = [valid[i] for i in (above, below) if i is not None]
        out[r] = np.logical_and.reduce(parts)
    return out


def region_map(rows: np.ndarray, height: int) -> np.ndarray:
    """``[height, A-line]`` integer region map filled between human rows.

    A pixel belongs to the region above the first surface whose row is below it,
    so ties fall on the shallower side consistently.
    """
    rows = np.asarray(rows, float)
    if rows.shape[0] != N_SURFACES:
        raise AssertionError(f"rows must be [{N_SURFACES}, A-line], got {rows.shape}")
    depth = np.arange(height, dtype=float)[:, None]
    # below[s, r, c] is True where pixel r is at or past surface s; the region
    # id is how many surfaces the pixel has already passed.
    below = np.stack([depth >= np.rint(rows[s])[None, :] for s in range(N_SURFACES)])
    return below.sum(axis=0).astype(np.int8)


def region_weight(record, region_ids: np.ndarray, rows=None,
                  legacy_policy: str = DEFAULT_LEGACY_POLICY) -> np.ndarray:
    """``[height, A-line]`` loss weight for the region head.

    Looked up per column: pixel ``(d, c)`` is weighted only if the region it
    was assigned is supervised in column ``c``.  A column with a non-finite
    human row has no well-defined region map, so it is dropped entirely rather
    than filled with whatever the comparison happened to return.
    """
    valid_region = region_column_supervised(record, legacy_policy)
    ids = np.asarray(region_ids, int)
    columns_index = np.broadcast_to(
        np.arange(ids.shape[1])[None, :], ids.shape)
    weight = valid_region[ids, columns_index].astype(np.float32)
    columns = column_supervised(record).astype(np.float32)
    rows = np.asarray(record["surfaces"] if rows is None else rows, float)
    columns *= np.all(np.isfinite(rows), axis=0).astype(np.float32)
    weight *= columns[None, :]
    return weight


# ------------------------------------------------------- visibility targets --

def visibility_target(record) -> np.ndarray:
    """``[8, A-line]`` float32: 1 where the human could identify the boundary.

    Read together with :func:`visibility_weight`; the value in an unweighted
    column is meaningless and is set to 0 only because an array needs a value.
    """
    return (P.record_visibility(record) == P.MARK_YES).astype(np.float32)


def visibility_weight(record) -> np.ndarray:
    """``[8, A-line]`` float32: 1 only where a human actually said something.

    ``MARK_UNKNOWN`` -- nobody looked at that column -- gets zero weight and is
    never read as "not visible".  Whole-image exclusions are zeroed too: those
    columns say something about the image, not about this boundary.
    """
    marks = P.record_visibility(record)
    known = np.isin(marks, [P.MARK_YES, P.MARK_NO]).astype(np.float32)
    return known * (~np.asarray(record["region_excluded"], bool))[None, :]


def reliability_target(record) -> np.ndarray:
    """``[8, A-line]`` float32: 1 where the human left the column analysable."""
    return (P.record_reliability(record) == P.MARK_YES).astype(np.float32)


def reliability_weight(record) -> np.ndarray:
    """``[8, A-line]`` float32: 1 only where local reliability is known."""
    marks = P.record_reliability(record)
    known = np.isin(marks, [P.MARK_YES, P.MARK_NO]).astype(np.float32)
    return known * (~np.asarray(record["region_excluded"], bool))[None, :]


def boundary_maps(rows: np.ndarray, height: int,
                  sigma: float = BOUNDARY_SIGMA_PX) -> np.ndarray:
    """``[8, height, A-line]`` per-column Gaussian target, summing to 1.

    The boundary head takes a softmax **down each A-line**, so its target must
    be a distribution over depth in that column, not over the image.  Columns
    whose row is non-finite or off-image get an all-zero column; they are
    excluded by :func:`boundary_weight` anyway.
    """
    rows = np.asarray(rows, float)
    depth = np.arange(height, dtype=float)[None, :, None]
    centre = rows[:, None, :]
    with np.errstate(invalid="ignore"):
        maps = np.exp(-0.5 * ((depth - centre) / float(sigma)) ** 2)
    maps[~np.isfinite(maps)] = 0.0
    total = maps.sum(axis=1, keepdims=True)
    good = total > 1e-12
    maps = np.where(good, maps / np.where(good, total, 1.0), 0.0)
    return maps.astype(np.float32)


def layer_supervised(record, legacy_policy: str = DEFAULT_LEGACY_POLICY) -> dict:
    """``{layer: bool}`` -- a layer is measurable only if both surfaces are."""
    surf = surface_supervised(record, legacy_policy)
    return {name: bool(surf[IDX[top]] and surf[IDX[bottom]])
            for name, top, bottom in ANALYSIS_LAYER_DEFS}


def layer_column_supervised(record, legacy_policy: str = DEFAULT_LEGACY_POLICY
                            ) -> dict:
    """``{layer: [A-line] bool}`` -- both bounding surfaces valid per column."""
    valid = column_valid(record, legacy_policy)
    return {name: valid[IDX[top]] & valid[IDX[bottom]]
            for name, top, bottom in ANALYSIS_LAYER_DEFS}
