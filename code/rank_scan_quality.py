#!/usr/bin/env python3
"""Turn independent scan-QC measurements into transparent rank-based scores.

The score is an equal-weight average of three *metric ranks*, not a fourth
measurement: signal, slow-axis continuity, and repeat agreement.  Higher is
better.  Scans without a comparable repeat use the two observable ranks and
carry ``qc_score_component_n=2`` so that they are never mistaken for a
three-axis result.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


def _num(row: dict, name: str) -> float:
    try:
        x = float(row.get(name, ""))
        return x if np.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def percentile_rank(values: np.ndarray, higher_is_better: bool) -> np.ndarray:
    """0..100 empirical percentile rank; NaN stays unavailable."""
    out = np.full(values.shape, np.nan, dtype=float)
    valid = np.flatnonzero(np.isfinite(values))
    if not valid.size:
        return out
    vals = values[valid]
    order = np.argsort(vals, kind="stable")
    ranks = np.empty(vals.size, dtype=float)
    ranks[order] = np.arange(vals.size, dtype=float)
    # Average tied ranks: scores stay stable if values are exactly repeated.
    for value in np.unique(vals):
        tied = vals == value
        ranks[tied] = ranks[tied].mean()
    if vals.size == 1:
        pct = np.full(1, 50.0)
    else:
        pct = 100.0 * ranks / (vals.size - 1)
    out[valid] = pct if higher_is_better else 100.0 - pct
    return out


def add_ranks(rows: list[dict]) -> None:
    fields = [
        ("retina_cnr", True, "rank_signal_cnr"),
        ("low_signal_frac", False, "rank_signal_coverage"),
        ("bscan_discontinuity_p95", False, "rank_continuity_adjacent"),
        ("axial_centroid_residual_p95_px", False, "rank_continuity_axial"),
        ("brightness_stripe_mad", False, "rank_continuity_stripe"),
        ("repeat_corr_median", True, "rank_repeat_agreement"),
    ]
    ranks: dict[str, np.ndarray] = {}
    for source, direction, target in fields:
        ranks[target] = percentile_rank(
            np.asarray([_num(r, source) for r in rows]), direction)
        for row, value in zip(rows, ranks[target]):
            row[target] = "" if not np.isfinite(value) else round(float(value), 3)

    def mean_components(*names: str) -> np.ndarray:
        a = np.stack([ranks[n] for n in names], axis=1)
        with np.errstate(invalid="ignore"):
            return np.nanmean(a, axis=1)

    signal = mean_components("rank_signal_cnr", "rank_signal_coverage")
    continuity = mean_components("rank_continuity_adjacent", "rank_continuity_axial",
                                 "rank_continuity_stripe")
    repeat = ranks["rank_repeat_agreement"]
    overall = np.nanmean(np.stack([signal, continuity, repeat], axis=1), axis=1)
    overall_pct = percentile_rank(overall, True)
    for i, row in enumerate(rows):
        row["rank_signal"] = round(float(signal[i]), 3)
        row["rank_continuity"] = round(float(continuity[i]), 3)
        row["rank_repeat"] = "" if not np.isfinite(repeat[i]) else round(float(repeat[i]), 3)
        row["qc_score_component_n"] = int(2 + np.isfinite(repeat[i]))
        row["qc_score"] = round(float(overall[i]), 3)
        row["qc_score_percentile"] = round(float(overall_pct[i]), 3)


def choose_examples(rows: list[dict]) -> list[dict]:
    targets = [("low_01pct", 1.0), ("middle_50pct", 50.0), ("high_99pct", 99.0)]
    available = [r for r in rows if _num(r, "qc_score_percentile") == _num(r, "qc_score_percentile")]
    chosen: list[dict] = []
    used: set[str] = set()
    for label, target in targets:
        candidates = sorted((r for r in available if r["scan_id"] not in used),
                            key=lambda r: abs(_num(r, "qc_score_percentile") - target))
        r = candidates[0]
        used.add(r["scan_id"])
        chosen.append({"example_group": label, "target_percentile": target,
                       "scan_id": r["scan_id"], "qc_score": r["qc_score"],
                       "qc_score_percentile": r["qc_score_percentile"],
                       "rank_signal": r["rank_signal"],
                       "rank_continuity": r["rank_continuity"],
                       "rank_repeat": r["rank_repeat"],
                       "qc_score_component_n": r["qc_score_component_n"],
                       "source": r.get("source", "")})
    return chosen


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    for r in rows:
        for key in r:
            if key not in fields: fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="input", default="../outputs/scan_quality_metrics.csv")
    ap.add_argument("--out", default="../outputs/scan_quality_ranked.csv")
    ap.add_argument("--examples", default="../outputs/scan_quality_examples.csv")
    args = ap.parse_args()
    with Path(args.input).open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    add_ranks(rows)
    write_csv(Path(args.out), rows)
    write_csv(Path(args.examples), choose_examples(rows))
    print(f"wrote {args.out} ({len(rows)} rows)")
    print(f"wrote {args.examples}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
