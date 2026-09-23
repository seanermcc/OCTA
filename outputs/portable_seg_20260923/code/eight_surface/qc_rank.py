#!/usr/bin/env python3
"""Select the lowest-quality scans by an equal-weight sum of three ranks.

This is intentionally column-agnostic until the current QC run establishes its
final three summary columns.  Give exactly three ``COLUMN:DIRECTION`` terms;
rank 1 always means the lower-quality end, and the final ``rank_sum`` has a
minimum of 3 (1 + 1 + 1).

Example (replace the column names/directions with the QC run's final names)::

    python eight_surface/qc_rank.py outputs/scan_quality_metrics.csv \
      --metric retinal_cnr:low --metric continuity:low \
      --metric repeat_agreement:low --top 160 \
      --out outputs/eight_surface/qc_lowest_160.csv

Directions: ``low`` means a lower raw value is worse; ``high`` means a higher
raw value is worse.  Rows without all three metrics are excluded by default:
the requested equal-weight three-rank score cannot be computed honestly for
them (for example, non-comparable repeats).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_metric(text: str) -> tuple[str, str]:
    try:
        column, direction = text.rsplit(":", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("metric must be COLUMN:low or COLUMN:high") from exc
    direction = direction.lower()
    if not column or direction not in {"low", "high"}:
        raise argparse.ArgumentTypeError("metric must be COLUMN:low or COLUMN:high")
    return column, direction


def average_ranks(values: list[float], worse_when: str) -> list[float]:
    """Competition-safe 1-based ranks; tied values receive their mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=worse_when == "high")
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and values[order[stop]] == values[order[start]]:
            stop += 1
        rank = ((start + 1) + stop) / 2.0
        for position in range(start, stop):
            ranks[order[position]] = rank
        start = stop
    return ranks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path")
    parser.add_argument("--metric", action="append", required=True, type=parse_metric)
    parser.add_argument("--id-column", default="scan_id")
    parser.add_argument("--top", type=int, default=160)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if len(args.metric) != 3:
        parser.error("exactly three --metric options are required")
    if args.top <= 0:
        parser.error("--top must be positive")

    with Path(args.csv_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        print("input CSV has no rows")
        return 1
    available = set(rows[0])
    required = {args.id_column, *(name for name, _direction in args.metric)}
    missing = sorted(required - available)
    if missing:
        parser.error("input CSV is missing: " + ", ".join(missing))

    eligible, excluded = [], []
    for row in rows:
        try:
            values = [float(row[name]) for name, _direction in args.metric]
            if not all(value == value and abs(value) != float("inf") for value in values):
                raise ValueError
        except (ValueError, TypeError):
            excluded.append(row)
            continue
        eligible.append((row, values))
    if not eligible:
        print("no rows have all three finite QC metrics")
        return 1

    rank_columns = []
    for metric_index, (_name, direction) in enumerate(args.metric):
        rank_columns.append(average_ranks([values[metric_index] for _row, values in eligible], direction))
    ranked = []
    for i, (row, values) in enumerate(eligible):
        out = dict(row)
        for (name, _direction), ranks in zip(args.metric, rank_columns):
            out[f"rank_{name}"] = f"{ranks[i]:.1f}"
        total = sum(ranks[i] for ranks in rank_columns)
        out["rank_sum"] = f"{total:.1f}"
        ranked.append(out)
    ranked.sort(key=lambda row: (float(row["rank_sum"]), row[args.id_column]))
    selected = ranked[:args.top]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) + [f"rank_{name}" for name, _direction in args.metric] + ["rank_sum"]
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selected)
    print(f"ranked {len(eligible)} eligible rows; excluded {len(excluded)} missing/non-finite rows")
    print(f"wrote lowest {len(selected)} equal-weight rank sums to {out_path}")
    print("minimum possible rank_sum is 3.0 (rank 1 on all three QC metrics)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

