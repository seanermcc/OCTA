#!/usr/bin/env python3
"""Build the manual-review strata from the ranked QC workbook.

The workbook's ``Metrics`` sheet is the source of truth.  It defines
``qc_score`` as the equal-weight overall QC score (higher is better) and
``qc_score_percentile`` as its dataset percentile.  The default selection is
for the first 160 B-scan pass:

* 16 bottom-score volumes × (5 suspect + 1 median control) = 96 low-QC B-scans
*  8 volumes nearest the 50th percentile × (3 + 1) = 32 medium-QC B-scans
*  8 volumes nearest the 90th percentile × (3 + 1) = 32 high-QC B-scans

This is a 3:1:1 low:medium:high-quality mix.  The three strata are disjoint.
The reader uses only Python's standard library so it runs in the existing OCT
environment without adding an Excel dependency.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _column_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - ord("A") + 1
    return value - 1


def _read_metrics(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read cached displayed values from the XLSX Metrics sheet."""
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relation = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        target = None
        for sheet in workbook.findall(f".//{MAIN_NS}sheet"):
            if sheet.attrib.get("name") == "Metrics":
                target = relation[sheet.attrib[f"{REL_NS}id"]]
                break
        if target is None:
            raise ValueError("workbook has no sheet named Metrics")
        target = target.lstrip("/")
        sheet_path = target if target.startswith("xl/") else "xl/" + target
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(item.itertext()) for item in shared_root.findall(f"{MAIN_NS}si")]
        root = ET.fromstring(archive.read(sheet_path))

    matrix: list[dict[int, str]] = []
    for row in root.findall(f".//{MAIN_NS}sheetData/{MAIN_NS}row"):
        values: dict[int, str] = {}
        for cell in row.findall(f"{MAIN_NS}c"):
            col = _column_index(cell.attrib["r"])
            raw = cell.find(f"{MAIN_NS}v")
            value = "" if raw is None or raw.text is None else raw.text
            if cell.attrib.get("t") == "s" and value:
                value = shared[int(value)]
            elif cell.attrib.get("t") == "inlineStr":
                inline = cell.find(f"{MAIN_NS}is")
                value = "" if inline is None else "".join(inline.itertext())
            values[col] = value
        matrix.append(values)
    if not matrix:
        raise ValueError("Metrics sheet has no rows")
    width = max(matrix[0]) + 1
    headers = [matrix[0].get(i, "") for i in range(width)]
    rows = [{header: row.get(i, "") for i, header in enumerate(headers)}
            for row in matrix[1:] if row]
    return headers, rows


def _nearest(rows: list[dict], percentile: float, n: int) -> list[dict]:
    return sorted(rows, key=lambda row: (
        abs(row["_percentile"] - percentile), row["_score"], row["scan_id"]))[:n]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True,
                        help="ranked QC .xlsx containing a Metrics sheet")
    parser.add_argument("--low-volumes", type=int, default=16)
    parser.add_argument("--medium-volumes", type=int, default=8)
    parser.add_argument("--high-volumes", type=int, default=8)
    parser.add_argument("--out", default="../outputs/eight_surface/qc_review_groups.csv")
    args = parser.parse_args()
    if min(args.low_volumes, args.medium_volumes, args.high_volumes) < 1:
        parser.error("all group sizes must be positive")

    try:
        fields, source = _read_metrics(Path(args.workbook))
    except Exception as exc:  # noqa: BLE001
        parser.error(f"could not read Metrics sheet: {exc}")
    required = {"scan_id", "qc_score", "qc_score_percentile"}
    missing = required - set(fields)
    if missing:
        parser.error("Metrics sheet missing: " + ", ".join(sorted(missing)))
    eligible = []
    for row in source:
        try:
            row["_score"] = float(row["qc_score"])
            row["_percentile"] = float(row["qc_score_percentile"])
            if row.get("status", "ok").lower() != "ok":
                continue
        except (ValueError, TypeError):
            continue
        eligible.append(row)
    if args.low_volumes + args.medium_volumes + args.high_volumes > len(eligible):
        parser.error("requested group sizes exceed usable QC rows")

    low = sorted(eligible, key=lambda row: (row["_score"], row["scan_id"]))[:args.low_volumes]
    low_ids = {row["scan_id"] for row in low}
    medium = _nearest([row for row in eligible if row["scan_id"] not in low_ids],
                      50.0, args.medium_volumes)
    used = low_ids | {row["scan_id"] for row in medium}
    high = _nearest([row for row in eligible if row["scan_id"] not in used],
                    90.0, args.high_volumes)
    selection = []
    for group, rule, rows in (
        ("low", "lowest qc_score", low),
        ("medium", "nearest qc_score_percentile 50", medium),
        ("high", "nearest qc_score_percentile 90", high),
    ):
        for row in rows:
            clean = {key: value for key, value in row.items() if not key.startswith("_")}
            clean["quality_group"] = group
            clean["selection_rule"] = rule
            selection.append(clean)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    out_fields = fields + ["quality_group", "selection_rule"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selection)
    print(f"read {len(eligible)} usable rows from {Path(args.workbook).name}")
    for group in ("low", "medium", "high"):
        sub = [row for row in selection if row["quality_group"] == group]
        score = [float(row["qc_score"]) for row in sub]
        pct = [float(row["qc_score_percentile"]) for row in sub]
        print(f"  {group:6s} n={len(sub):2d} qc_score {min(score):.3f}-{max(score):.3f}; "
              f"percentile {min(pct):.2f}-{max(pct):.2f}")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
