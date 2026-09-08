"""Head-to-head predictor comparison on identical decisions and eligible masks.

Added 2026-09-08 for the first development run. It lives outside the
`stage_a` package on purpose: `train.code_identity()` hashes every module in
that directory, so adding analysis code there would invalidate resume for
already-trained checkpoints. Run it as `python code/stage_a_compare.py ...`.

Reads only the prediction
arrays each `stage_a.evaluate` run already wrote plus the frozen derived
targets; it never re-runs a predictor, re-reads human labels or re-tunes
anything. Two cohorts are reported side by side because they answer different
questions:

  complete  - every decision in the split; a predictor with no output for a
              B-scan keeps those columns in its eligible denominator and they
              count as failures. This is the honest headline.
  shared    - restricted to decisions where *every* named predictor produced a
              file. Comparable, but a smaller and possibly easier cohort, so it
              may not be read as a complete-cohort result.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from stage_a.common import DEFAULT, output_dir, write_json, write_csv
from stage_a.data import Dataset
from stage_a.metrics import evaluate


def load_predictions(directory, records):
    directory = Path(directory)
    preds = {}
    for r in records:
        path = directory / f"{r['key']}.npz"
        if not path.exists():
            continue
        with np.load(path, allow_pickle=False) as d:
            preds[r["key"]] = {k: d[k].copy() for k in d.files}
    return preds


def run(args):
    root = Path(args.data)
    m = json.loads((root / "manifest.json").read_text())
    if args.split == "test":
        raise ValueError("Final-test animals are locked; comparison is development-only")
    data = Dataset(root, args.split, eligible_only=False)
    out = output_dir(args.out)
    named = dict(pair.split("=", 1) for pair in args.evals)
    records = data.records
    targets = {}
    for r in records:
        with np.load(r["targets"], allow_pickle=False) as t:
            targets[r["key"]] = {k: t[k].copy() for k in t.files}
    preds = {name: load_predictions(d, records) for name, d in named.items()}

    eligible = [r for r in records if targets[r["key"]]["valid"].any()]
    shared_keys = sorted(set.intersection(*[set(p) for p in preds.values()])) if preds else []
    shared = [r for r in records if r["key"] in shared_keys]

    rows, macro_rows, coverage = [], [], []
    for name in named:
        present = set(preds[name])
        coverage.append(dict(predictor=name, source=named[name],
            decisions_in_split=len(records), decisions_with_prediction=len(present),
            decisions_missing=len(records) - len(present),
            eligible_decisions=len(eligible),
            eligible_with_prediction=sum(r["key"] in present for r in eligible),
            eligible_missing=sum(r["key"] not in present for r in eligible),
            eligible_animals=len(sorted({r["animal"] for r in eligible})),
            eligible_animals_with_any_prediction=len(sorted({r["animal"] for r in eligible if r["key"] in present})),
            missing_eligible_keys=";".join(r["key"] for r in eligible if r["key"] not in present)))
        for cohort, subset in (("complete", records), ("shared_available", shared)):
            report = evaluate(subset, targets, preds[name], m["sources"], args.gross_um)
            for s in report["summary"]:
                rows.append(dict(predictor=name, cohort=cohort, n_decisions=len(subset), **s))
            for s in report["animal_macro"]:
                macro_rows.append(dict(predictor=name, cohort=cohort,
                                       n_decisions=len(subset), **s))
    write_csv(out / "comparison.csv", rows)
    write_csv(out / "comparison_animal_macro.csv", macro_rows)
    write_csv(out / "prediction_coverage.csv", coverage)
    write_json(out / "comparison_meta.json", dict(
        dataset_id=m["dataset_id"], partition_id=data.partitions["partition_id"], split=args.split,
        predictors=named, gross_um=args.gross_um,
        shared_available_keys=shared_keys, n_shared_available=len(shared),
        n_decisions=len(records), n_eligible_decisions=len(eligible),
        convention=("complete cohort keeps missing predictions in eligible denominators as failures; "
                    "shared_available restricts to decisions all listed predictors produced and is not "
                    "a complete-cohort result."),
        experimental=True, validated=False))
    print(json.dumps(coverage, indent=2))
    print(f"shared_available decisions: {len(shared)} of {len(records)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=DEFAULT)
    p.add_argument("--split", choices=["train", "validation"], default="validation")
    p.add_argument("--evals", nargs="+", required=True, help="name=eval_directory")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--gross-um", type=float, default=25.0)
    run(p.parse_args())
