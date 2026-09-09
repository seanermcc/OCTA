#!/usr/bin/env python3
"""Interactive correction for the isolated eight-boundary review packs.

Run from ``code`` after activating ``octa``::

    python eight_surface/label_gui.py ../outputs/eight_surface/review

Tracing is unchanged: left-drag redraws the active boundary and the correction
is tapered back onto the automatic line beyond the ends of the stroke.  What is
new is that the file now records **where** each of those things happened,
per A-line, instead of one flag for the whole boundary.

Four independent judgements
---------------------------
* **whole-image exclusion** (right-drag) -- the image is unusable in these
  columns for *every* boundary: a shadow, an edge artefact, no signal.
* **local visibility** (shift+right-drag) -- *this* boundary cannot be
  identified confidently in these columns, while every other boundary in the
  same columns is untouched.  This is the CNV case: the outer RPE edge is
  visible beside a lesion and unidentifiable through its centre, and the ILM is
  fine all the way across.  "Not visible" is a statement about the recorded
  image, never a claim that the tissue is absent.
* **local reliability** (alt+right-drag) -- the answer here is not good enough
  to analyse, whether or not the boundary can be seen.
* **explicit local review** (shift+left-drag) -- "I looked at this stretch and
  the automatic line is right."  Recorded as review, never as drawing, and it
  never becomes a boundary-position training target on its own.

Columns nobody has ruled on stay **unknown**, which is a third state: not
visible, not invisible.  The top ruler strip shows the active boundary's state
across the B-scan at a glance.

Provenance is recorded automatically
------------------------------------
Every column is one of: drawn by a stroke, software taper joining a stroke back
to the automatic line, moved by the ordering constraint, explicitly reviewed, or
untouched automatic output.  A stroke over 40 A-lines marks 40 A-lines, not the
whole boundary.  If ordering later shoves a segment somebody had drawn, the
drawing history is kept *and* the segment stops counting as trusted ground
truth.

Controls
--------
left-drag             redraw active boundary
shift+left-drag       mark this range of the active boundary reviewed-as-correct
right-drag            mark an A-line range unusable for every boundary
ctrl+right-drag       clear that range
shift+right-drag      active boundary only: cannot identify confidently here
ctrl+shift+right-drag active boundary only: restore visibility here
alt+right-drag        active boundary only: locally unreliable for analysis
ctrl+alt+right-drag   active boundary only: locally reliable
u                     clear active boundary's local marks back to unknown
[ ]                   previous / next boundary
, . or PgUp/Dn        previous / next B-scan
n                     next undecided B-scan (across every pack)
v                     toggle whether active boundary is visible ANYWHERE here
q                     toggle whether active boundary is included in analysis
a / x                 accept / reject B-scan
r / shift+r           revert active boundary / whole B-scan
ctrl+z / ctrl+y       undo / redo    ctrl+s  save    e  clear all exclusions
h                     this help
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

import label_gui as legacy  # noqa: E402

from eight_surface import labels as L  # noqa: E402
from eight_surface import provenance as P  # noqa: E402
from eight_surface.config import (  # noqa: E402
    CASCADE_VERSION, N_SURFACES, SURFACE_NAMES, affected_layers,
)


Qt = legacy.Qt
QtCore, QtGui, QtWidgets = legacy.QtCore, legacy.QtGui, legacy.QtWidgets
DEFAULT_REVIEW_DIR = Path("../outputs/eight_surface/review")
DEFAULT_LABEL_DIR = Path("../outputs/eight_surface/labels")

# Reuse the mature canvas and navigation machinery from the original GUI, but
# bind every global it consults to this incompatible eight-boundary contract.
legacy.SURFACE_NAMES = SURFACE_NAMES
legacy.CASCADE_VERSION = CASCADE_VERSION
legacy.L = L
legacy.DEFAULT_REVIEW_DIR = DEFAULT_REVIEW_DIR
legacy.DEFAULT_LABEL_DIR = DEFAULT_LABEL_DIR
legacy.SURFACE_COLOURS = legacy.SURFACE_COLOURS[:N_SURFACES]


class BscanState(legacy.BscanState):
    """Original state, plus whole-boundary reliability and the local record.

    ``local`` holds the six ``[8, A-line]`` planes of
    :mod:`eight_surface.provenance`.  It is part of every undo snapshot: a
    stroke changes the line *and* the drawing history, and an undo that put the
    line back while leaving the history claiming a human drew there would be
    worse than no history at all.
    """

    def __init__(self, auto: np.ndarray, n_surf: int):
        super().__init__(auto, n_surf)
        self.reliable = np.ones(n_surf, dtype=bool)
        self.local = P.empty_local(auto.shape[1])

    def _snapshot(self):
        return (self.current.copy(), self.edited.copy(), self.displaced.copy(),
                self.visible.copy(), self.reliable.copy(), self.excluded.copy(),
                {k: v.copy() for k, v in self.local.items()})

    def _restore(self, snap):
        (self.current, self.edited, self.displaced, self.visible,
         self.reliable, self.excluded) = tuple(item.copy() for item in snap[:6])
        self.local = {k: v.copy() for k, v in snap[6].items()}

    def sync_surface_flags(self):
        """Derive the ``[8]`` flags from the local record, never the reverse.

        ``surface_edited`` keeps meaning "a stroke landed somewhere on this
        boundary" and ``surface_displaced`` keeps its original meaning, so an
        older reader of these files sees exactly what it saw before.  Deriving
        them is what stops the two levels from ever disagreeing.
        """
        self.edited = self.local["local_drawn"].any(axis=1)
        self.displaced = (~self.edited) & self.local["local_displaced"].any(axis=1)

    def reset_local(self, k=None):
        blank = P.empty_local(self.current.shape[1])
        for key, value in blank.items():
            if k is None:
                self.local[key] = value
            else:
                self.local[key][k] = value[k]


# ---------------------------------------------------------------- canvas ----

LOCAL_STYLE = {
    "not_visible": ("#ff5ce6", "cannot identify"),
    "unreliable": ("#ffb020", "unreliable"),
    "supported": ("#3cb44b", "drawn / reviewed"),
    "unknown": ("#4a4a55", "unreviewed"),
}
RULER_HEIGHT_PX = 6.0


def _runs(mask):
    """Contiguous True runs of a 1-D bool mask, as ``(start, stop)`` pairs."""
    mask = np.asarray(mask, bool)
    if not mask.any():
        return []
    padded = np.concatenate(([False], mask, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[0::2].tolist(), edges[1::2].tolist()))


class Canvas(legacy.Canvas):
    """Legacy canvas plus the local-mark gestures and their overlay.

    The overlay deliberately never covers the pixels a reviewer is judging.
    Local marks are drawn as translucent bands *along the active boundary*, and
    the complete per-column state is shown as a thin ruler across the top of
    the image, where it hides nothing.
    """

    localMarked = QtCore.Signal(float, float, str)   # x0, x1, action

    def __init__(self):
        super().__init__()
        self._local_action = None
        self._band_items = {}
        for key in ("not_visible", "unreliable"):
            item = self.scene().addPath(QtGui.QPainterPath())
            item.setZValue(30)
            pen = QtGui.QPen(QtGui.QColor(LOCAL_STYLE[key][0]), 11.0)
            pen.setCosmetic(True)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            if key == "not_visible":
                pen.setStyle(Qt.PenStyle.DashLine)
            item.setPen(pen)
            item.setOpacity(0.38)
            self._band_items[key] = item
        self._ruler_items = {}
        for key, (colour, _) in LOCAL_STYLE.items():
            item = self.scene().addPath(QtGui.QPainterPath())
            item.setZValue(40)
            item.setPen(QtGui.QPen(Qt.PenStyle.NoPen))
            item.setBrush(QtGui.QColor(colour))
            item.setOpacity(0.85)
            self._ruler_items[key] = item

    # -- gestures ------------------------------------------------------
    @staticmethod
    def _intent(button, mods, space):
        """Which local mark, if any, this press is starting."""
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        if space:
            return None
        if button == Qt.MouseButton.RightButton:
            if shift:
                return "visible" if ctrl else "not_visible"
            if alt:
                return "reliable" if ctrl else "unreliable"
            return None
        if button == Qt.MouseButton.LeftButton and shift and not (ctrl or alt):
            return "reviewed"
        return None

    def mousePressEvent(self, ev):
        action = self._intent(ev.button(), ev.modifiers(), self._space)
        if action is None:
            self._local_action = None
            super().mousePressEvent(ev)
            return
        self._local_action = action
        self._region_dragging = True
        self._region_clear = False
        point = self.mapToScene(ev.position().toPoint())
        self._region_x0 = point.x()
        self._draw_region_preview(point.x())

    def mouseReleaseEvent(self, ev):
        if self._local_action is not None and self._region_dragging:
            self._region_dragging = False
            action, self._local_action = self._local_action, None
            point = self.mapToScene(ev.position().toPoint())
            x0, x1 = sorted((self._region_x0, point.x()))
            self._region_preview.setPath(QtGui.QPainterPath())
            self.localMarked.emit(x0, x1, action)
            return
        super().mouseReleaseEvent(ev)

    # -- overlay -------------------------------------------------------
    def set_local_marks(self, y, visibility, reliability, code):
        """Repaint the overlay for the active boundary only.

        ``visibility``/``reliability`` are tri-state ``[A-line]`` arrays and
        ``code`` the ``[A-line]`` provenance codes.  Every other boundary's
        local state stays off-screen; painting eight of these at once is how
        the display would stop being readable.
        """
        y = np.asarray(y, float)
        finite = np.isfinite(y)
        masks = {
            "not_visible": np.asarray(visibility) == P.MARK_NO,
            "unreliable": np.asarray(reliability) == P.MARK_NO,
        }
        for key, item in self._band_items.items():
            path = QtGui.QPainterPath()
            for lo, hi in _runs(masks[key] & finite):
                path.moveTo(float(lo), y[lo])
                for c in range(lo + 1, hi):
                    path.lineTo(float(c), y[c])
            item.setPath(path)

        supported = np.isin(np.asarray(code), [
            P.PROV_DRAWN, P.PROV_REVIEWED, P.PROV_DRAWN_DISPLACED])
        known = masks["not_visible"] | masks["unreliable"] | supported
        ruler = {
            "not_visible": masks["not_visible"],
            "unreliable": masks["unreliable"] & ~masks["not_visible"],
            "supported": supported & ~masks["not_visible"] & ~masks["unreliable"],
            "unknown": ~known,
        }
        for key, item in self._ruler_items.items():
            path = QtGui.QPainterPath()
            for lo, hi in _runs(ruler[key]):
                path.addRect(lo - 0.5, 0.0, hi - lo, RULER_HEIGHT_PX)
            item.setPath(path)


# The inherited MainWindow constructs ``Canvas()`` by module-global lookup.
legacy.Canvas = Canvas


class Pack(legacy.Pack):
    """Pack reader/writer for the eight-boundary label schema."""

    def __init__(self, path: Path, label_dir: Path):
        super().__init__(path, label_dir)
        # Lesion-centred packs add metadata without creating a second surface
        # label format. Ordinary QC packs receive empty roles here.
        with np.load(self.path, allow_pickle=False) as data:
            self.selection_role = (
                np.asarray(data["selection_role"]).astype(str)
                if "selection_role" in data.files
                else np.full(self.n, "", dtype="U1"))
            self.lesion_zone = (
                data["lesion_zone"].astype(np.uint8)
                if "lesion_zone" in data.files else None)
            self.zone_names = (
                [str(x) for x in data["zone_names"]]
                if "zone_names" in data.files else [])
        if self.selection_role.shape != (self.n,):
            raise ValueError("selection_role must have one value per packed B-scan")
        if self.lesion_zone is not None and self.lesion_zone.shape != (
                self.n, self.images.shape[2]):
            raise ValueError("lesion_zone must be [packed B-scan, A-line]")

    def _load_existing(self):
        self.n_preloaded = 0
        for i, bscan in enumerate(self.bscan_index):
            path = L.label_path(self.label_dir, self.scan_id, int(bscan))
            if not path.exists():
                continue
            try:
                record = L.load_label(path)
            except Exception:  # noqa: BLE001
                continue
            if (record["surface_names"] != self.names or
                    record.get("cascade_version") != CASCADE_VERSION):
                continue
            state = self.states[i]
            state.current = record["surfaces"].astype(float)
            state.edited = record["surface_edited"].astype(bool)
            state.displaced = record["surface_displaced"].astype(bool)
            state.visible = record["surface_visible"].astype(bool)
            state.reliable = record["surface_reliable"].astype(bool)
            state.excluded = record["region_excluded"].astype(bool)
            # Resuming must not upgrade a legacy label's silence into a claim.
            # ``local_arrays`` returns empty planes for a file that never
            # recorded them, so a resumed legacy B-scan carries no invented
            # stroke history -- while its [8] flags, above, are preserved.
            state.local = L.local_arrays(record)
            state.verdict = record["verdict"]
            state.seconds = float(record.get("seconds_active") or 0.0)
            state.n_strokes = max(int(record.get("n_strokes") or 0), 0)
            state.notes = str(record.get("notes", ""))
            self.n_preloaded += 1

    def save(self, i: int):
        state = self.states[i]
        if state.verdict is None:
            return None
        return L.save_label(
            self.label_dir, scan_id=self.scan_id, bscan=int(self.bscan_index[i]),
            verdict=state.verdict, surfaces=state.current, auto_surfaces=state.auto,
            surface_names=self.names, surface_edited=state.edited,
            surface_displaced=state.displaced, surface_visible=state.visible,
            surface_reliable=state.reliable, region_excluded=state.excluded,
            local=state.local,
            px_um=self.px_um, cascade_version=CASCADE_VERSION,
            seconds_active=state.seconds, n_strokes=state.n_strokes,
            is_control=bool(self.is_control[i]),
            labeller=os.environ.get("USERNAME") or os.environ.get("USER") or "",
            source_pack=self.path.name, notes=state.notes)


# Global lookups inside inherited methods resolve in the original module.
legacy.BscanState = BscanState
legacy.Pack = Pack


class MainWindow(legacy.MainWindow):
    # QListWidget emits ``itemChanged`` for both a human checkbox click and a
    # programmatic change to the item's label/font/check-state.  The legacy
    # editor only redraws in that signal handler; this editor also refreshes
    # the explanatory text, so it needs an explicit re-entry guard.
    _updating_surface_list = False

    #: What each local gesture writes.  Kept as data so the help text, the
    #: side-panel legend and the handler cannot drift apart.
    LOCAL_ACTIONS = {
        "not_visible": "cannot identify this boundary here",
        "visible": "boundary identifiable here",
        "unreliable": "not reliable enough to analyse here",
        "reliable": "reliable to analyse here",
        "reviewed": "reviewed: automatic line is right here",
    }

    def __init__(self, packs, label_dir):
        super().__init__(packs, label_dir)
        self.canvas.localMarked.connect(self.on_local_marked)

    def _build_side_panel(self):
        super()._build_side_panel()
        dock = self.findChildren(QtWidgets.QDockWidget)[0]
        dock.setWindowTitle("boundaries — check = include in analysis")
        layout = dock.widget().layout()
        note = QtWidgets.QLabel(
            "Uncheck an unreliable boundary to exclude its adjacent thickness "
            "band(s) across the whole B-scan. Lines remain visible; <b>v</b> "
            "means not visible <i>anywhere</i> here.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #d9b66f;")
        layout.insertWidget(0, note)

        local = QtWidgets.QLabel(
            "<b>Local marks &mdash; active boundary only</b><br>"
            "shift+right-drag &nbsp;cannot identify here<br>"
            "ctrl+shift+right-drag &nbsp;restore visible<br>"
            "alt+right-drag &nbsp;unreliable here<br>"
            "ctrl+alt+right-drag &nbsp;reliable here<br>"
            "shift+left-drag &nbsp;reviewed, line is right<br>"
            "<b>u</b> &nbsp;back to unreviewed &nbsp;&middot;&nbsp; "
            "right-drag still excludes <i>every</i> boundary")
        local.setWordWrap(True)
        local.setStyleSheet(
            "color: #cfd3dc; background: #23252c; padding: 6px;")
        layout.insertWidget(1, local)

        swatches = " ".join(
            f"<span style='color:{colour};'>&#9632;</span>&nbsp;{text}"
            for colour, text in
            (LOCAL_STYLE[k] for k in
             ("not_visible", "unreliable", "supported", "unknown")))
        legend = QtWidgets.QLabel("top ruler: " + swatches)
        legend.setWordWrap(True)
        layout.insertWidget(2, legend)

    def _has_current_bscan(self) -> bool:
        return (self.pack is not None and
                0 <= self.i < self.pack.n)

    @staticmethod
    def _displayable_index(pack, start: int, direction: int) -> int | None:
        """First B-scan at/after ``start`` that was not rejected."""
        for i in range(start, pack.n if direction > 0 else -1, direction):
            if pack.states[i].verdict != "rejected":
                return i
        return None

    def load_pack(self, pi: int, *, start_index: int | None = None,
                  direction: int = 1) -> bool:
        """Switch packs without exposing a stale index to Qt callbacks.

        The inherited implementation assigns the new, potentially shorter
        pack before resetting ``self.i``.  A mouse-move or window-focus event
        can run in that tiny interval and index the new state list with the
        old pack's B-scan index.  Reset the index before any UI work instead.
        """
        if direction not in (-1, 1) or not (0 <= pi < len(self.pack_paths)):
            return False
        if self._has_current_bscan():
            self.commit_current()
        target_pi, requested = pi, start_index
        while 0 <= target_pi < len(self.pack_paths):
            try:
                incoming = Pack(self.pack_paths[target_pi], self.label_dir)
            except Exception as exc:  # noqa: BLE001
                QtWidgets.QMessageBox.critical(
                    self, "cannot open pack",
                    f"{self.pack_paths[target_pi].name}\n\n{exc}")
                return False
            anchor = (requested if requested is not None
                      else (0 if direction > 0 else incoming.n - 1))
            anchor = int(np.clip(anchor, 0, incoming.n - 1))
            start = self._displayable_index(incoming, anchor, direction)
            if start is not None:
                self.pack = incoming
                self.pi = target_pi
                self.i = 0         # before any signal-producing UI call
                self.s = 0
                self._t0 = legacy.time.monotonic()
                if self.pack.retired:
                    self.statusBar().showMessage(
                        f"ignoring retired surfaces: {', '.join(self.pack.retired)}", 8000)
                self._rebuild_surface_list()
                self.canvas.ensure_surface_items(
                    len(self.pack.names), legacy.SURFACE_COLOURS)
                self.show_bscan(start, fit=True)
                return True
            target_pi += direction
            requested = None
        self.statusBar().showMessage("no non-rejected B-scans in that direction", 5000)
        return False

    def _bank_time(self):
        # Focus-change events can arrive while Qt is replacing widgets.  They
        # are not a review action, so simply reset the clock if no current
        # B-scan is available rather than raising from a stale callback.
        if not self._has_current_bscan():
            self._t0 = legacy.time.monotonic()
            return
        super()._bank_time()

    def on_cursor(self, x, y):
        if self._has_current_bscan():
            super().on_cursor(x, y)

    def next_bscan(self, step: int):
        """Walk the packed queue predictably, skipping only rejections."""
        if step not in (-1, 1) or not self._has_current_bscan():
            return
        j = self.i + step
        while 0 <= j < self.pack.n:
            if self.pack.states[j].verdict != "rejected":
                self.show_bscan(j)
                return
            j += step
        self.load_pack(self.pi + step,
                       start_index=0 if step > 0 else None,
                       direction=step)

    def jump_next_unreviewed(self):
        """Move to the next undecided B-scan without changing any verdict."""
        if not self._has_current_bscan():
            return
        for i in range(self.i + 1, self.pack.n):
            if self.pack.states[i].verdict is None:
                self.show_bscan(i)
                return
        for pi in range(self.pi + 1, len(self.pack_paths)):
            if not self.load_pack(pi, direction=1):
                break
            start = self._first_unreviewed(self.pack)
            if start is not None:
                self.show_bscan(start)
                return
        self.statusBar().showMessage("no unreviewed B-scans left in the queue", 5000)

    def _rebuild_surface_list(self):
        super()._rebuild_surface_list()
        for k, name in enumerate(self.pack.names):
            item = self.surface_list.item(k)
            item.setToolTip(
                f"{name}: checked = include in analysis.  Unchecked excludes "
                f"{', '.join(affected_layers(name)) or 'no direct layer'}.")
        self._sync_checkboxes()

    def _sync_checkboxes(self):
        if self.pack is None:
            return
        state = self.pack.states[self.i]
        self.surface_list.blockSignals(True)
        for k in range(self.surface_list.count()):
            self.surface_list.item(k).setCheckState(
                Qt.CheckState.Checked if state.reliable[k]
                else Qt.CheckState.Unchecked)
        self.surface_list.blockSignals(False)

    def _on_item_changed(self, item):
        if self._updating_surface_list or self.pack is None:
            return
        # Qt can deliver deferred itemChanged events from list construction
        # before the inherited canvas has created its line items.  Those are
        # presentation-only changes, not a user reliability decision.
        if len(self.canvas._surface_items) < len(self.pack.names):
            return
        k = self.surface_list.row(item)
        if not 0 <= k < len(self.pack.names):
            return
        state = self.pack.states[self.i]
        reliable = item.checkState() == Qt.CheckState.Checked
        if state.reliable[k] != reliable:
            state.push_undo()
            state.reliable[k] = reliable
            if state.verdict is None:
                state.verdict = "corrected"
        self.redraw_surfaces()
        self.update_labels()

    def redraw_surfaces(self):
        if self.pack is None:
            return
        state = self.pack.states[self.i]
        confidence = self.pack.confidence[self.i]
        for k in range(len(self.pack.names)):
            shown = not self.only_active.isChecked() or k == self.s
            weak = np.isfinite(confidence[k]) & (confidence[k] < legacy.CONF_FLOOR)
            self.canvas.set_surface(
                k, state.current[k], legacy.SURFACE_COLOURS[k], active=(k == self.s),
                shown=shown, weak=weak)
            # Keep an unreliable line on-screen for context without making it
            # look equally trusted.  The warning segment remains visible when
            # it is the active boundary.
            alpha = 1.0 if state.reliable[k] else 0.28
            self.canvas._surface_items[k].setOpacity(alpha if not k == self.s else max(alpha, 0.50))
        self.redraw_local_marks()

    def redraw_local_marks(self):
        """Show the active boundary's local state, and only its own."""
        if self.pack is None:
            return
        state = self.pack.states[self.i]
        record = {
            "surfaces": state.current,
            "surface_visible": state.visible,
            "surface_reliable": state.reliable,
            "local_visibility": state.local["local_visibility"],
            "local_reliability": state.local["local_reliability"],
        }
        code = P.provenance_code(
            state.local["local_drawn"], state.local["local_taper"],
            state.local["local_displaced"], state.local["local_reviewed"])
        self.canvas.set_local_marks(
            state.current[self.s],
            P.record_visibility(record)[self.s],
            P.record_reliability(record)[self.s],
            code[self.s])

    # -- local marks ----------------------------------------------------
    def on_local_marked(self, x0: float, x1: float, action: str):
        """Apply one local gesture to the ACTIVE boundary only.

        Nothing here touches any other boundary, and nothing here touches the
        whole-column exclusion mask.  That separation is the entire point: a
        lesion that hides the outer RPE edge through its centre must not take
        the ILM in the same columns down with it.
        """
        if self.pack is None or action not in self.LOCAL_ACTIONS:
            return
        state = self.pack.states[self.i]
        n = state.current.shape[1]
        c0 = int(np.clip(round(x0), 0, n - 1))
        c1 = int(np.clip(round(x1), 0, n - 1))
        if c1 < c0:
            return
        span = slice(c0, c1 + 1)
        state.push_undo()
        if action == "not_visible":
            state.local["local_visibility"][self.s, span] = P.MARK_NO
        elif action == "visible":
            state.local["local_visibility"][self.s, span] = P.MARK_YES
        elif action == "unreliable":
            state.local["local_reliability"][self.s, span] = P.MARK_NO
        elif action == "reliable":
            state.local["local_reliability"][self.s, span] = P.MARK_YES
        elif action == "reviewed":
            # An intentional "I looked and the automatic line is right here".
            # It records review, never drawing: it must stay distinguishable
            # from a stroke and must not become a boundary-position target.
            state.local["local_reviewed"][self.s, span] = True
            state.local["local_visibility"][self.s, span] = P.MARK_YES
            state.local["local_reliability"][self.s, span] = P.MARK_YES
        if state.verdict is None:
            state.verdict = "corrected"
        self.statusBar().showMessage(
            f"{self.pack.names[self.s]}  A-lines {c0}-{c1}: "
            f"{self.LOCAL_ACTIONS[action]}", 4000)
        self.redraw_surfaces()
        self.update_labels()

    def clear_local_marks(self):
        """``u``: active boundary back to unreviewed over the whole B-scan.

        Clears the human judgements and the explicit-review record.  It does
        not clear stroke or displacement history -- that is what ``r`` is for,
        and silently forgetting a stroke would be the one unrecoverable edit.
        """
        if self.pack is None:
            return
        state = self.pack.states[self.i]
        state.push_undo()
        state.local["local_visibility"][self.s] = P.MARK_UNKNOWN
        state.local["local_reliability"][self.s] = P.MARK_UNKNOWN
        state.local["local_reviewed"][self.s] = False
        self.redraw_surfaces()
        self.update_labels()

    # -- drawing --------------------------------------------------------
    def on_stroke(self, xs, ys):
        """Splice a stroke in, and record exactly which columns it supports.

        Stroke support is taken from the stroke itself, never from where the
        corrected line ends up relative to the automatic one: a column can
        differ by nothing because the automatic answer was already right, and
        differ by a lot because the taper moved it.
        """
        if self.pack is None:
            return
        state = self.pack.states[self.i]
        state.push_undo(self.s)
        taper = float(self.taper_spin.value())
        n = state.current.shape[1]
        drawn, tapered = L.stroke_support(n, xs, taper)

        state.current[self.s] = L.apply_stroke(
            state.current[self.s], xs, ys, taper=taper)
        before = state.current.copy()
        state.current = L.enforce_order(state.current)
        moved = np.abs(state.current - before) > 1e-6      # [8, A-line]

        local = state.local
        local["local_drawn"][self.s] |= drawn
        local["local_taper"][self.s] |= tapered
        local["local_taper"] &= ~local["local_drawn"]
        # Ordering displacement is recorded per column and for every boundary,
        # the drawn one included.  A column that was drawn earlier and has now
        # been shoved keeps its drawn history and stops being trusted: the code
        # becomes PROV_DRAWN_DISPLACED, which no consumer supervises on.
        local["local_displaced"] |= moved
        # Redrawing a column the constraint had previously shoved makes it the
        # human's again, unless this same edit moved it too.
        local["local_displaced"][self.s] &= ~(drawn & ~moved[self.s])
        # You cannot draw a boundary you cannot see; the reverse is not implied,
        # so reliability is left at whatever the human has actually said.
        local["local_visibility"][self.s, drawn] = P.MARK_YES

        state.sync_surface_flags()
        state.n_strokes += 1
        if state.verdict in (None, "accepted"):
            state.verdict = "corrected"
        self.redraw_surfaces()
        self.update_labels()
        self._sync_checkboxes()

    def revert_surface(self):
        """``r``: active boundary back to the automatic line, history cleared."""
        if self.pack is None:
            return
        state = self.pack.states[self.i]
        state.push_undo()
        state.current[self.s] = state.auto[self.s].copy()
        state.reset_local(self.s)
        state.sync_surface_flags()
        self.redraw_surfaces()
        self.update_labels()

    def toggle_reliable(self):
        if self.pack is None:
            return
        item = self.surface_list.item(self.s)
        item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked
                           else Qt.CheckState.Checked)

    def set_verdict(self, verdict: str):
        """Persist a rejection immediately and move it out of the work queue.

        A rejected B-scan is a decision that its image cannot supply a usable
        manual label.  It must survive a restart and is omitted from normal
        review navigation.  Corrected and untouched B-scans remain available.
        """
        super().set_verdict(verdict)
        if verdict == "rejected":
            self.commit_current()
            self.jump_next_unreviewed()

    def revert_all(self):
        if self.pack is None:
            return
        state = self.pack.states[self.i]
        state.push_undo()
        state.current = state.auto.copy()
        state.reset_local()
        state.sync_surface_flags()
        state.visible[:] = True
        state.reliable[:] = True
        state.excluded[:] = False
        self.canvas.set_excluded(state.excluded)
        self._sync_checkboxes()
        self.redraw_surfaces()
        self.update_labels()

    def update_labels(self):
        # ``super().update_labels`` changes every item's text.  Block the
        # list's signal while doing so; otherwise Qt feeds those changes back
        # into _on_item_changed and recursively calls this method.
        if self._updating_surface_list:
            return
        self._updating_surface_list = True
        self.surface_list.blockSignals(True)
        try:
            super().update_labels()
            if self.pack is None:
                return
            state = self.pack.states[self.i]
            record = {
                "surfaces": state.current,
                "surface_visible": state.visible,
                "surface_reliable": state.reliable,
                "local_visibility": state.local["local_visibility"],
                "local_reliability": state.local["local_reliability"],
            }
            visibility = P.record_visibility(record)
            reliability = P.record_reliability(record)
            code = P.provenance_code(
                state.local["local_drawn"], state.local["local_taper"],
                state.local["local_displaced"], state.local["local_reviewed"])
            excluded = []
            for k, name in enumerate(self.pack.names):
                item = self.surface_list.item(k)
                if not state.reliable[k]:
                    adjacent = "/".join(affected_layers(name)) or "endpoint"
                    item.setText(item.text() + f"  [excluded: {adjacent}]")
                    excluded.append(name)
                # Column counts, because "edited" alone never said how much of
                # a 512-A-line boundary a human actually stood behind.
                bits = []
                n_drawn = int((code[k] == P.PROV_DRAWN).sum())
                n_shoved = int((code[k] == P.PROV_DRAWN_DISPLACED).sum())
                n_review = int((code[k] == P.PROV_REVIEWED).sum())
                n_hidden = int((visibility[k] == P.MARK_NO).sum())
                n_weak = int((reliability[k] == P.MARK_NO).sum())
                if n_drawn:
                    bits.append(f"{n_drawn} drawn")
                if n_shoved:
                    bits.append(f"{n_shoved} drawn-then-shoved")
                if n_review:
                    bits.append(f"{n_review} reviewed")
                if n_hidden:
                    bits.append(f"{n_hidden} not identifiable")
                if n_weak:
                    bits.append(f"{n_weak} unreliable")
                if bits:
                    item.setText(item.text() + "  |  " + ", ".join(bits))
                font = item.font()
                font.setStrikeOut((not state.visible[k]) or (not state.reliable[k]))
                item.setFont(font)
            if excluded:
                self.progress.setText(
                    self.progress.text() + "<br>analysis-excluded boundaries: <b>" +
                    ", ".join(excluded) + "</b>")
            active = self.pack.names[self.s]
            unknown = int((visibility[self.s] == P.MARK_UNKNOWN).sum())
            self.progress.setText(
                self.progress.text() +
                f"<br>active <b>{active}</b>: {unknown} A-lines unreviewed "
                f"for visibility")
            role = str(self.pack.selection_role[self.i])
            if role:
                self.progress.setText(
                    self.progress.text() +
                    f"<br>CNV sampling role: <b>{role}</b>")
        finally:
            self.surface_list.blockSignals(False)
            self._updating_surface_list = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Q:
            self.toggle_reliable()
            return
        if event.key() == Qt.Key.Key_U:
            self.clear_local_marks()
            return
        if event.key() == Qt.Key.Key_H:
            QtWidgets.QMessageBox.information(self, "controls", __doc__)
            return
        super().keyPressEvent(event)


def collect_packs(target: Path) -> list[Path]:
    target = Path(target)
    return (sorted(target.glob("*_pack.npz")) or sorted(target.glob("*.npz"))
            if target.is_dir() else [target])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", default=str(DEFAULT_REVIEW_DIR))
    parser.add_argument("--labels", default=str(DEFAULT_LABEL_DIR))
    parser.add_argument("--window-title", default="OCT eight-boundary correction")
    args = parser.parse_args()
    packs = collect_packs(Path(args.target))
    if not packs:
        print(f"no review packs in {args.target}")
        return 1
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow(packs, Path(args.labels))
    window.setWindowTitle(args.window_title)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
