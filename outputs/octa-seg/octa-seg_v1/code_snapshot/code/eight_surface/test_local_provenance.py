#!/usr/bin/env python3
"""Tests for per-A-line provenance, visibility and reliability.

    conda activate octa
    python eight_surface/test_local_provenance.py          # from code/

Every fixture is synthetic and every label is written into a fresh
``tempfile.TemporaryDirectory``.  Nothing here reads or writes
``outputs/eight_surface/labels`` or any other real human-label directory --
one test does *open* the real directory read-only to prove the existing files
still load, and it skips silently if the directory is absent.

The GUI tests drive the real widget classes with a fake pack, offscreen.  They
exist because the interesting failures are all in the interaction: a stroke that
marks a whole boundary, an ordering displacement that leaves a drawn segment
still looking trusted, an undo that restores the line but not the history.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from eight_surface import labels as L                      # noqa: E402
from eight_surface import provenance as P                  # noqa: E402
from eight_surface.config import (                         # noqa: E402
    LABEL_FORMAT_VERSION, N_SURFACES, SURFACE_NAMES,
)
from eight_surface.volume import thickness_maps            # noqa: E402
from auto_seg_8layer_v2.unet import targets as T           # noqa: E402

N_COL = 128
REAL_LABEL_DIR = CODE_DIR.parent / "outputs" / "eight_surface" / "labels"

IDX = {name: i for i, name in enumerate(SURFACE_NAMES)}
RPE = IDX["RPE"]
ILM = IDX["ILM"]


def synthetic_auto(n_col: int = N_COL) -> np.ndarray:
    """Eight ordered, well-separated lines."""
    return (np.arange(N_SURFACES, dtype=float)[:, None] * 20.0
            + 30.0 + np.zeros((N_SURFACES, n_col)))


def write(temp, *, surfaces, auto, local=None, verdict="corrected",
          visible=None, reliable=None, excluded=None, edited=None,
          scan_id="TS999_OD_2025-01-01_D7_s01", bscan=3):
    edited = (np.zeros(N_SURFACES, bool) if edited is None
              else np.asarray(edited, bool))
    if local is not None:
        edited = local["local_drawn"].any(axis=1)
    return L.save_label(
        temp, scan_id=scan_id, bscan=bscan, verdict=verdict,
        surfaces=surfaces, auto_surfaces=auto, surface_names=SURFACE_NAMES,
        surface_edited=edited,
        surface_visible=(np.ones(N_SURFACES, bool) if visible is None
                         else np.asarray(visible, bool)),
        surface_reliable=(np.ones(N_SURFACES, bool) if reliable is None
                          else np.asarray(reliable, bool)),
        region_excluded=(np.zeros(surfaces.shape[1], bool) if excluded is None
                         else np.asarray(excluded, bool)),
        local=local, px_um=1.12)


# ------------------------------------------------------------------ geometry

class StrokeSupportTests(unittest.TestCase):
    """``stroke_support`` must agree with ``apply_stroke``, exactly."""

    def test_drawn_span_matches_the_columns_the_cursor_visited(self):
        from octa.labels import apply_stroke, stroke_support
        base = np.zeros(N_COL)
        xs = np.array([40.2, 45.0, 52.7, 60.4])
        drawn, tapered = stroke_support(N_COL, xs, taper=10.0)
        self.assertEqual(np.flatnonzero(drawn).min(), 40)
        self.assertEqual(np.flatnonzero(drawn).max(), 60)
        self.assertFalse((drawn & tapered).any())
        moved = apply_stroke(base, xs, np.full(xs.shape, 5.0), taper=10.0) != base
        # every column apply_stroke changed is either drawn or tapered
        self.assertTrue(np.all(~moved | (drawn | tapered)))
        # and the taper reaches exactly as far as the ramp, not further
        self.assertEqual(np.flatnonzero(tapered).min(), 31)
        self.assertEqual(np.flatnonzero(tapered).max(), 69)

    def test_a_localised_stroke_does_not_support_the_whole_boundary(self):
        from octa.labels import stroke_support
        drawn, tapered = stroke_support(512, np.arange(200, 240.0), taper=30.0)
        self.assertEqual(int(drawn.sum()), 40)
        self.assertLess(int(drawn.sum() + tapered.sum()), 512)

    def test_empty_stroke_supports_nothing(self):
        from octa.labels import stroke_support
        drawn, tapered = stroke_support(N_COL, np.array([]), taper=30.0)
        self.assertFalse(drawn.any() or tapered.any())


class ProvenanceCodeTests(unittest.TestCase):
    def test_drawn_then_displaced_keeps_history_and_loses_trust(self):
        code = P.provenance_code([[True]], [[False]], [[True]], [[False]])
        self.assertEqual(code[0, 0], P.PROV_DRAWN_DISPLACED)
        self.assertNotIn(P.PROV_DRAWN_DISPLACED, P.TRUSTED_POSITION_CODES)

    def test_each_history_maps_to_its_own_code(self):
        cases = {
            P.PROV_AUTO: (False, False, False, False),
            P.PROV_DRAWN: (True, False, False, False),
            P.PROV_TAPER: (False, True, False, False),
            P.PROV_DISPLACED: (False, False, True, False),
            P.PROV_REVIEWED: (False, False, False, True),
            P.PROV_DRAWN_DISPLACED: (True, False, True, False),
        }
        for expected, (d, t, x, r) in cases.items():
            got = P.provenance_code([[d]], [[t]], [[x]], [[r]])[0, 0]
            self.assertEqual(got, expected, P.PROVENANCE_NAMES[expected])

    def test_whole_surface_flag_forces_no_but_never_forces_yes(self):
        local = np.full((N_SURFACES, 4), P.MARK_UNKNOWN, np.uint8)
        flag = np.ones(N_SURFACES, bool)
        flag[RPE] = False
        out = P.effective_marks(local, flag)
        self.assertTrue((out[RPE] == P.MARK_NO).all())
        self.assertTrue((out[ILM] == P.MARK_UNKNOWN).all())


# ------------------------------------------------------------- round tripping

class RoundTripTests(unittest.TestCase):
    def test_local_arrays_survive_save_and_reload(self):
        auto = synthetic_auto()
        surfaces = auto.copy()
        surfaces[RPE, 20:40] += 3.0
        local = P.empty_local(N_COL)
        local["local_drawn"][RPE, 20:40] = True
        local["local_taper"][RPE, 10:20] = True
        local["local_displaced"][RPE - 1, 20:40] = True
        local["local_reviewed"][ILM, 0:64] = True
        local["local_visibility"][RPE, 60:90] = P.MARK_NO
        local["local_reliability"][RPE, 90:100] = P.MARK_NO
        with tempfile.TemporaryDirectory() as temp:
            record = L.load_label(write(temp, surfaces=surfaces, auto=auto,
                                        local=local))
        self.assertTrue(record["local_provenance_available"])
        self.assertEqual(record["label_format_version"], LABEL_FORMAT_VERSION)
        for key, value in local.items():
            self.assertTrue(np.array_equal(record[key], value), key)
        code = record["provenance_code"]
        self.assertTrue((code[RPE, 20:40] == P.PROV_DRAWN).all())
        self.assertTrue((code[RPE, 10:20] == P.PROV_TAPER).all())
        self.assertTrue((code[RPE - 1, 20:40] == P.PROV_DISPLACED).all())
        self.assertTrue((code[ILM, 0:64] == P.PROV_REVIEWED).all())
        self.assertTrue((code[RPE, 100:] == P.PROV_AUTO).all())

    def test_a_label_written_without_local_arrays_claims_nothing(self):
        auto = synthetic_auto()
        with tempfile.TemporaryDirectory() as temp:
            record = L.load_label(write(temp, surfaces=auto.copy(), auto=auto))
        self.assertTrue(record["local_provenance_available"])
        self.assertFalse(record["local_drawn"].any())
        self.assertTrue((record["local_visibility"] == P.MARK_UNKNOWN).all())

    def test_a_tri_state_array_with_a_bogus_value_is_refused(self):
        auto = synthetic_auto()
        local = P.empty_local(N_COL)
        local["local_visibility"][0, 0] = 9
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                write(temp, surfaces=auto.copy(), auto=auto, local=local)


# ------------------------------------------------------------------- legacy

class LegacyTests(unittest.TestCase):
    """Old labels must stay readable, unchanged, and honestly described."""

    def _legacy_file(self, temp) -> Path:
        """A format-2 label: the [8] flags, no local arrays."""
        auto = synthetic_auto()
        surfaces = auto.copy()
        surfaces[RPE] += 2.0
        edited = np.zeros(N_SURFACES, bool)
        edited[RPE] = True
        path = write(temp, surfaces=surfaces, auto=auto, edited=edited)
        with np.load(path, allow_pickle=False) as data:
            kept = {k: data[k] for k in data.files
                    if k not in P.LOCAL_KEYS and k != "label_format_version"}
        kept["label_format_version"] = np.array(["2-surface-reliability"])
        np.savez_compressed(path, **kept)
        return path

    def test_legacy_label_loads_and_reports_provenance_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            record = L.load_label(self._legacy_file(temp))
        self.assertFalse(record["local_provenance_available"])
        code = record["provenance_code"]
        self.assertTrue((code[RPE] == P.PROV_UNAVAILABLE).all())
        self.assertTrue((code[ILM] == P.PROV_AUTO).all())

    def test_legacy_policies_differ_and_neither_invents_a_stroke(self):
        with tempfile.TemporaryDirectory() as temp:
            record = L.load_label(self._legacy_file(temp))
        lenient = T.column_valid(record, "surface_flag")
        strict = T.column_valid(record, "strict")
        self.assertTrue(lenient[RPE].all())          # the old whole-boundary rule
        self.assertFalse(lenient[ILM].any())
        self.assertFalse(strict.any())               # nothing is invented
        with self.assertRaises(ValueError):
            T.column_valid(record, "guess")

    def test_reading_a_legacy_label_does_not_rewrite_it(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self._legacy_file(temp)
            before = path.read_bytes()
            L.load_label(path)
            L.load_labels(temp)
            self.assertEqual(path.read_bytes(), before)

    def test_an_unknown_future_format_is_refused_not_guessed(self):
        auto = synthetic_auto()
        with tempfile.TemporaryDirectory() as temp:
            path = write(temp, surfaces=auto.copy(), auto=auto)
            with np.load(path, allow_pickle=False) as data:
                kept = {k: data[k] for k in data.files}
            kept["label_format_version"] = np.array(["99-from-the-future"])
            np.savez_compressed(path, **kept)
            with self.assertRaises(ValueError):
                L.load_label(path)

    @unittest.skipUnless(REAL_LABEL_DIR.is_dir(), "no real label directory here")
    def test_every_existing_human_label_still_loads_unchanged(self):
        paths = sorted(REAL_LABEL_DIR.glob("*.npz"))
        if not paths:
            self.skipTest("no labels on disk")
        digests = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in paths}
        records = [L.load_label(p) for p in paths]
        self.assertEqual(len(records), len(paths))
        self.assertEqual(
            {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in paths},
            digests, "reading the real labels modified them")
        for record in records:
            self.assertEqual(record["surface_names"], SURFACE_NAMES)
            self.assertIn("provenance_code", record)


# ------------------------------------------------------------ supervision

class SupervisionTests(unittest.TestCase):
    def _cnv_record(self, temp):
        """The critical example, as a label.

        The outer ``RPE`` boundary was drawn on both flanks of a lesion and
        marked unidentifiable through its centre; the ``ILM`` was drawn right
        across.  Nothing is excluded whole-column: the image is fine.
        """
        auto = synthetic_auto()
        surfaces = auto.copy()
        surfaces[RPE, 10:40] += 4.0
        surfaces[RPE, 88:118] += 4.0
        local = P.empty_local(N_COL)
        local["local_drawn"][RPE, 10:40] = True
        local["local_drawn"][RPE, 88:118] = True
        local["local_visibility"][RPE, 10:40] = P.MARK_YES
        local["local_visibility"][RPE, 88:118] = P.MARK_YES
        local["local_visibility"][RPE, 48:80] = P.MARK_NO      # lesion core
        local["local_drawn"][ILM, :] = True
        local["local_visibility"][ILM, :] = P.MARK_YES
        return L.load_label(write(temp, surfaces=surfaces, auto=auto,
                                  local=local))

    def test_cnv_example_supervises_flanks_only_and_keeps_the_ilm(self):
        with tempfile.TemporaryDirectory() as temp:
            record = self._cnv_record(temp)
        valid = T.column_valid(record)
        self.assertTrue(valid[RPE, 10:40].all())
        self.assertTrue(valid[RPE, 88:118].all())
        self.assertFalse(valid[RPE, 48:80].any())    # core: no position target
        self.assertFalse(valid[RPE, 0:10].any())     # never drawn, never claimed
        self.assertTrue(valid[ILM].all())            # untouched by the RPE mark
        self.assertFalse(record["region_excluded"].any())

    def test_cnv_example_visibility_supervision_excludes_the_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            record = self._cnv_record(temp)
        target = T.visibility_target(record)
        weight = T.visibility_weight(record)
        self.assertTrue((weight[RPE, 48:80] == 1).all())
        self.assertTrue((target[RPE, 48:80] == 0).all())     # explicitly hidden
        self.assertTrue((weight[RPE, 10:40] == 1).all())
        self.assertTrue((target[RPE, 10:40] == 1).all())
        self.assertTrue((weight[RPE, 0:10] == 0).all())      # unknown, not "no"
        self.assertTrue((weight[ILM] == 1).all())

    def test_region_supervision_needs_both_bounding_surfaces_in_that_column(self):
        with tempfile.TemporaryDirectory() as temp:
            record = self._cnv_record(temp)
        per_column = T.region_column_supervised(record)
        rpe_band = T.REGION_NAMES.index("RPE")            # PR_RPE .. RPE
        self.assertFalse(per_column[rpe_band].any())      # PR_RPE never drawn
        vitreous = T.REGION_NAMES.index("VITREOUS")       # bounded by ILM only
        self.assertTrue(per_column[vitreous].all())
        rows = record["surfaces"]
        ids = T.region_map(rows, 240)
        weight = T.region_weight(record, ids)
        self.assertEqual(weight.shape, (240, N_COL))
        above_ilm = ids == vitreous
        self.assertTrue((weight[above_ilm] == 1).all())

    def test_taper_review_and_displacement_are_not_position_evidence(self):
        auto = synthetic_auto()
        surfaces = auto.copy()
        local = P.empty_local(N_COL)
        local["local_taper"][RPE, 0:10] = True
        local["local_reviewed"][RPE, 10:20] = True
        local["local_displaced"][RPE, 20:30] = True
        local["local_drawn"][RPE, 30:40] = True
        local["local_drawn"][RPE, 40:50] = True
        local["local_displaced"][RPE, 40:50] = True       # drawn, then shoved
        with tempfile.TemporaryDirectory() as temp:
            record = L.load_label(write(temp, surfaces=surfaces, auto=auto,
                                        local=local))
        valid = T.column_valid(record)
        self.assertFalse(valid[RPE, 0:30].any())
        self.assertTrue(valid[RPE, 30:40].all())
        self.assertFalse(valid[RPE, 40:50].any())
        self.assertTrue(T.reviewed_only(record)[RPE, 10:20].all())
        self.assertFalse(T.reviewed_only(record)[RPE, 30:40].any())

    def test_local_unreliable_and_whole_column_exclusion_both_bite(self):
        auto = synthetic_auto()
        local = P.empty_local(N_COL)
        local["local_drawn"][RPE, :] = True
        local["local_reliability"][RPE, 0:20] = P.MARK_NO
        excluded = np.zeros(N_COL, bool)
        excluded[100:] = True
        with tempfile.TemporaryDirectory() as temp:
            record = L.load_label(write(temp, surfaces=auto.copy(), auto=auto,
                                        local=local, excluded=excluded))
        valid = T.column_valid(record)
        self.assertFalse(valid[RPE, 0:20].any())     # locally unreliable
        self.assertTrue(valid[RPE, 20:100].all())
        self.assertFalse(valid[RPE, 100:].any())     # whole-column exclusion
        self.assertTrue((T.visibility_weight(record)[:, 100:] == 0).all())

    def test_thickness_maps_take_per_a_line_reliability(self):
        surfaces = synthetic_auto()[None, ...]
        shadow = np.zeros((1, N_COL), bool)
        rel = np.ones((1, N_SURFACES, N_COL), bool)
        rel[0, RPE, 48:80] = False
        maps = thickness_maps(surfaces, shadow, surface_reliable=rel)
        self.assertTrue(np.isnan(maps["RPE"][0, 48:80]).all())
        self.assertTrue(np.isfinite(maps["RPE"][0, :48]).all())
        self.assertTrue(np.isfinite(maps["RNFL"][0]).all())   # ILM band survives
        # the older shapes still behave exactly as before
        flat = np.ones(N_SURFACES, bool)
        flat[RPE] = False
        old = thickness_maps(surfaces, shadow, surface_reliable=flat)
        self.assertTrue(np.isnan(old["RPE"][0]).all())
        self.assertTrue(np.isfinite(old["RNFL"][0]).all())


# ------------------------------------------------------------------- the GUI

def _make_pack(path: Path, n_bscan: int = 2, n_col: int = N_COL):
    """A minimal review pack the real Pack class will accept."""
    auto = synthetic_auto(n_col)
    images = np.zeros((n_bscan, 240, n_col), np.float32)
    images[:, 60:140, :] = 12.0
    np.savez_compressed(
        path,
        images=images,
        surfaces=np.broadcast_to(auto, (n_bscan, N_SURFACES, n_col)).copy(),
        confidence=np.full((n_bscan, N_SURFACES, n_col), 2.0, np.float32),
        shadow=np.zeros((n_bscan, n_col), bool),
        surface_names=np.array(SURFACE_NAMES),
        bscan_index=np.arange(n_bscan, dtype=int),
        is_control=np.zeros(n_bscan, bool),
        suspect_score=np.full(n_bscan, 0.5),
        scan_id=np.array(["TS999_OD_2025-01-01_D7_s01"]),
        px_um=np.array([1.12], np.float32))
    return path


class GuiTests(unittest.TestCase):
    """Drive the real widgets offscreen; the interaction is where bugs live."""

    app = None
    gui = None

    @classmethod
    def setUpClass(cls):
        try:
            from eight_surface import label_gui
        except Exception as exc:                            # noqa: BLE001
            raise unittest.SkipTest(f"GUI unavailable: {exc}")
        cls.gui = label_gui
        cls.app = (label_gui.QtWidgets.QApplication.instance()
                   or label_gui.QtWidgets.QApplication([]))

    def _window(self, stack):
        temp = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        pack = _make_pack(temp / "TS999_pack.npz")
        labels_dir = temp / "labels"
        window = self.gui.MainWindow([pack], labels_dir)
        stack.callback(window.close)
        return window, labels_dir, pack

    def test_a_localised_stroke_marks_only_the_columns_it_covered(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, _labels, _pack = self._window(stack)
            window.s = RPE
            state = window.pack.states[window.i]
            base = state.current[RPE].copy()
            window.taper_spin.setValue(10)
            xs = np.arange(50.0, 70.0)
            window.on_stroke(xs, base[50:70] + 5.0)

            drawn = state.local["local_drawn"][RPE]
            self.assertTrue(drawn[50:70].all())
            self.assertFalse(drawn[:50].any() or drawn[70:].any())
            self.assertTrue(state.local["local_taper"][RPE, 45])
            self.assertFalse(state.local["local_taper"][RPE, 60])
            self.assertTrue(state.edited[RPE])
            self.assertFalse(state.edited[ILM])
            # visibility follows for free: you cannot draw what you cannot see
            self.assertTrue(
                (state.local["local_visibility"][RPE, 50:70] == P.MARK_YES).all())
            self.assertEqual(
                state.local["local_visibility"][RPE, 0], P.MARK_UNKNOWN)

    def test_ordering_displacement_of_a_drawn_segment_loses_trust(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, _labels, _pack = self._window(stack)
            state = window.pack.states[window.i]
            # draw RNFL_GCL first, then drag the ILM straight through it
            window.s = 1
            window.taper_spin.setValue(0)
            window.on_stroke(np.arange(40.0, 60.0),
                             state.current[1, 40:60].copy())
            self.assertTrue(state.local["local_drawn"][1, 40:60].all())
            code = P.provenance_code(
                state.local["local_drawn"], state.local["local_taper"],
                state.local["local_displaced"], state.local["local_reviewed"])
            self.assertTrue((code[1, 40:60] == P.PROV_DRAWN).all())

            window.s = 0
            window.on_stroke(np.arange(40.0, 60.0),
                             np.full(20, state.current[1, 50] + 30.0))
            code = P.provenance_code(
                state.local["local_drawn"], state.local["local_taper"],
                state.local["local_displaced"], state.local["local_reviewed"])
            self.assertTrue((code[1, 40:60] == P.PROV_DRAWN_DISPLACED).all(),
                            "a shoved drawn segment still looks like ground truth")
            self.assertTrue(state.local["local_drawn"][1, 40:60].all(),
                            "the drawing history was lost")
            self.assertFalse(state.local["local_displaced"][1, 0])

    def test_local_marks_touch_one_boundary_and_never_the_exclusion_mask(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, _labels, _pack = self._window(stack)
            window.s = RPE
            state = window.pack.states[window.i]
            window.on_local_marked(48, 79, "not_visible")
            self.assertTrue(
                (state.local["local_visibility"][RPE, 48:80] == P.MARK_NO).all())
            self.assertTrue(
                (state.local["local_visibility"][ILM] == P.MARK_UNKNOWN).all())
            self.assertFalse(state.excluded.any())
            self.assertTrue(state.visible.all(), "whole-surface flag was touched")

            window.on_local_marked(48, 59, "visible")
            self.assertTrue(
                (state.local["local_visibility"][RPE, 48:60] == P.MARK_YES).all())
            self.assertTrue(
                (state.local["local_visibility"][RPE, 60:80] == P.MARK_NO).all())

            window.on_local_marked(0, 9, "unreliable")
            self.assertTrue(
                (state.local["local_reliability"][RPE, 0:10] == P.MARK_NO).all())
            self.assertTrue(
                (state.local["local_visibility"][RPE, 0:10] == P.MARK_UNKNOWN).all(),
                "reliability and visibility are not the same axis")

    def test_explicit_review_is_recorded_as_review_not_as_drawing(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, labels_dir, _pack = self._window(stack)
            window.s = RPE
            state = window.pack.states[window.i]
            before = state.current[RPE].copy()
            window.on_local_marked(0, 63, "reviewed")
            self.assertTrue(np.array_equal(state.current[RPE], before))
            self.assertTrue(state.local["local_reviewed"][RPE, 0:64].all())
            self.assertFalse(state.local["local_drawn"].any())
            self.assertFalse(state.edited.any())
            window.commit_current()
            record = L.load_label(next(labels_dir.glob("*.npz")))
            self.assertFalse(T.column_valid(record).any(),
                             "a reviewed automatic line became a training target")
            self.assertTrue(T.reviewed_only(record)[RPE, 0:64].all())
            self.assertTrue((T.visibility_weight(record)[RPE, 0:64] == 1).all())

    def test_undo_redo_and_reset_carry_the_history_with_the_line(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, _labels, _pack = self._window(stack)
            window.s = RPE
            state = window.pack.states[window.i]
            original = state.current[RPE].copy()
            window.on_stroke(np.arange(50.0, 70.0), original[50:70] + 6.0)
            window.on_local_marked(80, 99, "not_visible")

            self.assertTrue(state.undo())              # undo the local mark
            self.assertTrue(
                (state.local["local_visibility"][RPE, 80:100] == P.MARK_UNKNOWN).all())
            self.assertTrue(state.local["local_drawn"][RPE, 50:70].all())

            self.assertTrue(state.undo())              # undo the stroke
            self.assertTrue(np.allclose(state.current[RPE], original))
            self.assertFalse(state.local["local_drawn"].any(),
                             "undo restored the line but kept the drawing claim")

            self.assertTrue(state.redo())
            self.assertTrue(state.local["local_drawn"][RPE, 50:70].all())
            self.assertFalse(np.allclose(state.current[RPE], original))

            window.revert_all()
            self.assertFalse(state.local["local_drawn"].any())
            self.assertFalse(state.local["local_visibility"].any())
            self.assertTrue(np.allclose(state.current, state.auto))
            self.assertFalse(state.edited.any() or state.displaced.any())

    def test_revert_surface_clears_only_that_boundary(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, _labels, _pack = self._window(stack)
            state = window.pack.states[window.i]
            window.s = RPE
            window.on_stroke(np.arange(50.0, 70.0), state.current[RPE, 50:70] + 6.0)
            window.s = ILM
            window.on_stroke(np.arange(10.0, 30.0), state.current[ILM, 10:30] - 4.0)
            window.revert_surface()
            self.assertFalse(state.local["local_drawn"][ILM].any())
            self.assertTrue(state.local["local_drawn"][RPE, 50:70].all())
            self.assertFalse(state.edited[ILM])
            self.assertTrue(state.edited[RPE])

    def test_clear_local_marks_keeps_stroke_history(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, _labels, _pack = self._window(stack)
            window.s = RPE
            state = window.pack.states[window.i]
            window.on_stroke(np.arange(50.0, 70.0), state.current[RPE, 50:70] + 6.0)
            window.on_local_marked(80, 99, "not_visible")
            window.clear_local_marks()
            self.assertTrue(
                (state.local["local_visibility"][RPE] == P.MARK_UNKNOWN).all())
            self.assertTrue(state.local["local_drawn"][RPE, 50:70].all())

    def test_save_and_resume_preserve_every_distinction(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, labels_dir, pack = self._window(stack)
            window.s = RPE
            state = window.pack.states[window.i]
            window.taper_spin.setValue(10)
            window.on_stroke(np.arange(10.0, 40.0), state.current[RPE, 10:40] + 5.0)
            window.on_local_marked(48, 79, "not_visible")
            window.on_local_marked(88, 117, "reviewed")
            before = {k: v.copy() for k, v in state.local.items()}
            before_line = state.current.copy()
            window.commit_current()

            reopened = self.gui.Pack(pack, labels_dir)
            resumed = reopened.states[0]
            self.assertEqual(resumed.verdict, "corrected")
            self.assertTrue(np.allclose(resumed.current, before_line))
            for key, value in before.items():
                self.assertTrue(np.array_equal(resumed.local[key], value), key)

            record = L.load_label(next(labels_dir.glob("*.npz")))
            valid = T.column_valid(record)
            self.assertTrue(valid[RPE, 10:40].all())
            self.assertFalse(valid[RPE, 48:80].any())
            self.assertFalse(valid[RPE, 88:118].any())   # reviewed, not drawn
            self.assertFalse(valid[RPE, 0:10].any())     # taper only

    def test_the_cnv_case_end_to_end_in_the_gui(self):
        """Outer boundary unidentifiable through a lesion, ILM fine throughout.

        Neither the whole outer boundary nor the ILM's columns may be disabled.
        """
        import contextlib
        with contextlib.ExitStack() as stack:
            window, labels_dir, _pack = self._window(stack)
            state = window.pack.states[window.i]
            window.taper_spin.setValue(0)
            window.s = RPE
            window.on_stroke(np.arange(10.0, 40.0), state.current[RPE, 10:40] + 4.0)
            window.on_stroke(np.arange(88.0, 118.0), state.current[RPE, 88:118] + 4.0)
            window.on_local_marked(48, 79, "not_visible")
            window.s = ILM
            window.on_stroke(np.arange(0.0, float(N_COL)), state.current[ILM] - 2.0)
            window.on_local_marked(0, N_COL - 1, "visible")
            window.commit_current()

            record = L.load_label(next(labels_dir.glob("*.npz")))
            valid = T.column_valid(record)
            self.assertTrue(valid[ILM].all(), "the ILM was excluded by the RPE mark")
            self.assertTrue(valid[RPE, 10:40].all())
            self.assertTrue(valid[RPE, 88:118].all())
            self.assertFalse(valid[RPE, 48:80].any())
            self.assertTrue(record["surface_visible"][RPE],
                            "the whole outer boundary was disabled")
            self.assertFalse(record["region_excluded"].any(),
                             "whole-column exclusion was used for a local problem")
            visibility = P.record_visibility(record)
            self.assertTrue((visibility[RPE, 48:80] == P.MARK_NO).all())
            self.assertTrue((visibility[ILM] == P.MARK_YES).all())
            summary = P.summarise(record)
            self.assertEqual(int(summary["drawn_columns"][RPE]), 60)
            self.assertEqual(int(summary["not_visible_columns"][RPE]), 32)
            self.assertEqual(int(summary["drawn_columns"][ILM]), N_COL)

    def test_whole_column_exclusion_still_disables_every_boundary(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, labels_dir, _pack = self._window(stack)
            state = window.pack.states[window.i]
            window.s = RPE
            window.on_stroke(np.arange(0.0, float(N_COL)), state.current[RPE] + 3.0)
            window.s = ILM
            window.on_stroke(np.arange(0.0, float(N_COL)), state.current[ILM] - 3.0)
            window.on_region_marked(100, 120, True)
            window.commit_current()
            record = L.load_label(next(labels_dir.glob("*.npz")))
            valid = T.column_valid(record)
            self.assertFalse(valid[:, 100:121].any())
            self.assertTrue(valid[RPE, 0:100].all())
            self.assertTrue(valid[ILM, 0:100].all())

    def test_gesture_modifiers_map_to_the_documented_actions(self):
        mods = self.gui.Qt.KeyboardModifier
        button = self.gui.Qt.MouseButton
        cases = {
            (button.RightButton, mods.ShiftModifier): "not_visible",
            (button.RightButton, mods.ShiftModifier | mods.ControlModifier): "visible",
            (button.RightButton, mods.AltModifier): "unreliable",
            (button.RightButton, mods.AltModifier | mods.ControlModifier): "reliable",
            (button.LeftButton, mods.ShiftModifier): "reviewed",
            (button.RightButton, mods.NoModifier): None,      # whole-column
            (button.RightButton, mods.ControlModifier): None,  # clear exclusion
            (button.LeftButton, mods.NoModifier): None,        # draw
        }
        for (btn, mod), expected in cases.items():
            self.assertEqual(self.gui.Canvas._intent(btn, mod, False), expected)
        self.assertIsNone(                                     # space = pan
            self.gui.Canvas._intent(button.LeftButton, mods.ShiftModifier, True))

    def test_overlay_paints_bands_only_where_marks_exist(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            window, _labels, _pack = self._window(stack)
            window.s = RPE
            state = window.pack.states[window.i]
            self.assertTrue(
                window.canvas._band_items["not_visible"].path().isEmpty())
            window.on_local_marked(48, 79, "not_visible")
            self.assertFalse(
                window.canvas._band_items["not_visible"].path().isEmpty())
            self.assertTrue(
                window.canvas._band_items["unreliable"].path().isEmpty())
            # the ruler always covers the full width across its four states
            widths = sum(
                item.path().boundingRect().width()
                for item in window.canvas._ruler_items.values()
                if not item.path().isEmpty())
            self.assertGreaterEqual(widths, N_COL - 1)
            self.assertTrue(state.local["local_visibility"][RPE, 48:80].all())


if __name__ == "__main__":
    unittest.main(verbosity=2)
