#!/usr/bin/env python3
"""Self-tests for the Phase 1 data pipeline and evaluation harness.

Runs without ``pytest``: ``python auto_seg_8layer_v2/unet/test_phase1.py`` from
``code`` with ``octa`` activated.  Tests that need the source ``.mat`` volumes
are skipped unless the tensor cache has been built by ``run_phase1.py``.

Every check is a numeric assertion.  The flattening round trip in particular is
asserted to be **exact**, not approximately equal: an interpolated shift would
pass an approximate check and hide the bug it is there to catch.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[2]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from eight_surface import labels as L  # noqa: E402
from eight_surface.config import N_SURFACES, SURFACE_NAMES  # noqa: E402

from auto_seg_8layer_v2.unet import dataset, evaluate, flatten, folds, targets  # noqa: E402
from auto_seg_8layer_v2.unet import tensors  # noqa: E402

OUT = CODE_DIR.parent / "outputs"
LABEL_DIR = OUT / "eight_surface" / "labels"
PACK_DIR = OUT / "eight_surface" / "review"
CACHE_DIR = OUT / "auto_seg_8layer_v2" / "unet" / "tensors"
QC_GROUPS = OUT / "eight_surface" / "qc_review_groups.csv"
VARIANTS = OUT / "auto_seg_8layer_v2" / "qc" / "variant_comparison.json"

_TESTS = []


def test(fn):
    _TESTS.append(fn)
    return fn


def _synthetic(height=200, width=64, seed=0):
    rng = np.random.default_rng(seed)
    img = rng.normal(0.0, 1.0, (height, width)).astype(np.float32)
    tilt = np.rint(20 * np.sin(np.linspace(0, 3, width))).astype(int)
    return img, tilt


# ------------------------------------------------------------- flattening ----

@test
def test_round_trip_is_exact():
    img, shifts = _synthetic()
    back = flatten.invert_shifts(flatten.apply_shifts(img, shifts), shifts)
    assert np.array_equal(back, img), "shift/unshift is not bit-identical"
    # and the other way round, on integer data where "approximately equal"
    # would be indistinguishable from equal
    ints = np.arange(img.size, dtype=np.int64).reshape(img.shape)
    assert np.array_equal(
        flatten.invert_shifts(flatten.apply_shifts(ints, shifts), shifts), ints)


@test
def test_round_trip_exact_for_every_label_geometry():
    shapes = [(452, 512), (370, 512), (500, 512)]
    rng = np.random.default_rng(1)
    for height, width in shapes:
        img = rng.normal(size=(height, width)).astype(np.float32)
        shifts = rng.integers(-height, height, width)
        back = flatten.invert_shifts(flatten.apply_shifts(img, shifts), shifts)
        assert np.array_equal(back, img), f"round trip failed for {height}x{width}"


@test
def test_fractional_shifts_are_refused():
    img, shifts = _synthetic()
    try:
        flatten.apply_shifts(img, shifts.astype(float))
    except TypeError:
        return
    raise AssertionError("a fractional shift array was accepted")


@test
def test_surface_rows_round_trip_exactly():
    _img, shifts = _synthetic()
    rows = np.random.default_rng(2).uniform(10, 180, (N_SURFACES, shifts.size))
    back = flatten.unshift_rows(flatten.shift_rows(rows, shifts), shifts)
    assert np.array_equal(back, rows), "surface row round trip is not exact"


@test
def test_shift_moves_the_edge_to_the_anchor():
    height, width = 300, 128
    edge = 150 + np.rint(30 * np.sin(np.linspace(0, 4, width))).astype(int)
    img = np.zeros((height, width), np.float32)
    for c in range(width):
        img[:edge[c] + 1, c] = 10.0          # tissue above the posterior edge
    img += np.random.default_rng(3).normal(0, 0.01, img.shape)
    shifts = flatten.flatten_shifts(img, target_row=100)
    flat = flatten.apply_shifts(img, shifts)
    # The detected edge is median-smoothed, so check the geometry directly:
    # flattened row 100 - k must hold the same pixel as original row edge - k.
    detected = np.rint(flatten.posterior_edge(img)).astype(int)
    for k in (0, 5, 40):
        for c in (0, 17, 63):
            assert flat[100 - k, c] == img[detected[c] - k, c]
    assert np.median(np.abs(detected - edge)) <= 3.0, (
        "posterior tissue edge was not detected where it was drawn")
    # and the retained mask marks exactly the rows that did not wrap around
    valid = flatten.wrap_mask(img.shape, shifts)
    assert valid.shape == img.shape and valid.any() and not valid.all()


@test
def test_crop_geometry_is_consistent():
    img, shifts = _synthetic(height=600, width=32)
    flat = flatten.apply_shifts(img, shifts)
    window, row0 = flatten.crop(flat, target_row=384, above=384, below=64)
    assert window.shape == (448, 32) and row0 == 0
    window, row0 = flatten.crop(flat, target_row=500, above=384, below=64)
    assert window.shape == (448, 32) and row0 == 116
    assert np.array_equal(window, flat[116:564])


# ------------------------------------------------------ targets and masks ----

def _fake_record(width=64, height=200):
    rows = np.linspace(20, 150, N_SURFACES)[:, None] * np.ones((1, width))
    return {
        "scan_id": "TS999_OD_2026-01-01_D7_s01_000000", "bscan": 3,
        "verdict": "corrected", "px_um": 1.12,
        "surfaces": rows.astype(np.float32),
        "auto_surfaces": rows.astype(np.float32) + 1.0,
        "surface_edited": np.ones(N_SURFACES, bool),
        "surface_visible": np.ones(N_SURFACES, bool),
        "surface_reliable": np.ones(N_SURFACES, bool),
        "surface_displaced": np.zeros(N_SURFACES, bool),
        "region_excluded": np.zeros(width, bool),
    }, height


@test
def test_masking_semantics_are_not_conflated():
    record, _h = _fake_record()
    record["surface_edited"][1] = False       # nobody drew it
    record["surface_visible"][2] = False      # drawn but invisible
    record["surface_reliable"][3] = False     # drawn, visible, not reliable
    record["surface_displaced"][4] = True     # shoved by ordering, still drawn
    supervised = targets.surface_supervised(record)
    assert not supervised[1] and not supervised[2] and not supervised[3]
    assert supervised[4], (
        "surface_displaced must not by itself remove a drawn surface; "
        "it is a separate question from whether a human drew it")
    assert supervised[0] and supervised[5] and supervised[6] and supervised[7]


@test
def test_excluded_columns_carry_no_weight_anywhere():
    record, height = _fake_record()
    record["region_excluded"][10:20] = True
    weight_b = targets.boundary_weight(record, height=height)
    ids = targets.region_map(record["surfaces"], height)
    weight_r = targets.region_weight(record, ids)
    assert weight_b[:, 10:20].sum() == 0 and weight_r[:, 10:20].sum() == 0
    assert weight_b[:, :10].min() == 1 and weight_r[:, :10].min() == 1


@test
def test_region_is_supervised_only_when_both_surfaces_are():
    record, _h = _fake_record()
    record["surface_edited"][2] = False
    valid = targets.region_supervised(record)
    # surface 2 bounds region 2 (below surface 1, above surface 2) and region 3
    assert not valid[2] and not valid[3]
    assert valid[0] and valid[1] and valid[4]


@test
def test_rejected_and_accepted_records_are_dropped():
    record, _h = _fake_record()
    pool = [dict(record, verdict=v) for v in ("corrected", "accepted", "rejected")]
    kept = targets.supervised_records(pool)
    assert len(kept) == 1 and kept[0]["verdict"] == "corrected"


@test
def test_region_map_matches_the_human_rows():
    record, height = _fake_record()
    ids = targets.region_map(record["surfaces"], height)
    rows = np.rint(record["surfaces"][:, 0]).astype(int)
    assert ids.shape == (height, record["surfaces"].shape[1])
    assert ids[0, 0] == 0 and ids[-1, 0] == targets.N_REGIONS - 1
    for s, row in enumerate(rows):
        assert ids[row, 0] == s + 1, "a pixel on a surface belongs below it"
        assert ids[row - 1, 0] == s


@test
def test_boundary_maps_are_per_column_distributions():
    record, height = _fake_record()
    maps = targets.boundary_maps(record["surfaces"], height, sigma=2.0)
    assert maps.shape == (N_SURFACES, height, record["surfaces"].shape[1])
    total = maps.sum(axis=1)
    assert np.allclose(total, 1.0, atol=1e-5), "columns are not distributions"
    peak = maps.argmax(axis=1)
    assert np.array_equal(peak, np.rint(record["surfaces"]).astype(int))


@test
def test_offimage_boundary_gets_no_weight():
    record, height = _fake_record()
    rows = record["surfaces"].copy()
    rows[0] = -5.0                            # above the top of the crop
    weight = targets.boundary_weight(record, rows=rows, height=height)
    assert weight[0].sum() == 0 and weight[1].sum() > 0


# ------------------------------------------------------------------ folds ----

@test
def test_leave_two_animals_out_is_generated_not_hardcoded():
    six = ["TS165", "TS169", "TS241", "TS247", "TS250", "TS267"]
    got = folds.leave_two_animals_out(six)
    assert len(got) == 15, f"expected C(6,2)=15 folds, got {len(got)}"
    grown = folds.leave_two_animals_out(six + ["TS283", "TS305"])
    assert len(grown) == 28, "new animals were not absorbed automatically"
    for fold in grown:
        assert len(fold.test_animals) == 2
        assert not set(fold.test_animals) & set(fold.train_animals)


@test
def test_no_animal_straddles_a_fold():
    records = [{"scan_id": f"{a}_OD_2025-01-01_D7_s01_000000", "bscan": i}
               for i, a in enumerate(["TS165", "TS165", "TS169", "TS241",
                                      "TS247", "TS250"])]
    for fold in folds.leave_two_animals_out(folds.animals_present(records)):
        train, test = folds.split_records(records, fold)
        assert len(train) + len(test) == len(records)
        assert not ({folds.animal_of(r["scan_id"]) for r in train}
                    & {folds.animal_of(r["scan_id"]) for r in test})


# ------------------------------------------------------------- evaluation ----

@test
def test_perfect_prediction_scores_zero():
    record, _h = _fake_record()
    prediction = {(record["scan_id"], record["bscan"]): record["surfaces"]}
    rows = evaluate.collect([record], prediction)
    summary = evaluate.summarise(rows, kind="surface")
    assert len(summary) == N_SURFACES
    assert all(s["median_abs_um"] == 0.0 for s in summary.values())
    layers = evaluate.summarise(rows, kind="layer")
    assert all(s["median_abs_um"] == 0.0 for s in layers.values())


@test
def test_mock_predictors_agree_with_the_hand_route():
    record, _h = _fake_record()
    identity = evaluate.identity_predictions([record])
    assert np.array_equal(identity[(record["scan_id"], record["bscan"])],
                          record["surfaces"])
    summary = evaluate.summarise(evaluate.collect([record], identity))
    assert all(s["median_abs_um"] == 0.0 for s in summary.values())
    stored = evaluate.stored_auto_predictions([record])
    direct = evaluate.summarise(evaluate.collect([record], stored))
    via_flag = evaluate.summarise(
        evaluate.collect([record], {}, use_stored_auto=True))
    assert direct == via_flag


@test
def test_known_offset_scores_in_micrometres():
    record, _h = _fake_record()
    shifted = record["surfaces"] + 10.0        # 10 px = 11.2 um
    rows = evaluate.collect([record], {(record["scan_id"], record["bscan"]): shifted})
    summary = evaluate.summarise(rows, kind="surface")
    assert np.isclose(summary["ILM"]["median_abs_um"], 11.2, atol=1e-4)
    assert np.isclose(summary["ILM"]["median_signed_um"], 11.2, atol=1e-4)
    # every surface moved by the same amount, so no layer thickness changed
    # (to float32 resolution: the label arrays are float32)
    layers = evaluate.summarise(rows, kind="layer")
    assert all(s["median_abs_um"] < 1e-4 for s in layers.values())


@test
def test_layer_error_is_reported_separately_from_surface_error():
    record, _h = _fake_record()
    moved = record["surfaces"].copy()
    moved[1] += 5.0                            # RNFL thicker, GCL thinner
    rows = evaluate.collect([record], {(record["scan_id"], record["bscan"]): moved})
    layers = evaluate.summarise(rows, kind="layer")
    assert np.isclose(layers["RNFL"]["median_signed_um"], 5.6, atol=1e-4)
    assert np.isclose(layers["GCL"]["median_signed_um"], -5.6, atol=1e-4)
    assert np.isclose(layers["TOTAL"]["median_abs_um"], 0.0)


@test
def test_unsupervised_surfaces_are_not_scored():
    record, _h = _fake_record()
    record["surface_visible"][0] = False
    rows = evaluate.collect(
        [record], {(record["scan_id"], record["bscan"]): record["surfaces"]})
    names = {r["name"] for r in rows if r["kind"] == "surface"}
    assert "ILM" not in names
    layer_names = {r["name"] for r in rows if r["kind"] == "layer"}
    assert "RNFL" not in layer_names and "TOTAL" not in layer_names


@test
def test_shape_mismatch_fails_loudly():
    record, _h = _fake_record()
    try:
        evaluate.surface_errors(record, record["surfaces"][:, :10])
    except AssertionError:
        return
    raise AssertionError("a prediction of the wrong shape was accepted")


@test
def test_lesion_group_from_day_label():
    assert evaluate.lesion_group("TS165_OD_2025-04-29_WT_s06_114517") == "control"
    assert evaluate.lesion_group(
        "TS247_OD_2024-10-17_beforelaser_s06_110555") == "control"
    assert evaluate.lesion_group("TS247_OD_2024-11-06_D21_s03_104157") == "cnv"
    assert evaluate.lesion_group("TS325_OD_2026-05-26_6mo_s01_112940") == "cnv"


# ----------------------------------------------- against the real dataset ----

@test
def test_baseline_selftest_reproduces_variant_comparison():
    records = [r for r in L.load_labels(LABEL_DIR) if r["verdict"] == "corrected"]
    assert records, "no corrected labels found"
    summary, problems, _rows = evaluate.selftest_baseline(records, VARIANTS)
    assert not problems, "harness does not reproduce the reported baseline:\n  " \
        + "\n  ".join(problems)
    assert set(summary) <= set(SURFACE_NAMES)


@test
def test_real_labels_build_samples_with_exact_round_trip():
    if not CACHE_DIR.exists() or not any(CACHE_DIR.glob("*.npz")):
        print("    (skipped: tensor cache not built; run run_phase1.py)")
        return
    records = targets.supervised_records(L.load_labels(LABEL_DIR))
    checked = 0
    for record in records:
        path = tensors.cache_path(CACHE_DIR, record["scan_id"], record["bscan"])
        if not path.exists():
            continue
        image = tensors.load_image(CACHE_DIR, record["scan_id"], record["bscan"])
        shifts = flatten.flatten_shifts(image, target_row=dataset.ANCHOR_ROW)
        back = flatten.invert_shifts(flatten.apply_shifts(image, shifts), shifts)
        assert np.array_equal(back, image), f"{path.name}: round trip inexact"
        sample = dataset.build_sample(record, image)
        restored = dataset.to_image_rows(sample.rows.astype(float), sample.shifts,
                                         sample.row0)
        assert np.allclose(restored, record["surfaces"], atol=1e-3), \
            f"{path.name}: surface rows do not return to image coordinates"
        assert sample.channels.shape[0] == 2
        assert sample.boundary_weight.shape == (N_SURFACES, sample.width)
        assert sample.region_weight.shape == (sample.height, sample.width)
        checked += 1
    assert checked > 0, "cache exists but no sample could be built"
    print(f"    ({checked} real B-scans checked)")


def main() -> int:
    failures = 0
    for fn in _TESTS:
        try:
            fn()
        except Exception:  # noqa: BLE001
            failures += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
        else:
            print(f"ok   {fn.__name__}")
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
