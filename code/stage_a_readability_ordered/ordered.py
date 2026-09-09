"""Ordered native-depth posterior decoding, independent across rejected gaps.

Exact eight-surface column DP, then two deterministic coordinate-descent sweeps
with bounded lateral penalties. This is not a global 2-D optimum. No anatomy
thickness prior, interpolation, or post-hoc displacement of unsupported rows.
"""
import numpy as np
from stage_a.inference import REASONS as BASE_REASONS

REASONS = {**BASE_REASONS, "readability": 32, "posterior_unsupported": 64,
           "order_infeasible": 128, "simple_entropy_signal": 256}


def intervals(mask):
    padded = np.r_[False, np.asarray(mask, bool), False].astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return list(zip(edges[::2], edges[1::2]))


def ordered_column(cost, gap=1):
    """Globally minimal ordered depths for one [surface, depth] cost array."""
    cost = np.asarray(cost, np.float64)
    if cost.ndim != 2 or gap < 1 or int(gap) != gap or np.isnan(cost).any():
        raise ValueError("Invalid ordered-column cost/gap")
    n, height = cost.shape
    dp = cost[0].copy()
    trace = np.full((n, height), -1, np.int32)
    index = np.arange(height)
    for k in range(1, n):
        minima = np.minimum.accumulate(dp)
        # Earliest minimum wins ties, independently of platform.
        changed = np.r_[True, minima[1:] < minima[:-1]]
        argmin = np.maximum.accumulate(np.where(changed, index, 0))
        prev = np.full(height, np.inf)
        prev[gap:] = minima[:-gap]
        trace[k, gap:] = argmin[:-gap]
        dp = cost[k] + prev
    last = int(np.argmin(dp))
    if not np.isfinite(dp[last]):
        return None
    rows = np.empty(n, np.int32)
    rows[-1] = last
    for k in range(n - 1, 0, -1):
        rows[k - 1] = trace[k, rows[k]]
    return rows


def base_reasons(rows, scope, shadow):
    reason = np.zeros(rows.shape, np.uint16)
    reason[:, ~np.asarray(scope, bool)] |= REASONS["outside_scope"]
    reason[:, np.asarray(shadow, bool)] |= REASONS["shadow"]
    reason[~np.isfinite(rows)] |= REASONS["missing"]
    return reason


def crossing_flags(rows):
    bad = np.isfinite(rows[:-1]) & np.isfinite(rows[1:]) & (rows[:-1] > rows[1:])
    flags = np.zeros(rows.shape, bool)
    flags[:-1] |= bad
    flags[1:] |= bad
    return flags


def decode_ordered(logits, raw_rows, entropy, scope, shadow, config, keep=None):
    """Return diagnostic decoded rows plus reason-coded NaN measurement rows.

    A column is unsupported if ANY boundary exceeds its training p99.5 entropy
    or lacks a finite posterior. Ordered DP candidates must be within log(20)
    of their own posterior peak. If eight supported ordered rows do not exist,
    withhold the entire column. Surviving intervals are solved independently.
    """
    logits = np.asarray(logits, np.float32)
    raw_rows, entropy = np.asarray(raw_rows), np.asarray(entropy)
    if logits.ndim != 3 or logits.shape[0] != 8 or raw_rows.shape != logits.shape[::2] or entropy.shape != raw_rows.shape:
        raise ValueError("Expected [8, native depth, A-line] logits")
    n, height, width = logits.shape
    reason = base_reasons(raw_rows, scope, shadow)
    if keep is not None:
        reason[:, ~np.asarray(keep, bool)] |= REASONS["readability"]
    finite = np.isfinite(logits).all((0, 1))
    unsupported = (~finite | (~np.isfinite(entropy)).any(0)
                   | (entropy > np.asarray(config["entropy_cap"])[:, None]).any(0))
    reason[:, unsupported] |= REASONS["posterior_unsupported"]
    candidate = (reason == 0).all(0)
    safe = np.where(np.isfinite(logits), logits, -1e6)
    cost = safe.max(1, keepdims=True) - safe
    cost[cost > config["max_log_drop"]] = np.inf
    decoded = np.full((n, width), np.nan, np.float32)
    for c in np.flatnonzero(candidate):
        rows = ordered_column(cost[:, :, c])
        if rows is None:
            reason[:, c] |= REASONS["order_infeasible"]
            candidate[c] = False
        else:
            decoded[:, c] = rows
    depth = np.arange(height)[None, :]
    scale = np.asarray(config["continuity_scale_px"])[:, None]
    if scale.shape != (8, 1) or not np.isfinite(scale).all() or (scale <= 0).any():
        raise ValueError("Invalid measured continuity scales")
    for start, end in intervals(candidate):
        for direction in (range(start, end), range(end - 1, start - 1, -1)):
            for c in direction:
                local = cost[:, :, c].copy()
                for neighbor in (c - 1, c + 1):
                    if start <= neighbor < end:
                        penalty = np.minimum(abs(depth - decoded[:, neighbor, None]) / scale,
                                             config["continuity_truncation"])
                        local += config["continuity_weight"] * penalty
                rows = ordered_column(local)
                if rows is None:
                    raise RuntimeError("Finite bounded penalty made a feasible column infeasible")
                decoded[:, c] = rows
    retained = reason == 0
    reason[~np.isfinite(decoded) & retained] |= REASONS["missing"]
    retained = reason == 0
    if crossing_flags(np.where(retained, decoded, np.nan)).any():
        raise RuntimeError("Ordered decoder invariant failed")
    return dict(rows=decoded, retained=retained, reason_bits=reason,
                retained_rows=np.where(retained, decoded, np.nan),
                decoder_displacement_px=decoded - raw_rows)


def gated_raw(rows, scope, shadow, keep=None, reason_name="readability"):
    reason = base_reasons(rows, scope, shadow)
    reason[crossing_flags(rows)] |= REASONS["crossing"]
    if keep is not None:
        reason[:, ~np.asarray(keep, bool)] |= REASONS[reason_name]
    retained = reason == 0
    return dict(rows=rows.copy(), retained=retained, reason_bits=reason,
                retained_rows=np.where(retained, rows, np.nan),
                decoder_displacement_px=np.zeros_like(rows))
