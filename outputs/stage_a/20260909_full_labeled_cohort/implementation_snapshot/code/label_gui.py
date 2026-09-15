#!/usr/bin/env python3
"""
Interactive surface correction for tree shrew OCT B-scans.

    conda activate octa
    python label_gui.py                                  # open the review dir
    python label_gui.py ../outputs/review/<scan>_pack.npz
    python label_gui.py ../outputs/review                # queue every pack

What this is for
----------------
The automatic cascade places twelve-ish surfaces on every B-scan of 314 scans.
Some of them are right, some are held in place by a prior and confirmed by
nothing, and the second kind is invisible to inspection -- it is smooth,
correctly ordered and sits at an anatomically sensible depth, because a prior
put it there. This window is where a human settles which is which, and the
record it writes is the only ground truth this project has.

Three things it deliberately does
---------------------------------
1. **Shows where the image did not decide.** A-lines whose `local_confidence`
   is below the floor are drawn in a warning colour on the active surface. That
   is the part worth a human's attention; the rest of the surface usually is
   not.

2. **Distinguishes "wrong" from "invisible".** Marking a surface *not visible*
   in a B-scan is not the same as correcting it, and neither is the same as
   accepting it. A boundary nobody can see has no correct answer to learn, and
   recording that is how the IPL-sublaminae question gets settled with data
   rather than argument.

3. **Measures its own cost.** Time on task and stroke count are recorded per
   B-scan. Nobody yet knows whether correcting a B-scan takes 30 seconds or
   five minutes, and that number decides whether a learned model is reachable
   at all. It is not an estimate worth guessing at.

Controls
--------
    left-drag        redraw the ACTIVE surface where you drag
    right-drag       mark this A-line range as image quality too poor to
                     measure ANY surface here (not a per-surface judgement)
    ctrl+right-drag  clear that mark over the dragged range
    e                clear every "not measurable" mark on this B-scan
    middle-drag      pan                 (also: hold space and drag)
    wheel            zoom about cursor
    [ ]              previous / next surface
    , .   or  PgUp/PgDn    previous / next B-scan (steps through everything,
                     including B-scans already given a verdict)
    n                jump to the next B-scan with NO verdict yet, skipping
                     everything already decided (a pack also opens on its
                     first undecided B-scan automatically, not index 0)
    1..9 0           jump to surface by index
    a                accept this B-scan (automatic surfaces were right)
    x                reject it (unusable image -- excluded from training)
    v                toggle "can see this surface" for the active surface
    r                revert the active surface to the automatic result
    R                revert the whole B-scan
    ctrl+z / ctrl+y  undo / redo
    ctrl+s           save now (navigating away also saves)
    f                fit to window
    h                help
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from octa import labels as L                                       # noqa: E402
from octa.segment import SURFACE_NAMES, CASCADE_VERSION            # noqa: E402

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:                                                # pragma: no cover
    print("PySide6 is not installed in this environment.\n"
          "  conda activate octa && pip install PySide6\n"
          "`review_surfaces.py pack` and `refit` do not need it.")
    raise SystemExit(1)

Qt = QtCore.Qt

DEFAULT_REVIEW_DIR = Path("../outputs/review")
DEFAULT_LABEL_DIR = Path("../outputs/labels")

# Matches qc_vs_reference.CONF_FLOOR. Below this the chosen depth was no better
# than its local neighbourhood and the prior is holding the surface up.
CONF_FLOOR = 0.5

# Distinct at a glance and colour-blind-survivable, ordered so that adjacent
# surfaces never share a hue -- adjacent confusion is the expensive kind here.
SURFACE_COLOURS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe",
    "#008080", "#e6beff",
]
UNSUPPORTED_COLOUR = "#ff2d2d"


# ==========================================================================
# model
# ==========================================================================

class BscanState:
    """Everything mutable about one B-scan under review."""

    def __init__(self, auto: np.ndarray, n_surf: int):
        self.auto = auto.astype(float)
        self.current = auto.astype(float).copy()
        self.edited = np.zeros(n_surf, dtype=bool)
        # Moved by the ordering constraint to make room for someone else's
        # edit, not drawn by anyone. Not a label -- see octa/labels.py.
        self.displaced = np.zeros(n_surf, dtype=bool)
        self.visible = np.ones(n_surf, dtype=bool)      # "can the human see it"
        # Per-A-line, not per-surface: "the image itself is unusable here,
        # whichever surface you're looking for." Independent of `visible`,
        # which is one surface at a time.
        self.excluded = np.zeros(auto.shape[1], dtype=bool)
        self.verdict: str | None = None
        self.n_strokes = 0
        self.seconds = 0.0
        self.notes = ""
        self._undo: list[tuple] = []
        self._redo: list[tuple] = []

    # -- undo/redo -------------------------------------------------------
    #
    # Snapshots are of the whole stack, not just the surface being drawn on.
    # One stroke can move several surfaces, because the ordering constraint
    # pushes deeper ones out of the way, and an undo that restored only the
    # drawn surface would leave the others shoved -- a state the user never
    # created and cannot get out of.
    def _snapshot(self):
        return (self.current.copy(), self.edited.copy(), self.displaced.copy(),
                self.excluded.copy())

    def _restore(self, snap):
        self.current, self.edited, self.displaced, self.excluded = (
            snap[0].copy(), snap[1].copy(), snap[2].copy(), snap[3].copy())

    def push_undo(self, s: int = -1):
        self._undo.append(self._snapshot())
        self._redo.clear()
        if len(self._undo) > 200:
            self._undo.pop(0)

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        return True

    @property
    def dirty(self) -> bool:
        return bool(self.edited.any()) or self.verdict is not None


class Pack:
    """One review pack on disk, plus the review state of its B-scans."""

    def __init__(self, path: Path, label_dir: Path):
        self.path = Path(path)
        d = np.load(self.path, allow_pickle=False)
        names = [str(x) for x in d["surface_names"]]
        surfaces = d["surfaces"].astype(float)
        conf = (d["confidence"].astype(np.float32) if "confidence" in d.files
                else np.full(surfaces.shape, np.nan, np.float32))

        # A pack written before the IPL sublaminae were retired carries every
        # surface the cascade still defines plus the two it dropped. Score it on
        # the shared ones rather than refusing it -- but never silently invent a
        # surface that is missing, which would mean the pack predates the
        # reference-based priors and its inner-retina labels are wrong by one
        # landmark all the way down.
        missing = [n for n in SURFACE_NAMES if n not in names]
        if missing:
            raise ValueError(
                f"{self.path.name} is missing {', '.join(missing)}, which the "
                f"current cascade defines.\nIt predates the reference-based "
                f"priors; re-pack it with review_surfaces.py.")
        self.retired = [n for n in names if n not in SURFACE_NAMES]
        keep = [names.index(n) for n in SURFACE_NAMES]
        surfaces, conf = surfaces[:, keep, :], conf[:, keep, :]

        self.names = list(SURFACE_NAMES)
        self.images = d["images"].astype(np.float32)
        self.surfaces = surfaces
        self.confidence = conf
        self.shadow = (d["shadow"].astype(bool) if "shadow" in d.files
                       else np.zeros(self.images.shape[::2], bool))
        self.bscan_index = d["bscan_index"].astype(int)
        self.is_control = (d["is_control"].astype(bool) if "is_control" in d.files
                           else np.zeros(len(self.bscan_index), bool))
        self.suspect = (d["suspect_score"].astype(float)
                        if "suspect_score" in d.files
                        else np.full(len(self.bscan_index), np.nan))
        self.scan_id = str(d["scan_id"][0])
        self.px_um = float(d["px_um"][0])
        self.label_dir = Path(label_dir)

        self.states = [BscanState(self.surfaces[i], len(self.names))
                       for i in range(self.images.shape[0])]
        self._load_existing()

    def _load_existing(self):
        """Re-open a part-finished pack where it was left."""
        self.n_preloaded = 0
        for i, b in enumerate(self.bscan_index):
            p = L.label_path(self.label_dir, self.scan_id, int(b))
            if not p.exists():
                continue
            try:
                r = L.load_label(p)
            except Exception:                                   # noqa: BLE001
                continue
            if r["surface_names"] != self.names:
                continue
            st = self.states[i]
            st.current = r["surfaces"].astype(float)
            st.edited = np.asarray(r["surface_edited"], bool)
            st.displaced = np.asarray(r["surface_displaced"], bool)
            st.visible = np.asarray(r["surface_visible"], bool)
            st.excluded = np.asarray(r["region_excluded"], bool)
            st.verdict = r["verdict"]
            st.seconds = float(r.get("seconds_active") or 0.0)
            st.n_strokes = max(int(r.get("n_strokes") or 0), 0)
            st.notes = str(r.get("notes", ""))
            self.n_preloaded += 1

    @property
    def n(self) -> int:
        return self.images.shape[0]

    def save(self, i: int) -> Path | None:
        st = self.states[i]
        if st.verdict is None:
            return None
        return L.save_label(
            self.label_dir, scan_id=self.scan_id, bscan=int(self.bscan_index[i]),
            verdict=st.verdict, surfaces=st.current, auto_surfaces=st.auto,
            surface_names=self.names, surface_edited=st.edited,
            surface_displaced=st.displaced,
            surface_visible=st.visible, region_excluded=st.excluded,
            px_um=self.px_um,
            cascade_version=CASCADE_VERSION, seconds_active=st.seconds,
            n_strokes=st.n_strokes, is_control=bool(self.is_control[i]),
            labeller=os.environ.get("USERNAME") or os.environ.get("USER") or "",
            source_pack=self.path.name, notes=st.notes)


# ==========================================================================
# canvas
# ==========================================================================

def to_qimage(img: np.ndarray, lo_pct: float, hi_pct: float) -> QtGui.QImage:
    """Percentile-stretch a dB B-scan into an 8-bit greyscale QImage."""
    finite = img[np.isfinite(img)]
    if finite.size == 0:
        finite = np.zeros(1, np.float32)
    lo, hi = np.percentile(finite, [lo_pct, hi_pct])
    if hi <= lo:
        hi = lo + 1.0
    a = np.clip((img - lo) / (hi - lo), 0, 1)
    a = np.ascontiguousarray((a * 255).astype(np.uint8))
    h, w = a.shape
    # copy(): QImage does not take ownership of the buffer, and `a` is local.
    return QtGui.QImage(a.data, w, h, w, QtGui.QImage.Format.Format_Grayscale8).copy()


class Canvas(QtWidgets.QGraphicsView):
    strokeFinished = QtCore.Signal(object, object)      # xs, ys
    cursorMoved = QtCore.Signal(float, float)
    regionMarked = QtCore.Signal(float, float, bool)    # x0, x1, exclude

    def __init__(self):
        super().__init__()
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(QtGui.QColor("#101014"))
        self.setMouseTracking(True)

        self._pix = self.scene().addPixmap(QtGui.QPixmap())
        self._pix.setZValue(0)
        self._surface_items: list[QtWidgets.QGraphicsPathItem] = []
        self._weak_items: list[QtWidgets.QGraphicsPathItem] = []
        self._stroke_item = self.scene().addPath(QtGui.QPainterPath())
        self._stroke_item.setZValue(50)
        pen = QtGui.QPen(QtGui.QColor("#ffffff"), 2.0)
        pen.setCosmetic(True)
        self._stroke_item.setPen(pen)

        # Committed "image is unusable here" regions: a translucent band
        # spanning the full depth of the image, behind the surfaces but in
        # front of the pixel data.
        self._region_item = self.scene().addPath(QtGui.QPainterPath())
        self._region_item.setZValue(5)
        self._region_item.setPen(QtGui.QPen(Qt.PenStyle.NoPen))
        self._region_item.setBrush(QtGui.QColor(200, 30, 30, 70))
        # The in-progress drag, styled differently so "about to mark" is never
        # confused with "already marked".
        self._region_preview = self.scene().addPath(QtGui.QPainterPath())
        self._region_preview.setZValue(6)
        prev_pen = QtGui.QPen(QtGui.QColor("#ffb020"), 2.0, Qt.PenStyle.DashLine)
        prev_pen.setCosmetic(True)
        self._region_preview.setPen(prev_pen)
        self._region_preview.setBrush(QtGui.QColor(255, 176, 32, 40))

        self._drawing = False
        self._space = False
        self._xs: list[float] = []
        self._ys: list[float] = []

        self._region_dragging = False
        self._region_clear = False
        self._region_x0 = 0.0
        self._n_depth = 1

    # -- rendering -------------------------------------------------------
    def set_image(self, qimg: QtGui.QImage):
        self._pix.setPixmap(QtGui.QPixmap.fromImage(qimg))
        self.scene().setSceneRect(QtCore.QRectF(qimg.rect()))
        self._n_depth = qimg.height()

    def set_excluded(self, mask: np.ndarray):
        """Redraw the committed exclusion bands from a per-A-line bool mask."""
        path = QtGui.QPainterPath()
        n = mask.size
        i = 0
        while i < n:
            if not mask[i]:
                i += 1
                continue
            j = i
            while j < n and mask[j]:
                j += 1
            path.addRect(i - 0.5, 0, (j - i), self._n_depth)
            i = j
        self._region_item.setPath(path)

    def ensure_surface_items(self, n: int, colours):
        while len(self._surface_items) < n:
            it = self.scene().addPath(QtGui.QPainterPath())
            it.setZValue(10)
            self._surface_items.append(it)
            wk = self.scene().addPath(QtGui.QPainterPath())
            wk.setZValue(20)
            self._weak_items.append(wk)
        for k, it in enumerate(self._surface_items):
            it.setVisible(k < n)
            self._weak_items[k].setVisible(k < n)

    def set_surface(self, k: int, y: np.ndarray, colour: str, active: bool,
                    shown: bool, weak: np.ndarray | None):
        item, weak_item = self._surface_items[k], self._weak_items[k]
        if not shown:
            item.setVisible(False)
            weak_item.setVisible(False)
            return
        item.setVisible(True)

        path = QtGui.QPainterPath()
        x = np.arange(y.size, dtype=float)
        ok = np.isfinite(y)
        started = False
        for i in np.flatnonzero(ok):
            if not started:
                path.moveTo(x[i], y[i])
                started = True
            else:
                path.lineTo(x[i], y[i])
        pen = QtGui.QPen(QtGui.QColor(colour), 2.6 if active else 1.2)
        pen.setCosmetic(True)
        item.setPen(pen)
        item.setPath(path)
        item.setOpacity(1.0 if active else 0.65)

        # Unsupported stretches, drawn only for the active surface: the whole
        # point of the window is to send attention to these, and painting them
        # on every surface at once turns the display into noise.
        wpath = QtGui.QPainterPath()
        if active and weak is not None and weak.any():
            run = None
            for i in range(y.size):
                bad = bool(weak[i]) and ok[i]
                if bad and run is None:
                    run = i
                    wpath.moveTo(x[i], y[i])
                elif bad:
                    wpath.lineTo(x[i], y[i])
                elif run is not None:
                    run = None
        wpen = QtGui.QPen(QtGui.QColor(UNSUPPORTED_COLOUR), 5.0)
        wpen.setCosmetic(True)
        wpen.setCapStyle(Qt.PenCapStyle.RoundCap)
        weak_item.setPen(wpen)
        weak_item.setPath(wpath)
        weak_item.setOpacity(0.55)
        weak_item.setVisible(active)

    # -- interaction -----------------------------------------------------
    def wheelEvent(self, ev):
        f = 1.0015 ** ev.angleDelta().y()
        self.scale(f, f)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.MiddleButton or self._space:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
            fake = QtGui.QMouseEvent(
                ev.type(), ev.position(), ev.globalPosition(),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                ev.modifiers())
            super().mousePressEvent(fake)
            return
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._xs, self._ys = [], []
            self._append(ev)
            return
        if ev.button() == Qt.MouseButton.RightButton:
            self._region_dragging = True
            self._region_clear = bool(
                ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
            p = self.mapToScene(ev.position().toPoint())
            self._region_x0 = p.x()
            self._draw_region_preview(p.x())
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        p = self.mapToScene(ev.position().toPoint())
        self.cursorMoved.emit(p.x(), p.y())
        if self._drawing:
            self._append(ev)
            return
        if self._region_dragging:
            self._draw_region_preview(p.x())
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._drawing and ev.button() == Qt.MouseButton.LeftButton:
            self._drawing = False
            if self._xs:
                self.strokeFinished.emit(np.array(self._xs), np.array(self._ys))
            self._xs, self._ys = [], []
            self._stroke_item.setPath(QtGui.QPainterPath())
            return
        if self._region_dragging and ev.button() == Qt.MouseButton.RightButton:
            self._region_dragging = False
            p = self.mapToScene(ev.position().toPoint())
            x0, x1 = sorted((self._region_x0, p.x()))
            self._region_preview.setPath(QtGui.QPainterPath())
            if x1 - x0 > 0.5:
                self.regionMarked.emit(x0, x1, not self._region_clear)
            return
        super().mouseReleaseEvent(ev)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)

    def _draw_region_preview(self, x1: float):
        x0, x1 = sorted((self._region_x0, x1))
        path = QtGui.QPainterPath()
        path.addRect(x0, 0, max(x1 - x0, 0.5), self._n_depth)
        self._region_preview.setPath(path)

    def _append(self, ev):
        p = self.mapToScene(ev.position().toPoint())
        self._xs.append(p.x())
        self._ys.append(p.y())
        path = QtGui.QPainterPath()
        path.moveTo(self._xs[0], self._ys[0])
        for x, y in zip(self._xs[1:], self._ys[1:]):
            path.lineTo(x, y)
        self._stroke_item.setPath(path)

    def set_space(self, down: bool):
        self._space = down
        self.setCursor(Qt.CursorShape.OpenHandCursor if down
                       else Qt.CursorShape.CrossCursor)

    def fit(self):
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(),
                           Qt.AspectRatioMode.KeepAspectRatio)


# ==========================================================================
# main window
# ==========================================================================

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, packs: list[Path], label_dir: Path):
        super().__init__()
        self.label_dir = Path(label_dir)
        self.label_dir.mkdir(parents=True, exist_ok=True)
        self.pack_paths = packs
        self.pack: Pack | None = None
        self.pi = -1
        self.i = 0
        self.s = 0
        self._t0 = time.monotonic()
        self._focused = True

        self.canvas = Canvas()
        self.canvas.strokeFinished.connect(self.on_stroke)
        self.canvas.cursorMoved.connect(self.on_cursor)
        self.canvas.regionMarked.connect(self.on_region_marked)
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setCentralWidget(self.canvas)

        self._build_side_panel()
        self._build_status()
        self.resize(1500, 900)
        self.setWindowTitle("OCT surface correction")
        self.load_pack(0)

    # -- ui construction -------------------------------------------------
    def _build_side_panel(self):
        dock = QtWidgets.QDockWidget("surfaces", self)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)

        self.surface_list = QtWidgets.QListWidget()
        self.surface_list.setAlternatingRowColors(True)
        self.surface_list.currentRowChanged.connect(self.set_surface)
        self.surface_list.itemChanged.connect(self._on_item_changed)
        v.addWidget(self.surface_list, 3)

        box = QtWidgets.QGroupBox("this B-scan")
        g = QtWidgets.QVBoxLayout(box)
        self.btn_accept = QtWidgets.QPushButton("accept  (a)")
        self.btn_reject = QtWidgets.QPushButton("reject  (x)")
        self.btn_revert = QtWidgets.QPushButton("revert all  (shift+R)")
        self.btn_accept.clicked.connect(lambda: self.set_verdict("accepted"))
        self.btn_reject.clicked.connect(lambda: self.set_verdict("rejected"))
        self.btn_revert.clicked.connect(self.revert_all)
        for b in (self.btn_accept, self.btn_reject, self.btn_revert):
            g.addWidget(b)
        self.verdict_label = QtWidgets.QLabel("verdict: unreviewed")
        self.verdict_label.setStyleSheet("font-weight: bold;")
        g.addWidget(self.verdict_label)
        v.addWidget(box)

        box2 = QtWidgets.QGroupBox("display")
        g2 = QtWidgets.QFormLayout(box2)
        self.lo_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.lo_slider.setRange(0, 50)
        self.lo_slider.setValue(2)
        self.hi_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.hi_slider.setRange(50, 100)
        self.hi_slider.setValue(100)
        for sl in (self.lo_slider, self.hi_slider):
            sl.valueChanged.connect(self.redraw_image)
        g2.addRow("black %", self.lo_slider)
        g2.addRow("white %", self.hi_slider)
        self.taper_spin = QtWidgets.QSpinBox()
        self.taper_spin.setRange(0, 200)
        self.taper_spin.setValue(30)
        self.taper_spin.setToolTip(
            "How many A-lines a correction fades out over, beyond the ends of "
            "the stroke.\nToo small and a correction becomes a spike no DP "
            "surface could produce;\ntoo large and one stroke silently "
            "rewrites the whole B-scan.")
        g2.addRow("taper (A-lines)", self.taper_spin)
        self.only_active = QtWidgets.QCheckBox("show active surface only")
        self.only_active.stateChanged.connect(self.redraw_surfaces)
        g2.addRow(self.only_active)
        v.addWidget(box2)

        self.progress = QtWidgets.QLabel("")
        self.progress.setWordWrap(True)
        v.addWidget(self.progress)
        v.addStretch(1)

        dock.setWidget(w)
        dock.setMinimumWidth(310)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _build_status(self):
        sb = self.statusBar()
        self.pos_label = QtWidgets.QLabel("")
        self.info_label = QtWidgets.QLabel("")
        sb.addWidget(self.info_label, 1)
        sb.addPermanentWidget(self.pos_label)

    # -- pack / bscan navigation ----------------------------------------
    def load_pack(self, pi: int):
        if not (0 <= pi < len(self.pack_paths)):
            return
        if self.pack is not None:
            self.commit_current()
        try:
            self.pack = Pack(self.pack_paths[pi], self.label_dir)
        except Exception as e:                                   # noqa: BLE001
            QtWidgets.QMessageBox.critical(
                self, "cannot open pack",
                f"{self.pack_paths[pi].name}\n\n{e}")
            return
        self.pi = pi
        self.s = 0
        if self.pack.retired:
            self.statusBar().showMessage(
                f"ignoring retired surfaces: {', '.join(self.pack.retired)}", 8000)
        self._rebuild_surface_list()
        self.canvas.ensure_surface_items(len(self.pack.names), SURFACE_COLOURS)
        # Land on the first B-scan nobody has ruled on yet, not always index 0.
        # Reopening a pack that is half done should not require paging past
        # everything already decided just to reach the next real work.
        start = self._first_unreviewed(self.pack)
        self.i = start if start is not None else 0
        self.show_bscan(self.i, fit=True)

    def _rebuild_surface_list(self):
        self.surface_list.blockSignals(True)
        self.surface_list.clear()
        for k, n in enumerate(self.pack.names):
            it = QtWidgets.QListWidgetItem(n)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            it.setForeground(QtGui.QColor(SURFACE_COLOURS[k % len(SURFACE_COLOURS)]))
            f = it.font()
            f.setBold(k == self.s)
            it.setFont(f)
            self.surface_list.addItem(it)
        self.surface_list.setCurrentRow(self.s)
        self.surface_list.blockSignals(False)

    def commit_current(self):
        """Bank time on task, then write the label if there is a verdict."""
        if self.pack is None:
            return
        self._bank_time()
        st = self.pack.states[self.i]
        if st.verdict is None and st.edited.any():
            st.verdict = "corrected"
        self.pack.save(self.i)

    def _bank_time(self):
        now = time.monotonic()
        if self.pack is not None and self._focused:
            self.pack.states[self.i].seconds += now - self._t0
        self._t0 = now

    def show_bscan(self, i: int, fit: bool = False):
        if self.pack is None:
            return
        i = int(np.clip(i, 0, self.pack.n - 1))
        if i != self.i:
            self.commit_current()
        self._t0 = time.monotonic()
        self.i = i
        self.redraw_image()
        self.canvas.set_excluded(self.pack.states[i].excluded)
        self.redraw_surfaces()
        self._sync_checkboxes()
        self.update_labels()
        if fit:
            self.canvas.fit()

    @staticmethod
    def _first_unreviewed(pack: "Pack") -> int | None:
        """Index of the first B-scan in `pack` with no verdict yet, or None if
        every one of them has already been decided."""
        for i, st in enumerate(pack.states):
            if st.verdict is None:
                return i
        return None

    def jump_next_unreviewed(self):
        """
        Skip forward to the next B-scan nobody has ruled on yet: later in this
        pack first, then into subsequent packs.

        This is the deliberate-skip counterpart to landing on the first
        unreviewed B-scan when a pack opens -- for stepping past something you
        want to leave for later without marking it, not for hiding finished
        work. `,` and `.` still walk one at a time through everything,
        including B-scans already given a verdict, so nothing already decided
        becomes unreachable.
        """
        if self.pack is None:
            return
        for i in range(self.i + 1, self.pack.n):
            if self.pack.states[i].verdict is None:
                self.show_bscan(i)
                return
        pi = self.pi + 1
        while pi < len(self.pack_paths):
            self.load_pack(pi)
            if self.pack is not None and self._first_unreviewed(self.pack) is not None:
                return
            pi += 1
        self.statusBar().showMessage(
            "no unreviewed B-scans left in the queue", 5000)

    def next_bscan(self, step: int):
        if self.pack is None:
            return
        j = self.i + step
        if j >= self.pack.n and self.pi + 1 < len(self.pack_paths):
            self.commit_current()
            self.load_pack(self.pi + 1)
            return
        if j < 0 and self.pi > 0:
            self.commit_current()
            self.load_pack(self.pi - 1)
            return
        self.show_bscan(j)

    # -- drawing ---------------------------------------------------------
    def redraw_image(self):
        if self.pack is None:
            return
        img = self.pack.images[self.i]
        self.canvas.set_image(to_qimage(img, self.lo_slider.value(),
                                        self.hi_slider.value()))

    def redraw_surfaces(self):
        if self.pack is None:
            return
        st = self.pack.states[self.i]
        conf = self.pack.confidence[self.i]
        for k in range(len(self.pack.names)):
            item = self.surface_list.item(k)
            shown = (item.checkState() == Qt.CheckState.Checked
                     and (not self.only_active.isChecked() or k == self.s))
            c = conf[k]
            weak = np.isfinite(c) & (c < CONF_FLOOR)
            self.canvas.set_surface(
                k, st.current[k], SURFACE_COLOURS[k % len(SURFACE_COLOURS)],
                active=(k == self.s), shown=shown, weak=weak)

    def on_stroke(self, xs, ys):
        if self.pack is None:
            return
        st = self.pack.states[self.i]
        st.push_undo(self.s)
        st.current[self.s] = L.apply_stroke(
            st.current[self.s], xs, ys, taper=float(self.taper_spin.value()))

        # Ordering can shove surfaces nobody drew. Catch that here, where the
        # cause is still known, rather than inferring it later from the arrays.
        before = st.current.copy()
        st.current = L.enforce_order(st.current)
        moved = np.any(np.abs(st.current - before) > 1e-6, axis=1)
        moved[self.s] = False
        st.displaced |= moved

        st.edited[self.s] = True
        st.displaced[self.s] = False
        st.n_strokes += 1
        if st.verdict in (None, "accepted"):
            st.verdict = "corrected"
        self.redraw_surfaces()
        self.update_labels()

    def on_region_marked(self, x0: float, x1: float, exclude: bool):
        """Right-drag: mark (or, with ctrl, clear) an A-line range as image
        quality being too poor for any surface to mean anything there."""
        if self.pack is None:
            return
        st = self.pack.states[self.i]
        n = st.excluded.size
        c0 = int(np.clip(round(x0), 0, n - 1))
        c1 = int(np.clip(round(x1), 0, n - 1))
        if c1 < c0:
            return
        st.push_undo()
        st.excluded[c0:c1 + 1] = exclude
        if st.verdict is None:
            st.verdict = "corrected"
        self.canvas.set_excluded(st.excluded)
        self.update_labels()

    def clear_excluded(self):
        if self.pack is None:
            return
        st = self.pack.states[self.i]
        if not st.excluded.any():
            return
        st.push_undo()
        st.excluded[:] = False
        self.canvas.set_excluded(st.excluded)
        self.update_labels()

    # -- verdicts and flags ---------------------------------------------
    def set_verdict(self, v: str):
        if self.pack is None:
            return
        self.pack.states[self.i].verdict = v
        self.update_labels()

    def set_surface(self, k: int):
        if self.pack is None or not (0 <= k < len(self.pack.names)):
            return
        self.s = k
        for j in range(self.surface_list.count()):
            it = self.surface_list.item(j)
            f = it.font()
            f.setBold(j == k)
            it.setFont(f)
        self.redraw_surfaces()
        self.update_labels()

    def _on_item_changed(self, _item):
        self.redraw_surfaces()

    def toggle_visible(self):
        """Mark whether this boundary is actually discernible in this B-scan."""
        if self.pack is None:
            return
        st = self.pack.states[self.i]
        st.visible[self.s] = not st.visible[self.s]
        if st.verdict is None:
            st.verdict = "corrected"
        self.update_labels()

    def revert_surface(self):
        if self.pack is None:
            return
        st = self.pack.states[self.i]
        st.push_undo()
        st.current[self.s] = st.auto[self.s].copy()
        st.edited[self.s] = False
        st.displaced[self.s] = False
        self.redraw_surfaces()
        self.update_labels()

    def revert_all(self):
        if self.pack is None:
            return
        st = self.pack.states[self.i]
        st.push_undo()
        st.current = st.auto.copy()
        st.edited[:] = False
        st.displaced[:] = False
        st.visible[:] = True
        self.redraw_surfaces()
        self.update_labels()

    def _sync_checkboxes(self):
        self.surface_list.blockSignals(True)
        for k in range(self.surface_list.count()):
            self.surface_list.item(k).setCheckState(Qt.CheckState.Checked)
        self.surface_list.blockSignals(False)

    # -- labels ----------------------------------------------------------
    def update_labels(self):
        if self.pack is None:
            return
        p, st = self.pack, self.pack.states[self.i]
        conf = p.confidence[self.i]

        for k, n in enumerate(p.names):
            it = self.surface_list.item(k)
            c = conf[k]
            frac = float(np.mean(c < CONF_FLOOR)) if np.isfinite(c).any() else np.nan
            bits = [n]
            if not st.visible[k]:
                bits.append("[not visible]")
            if st.edited[k]:
                d = st.current[k] - st.auto[k]
                bits.append(f"edited {np.sqrt(np.mean(d ** 2)) * p.px_um:.1f}um")
            elif st.displaced[k]:
                d = st.current[k] - st.auto[k]
                bits.append(f"displaced {np.sqrt(np.mean(d ** 2)) * p.px_um:.1f}um")
            if np.isfinite(frac):
                bits.append(f"{frac * 100:.0f}% unsup")
            it.setText("  ".join(bits))
            f = it.font()
            f.setStrikeOut(not st.visible[k])
            it.setFont(f)

        v = st.verdict or "unreviewed"
        self.verdict_label.setText(f"verdict: {v}")
        self.verdict_label.setStyleSheet(
            "font-weight: bold; color: " +
            {"accepted": "#3cb44b", "corrected": "#4363d8",
             "rejected": "#e6194b"}.get(v, "#999999"))

        ctrl = "  [CONTROL]" if p.is_control[self.i] else ""
        sus = ("" if not np.isfinite(p.suspect[self.i])
               else f"  suspect {p.suspect[self.i]:.2f}")
        self.info_label.setText(
            f"{p.scan_id}   B-scan {p.bscan_index[self.i]}   "
            f"({self.i + 1}/{p.n}){ctrl}{sus}   active: {p.names[self.s]}   "
            f"pack {self.pi + 1}/{len(self.pack_paths)}")

        done = sum(1 for s in p.states if s.verdict is not None)
        secs = [s.seconds for s in p.states if s.verdict is not None and s.seconds > 0]
        med = f"{np.median(secs):.0f}s" if secs else "-"
        tot = f"{sum(s.seconds for s in p.states) / 60:.1f} min"
        excl_frac = float(st.excluded.mean())
        excl_line = (f"marked not-measurable: <b>{excl_frac * 100:.0f}%</b> "
                    f"of A-lines<br>" if excl_frac > 0 else "")
        self.progress.setText(
            f"<b>{done}/{p.n}</b> B-scans reviewed in this pack<br>"
            f"median time each: <b>{med}</b><br>"
            f"time in this pack: {tot}<br>"
            f"strokes here: {st.n_strokes}<br>"
            f"{excl_line}"
            f"labels dir: {self.label_dir}")

    def on_cursor(self, x, y):
        if self.pack is None:
            return
        px = self.pack.px_um
        st = self.pack.states[self.i]
        n_col = st.current.shape[1]
        j = int(np.clip(round(x), 0, n_col - 1))
        d = y - st.current[0][j]
        self.pos_label.setText(
            f"A-line {j}   depth {y:.0f} px   {d * px:+.0f} um below ILM")

    # -- events ----------------------------------------------------------
    def keyPressEvent(self, ev):
        k = ev.key()
        mod = ev.modifiers()
        ctrl = bool(mod & Qt.KeyboardModifier.ControlModifier)
        if k == Qt.Key.Key_Space:
            self.canvas.set_space(True)
        elif ctrl and k == Qt.Key.Key_Z:
            if self.pack and self.pack.states[self.i].undo():
                self.canvas.set_excluded(self.pack.states[self.i].excluded)
                self.redraw_surfaces(); self.update_labels()
        elif ctrl and k == Qt.Key.Key_Y:
            if self.pack and self.pack.states[self.i].redo():
                self.canvas.set_excluded(self.pack.states[self.i].excluded)
                self.redraw_surfaces(); self.update_labels()
        elif ctrl and k == Qt.Key.Key_S:
            self.commit_current()
            self.statusBar().showMessage("saved", 2000)
        elif k == Qt.Key.Key_BracketRight:
            self.surface_list.setCurrentRow((self.s + 1) % len(self.pack.names))
        elif k == Qt.Key.Key_BracketLeft:
            self.surface_list.setCurrentRow((self.s - 1) % len(self.pack.names))
        elif k in (Qt.Key.Key_Period, Qt.Key.Key_PageDown):
            self.next_bscan(+1)
        elif k in (Qt.Key.Key_Comma, Qt.Key.Key_PageUp):
            self.next_bscan(-1)
        elif k == Qt.Key.Key_A:
            self.set_verdict("accepted")
        elif k == Qt.Key.Key_X:
            self.set_verdict("rejected")
        elif k == Qt.Key.Key_V:
            self.toggle_visible()
        elif k == Qt.Key.Key_R:
            self.revert_all() if (mod & Qt.KeyboardModifier.ShiftModifier) \
                else self.revert_surface()
        elif k == Qt.Key.Key_F:
            self.canvas.fit()
        elif k == Qt.Key.Key_E:
            self.clear_excluded()
        elif k == Qt.Key.Key_N:
            self.jump_next_unreviewed()
        elif k == Qt.Key.Key_H:
            QtWidgets.QMessageBox.information(self, "controls", __doc__)
        elif Qt.Key.Key_0 <= k <= Qt.Key.Key_9:
            idx = (k - Qt.Key.Key_0 - 1) % 10
            if idx < len(self.pack.names):
                self.surface_list.setCurrentRow(idx)
        else:
            super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key.Key_Space:
            self.canvas.set_space(False)
        super().keyReleaseEvent(ev)

    def changeEvent(self, ev):
        # Time on task must not accumulate while the window is in the
        # background, or the cost measurement this tool exists to produce is
        # just a measure of how long the app was left open.
        if ev.type() == QtCore.QEvent.Type.ActivationChange:
            self._bank_time()
            self._focused = self.isActiveWindow()
            self._t0 = time.monotonic()
        super().changeEvent(ev)

    def closeEvent(self, ev):
        self.commit_current()
        super().closeEvent(ev)


# ==========================================================================

def collect_packs(target: Path) -> list[Path]:
    target = Path(target)
    if target.is_dir():
        return sorted(target.glob("*_pack.npz")) or sorted(target.glob("*.npz"))
    return [target]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", default=str(DEFAULT_REVIEW_DIR),
                    help="a review pack .npz, or a directory of them")
    ap.add_argument("--labels", default=str(DEFAULT_LABEL_DIR))
    args = ap.parse_args()

    packs = collect_packs(Path(args.target))
    if not packs:
        print(f"no review packs in {args.target}\n"
              f"  build one first:  python review_surfaces.py pack --npz <segmented.npz>")
        return 1

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow(packs, Path(args.labels))
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
