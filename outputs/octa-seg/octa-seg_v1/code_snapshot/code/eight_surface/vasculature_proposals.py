"""Read automatic vessel starting masks separately from human annotation files."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

DEFAULT_PROPOSALS = Path(__file__).resolve().parents[2] / "outputs/eight_surface/vasculature_proposals"
PROPOSAL_VERSION = "1-major-vessel-gui-seed"


def load_proposal(directory, scan):
    path = Path(directory) / f"{scan.scan_id}_proposal.npz"
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as data:
        def scalar(key):
            return str(data[key][0])
        if scalar("proposal_format_version") != PROPOSAL_VERSION:
            raise ValueError(f"Unsupported vessel proposal format: {path.name}")
        if scalar("scan_id") != scan.scan_id:
            raise ValueError(f"Vessel proposal belongs to another scan: {path.name}")
        if scalar("axis_order") != "B-scan,A-line":
            raise ValueError(f"Vessel proposal has incompatible axes: {path.name}")
        mask = data["predicted_vasculature_mask"]
        if mask.dtype != bool or mask.shape != scan.native_shape:
            raise ValueError(f"Vessel proposal does not match the native grid: {path.name}")
        if Path(scalar("source_volume")).resolve() != scan.source_volume.resolve():
            raise ValueError(f"Vessel proposal has a different source volume: {path.name}")
        if tuple(data["retina_band"]) != tuple(scan.retina_band):
            raise ValueError(f"Vessel proposal has a different projection band: {path.name}")
        if bool(data["human_reviewed"][0]):
            raise ValueError("An automatic proposal cannot claim human review")
        return dict(mask=mask.copy(), path=str(path.resolve()),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    method=scalar("method"))


def has_saved_vessel_work(record):
    """A reviewed empty mask or a saved empty automatic draft must also win."""
    return record is not None and bool(
        record["reviewed_targets"][1] or record["vasculature_mask"].any()
        or record.get("vasculature_proposal_path", "")
        or np.asarray(record.get("vasculature_brush_touched", False)).any())
