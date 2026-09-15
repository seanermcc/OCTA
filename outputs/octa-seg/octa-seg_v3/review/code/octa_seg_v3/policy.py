"""Display and measurement policy. Model confidence never becomes a human annotation."""
import numpy as np
from octa_seg_v1.decisions import thickness
from octa_seg_v2.policy import apply as v2_apply, geometry_valid
from .feedback import geometry


def baseline(raw, probabilities, calibration, vessel, offset, depth):
    # Use frozen predictions, without loading anybody else's correction or guard.
    # This is the v2 working ILM / expanded-candidate policy, not a trained v3 model.
    return v2_apply(raw, probabilities, calibration, vessel, offset, depth)


def render(base, r, offset, depth, shadow):
    z = r['positions']
    state = base['state'].copy()
    visible = (r['trace'] == 1) & (r['anatomy'] != 0)
    state[visible & (state == 2)] = 3
    # Joins and ordering record how coordinates moved, not reliability judgments.
    # Keep their working appearance; training still requires a current confirmation.
    state[r.get('display_reliable', np.zeros_like(state, bool))] = 1
    state[(r['reliability'] == 1) & (r['trace'] != 0)] = 1
    # Display every finite working proposal for inspection; model confidence is not a human veto.
    state[(state == 2) & (r['trace'] != 0) & np.isfinite(z)] = 3
    state[r['approved']] = 1
    state[r['reliability'] == 0] = 3
    # Restoring reliability alone cannot cancel an explicit visibility denial.
    denied = (r['trace'] == 0) | (r['anatomy'] == 0)
    state[denied] = 2
    valid, unresolved = geometry(r, offset, depth)
    state[~valid & ~denied] = 3
    state[r['excluded'][None].repeat(len(z), axis=0) & ~denied] = 3
    allowed = valid & ~r['excluded'][None] & ~denied
    reported = np.where((state == 1) & allowed, z, np.nan).astype(np.float32)
    candidates = np.where((state == 3) & np.isfinite(z) & ~r['excluded'][None] & ~denied, z, np.nan).astype(np.float32)
    return dict(reported_positions=reported, uncertain_estimates=candidates,
                working_positions=z, state=state, valid_geometry=valid,
                thickness_um=thickness(reported, shadow))
