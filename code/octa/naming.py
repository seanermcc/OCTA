"""
Filename / folder-name parsing and normalisation for the tree shrew OCT-A dataset.

The dataset has accumulated three years of inconsistent naming:

    T241F-R1_11_04_02_512_512_Rect_X500um_Y500um_RPE_OCTA.RAW
    TS241-L1_...          <- same animal, no sex letter
    TS241F-L1_...         <- same animal again
    TS328R1_...           <- no dash before the eye
    TS336M-R01_...        <- zero-padded scan number
    TS305F-R1_...         <- sex letter disagrees with TS305M elsewhere

and day folders that sometimes hold two animals:

    26.03.03 TS250 CNVD7 TS325 CNV D98
    26.06.16 TS328M CND D63 TS36 CNV D42      <- 'CND' typo, 'TS36' means TS336
    26.04.09 TS328M before laser
    26.05.26 TS325m cnv 6mo
    25.04.29 TS165M WT

Everything here is deliberately conservative: when a name is ambiguous the parser
records what it found and raises a `needs_review` flag rather than guessing.
Nothing downstream should silently depend on a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional


# --------------------------------------------------------------------------
# Animal identity
# --------------------------------------------------------------------------

# Canonical animal id is "TS" + the numeric part, e.g. TS241, TS267, TS336.
# Sex letters are recorded but NOT part of the identity, because they conflict
# between sessions for the same animal (TS305M vs TS305F).
_ANIMAL_RE = re.compile(r"\bT[Ss]?\s*0*(\d{2,4})\s*([FfMm])?\b")

# Scan-level prefix of a RAW filename, e.g. "TS336M-R01", "TS328R1", "T241F-L4"
_SCAN_PREFIX_RE = re.compile(
    r"""^
    T[Ss]?              # T or TS
    0*(?P<num>\d{2,4})  # animal number
    (?P<sex>[FfMm])?    # optional sex letter
    [-_ ]?              # optional separator (sometimes absent: TS328R1)
    (?P<eye>[LlRr])     # eye
    0*(?P<scan>\d{1,3}) # scan number within the session
    (?=_|$)
    """,
    re.VERBOSE,
)

# Known typos mapped to the animal they actually refer to. Keep this table
# explicit and small; every entry is a judgement call that should be visible.
ANIMAL_ALIASES = {
    "TS36": "TS336",   # '26.06.16 ... TS36 CNV D42' - TS336 is the animal imaged that day
}


def canonical_animal(num: str | int) -> str:
    return f"TS{int(num)}"


# --------------------------------------------------------------------------
# Timepoint
# --------------------------------------------------------------------------

# 'CNV D7', 'CNVD7', 'cnv d56', 'D0', 'DAY0', 'CND D63', 'd21'
_DAY_RE = re.compile(r"\b(?:CNV|CND)?\s*[Dd](?:ay|AY)?\s*0*(\d{1,3})\b")
# '6mo', '6 mo', '6month'
_MONTH_RE = re.compile(r"\b0*(\d{1,2})\s*mo(?:nth)?s?\b", re.IGNORECASE)

_PRE_LASER_RE = re.compile(r"before\s+(?:and\s+after\s+)?laser", re.IGNORECASE)
_LASER_DAY_RE = re.compile(r"laser\s*day", re.IGNORECASE)
_WT_RE = re.compile(r"\bWT\b", re.IGNORECASE)

DAYS_PER_MONTH = 30


@dataclass
class Timepoint:
    """Days since CNV laser induction. `label` preserves the original wording."""
    days: Optional[int]
    label: str
    kind: str  # 'day' | 'month' | 'laser_day' | 'pre_laser' | 'wildtype' | 'unknown'

    @property
    def is_baseline(self) -> bool:
        return self.kind in ("laser_day", "pre_laser") or self.days == 0


def _timepoint_from_text(text: str) -> Timepoint:
    """Interpret one fragment of a folder name as a timepoint."""
    if _WT_RE.search(text):
        return Timepoint(None, "WT", "wildtype")
    if _PRE_LASER_RE.search(text):
        return Timepoint(0, "before laser", "pre_laser")
    if _LASER_DAY_RE.search(text):
        return Timepoint(0, "laser day", "laser_day")
    m = _MONTH_RE.search(text)
    if m:
        months = int(m.group(1))
        return Timepoint(months * DAYS_PER_MONTH, f"{months} mo", "month")
    m = _DAY_RE.search(text)
    if m:
        d = int(m.group(1))
        return Timepoint(d, f"D{d}", "day")
    return Timepoint(None, text.strip(), "unknown")


# --------------------------------------------------------------------------
# Session folder
# --------------------------------------------------------------------------

_DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{2})\b")


@dataclass
class SessionInfo:
    folder: str
    date: Optional[str]                       # ISO yyyy-mm-dd
    animals: dict = field(default_factory=dict)   # canonical id -> Timepoint
    needs_review: list = field(default_factory=list)

    def timepoint_for(self, animal: str) -> Timepoint:
        if animal in self.animals:
            return self.animals[animal]
        # Single-animal session: the one timepoint applies regardless of how the
        # scan filename spelled the animal.
        if len(self.animals) == 1:
            return next(iter(self.animals.values()))
        return Timepoint(None, "", "unknown")


def parse_session_folder(name: str) -> SessionInfo:
    """
    Parse a day-folder name into a date and an {animal -> timepoint} mapping.

    Strategy: find every animal token and every timepoint token, in order of
    appearance, then pair them positionally. A folder naming two animals reads
    '<animal A> <tp A> <animal B> <tp B>', so slicing the string at each animal
    token and reading the fragment that follows gives the right pairing.
    """
    info = SessionInfo(folder=name, date=None)

    m = _DATE_RE.match(name)
    if m:
        yy, mm, dd = m.groups()
        info.date = f"20{yy}-{mm}-{dd}"
    else:
        info.needs_review.append("no leading date")

    rest = name[m.end():] if m else name

    hits = list(_ANIMAL_RE.finditer(rest))
    if not hits:
        # e.g. '24.08.14 tree shrew CNV d0' - animal is only in the filenames.
        tp = _timepoint_from_text(rest)
        if tp.kind == "unknown":
            info.needs_review.append("no animal and no timepoint in folder name")
        else:
            info.animals["__unnamed__"] = tp
        return info

    for i, h in enumerate(hits):
        raw = f"TS{int(h.group(1))}"
        animal = ANIMAL_ALIASES.get(raw, raw)
        if raw in ANIMAL_ALIASES:
            info.needs_review.append(f"alias {raw} -> {animal}")
        end = hits[i + 1].start() if i + 1 < len(hits) else len(rest)
        fragment = rest[h.end():end]
        tp = _timepoint_from_text(fragment)
        if tp.kind == "unknown":
            # Timepoint may sit before the animal token ('CNV D14 D28 for section')
            start = hits[i - 1].end() if i > 0 else 0
            tp = _timepoint_from_text(rest[start:h.start()])
        if tp.kind == "unknown":
            info.needs_review.append(f"no timepoint found for {animal}")
        info.animals[animal] = tp

    return info


# --------------------------------------------------------------------------
# Acquisition (RAW) filename
# --------------------------------------------------------------------------

_SCANPARAM_RE = re.compile(
    r"_(?P<nfast>\d+)_(?P<nslow>\d+)_(?P<pattern>[A-Za-z]+)"
    r"_X(?P<xum>\d+)um_Y(?P<yum>\d+)um"
)
_TIME_RE = re.compile(r"_(\d{2})_(\d{2})_(\d{2})_")


@dataclass
class ScanInfo:
    stem: str                      # filename without extension
    animal: Optional[str]          # canonical, e.g. TS336
    sex_letter: Optional[str]      # as written on THIS scan, may conflict across sessions
    eye: Optional[str]             # 'OD' (right) or 'OS' (left)
    scan_no: Optional[int]
    acq_time: Optional[str]        # HH:MM:SS
    n_fast: Optional[int]
    n_slow: Optional[int]
    x_drive_um: Optional[int]      # galvo drive amplitude, NOT retinal extent
    y_drive_um: Optional[int]
    needs_review: list = field(default_factory=list)


def parse_scan_name(stem: str) -> ScanInfo:
    """Parse a RAW filename stem such as
    'TS267F-R2_11_20_13_512_512_Rect_X500um_Y500um_RPE_OCTA'."""
    out = ScanInfo(stem=stem, animal=None, sex_letter=None, eye=None,
                   scan_no=None, acq_time=None, n_fast=None, n_slow=None,
                   x_drive_um=None, y_drive_um=None)

    m = _SCAN_PREFIX_RE.match(stem)
    if m:
        raw = f"TS{int(m.group('num'))}"
        out.animal = ANIMAL_ALIASES.get(raw, raw)
        out.sex_letter = (m.group("sex") or "").upper() or None
        out.eye = "OD" if m.group("eye").upper() == "R" else "OS"
        out.scan_no = int(m.group("scan"))
    else:
        out.needs_review.append("unparsed scan prefix")

    m = _TIME_RE.search(stem)
    if m:
        out.acq_time = ":".join(m.groups())

    m = _SCANPARAM_RE.search(stem)
    if m:
        out.n_fast = int(m.group("nfast"))
        out.n_slow = int(m.group("nslow"))
        out.x_drive_um = int(m.group("xum"))
        out.y_drive_um = int(m.group("yum"))
    else:
        out.needs_review.append("unparsed scan parameters")

    return out


def processed_dir_name(raw_stem: str) -> str:
    """`X_OCTA.RAW` -> `X_OCTA_Processed`."""
    return raw_stem + "_Processed"


def volumes_mat_name(raw_stem: str) -> str:
    """The pipeline drops '_OCTA' before appending '_processedVolumes.mat'
    (see avgVols_saveVol.m: fname = fname1(1:end-5))."""
    stem = raw_stem[:-5] if raw_stem.endswith("_OCTA") else raw_stem
    return stem + "_processedVolumes.mat"
