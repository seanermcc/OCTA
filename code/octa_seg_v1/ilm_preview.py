"""Read-only ILM diagnostic overlay; never a measurement or training target."""
from pathlib import Path
import numpy as np
from eight_surface import provenance as P


def load_ilm_preview(provider_path, scan_id, names, shape):
    """Load the frozen position branch in the provider's canonical crop frame."""
    provider_path = Path(provider_path)
    path = provider_path.parents[2] / "volumes" / scan_id / "measurements.npz"
    if not path.exists():
        return None, path
    with np.load(provider_path, allow_pickle=False) as provider:
        if str(provider["scan_id"].reshape(-1)[0]) != scan_id:
            raise ValueError("ILM preview scan identity mismatch")
        offset = int(provider["label_offset"].item())
        if list(provider["surface_names"]) != list(names):
            raise ValueError("ILM preview boundary names mismatch")
    with np.load(path, allow_pickle=False) as data:
        if int(data["label_offset"].item()) != offset or list(data["surface_names"]) != list(names):
            raise ValueError("ILM preview coordinate frame mismatch")
        raw = data["raw_position_branch"]
        if raw.shape != tuple(shape):
            raise ValueError("ILM preview native shape mismatch")
        return raw[:, list(names).index("ILM"), :].astype(np.float32) - offset, path


def ilm_preview_mask(rows, state, automatic_state, ilm_index, depth):
    """Deny continuations at not-traceable/excluded locations, without edits."""
    visible = P.effective_marks(state.local["local_visibility"], state.visible)[ilm_index]
    mask = (np.isfinite(rows) & (rows >= 0) & (rows <= depth - 1)
            & (visible != P.MARK_NO) & ~state.excluded
            & (automatic_state[ilm_index] != 2))
    if state.verdict == "rejected":
        mask[:] = False
    return mask
