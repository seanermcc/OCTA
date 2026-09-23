"""Per-boundary, per-A-line drawing provenance, visibility and reliability.

Why this exists
---------------
Until label format ``2-surface-reliability`` the eight-boundary labels recorded
``surface_edited``/``surface_visible``/``surface_reliable`` with shape ``[8]``
while ``region_excluded`` had shape ``[A-line]``.  A single 40-A-line stroke
somewhere on a 512-A-line boundary therefore marked that boundary as
human-drawn *everywhere*, and the only way to say "I cannot identify this one
boundary through the middle of this lesion" was to disable the boundary for the
whole B-scan or to exclude the columns for **every** boundary at once.  Both
answers are wrong for the CNV round: beside a lesion the outer RPE edge is
perfectly visible, through its centre it is not, and the ILM is visible all the
way across.

This module defines the vocabulary that fixes it.  It holds no Qt and no file
I/O: :mod:`eight_surface.labels` writes it, :mod:`eight_surface.label_gui`
produces it, and the U-Net target builders consume it.

Four questions, four independent axes
-------------------------------------
1. **Where did this line come from?**  ``provenance`` codes below.
2. **Could a human identify the boundary here?**  ``visibility``, tri-state.
3. **Is the answer here good enough to analyse?**  ``reliability``, tri-state.
4. **Is the image itself usable here, for any boundary?**  ``region_excluded``
   in the label file — unchanged, still ``[A-line]``, still whole-column.

They are not interchangeable.  A boundary can be invisible in an image that is
otherwise fine (2), and an image can be unusable regardless of which boundary
you want (4).  "Not visible" is a statement about the *recorded image*, never a
claim that the tissue is absent — an obscured RPE and a destroyed RPE look the
same from here and this format deliberately cannot tell them apart.

Unknown is a real state
-----------------------
``MARK_UNKNOWN`` means nobody has said anything about that column yet.  It is
not "visible", it is not "not visible", and it must never be silently coerced
into either.  Most columns of most B-scans will stay unknown, because a
reviewer looks at the parts that matter.
"""

from __future__ import annotations

import numpy as np

from .config import N_SURFACES


# ---------------------------------------------------------------- provenance

PROV_AUTO = 0            # untouched automatic prediction
PROV_DRAWN = 1           # a human stroke actually passed over this column
PROV_TAPER = 2           # software-generated join fading the stroke offset out
PROV_DISPLACED = 3       # the ordering constraint moved it; nobody drew it
PROV_REVIEWED = 4        # a human explicitly reviewed the automatic line here
PROV_DRAWN_DISPLACED = 5  # drawn, then shoved by ordering: history, not truth
PROV_UNAVAILABLE = 255   # a legacy label that never recorded column provenance

PROVENANCE_NAMES = {
    PROV_AUTO: "auto",
    PROV_DRAWN: "drawn",
    PROV_TAPER: "taper",
    PROV_DISPLACED: "displaced",
    PROV_REVIEWED: "reviewed",
    PROV_DRAWN_DISPLACED: "drawn_then_displaced",
    PROV_UNAVAILABLE: "unavailable",
}

#: The only code that is direct human evidence of *where the boundary is*.
#: ``PROV_REVIEWED`` is direct human evidence that the automatic line was
#: looked at and not objected to, which is a weaker and different claim; it
#: must never become a boundary-position training target on its own.
#: ``PROV_DRAWN_DISPLACED`` is deliberately excluded: the ordering constraint
#: has since moved that column, so the stored row is no longer what the human
#: drew, even though the drawing history is preserved.
TRUSTED_POSITION_CODES = (PROV_DRAWN,)


# ------------------------------------------------------- tri-state judgements

MARK_UNKNOWN = 0
MARK_YES = 1             # visible / reliable
MARK_NO = 2              # not identifiable / not reliable

MARK_NAMES = {MARK_UNKNOWN: "unknown", MARK_YES: "yes", MARK_NO: "no"}


# ------------------------------------------------------------ legacy policies

#: How a reader may use a label written before per-column provenance existed.
#:
#: ``"surface_flag"``  Treat a surface flagged ``surface_edited`` as if the
#:                     human had drawn every non-excluded column of it.  This
#:                     reproduces exactly what every consumer did before this
#:                     format existed, so old numbers stay reproducible — but
#:                     it is an *approximation of unrecorded intent*, not a
#:                     recovered drawing history, and it over-claims by however
#:                     much of the boundary the stroke did not cover.
#: ``"strict"``        Legacy files supply no boundary-position supervision at
#:                     all.  Nothing is invented.  Use this to measure how much
#:                     the approximation above is worth.
#:
#: Neither policy ever writes to a label file.  Legacy labels are read as they
#: were written and are never migrated; see ``labels.load_label``.
LEGACY_POLICIES = ("surface_flag", "strict")
DEFAULT_LEGACY_POLICY = "surface_flag"


def check_legacy_policy(policy: str) -> str:
    if policy not in LEGACY_POLICIES:
        raise ValueError(
            f"legacy_policy must be one of {LEGACY_POLICIES}, got {policy!r}")
    return policy


# ------------------------------------------------------------ array factories

def empty_local(n_col: int) -> dict[str, np.ndarray]:
    """A fresh, wholly unreviewed local record for one B-scan."""
    shape = (N_SURFACES, int(n_col))
    return {
        "local_drawn": np.zeros(shape, bool),
        "local_taper": np.zeros(shape, bool),
        "local_displaced": np.zeros(shape, bool),
        "local_reviewed": np.zeros(shape, bool),
        "local_visibility": np.full(shape, MARK_UNKNOWN, np.uint8),
        "local_reliability": np.full(shape, MARK_UNKNOWN, np.uint8),
    }


LOCAL_KEYS = tuple(empty_local(1))


def provenance_code(drawn, taper, displaced, reviewed) -> np.ndarray:
    """Collapse the four history planes into one code per column.

    The planes are kept as the stored truth because they compose: a column can
    be drawn *and* later displaced, and that history must survive.  The code is
    the derived single answer to "what is this column, now".
    """
    drawn = np.asarray(drawn, bool)
    taper = np.asarray(taper, bool)
    displaced = np.asarray(displaced, bool)
    reviewed = np.asarray(reviewed, bool)
    out = np.full(drawn.shape, PROV_AUTO, np.uint8)
    out[reviewed] = PROV_REVIEWED
    out[taper & ~drawn] = PROV_TAPER
    out[displaced & ~drawn] = PROV_DISPLACED
    out[drawn] = PROV_DRAWN
    out[drawn & displaced] = PROV_DRAWN_DISPLACED
    return out


# ------------------------------------------------- combining with the [8] flags

def effective_marks(local: np.ndarray, whole_surface: np.ndarray) -> np.ndarray:
    """Fold a whole-surface ``[8]`` bool flag into a ``[8, A-line]`` tri-state.

    A whole-surface flag set to *False* is a statement about the entire B-scan
    ("this boundary is not identifiable anywhere here" / "do not analyse this
    boundary here") and forces ``MARK_NO`` in every column.  A flag left *True*
    is the default, not a positive claim, so it leaves ``MARK_UNKNOWN`` columns
    unknown.  That asymmetry is deliberate: the old GUI could only ever turn
    these flags off intentionally.
    """
    out = np.asarray(local, np.uint8).copy()
    flag = np.asarray(whole_surface, bool)
    if flag.shape != (out.shape[0],):
        raise ValueError(f"whole-surface flag must be [{out.shape[0]}]")
    out[~flag, :] = MARK_NO
    return out


def local_position_valid(record, legacy_policy: str = DEFAULT_LEGACY_POLICY
                         ) -> np.ndarray:
    """``[8, A-line]`` bool: columns that are direct human boundary evidence.

    A column qualifies only when a human stroke actually covered it, the
    ordering constraint has not since moved it, the human did not mark the
    boundary unidentifiable or unreliable there, and the column is not inside a
    whole-image exclusion.  Software taper, ordering displacement, an
    explicitly reviewed automatic line, and untouched automatic output are all
    excluded — none of them is a human saying "the boundary is here".
    """
    check_legacy_policy(legacy_policy)
    excluded = np.asarray(record["region_excluded"], bool)
    columns = ~excluded
    visibility = record_visibility(record)
    reliability = record_reliability(record)
    not_denied = (visibility != MARK_NO) & (reliability != MARK_NO)

    if record.get("local_provenance_available", False):
        code = np.asarray(record["provenance_code"], np.uint8)
        drawn = np.isin(code, np.asarray(TRUSTED_POSITION_CODES, np.uint8))
    elif legacy_policy == "strict":
        drawn = np.zeros(visibility.shape, bool)
    else:
        # Documented approximation, not a recovered history: see LEGACY_POLICIES.
        drawn = np.broadcast_to(
            np.asarray(record["surface_edited"], bool)[:, None], visibility.shape)
    return drawn & not_denied & columns[None, :]


def record_visibility(record) -> np.ndarray:
    """``[8, A-line]`` tri-state visibility, whole-surface flag folded in."""
    local = record.get("local_visibility")
    if local is None:
        local = np.full(
            (N_SURFACES, np.asarray(record["surfaces"]).shape[1]),
            MARK_UNKNOWN, np.uint8)
    return effective_marks(local, record["surface_visible"])


def record_reliability(record) -> np.ndarray:
    """``[8, A-line]`` tri-state analysis reliability, flag folded in."""
    local = record.get("local_reliability")
    if local is None:
        local = np.full(
            (N_SURFACES, np.asarray(record["surfaces"]).shape[1]),
            MARK_UNKNOWN, np.uint8)
    return effective_marks(local, record["surface_reliable"])


def legacy_local(record, legacy_policy: str = DEFAULT_LEGACY_POLICY) -> dict:
    """Local arrays synthesised for a label written before this format.

    The only inference made is the one that is actually sound: a surface whose
    ``surface_edited`` and ``surface_displaced`` flags are both false was not
    touched by anybody, so every one of its columns is genuinely ``PROV_AUTO``.
    Everything else becomes ``PROV_UNAVAILABLE`` — explicitly "this file never
    recorded it" — rather than a guessed stroke extent.
    """
    check_legacy_policy(legacy_policy)
    n_col = np.asarray(record["surfaces"]).shape[1]
    out = empty_local(n_col)
    edited = np.asarray(record["surface_edited"], bool)
    displaced = np.asarray(record["surface_displaced"], bool)
    code = np.full((N_SURFACES, n_col), PROV_AUTO, np.uint8)
    code[edited | displaced, :] = PROV_UNAVAILABLE
    out["provenance_code"] = code
    out["local_provenance_available"] = False
    return out


def summarise(record, legacy_policy: str = DEFAULT_LEGACY_POLICY) -> dict:
    """Counts a human or a log line can read, per surface."""
    code = np.asarray(record["provenance_code"], np.uint8)
    visibility = record_visibility(record)
    reliability = record_reliability(record)
    valid = local_position_valid(record, legacy_policy)
    return {
        "local_provenance_available": bool(
            record.get("local_provenance_available", False)),
        "drawn_columns": valid.sum(axis=1).astype(int),
        "taper_columns": (code == PROV_TAPER).sum(axis=1).astype(int),
        "displaced_columns": np.isin(
            code, [PROV_DISPLACED, PROV_DRAWN_DISPLACED]).sum(axis=1).astype(int),
        "reviewed_columns": (code == PROV_REVIEWED).sum(axis=1).astype(int),
        "unavailable_columns": (code == PROV_UNAVAILABLE).sum(axis=1).astype(int),
        "not_visible_columns": (visibility == MARK_NO).sum(axis=1).astype(int),
        "unreliable_columns": (reliability == MARK_NO).sum(axis=1).astype(int),
        "unknown_visibility_columns": (
            visibility == MARK_UNKNOWN).sum(axis=1).astype(int),
    }
