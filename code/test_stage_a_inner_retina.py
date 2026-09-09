"""Regression checks for inner-retina reporting; synthetic evidence only."""
import copy
import unittest
from unittest.mock import patch

import numpy as np

from stage_a.metrics import evaluate as evaluate_eight
from stage_a_inner_retina import BANDS, SURFACES, SENSITIVITY_KEY, evaluate, sensitivity, run
from stage_a_inner_retina_audit import spread_parts, offset_summary, manual_valid


def fixture(key="synthetic", width=6):
    r = dict(key=key, animal="TS1", scan_id="synthetic", verdict="corrected",
             scope_status="control", qc_group="unknown", biological_group="WT", px_um=1.)
    rows = np.repeat(np.arange(8, dtype=float)[:, None] * 10, width, axis=1)
    targets = {key: dict(rows_label=rows, valid=np.ones_like(rows, dtype=bool))}
    preds = {key: dict(rows=rows + 2, retained=np.ones_like(rows, dtype=bool))}
    return [r], targets, preds, {"synthetic": {"aline_um": 2.}}


def pooled(report, name, mode="raw", kind="thickness"):
    return next(r for r in report["summary"] if r["axis"] == "pooled"
                and r["name"] == name and r["kind"] == kind and r["mode"] == mode)


class InnerRetinaTests(unittest.TestCase):
    def test_existing_seven_components_exactly_unchanged(self):
        args = fixture()
        full, inner = evaluate_eight(*args), evaluate(*args)
        for row in full["summary"]:
            allowed = SURFACES if row["kind"] == "boundary" else BANDS
            if row["name"] in allowed:
                self.assertIn(row, inner["summary"])
        self.assertEqual({r["name"] for r in inner["summary"] if r["kind"] == "boundary"}, set(SURFACES))
        self.assertEqual({r["name"] for r in inner["summary"] if r["kind"] == "thickness"}, set(BANDS))

    def test_inner_span_common_shift_cancels(self):
        report = evaluate(*fixture())
        self.assertEqual(pooled(report, "INNER_RETINA")["median_abs_um"], 0.)

    def test_inner_span_requires_both_manual_endpoints(self):
        rs, targets, preds, sources = fixture()
        targets["synthetic"]["valid"][0, 0] = False
        targets["synthetic"]["valid"][3, 1] = False
        targets["synthetic"]["valid"][7, :] = False
        preds["synthetic"]["rows"][3] += 3
        st = pooled(evaluate(rs, targets, preds, sources), "INNER_RETINA")
        self.assertEqual(st["n_eligible"], 4)
        self.assertEqual(st["mean_signed_um"], 3.)

    def test_shadow_withholding_and_nan_count_as_missing(self):
        rs, targets, preds, sources = fixture()
        preds["synthetic"]["retained"][:, 0] = False
        preds["synthetic"]["rows"][3, 1] = np.nan
        report = evaluate(rs, targets, preds, sources)
        st = pooled(report, "INNER_RETINA", "retained")
        self.assertEqual(st["n_missing_or_abstained"], 2)
        self.assertEqual(st["coverage"], 4 / 6)
        self.assertEqual(st["failure_fraction_of_eligible"], 2 / 6)
        self.assertIsNone(st["all_eligible_p95_um"])

    def test_missing_predictor_remains_in_denominator(self):
        rs, targets, _, sources = fixture()
        report = evaluate(rs, targets, {}, sources)
        for row in report["summary"]:
            self.assertEqual(row["coverage"], 0.)
            self.assertEqual(row["failure_fraction_of_eligible"], 1.)
            self.assertIsNone(row["median_abs_um"])

    def test_four_head_predictions_match_eight_head_readout(self):
        args = fixture()
        full = evaluate(*args)
        args[2]["synthetic"] = {k: v[:4] for k, v in args[2]["synthetic"].items()}
        four = evaluate(*args)
        self.assertEqual(full, four)

    def test_sensitivity_removes_exact_key_only(self):
        records = [{"key": SENSITIVITY_KEY}, {"key": "another_volume_b0510"}]
        scenarios = dict(sensitivity(records))
        self.assertEqual(len(scenarios["with_b0510"]), 2)
        self.assertEqual(scenarios["without_b0510"], records[1:])

    def test_runs_do_not_join_bscans(self):
        rs, targets, preds, sources = fixture(width=6)
        rs.append({**rs[0], "key": "second"})
        targets["second"] = copy.deepcopy(targets["synthetic"])
        preds["second"] = copy.deepcopy(preds["synthetic"])
        for p in preds.values():
            p["rows"][3] += 30
        st = pooled(evaluate(rs, targets, preds, sources), "INNER_RETINA")
        self.assertEqual(st["longest_gross_error_columns"], 6)
        self.assertEqual(st["longest_gross_error_um"], 12)

    def test_decisions_do_not_count_outer_only_evidence(self):
        args = fixture()
        args[1]["synthetic"]["valid"][:4] = False
        report = evaluate(*args)
        self.assertFalse(report["decisions"][0]["eligible"])
        self.assertEqual(report["decisions"][0]["total_boundary_columns"], 24)

    def test_locked_split_rejected_before_dataset_is_constructed(self):
        from types import SimpleNamespace
        with patch("stage_a.data.Dataset", side_effect=AssertionError("Must not read files")):
            with self.assertRaisesRegex(ValueError, "locked"):
                run(SimpleNamespace(split="test"))

    def test_prior_audit_rejects_undrawn_anchor(self):
        rows = np.repeat(np.arange(8)[:, None] * 30., 24, axis=1)
        valid = np.ones_like(rows, dtype=bool)
        valid[0] = False
        records = [({"key": "manual"}, {"surfaces": rows}, valid)]
        self.assertEqual(spread_parts(records, 1, 6), [])

    def test_legacy_edited_and_displaced_is_not_manual_truth(self):
        label = dict(surfaces=np.zeros((8, 24)), surface_edited=np.ones(8, bool),
                     surface_displaced=np.zeros(8, bool), surface_visible=np.ones(8, bool),
                     surface_reliable=np.ones(8, bool), region_excluded=np.zeros(24, bool))
        label["surface_displaced"][2] = True
        valid = manual_valid(label)
        self.assertFalse(valid[2].any())
        self.assertTrue(valid[1].all())

    def test_offset_audit_uses_supplied_comparator_and_tracks_missing(self):
        rows = np.repeat(np.arange(8)[:, None] * 30., 24, axis=1)
        valid = np.ones_like(rows, dtype=bool)
        records = [({"key": "a", "scan_id": "s"},
                    {"surfaces": rows, "auto_surfaces": rows}, valid)]
        pred = rows.copy()
        pred[1] += np.arange(24)
        result = offset_summary(records, 1, "bscan", {"a": pred})
        self.assertGreater(result["residual_p95_px"], 10)
        missing = offset_summary(records, 1, "bscan", {})
        self.assertEqual(missing["missing_prediction_columns"], 24)


if __name__ == "__main__":
    unittest.main(verbosity=2)
