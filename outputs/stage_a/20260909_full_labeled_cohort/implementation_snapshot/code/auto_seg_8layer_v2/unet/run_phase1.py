#!/usr/bin/env python3
"""Phase 1 driver: census, tensor cache, samples, folds, evaluation self-test.

No model, no training -- this builds and checks the inputs Phase 2 will consume.

Run from ``code`` with ``octa`` activated::

    python auto_seg_8layer_v2/unet/run_phase1.py                # everything
    python auto_seg_8layer_v2/unet/run_phase1.py --census-only
    python auto_seg_8layer_v2/unet/run_phase1.py --rerun-v2     # slow, ~15 volumes

``--rerun-v2`` is the strongest form of the harness self-test: it re-runs the
revision-2 cascade through the real volume pipeline on the same 53 corrected
B-scans and checks the harness reproduces the ``v2_outer_anchor__priors_five``
block of ``qc/variant_comparison.json``.  The default self-test reproduces the
shipped-cascade block from the ``auto_surfaces`` stored in each label, which
needs no segmentation run.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[2]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from eight_surface import labels as L  # noqa: E402
from eight_surface.config import SURFACE_NAMES  # noqa: E402

from auto_seg_8layer_v2.unet import dataset, evaluate, flatten, folds, targets  # noqa: E402
from auto_seg_8layer_v2.unet import tensors  # noqa: E402

OUT = CODE_DIR.parent / "outputs"
DEFAULTS = {
    "labels": OUT / "eight_surface" / "labels",
    "repeat_labels": OUT / "auto_seg_8layer_v2" / "repeatability" / "labels",
    "packs": OUT / "eight_surface" / "review",
    "segmented": OUT / "eight_surface" / "segmented",
    "qc_groups": OUT / "eight_surface" / "qc_review_groups.csv",
    "variants": OUT / "auto_seg_8layer_v2" / "qc" / "variant_comparison.json",
    "cache": OUT / "auto_seg_8layer_v2" / "unet" / "tensors",
    "out": OUT / "auto_seg_8layer_v2" / "unet",
}


def census(args) -> dict:
    records = L.load_labels(args.labels)
    verdicts = Counter(r["verdict"] for r in records)
    corrected = targets.supervised_records(records)
    animals = folds.animals_present(corrected)
    packs = sorted(Path(args.packs).glob("*_pack.npz"))
    labelled_scans = {r["scan_id"] for r in records}
    repeat = sorted(Path(args.repeat_labels).glob("*.npz"))
    repeat_packs = sorted(
        (Path(args.repeat_labels).parent / "packs").glob("*_pack.npz"))

    print("== label census ==")
    print(f"  review packs on disk        : {len(packs)}")
    print(f"  packs with at least 1 label : {len(labelled_scans)}")
    print(f"  label files                 : {len(records)}  {dict(verdicts)}")
    print(f"  corrected (the only evidence): {len(corrected)} B-scans in "
          f"{len({r['scan_id'] for r in corrected})} scans")
    print(f"  animals with corrected labels: {len(animals)}  {animals}")
    print(f"  blind repeatability round   : {len(repeat)} labels of "
          f"{len(repeat_packs)} queued packs "
          f"{'(NOT STARTED)' if not repeat else ''}")
    by_animal = Counter(folds.animal_of(r["scan_id"]) for r in corrected)
    print("  corrected B-scans per animal: "
          + ", ".join(f"{a}={n}" for a, n in sorted(by_animal.items())))
    qc = evaluate.load_qc_groups(args.qc_groups)
    days = evaluate.load_day_labels(args.qc_groups)
    print("  by acquisition QC group     : " + str(dict(Counter(
        qc.get(r["scan_id"], "unknown") for r in corrected))))
    print("  by lesion group             : " + str(dict(Counter(
        evaluate.lesion_group(r["scan_id"], days) for r in corrected))))
    return {"records": records, "corrected": corrected, "animals": animals,
            "qc": qc, "days": days, "n_packs": len(packs),
            "n_labelled_packs": len(labelled_scans), "n_repeat": len(repeat),
            "n_repeat_packs": len(repeat_packs), "verdicts": dict(verdicts)}


def build_tensors(args, corrected):
    print("\n== training tensors: 3-B-scan averages from the source volumes ==")
    metas = tensors.build_cache(corrected, args.segmented, args.cache,
                                overwrite=args.overwrite)
    path = tensors.write_manifest(metas, args.cache)
    checked = tensors.assert_not_pack_images(args.cache, args.packs, corrected)
    shapes = Counter((m.height, m.width) for m in metas)
    n_avg = Counter(m.n_averaged for m in metas)
    print(f"  {len(metas)} averaged B-scans; manifest {path}")
    print(f"  distinct band geometries: {dict(shapes)}")
    print(f"  B-scans per average     : {dict(n_avg)} (edge B-scans use fewer)")
    print(f"  differ from the unaveraged pack image on all {checked} checked")
    return metas


def build_samples(args, corrected):
    print("\n== samples: flatten, crop, targets, masks ==")
    samples = []
    edge_to_ilm, edge_to_rpe, wrapped = [], [], []
    for record in corrected:
        image = tensors.load_image(args.cache, record["scan_id"], record["bscan"])
        edge = flatten.posterior_edge(image)
        edge_to_ilm.append(float(np.median(edge - record["surfaces"][0])))
        edge_to_rpe.append(float(np.median(edge - record["surfaces"][7])))
        sample = dataset.build_sample(record, image)
        restored = dataset.to_image_rows(sample.rows.astype(float),
                                         sample.shifts, sample.row0)
        # 1e-3 px, not 0: sample.rows is stored float32 for training, so these
        # rows return only to float32 resolution.  The *image* round trip is
        # separately asserted bit-identical in test_phase1.py.
        assert np.allclose(restored, record["surfaces"], atol=1e-3), \
            f"{record['scan_id']} b{record['bscan']}: rows do not round-trip"
        wrapped.append(1.0 - float(sample.valid_mask.mean()))
        samples.append(sample)
    print(f"  {len(samples)} samples, window "
          f"{samples[0].height}x{samples[0].width}, "
          f"{samples[0].channels.shape[0]} channels")
    print(f"  posterior edge above ILM: {np.min(edge_to_ilm):.0f}-"
          f"{np.max(edge_to_ilm):.0f} px (crop keeps {flatten.CROP_ABOVE})")
    print(f"  posterior edge below RPE: {np.min(edge_to_rpe):.0f}-"
          f"{np.max(edge_to_rpe):.0f} px (crop keeps {flatten.CROP_BELOW})")
    print(f"  wrapped/padded pixels per sample: "
          f"{100 * np.mean(wrapped):.1f}% mean, {100 * np.max(wrapped):.1f}% worst")
    b_weight = np.mean([s.boundary_weight.mean() for s in samples])
    r_weight = np.mean([s.region_weight.mean() for s in samples])
    per_surface = np.mean([(s.boundary_weight.sum(axis=1) > 0) for s in samples],
                          axis=0)
    print(f"  supervised fraction: boundary {b_weight:.3f}, region {r_weight:.3f}")
    print("  supervised B-scans per surface: " + ", ".join(
        f"{n}={f * len(samples):.0f}" for n, f in zip(SURFACE_NAMES, per_surface)))
    return samples


def report_folds(corrected, out_dir: Path):
    print("\n== leave-two-animals-out folds (regenerated from the labels) ==")
    rows = folds.fold_report(corrected)
    print(f"  {len(rows)} folds over {len(folds.animals_present(corrected))} animals")
    for row in rows:
        print(f"    fold {row['fold']:2d}  test {row['test_animals']:<14s} "
              f"train {row['n_train_bscans']:3d} B-scans / "
              f"{row['n_train_scans']:2d} scans   "
              f"test {row['n_test_bscans']:3d} / {row['n_test_scans']:2d}")
    (out_dir / "folds.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


def selftest(args, corrected, qc, days, out_dir: Path):
    print("\n== evaluation harness self-test against the reported v2 numbers ==")
    summary, problems, rows = evaluate.selftest_baseline(
        corrected, args.variants, qc_groups=qc, day_labels=days)
    evaluate.print_table("baseline_shipped_cascade (harness)", summary)
    if problems:
        print("\n  SELF-TEST FAILED:")
        for problem in problems:
            print(f"    {problem}")
        raise SystemExit(2)
    print("\n  reproduces qc/variant_comparison.json:baseline_shipped_cascade "
          "exactly on all 8 surfaces")

    layers = evaluate.summarise(rows, kind="layer")
    evaluate.print_table("layer thickness error, same predictions", layers)
    for key in ("qc_group", "lesion_group"):
        for group, block in evaluate.summarise_by(rows, key).items():
            evaluate.print_table(f"surfaces | {key} = {group}", block)
    evaluate.write_rows(rows, out_dir / "baseline_errors.csv")
    payload = {
        "baseline_shipped_cascade": summary,
        "layers": layers,
        "by_qc_group": evaluate.summarise_by(rows, "qc_group"),
        "by_lesion_group": evaluate.summarise_by(rows, "lesion_group"),
    }
    (out_dir / "harness_selftest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    return summary, rows


def rerun_v2(args, corrected, qc, days, out_dir: Path):
    """Re-run the revision-2 cascade and reproduce its published block."""
    from auto_seg_8layer_v2.eval_variants import run_variant, variant_priors

    print("\n== re-running the revision-2 cascade (real volume pipeline) ==")
    refit = json.loads(Path(args.priors).read_text(encoding="utf-8"))["priors"]
    priors = variant_priors(refit, "five")
    by_scan = defaultdict(list)
    for record in corrected:
        by_scan[record["scan_id"]].append(record)
    predictions = run_variant(by_scan, Path(args.segmented), priors, "v2-selftest")
    rows = evaluate.collect(corrected, predictions, qc_groups=qc, day_labels=days)
    summary = evaluate.summarise(rows, kind="surface")
    reference = json.loads(Path(args.variants).read_text(
        encoding="utf-8"))["v2_outer_anchor__priors_five"]
    problems = evaluate.compare_to_reference(summary, reference, tol=1e-6)
    evaluate.print_table("v2_outer_anchor__priors_five (harness, re-run)", summary)
    if problems:
        print("\n  V2 RE-RUN SELF-TEST FAILED:")
        for problem in problems:
            print(f"    {problem}")
        raise SystemExit(3)
    print("\n  reproduces qc/variant_comparison.json:v2_outer_anchor__priors_five")
    evaluate.write_rows(rows, out_dir / "v2_rerun_errors.csv")
    (out_dir / "v2_rerun_selftest.json").write_text(
        json.dumps({"v2_outer_anchor__priors_five": summary,
                    "layers": evaluate.summarise(rows, kind="layer"),
                    "by_qc_group": evaluate.summarise_by(rows, "qc_group"),
                    "by_lesion_group": evaluate.summarise_by(rows, "lesion_group")},
                   indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, value in DEFAULTS.items():
        parser.add_argument(f"--{key.replace('_', '-')}", default=str(value))
    parser.add_argument("--priors", default="auto_seg_8layer_v2/priors_v2.json")
    parser.add_argument("--census-only", action="store_true")
    parser.add_argument("--skip-tensors", action="store_true",
                        help="use the existing cache; do not read any volume")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--save-samples", action="store_true")
    parser.add_argument("--rerun-v2", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    state = census(args)
    if args.census_only:
        return 0
    corrected = state["corrected"]
    if not args.skip_tensors:
        build_tensors(args, corrected)
    samples = build_samples(args, corrected)
    if args.save_samples:
        sample_dir = out_dir / "samples"
        for sample in samples:
            dataset.save_sample(sample, sample_dir)
        print(f"  wrote {len(samples)} samples to {sample_dir}")
    report_folds(corrected, out_dir)
    selftest(args, corrected, state["qc"], state["days"], out_dir)
    if args.rerun_v2:
        rerun_v2(args, corrected, state["qc"], state["days"], out_dir)
    print(f"\nwrote harness outputs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
