#!/usr/bin/env python3
"""Integrated en-face annotation and automated surface-review GUI.

Run from ``code`` after activating ``octa``::

    python eight_surface/cnv_gui.py ../outputs/eight_surface/segmented

Structural and OCTA en-face panels share the native ``[B-scan, A-line]``
coordinates. Selecting a row updates the structural B-scan below and overlays
the eight automated boundaries. Double-click the B-scan (or use the side-panel
button) to open that one line in the provenance-aware manual surface editor.
That editor remains the only writer of surface labels.

CNV may be traced as a closed outline or painted. Vasculature and ONH are
painted masks. In every brush mode, left- or right-drag paints and
Ctrl+right-drag erases, matching the B-scan exclusion gesture; the brush
diameter is adjustable. Per-class review checkboxes distinguish an empty
reviewed mask from a class nobody labelled.
"""

from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from skimage.draw import disk as raster_disk
from skimage.draw import line as raster_line
from skimage.draw import polygon as raster_polygon

CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    print("PySide6 is required. Activate the octa environment first.")
    raise SystemExit(1)

from eight_surface import cnv_labels as CL  # noqa: E402
from eight_surface import labels as SL  # noqa: E402
from eight_surface.cnv_data import CnvScan, read_scan  # noqa: E402
from eight_surface.config import CASCADE_VERSION  # noqa: E402
from eight_surface.vasculature_proposals import (  # noqa: E402
    DEFAULT_PROPOSALS, has_saved_vessel_work, load_proposal)


Qt = QtCore.Qt
DEFAULT_SEGMENTED = Path("../outputs/eight_surface/segmented")
DEFAULT_LABELS = Path("../outputs/cnv_labels")
DEFAULT_SURFACE_LABELS = Path("../outputs/eight_surface/labels")
DEFAULT_LINE_REVIEW = Path("../outputs/eight_surface/enface_line_review")

SURFACE_COLOURS = (
    "#e6194b", "#f58231", "#ffe119", "#3cb44b",
    "#42d4f4", "#4363d8", "#911eb4", "#f032e6",
)
ANNOTATION_COLOURS = {
    "CNV": (255, 45, 35, 112),
    "VASCULATURE": (40, 160, 255, 104),
    "ONH": (60, 255, 105, 116),
}
BRUSH_MODES = {"cnv_brush": 0, "vasculature_brush": 1, "onh_brush": 2}


def _to_gray(image: np.ndarray, brightness: int = 0,
             contrast: int = 100) -> QtGui.QImage:
    """Return a display-only brightness/contrast rendering."""
    finite = image[np.isfinite(image)]
    if finite.size:
        lo, hi = np.percentile(finite, [1.0, 99.0])
    else:
        lo, hi = 0.0, 1.0
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((image - lo) / (hi - lo), 0, 1)
    scaled = (scaled - 0.5) * (float(contrast) / 100.0) + 0.5
    scaled += float(brightness) / 200.0
    pixels = np.ascontiguousarray((np.clip(scaled, 0, 1) * 255).astype(np.uint8))
    height, width = pixels.shape
    return QtGui.QImage(
        pixels.data, width, height, width,
        QtGui.QImage.Format.Format_Grayscale8).copy()


def _annotation_overlay(
    cnv_mask: np.ndarray,
    onh_edge_mask: np.ndarray | None = None,
    vasculature_mask: np.ndarray | None = None,
    onh_mask: np.ndarray | None = None,
) -> QtGui.QImage:
    """Return a translucent multi-class overlay; preserve legacy ONH edges."""
    shape = cnv_mask.shape
    masks = (
        np.asarray(cnv_mask, bool),
        np.zeros(shape, bool) if vasculature_mask is None else
        np.asarray(vasculature_mask, bool),
        np.zeros(shape, bool) if onh_mask is None else np.asarray(onh_mask, bool),
    )
    rgba = np.zeros((*shape, 4), dtype=np.uint8)
    rgb_sum = np.zeros((*shape, 3), dtype=np.float32)
    weight = np.zeros(shape, dtype=np.float32)
    alpha = np.zeros(shape, dtype=np.float32)
    for name, mask in zip(CL.ANNOTATION_NAMES, masks):
        colour = ANNOTATION_COLOURS[name]
        rgb_sum[mask] += np.asarray(colour[:3], dtype=np.float32)
        weight[mask] += 1.0
        alpha[mask] += colour[3]
    occupied = weight > 0
    rgba[occupied, :3] = np.clip(
        rgb_sum[occupied] / weight[occupied, None], 0, 255).astype(np.uint8)
    rgba[..., 3] = np.clip(alpha, 0, 175).astype(np.uint8)
    if onh_edge_mask is not None:
        edge = np.asarray(onh_edge_mask, bool)
        rgba[edge] = np.array([120, 255, 145, 245], dtype=np.uint8)
    rgba = np.ascontiguousarray(rgba)
    height, width, _ = rgba.shape
    return QtGui.QImage(
        rgba.data, width, height, width * 4,
        QtGui.QImage.Format.Format_RGBA8888).copy()


def _smooth_stroke(points: list[tuple[float, float]], *, closed: bool,
                   sigma_px: float = 1.8) -> np.ndarray:
    """Resample a freehand stroke and apply light circular/linear smoothing."""
    xy = np.asarray(points, dtype=float)
    if len(xy) < (3 if closed else 2):
        return xy
    walk = np.vstack((xy, xy[:1])) if closed else xy
    steps = np.hypot(np.diff(walk[:, 0]), np.diff(walk[:, 1]))
    keep = np.r_[True, steps > 0.15]
    walk = walk[keep]
    if closed and len(walk) < 4:
        return xy
    steps = np.hypot(np.diff(walk[:, 0]), np.diff(walk[:, 1]))
    distance = np.r_[0.0, np.cumsum(steps)]
    if distance[-1] < 1.0:
        return xy
    n_samples = int(np.clip(np.ceil(distance[-1]), 12 if closed else 2, 4096))
    samples = np.linspace(0, distance[-1], n_samples, endpoint=not closed)
    smooth = np.column_stack((
        np.interp(samples, distance, walk[:, 0]),
        np.interp(samples, distance, walk[:, 1]),
    ))
    return gaussian_filter1d(
        smooth, sigma=sigma_px, axis=0, mode="wrap" if closed else "nearest")


def _rasterize_edge(points: list[tuple[float, float]],
                    shape: tuple[int, int]) -> np.ndarray:
    """Rasterise a legacy open ONH edge as a one-pixel native-grid line."""
    xy = _smooth_stroke(points, closed=False)
    edge = np.zeros(shape, dtype=bool)
    if len(xy) < 2:
        return edge
    for first, second in zip(xy[:-1], xy[1:]):
        rr, cc = raster_line(
            int(np.clip(round(first[1]), 0, shape[0] - 1)),
            int(np.clip(round(first[0]), 0, shape[1] - 1)),
            int(np.clip(round(second[1]), 0, shape[0] - 1)),
            int(np.clip(round(second[0]), 0, shape[1] - 1)),
        )
        edge[rr, cc] = True
    return edge


def _brush_mask(points: list[tuple[float, float]], shape: tuple[int, int],
                diameter: int) -> np.ndarray:
    """Rasterise a round brush continuously along a freehand path."""
    result = np.zeros(shape, dtype=bool)
    if not points:
        return result
    radius = max(0.5, float(diameter) / 2.0)
    xy = np.asarray(points, dtype=float)
    samples = [xy[0]]
    spacing = max(0.5, radius * 0.45)
    for first, second in zip(xy[:-1], xy[1:]):
        distance = float(np.hypot(*(second - first)))
        count = max(1, int(np.ceil(distance / spacing)))
        samples.extend(first + (second - first) * (i / count)
                       for i in range(1, count + 1))
    for x, y in samples:
        rr, cc = raster_disk((y, x), radius=radius, shape=shape)
        result[rr, cc] = True
    return result


class EnfaceCanvas(QtWidgets.QGraphicsView):
    navigated = QtCore.Signal(int, int)
    strokeFinished = QtCore.Signal(object, str)  # [(x,y)], operation
    cursorMoved = QtCore.Signal(int, int)

    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setBackgroundBrush(QtGui.QColor("#101014"))
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setMouseTracking(True)
        self._pix = self.scene().addPixmap(QtGui.QPixmap())
        self._pix.setZValue(0)
        self._overlay = self.scene().addPixmap(QtGui.QPixmap())
        self._overlay.setZValue(5)
        self._cursor = self.scene().addPath(QtGui.QPainterPath())
        cursor_pen = QtGui.QPen(QtGui.QColor("#00ffff"), 1.2)
        cursor_pen.setCosmetic(True)
        self._cursor.setPen(cursor_pen)
        self._cursor.setZValue(10)
        self._draft = self.scene().addPath(QtGui.QPainterPath())
        self._draft.setZValue(20)
        self._brush_head = self.scene().addEllipse(QtCore.QRectF())
        brush_pen = QtGui.QPen(QtGui.QColor("#ffffff"), 1.2)
        brush_pen.setCosmetic(True)
        self._brush_head.setPen(brush_pen)
        self._brush_head.setBrush(QtGui.QColor(255, 255, 255, 28))
        self._brush_head.setZValue(25)
        self._brush_head.setVisible(False)
        self.mode = "navigate"
        self.brush_size = 18
        self.points: list[tuple[float, float]] = []
        self._drawing = False
        self._draw_button = None
        self._erase = False
        self._image: np.ndarray | None = None
        self._brightness = 0
        self._contrast = 100
        self._shape = (1, 1)

    def set_image(self, image: np.ndarray):
        self._image = np.asarray(image)
        self._render_image()

    def set_display(self, brightness: int, contrast: int):
        self._brightness = int(brightness)
        self._contrast = int(contrast)
        self._render_image()

    def _render_image(self):
        if self._image is None:
            return
        qimage = _to_gray(self._image, self._brightness, self._contrast)
        self._pix.setPixmap(QtGui.QPixmap.fromImage(qimage))
        self.scene().setSceneRect(QtCore.QRectF(qimage.rect()))
        self._shape = self._image.shape

    def set_annotations(self, cnv_mask: np.ndarray,
                        vasculature_mask: np.ndarray, onh_mask: np.ndarray,
                        onh_edge_mask: np.ndarray):
        image = _annotation_overlay(
            cnv_mask, onh_edge_mask, vasculature_mask, onh_mask)
        self._overlay.setPixmap(QtGui.QPixmap.fromImage(image))

    def set_mode(self, mode: str):
        self.mode = mode
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._brush_head.setVisible(mode in BRUSH_MODES)
        self.cancel_stroke()

    def set_brush_size(self, size: int):
        self.brush_size = int(size)

    def set_cursor(self, row: int, col: int):
        height, width = self._shape
        path = QtGui.QPainterPath()
        path.moveTo(0, row + 0.5)
        path.lineTo(width, row + 0.5)
        path.moveTo(col + 0.5, 0)
        path.lineTo(col + 0.5, height)
        self._cursor.setPath(path)

    def cancel_stroke(self):
        self._drawing = False
        self._draw_button = None
        self._erase = False
        self.points.clear()
        self._draft.setPath(QtGui.QPainterPath())

    def commit_stroke(self):
        if self.mode == "cnv_outline" and len(self.points) >= 3:
            self.strokeFinished.emit(list(self.points), "cnv_outline_add")
        elif self.mode in BRUSH_MODES and self.points:
            operation = "erase" if self._erase else "add"
            self.strokeFinished.emit(list(self.points), f"{self.mode}_{operation}")
        self.cancel_stroke()

    def _scene_pixel(self, event) -> tuple[int, int, float, float]:
        point = self.mapToScene(event.position().toPoint())
        height, width = self._shape
        col = int(np.clip(round(point.x()), 0, width - 1))
        row = int(np.clip(round(point.y()), 0, height - 1))
        return row, col, float(point.x()), float(point.y())

    def _show_brush_head(self, x: float, y: float):
        radius = self.brush_size / 2.0
        self._brush_head.setRect(x - radius, y - radius,
                                 self.brush_size, self.brush_size)

    def _append_point(self, x: float, y: float):
        if self.points and np.hypot(x - self.points[-1][0],
                                    y - self.points[-1][1]) < 0.35:
            return
        self.points.append((x, y))
        path = QtGui.QPainterPath()
        path.moveTo(*self.points[0])
        for point in self.points[1:]:
            path.lineTo(*point)
        if self.mode == "cnv_outline" and len(self.points) > 2:
            path.lineTo(*self.points[0])
        colour = "#ff7070" if self._erase else "#ffffff"
        pen = QtGui.QPen(
            QtGui.QColor(colour),
            float(self.brush_size) if self.mode in BRUSH_MODES else 2.0)
        pen.setCosmetic(self.mode not in BRUSH_MODES)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if self.mode == "cnv_outline":
            pen.setStyle(Qt.PenStyle.DashLine)
        self._draft.setPen(pen)
        self._draft.setPath(path)

    def mousePressEvent(self, event):
        row, col, x, y = self._scene_pixel(event)
        if self.mode == "navigate" and event.button() == Qt.MouseButton.LeftButton:
            self.navigated.emit(row, col)
            return
        allowed = (event.button() == Qt.MouseButton.LeftButton or
                   (self.mode in BRUSH_MODES and
                    event.button() == Qt.MouseButton.RightButton))
        if allowed and self.mode != "navigate":
            self.cancel_stroke()
            self._drawing = True
            self._draw_button = event.button()
            self._erase = bool(
                event.button() == Qt.MouseButton.RightButton and
                event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self._append_point(x, y)
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.cancel_stroke()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drawing and event.button() == self._draw_button:
            _row, _col, x, y = self._scene_pixel(event)
            self._append_point(x, y)
            self.commit_stroke()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        row, col, x, y = self._scene_pixel(event)
        self.cursorMoved.emit(row, col)
        self._show_brush_head(x, y)
        if self._drawing and self.mode != "navigate":
            self._append_point(x, y)
            return
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        factor = 1.0015 ** event.angleDelta().y()
        self.scale(factor, factor)

    def fit(self):
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(),
                           Qt.AspectRatioMode.KeepAspectRatio)


class BscanCanvas(QtWidgets.QGraphicsView):
    lineEditorRequested = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setBackgroundBrush(QtGui.QColor("#101014"))
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setToolTip(
            "Double-click to open this B-scan in the manual surface editor")
        self._pix = self.scene().addPixmap(QtGui.QPixmap())
        self._auto_items: list[QtWidgets.QGraphicsPathItem] = []
        self._manual_items: list[QtWidgets.QGraphicsPathItem] = []
        self._aline = self.scene().addLine(QtCore.QLineF())
        pen = QtGui.QPen(QtGui.QColor("#00ffff"), 1.2)
        pen.setCosmetic(True)
        self._aline.setPen(pen)
        self._aline.setZValue(20)
        self._status = self.scene().addSimpleText("")
        self._status.setBrush(QtGui.QColor("#ffffff"))
        self._status.setZValue(30)

    @staticmethod
    def _path(y: np.ndarray) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        started = False
        for x in np.flatnonzero(np.isfinite(y)):
            if not started:
                path.moveTo(float(x), float(y[x]))
                started = True
            else:
                path.lineTo(float(x), float(y[x]))
        return path

    def _ensure_surface_items(self, count: int):
        while len(self._auto_items) < count:
            auto = self.scene().addPath(QtGui.QPainterPath())
            auto.setZValue(10)
            self._auto_items.append(auto)
            manual = self.scene().addPath(QtGui.QPainterPath())
            manual.setZValue(14)
            self._manual_items.append(manual)

    def set_image(self, image: np.ndarray, aline: int, surfaces: np.ndarray,
                  manual: np.ndarray | None = None, verdict: str = "unreviewed",
                  show_surfaces: bool = True):
        qimage = _to_gray(image, 0, 115)
        self._pix.setPixmap(QtGui.QPixmap.fromImage(qimage))
        self.scene().setSceneRect(QtCore.QRectF(qimage.rect()))
        self._aline.setLine(aline + 0.5, 0, aline + 0.5, image.shape[0])
        self._ensure_surface_items(len(surfaces))
        for k, y in enumerate(surfaces):
            colour = SURFACE_COLOURS[k % len(SURFACE_COLOURS)]
            auto_pen = QtGui.QPen(
                QtGui.QColor(colour), 1.35, Qt.PenStyle.DashLine)
            auto_pen.setCosmetic(True)
            self._auto_items[k].setPen(auto_pen)
            self._auto_items[k].setPath(self._path(y))
            self._auto_items[k].setVisible(show_surfaces)
            if manual is not None:
                manual_pen = QtGui.QPen(QtGui.QColor(colour), 2.4)
                manual_pen.setCosmetic(True)
                self._manual_items[k].setPen(manual_pen)
                self._manual_items[k].setPath(self._path(manual[k]))
                self._manual_items[k].setVisible(show_surfaces)
            else:
                self._manual_items[k].setVisible(False)
        for k in range(len(surfaces), len(self._auto_items)):
            self._auto_items[k].setVisible(False)
            self._manual_items[k].setVisible(False)
        label = {
            "accepted": "accepted auto segmentation",
            "corrected": "manual correction saved (solid); auto is dashed",
            "rejected": "surface review rejected",
        }.get(verdict, "unreviewed auto segmentation - double-click to check/correct")
        self._status.setText(label)
        self._status.setBrush(QtGui.QColor({
            "accepted": "#65dc83", "corrected": "#78a8ff",
            "rejected": "#ff667a"}.get(verdict, "#ffffff")))
        self._status.setPos(8, 8)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.lineEditorRequested.emit()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        factor = 1.0015 ** event.angleDelta().y()
        self.scale(factor, factor)

    def fit(self):
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(),
                           Qt.AspectRatioMode.KeepAspectRatio)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, segmentations: list[Path], label_dir: Path,
                 surface_label_dir: Path = DEFAULT_SURFACE_LABELS,
                 line_review_dir: Path = DEFAULT_LINE_REVIEW,
                 proposals_dir: Path | None = DEFAULT_PROPOSALS,
                 start_index: int = 0):
        super().__init__()
        self.segmentations = segmentations
        self.label_dir = Path(label_dir)
        self.surface_label_dir = Path(surface_label_dir)
        self.line_review_dir = Path(line_review_dir)
        self.proposals_dir = Path(proposals_dir) if proposals_dir is not None else None
        self.vasculature_proposal_path = ""
        self.vasculature_proposal_sha256 = ""
        self.vasculature_initial_mask = np.zeros((1, 1), dtype=bool)
        self.vasculature_brush_touched = np.zeros((1, 1), dtype=bool)
        self.vasculature_new_proposal = False
        for directory in (self.label_dir, self.surface_label_dir,
                          self.line_review_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.index = -1
        self.scan: CnvScan | None = None
        self.mask = np.zeros((1, 1), dtype=bool)
        self.vasculature_mask = np.zeros((1, 1), dtype=bool)
        self.onh_mask = np.zeros((1, 1), dtype=bool)
        self.onh_edge_mask = np.zeros((1, 1), dtype=bool)
        self.reviewed_targets = np.zeros(len(CL.ANNOTATION_NAMES), dtype=bool)
        self.row = 0
        self.col = 0
        self.dirty = False
        self.undo_stack: list[tuple[np.ndarray, ...]] = []
        self.redo_stack: list[tuple[np.ndarray, ...]] = []
        self.surface_windows: dict[tuple[str, int], QtWidgets.QWidget] = {}
        self._loading_controls = False

        self.structural = EnfaceCanvas("Structural OCT")
        self.octa = EnfaceCanvas("OCTA")
        self.bscan = BscanCanvas()
        for canvas in (self.structural, self.octa):
            canvas.navigated.connect(self.navigate)
            canvas.strokeFinished.connect(self.apply_stroke)
            canvas.cursorMoved.connect(self.show_position)
        self.bscan.lineEditorRequested.connect(self.open_surface_editor)

        top = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        top.addWidget(self._panel("Structural OCT en face", self.structural))
        top.addWidget(self._panel("OCTA en face", self.octa))
        split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        split.addWidget(top)
        split.addWidget(self._panel(
            "Linked structural B-scan - dashed: automatic; solid: saved manual",
            self.bscan))
        split.setSizes([520, 390])
        self.setCentralWidget(split)
        self._build_toolbar()
        self._build_dock()
        self.resize(1550, 980)
        self.setWindowTitle("OCT en-face labels + segmentation review")
        self.load_scan(start_index)

    @staticmethod
    def _panel(title: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(widget)
        return box

    def _build_toolbar(self):
        toolbar = self.addToolBar("en-face annotation")
        group = QtGui.QActionGroup(self)
        group.setExclusive(True)
        for label, mode, shortcut in (
            ("Navigate", "navigate", "N"),
            ("CNV outline", "cnv_outline", "D"),
            ("CNV brush", "cnv_brush", "B"),
            ("Vasculature brush", "vasculature_brush", "V"),
            ("ONH brush", "onh_brush", "O"),
        ):
            action = QtGui.QAction(label, self)
            action.setCheckable(True)
            action.setChecked(mode == "navigate")
            action.setShortcut(shortcut)
            action.triggered.connect(
                lambda _checked=False, selected=mode: self.set_mode(selected))
            group.addAction(action)
            toolbar.addAction(action)
        toolbar.addSeparator()
        undo = toolbar.addAction("Undo")
        undo.setShortcut(QtGui.QKeySequence.StandardKey.Undo)
        undo.triggered.connect(self.undo)
        redo = toolbar.addAction("Redo")
        redo.setShortcut(QtGui.QKeySequence.StandardKey.Redo)
        redo.triggered.connect(self.redo)
        toolbar.addSeparator()
        editor = toolbar.addAction("Check/correct this B-scan")
        editor.setShortcut("Return")
        editor.triggered.connect(self.open_surface_editor)
        save = toolbar.addAction("Save en-face labels")
        save.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        save.triggered.connect(self.save)
        fit = toolbar.addAction("Fit")
        fit.setShortcut("F")
        fit.triggered.connect(self.fit_all)

    def _build_dock(self):
        dock = QtWidgets.QDockWidget("scan and labels", self)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        self.scan_label = QtWidgets.QLabel()
        self.scan_label.setWordWrap(True)
        layout.addWidget(self.scan_label)
        self.vessel_status = QtWidgets.QLabel()
        self.vessel_status.setWordWrap(True)
        layout.addWidget(self.vessel_status)

        scan_nav = QtWidgets.QHBoxLayout()
        previous = QtWidgets.QPushButton("Previous scan")
        previous.clicked.connect(lambda: self.load_scan(self.index - 1))
        following = QtWidgets.QPushButton("Next scan")
        following.clicked.connect(lambda: self.load_scan(self.index + 1))
        scan_nav.addWidget(previous)
        scan_nav.addWidget(following)
        layout.addLayout(scan_nav)

        line_box = QtWidgets.QGroupBox("B-scan navigation and surfaces")
        line_layout = QtWidgets.QFormLayout(line_box)
        self.bscan_choice = QtWidgets.QSpinBox()
        self.bscan_choice.setKeyboardTracking(False)
        self.bscan_choice.valueChanged.connect(
            lambda value: self.navigate(value, self.col))
        line_layout.addRow("B-scan", self.bscan_choice)
        self.bscan_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.bscan_slider.setTracking(False)
        self.bscan_slider.valueChanged.connect(
            lambda value: self.navigate(value, self.col))
        line_layout.addRow(self.bscan_slider)
        prev_line = QtWidgets.QPushButton("Previous line")
        prev_line.clicked.connect(lambda: self.next_bscan(-1))
        next_line = QtWidgets.QPushButton("Next line")
        next_line.clicked.connect(lambda: self.next_bscan(1))
        line_buttons = QtWidgets.QHBoxLayout()
        line_buttons.addWidget(prev_line)
        line_buttons.addWidget(next_line)
        line_layout.addRow(line_buttons)
        self.show_surfaces = QtWidgets.QCheckBox("show segmentation overlays")
        self.show_surfaces.setChecked(True)
        self.show_surfaces.toggled.connect(self.refresh_bscan)
        line_layout.addRow(self.show_surfaces)
        open_line = QtWidgets.QPushButton("Open this line to check/correct")
        open_line.clicked.connect(self.open_surface_editor)
        line_layout.addRow(open_line)
        layout.addWidget(line_box)

        brush_box = QtWidgets.QGroupBox("Brush")
        brush_layout = QtWidgets.QFormLayout(brush_box)
        self.brush_size = QtWidgets.QSpinBox()
        self.brush_size.setRange(1, 160)
        self.brush_size.setValue(18)
        self.brush_size.setSuffix(" px")
        self.brush_size.valueChanged.connect(self.set_brush_size)
        brush_layout.addRow("head diameter", self.brush_size)
        brush_help = QtWidgets.QLabel(
            "In a brush mode: <b>left- or right-drag paints</b>; "
            "<b>Ctrl+right-drag erases</b>.")
        brush_help.setWordWrap(True)
        brush_layout.addRow(brush_help)
        layout.addWidget(brush_box)

        review_box = QtWidgets.QGroupBox("Explicitly reviewed")
        review_layout = QtWidgets.QVBoxLayout(review_box)
        self.review_checks: list[QtWidgets.QCheckBox] = []
        for k, name in enumerate(CL.ANNOTATION_NAMES):
            display_name = name if name in ("CNV", "ONH") else name.title()
            check = QtWidgets.QCheckBox(
                f"{display_name} reviewed (empty = absent)")
            check.toggled.connect(
                lambda checked, index=k: self._review_changed(index, checked))
            self.review_checks.append(check)
            review_layout.addWidget(check)
        mark_all = QtWidgets.QPushButton("Mark all three reviewed")
        mark_all.clicked.connect(self.mark_all_reviewed)
        review_layout.addWidget(mark_all)
        layout.addWidget(review_box)

        clear_box = QtWidgets.QGroupBox("Clear a whole mask")
        clear_layout = QtWidgets.QHBoxLayout(clear_box)
        for label, kind in (("CNV", "cnv"), ("Vessels", "vasculature"),
                            ("ONH", "onh"), ("Old edge", "onh_edge")):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, selected=kind:
                self.clear_annotation(selected))
            clear_layout.addWidget(button)
        layout.addWidget(clear_box)

        instructions = QtWidgets.QLabel(
            "Click either en-face panel to select a B-scan. The bottom panel "
            "shows its automatic surfaces. Double-click it to use the full "
            "manual editor for that line. CNV outline closes on release; "
            "brush masks remain exactly where painted.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        display = QtWidgets.QGroupBox("En-face display (display only)")
        display_layout = QtWidgets.QGridLayout(display)
        self.struct_brightness = self._display_slider(
            display_layout, 0, "Structural brightness", -100, 100, 0)
        self.struct_contrast = self._display_slider(
            display_layout, 1, "Structural contrast", 25, 300, 100, suffix="%")
        self.octa_brightness = self._display_slider(
            display_layout, 2, "OCTA brightness", -100, 100, 0)
        self.octa_contrast = self._display_slider(
            display_layout, 3, "OCTA contrast", 25, 300, 100, suffix="%")
        reset_display = QtWidgets.QPushButton("Reset display")
        reset_display.clicked.connect(self.reset_display)
        display_layout.addWidget(reset_display, 4, 0, 1, 2)
        layout.addWidget(display)

        layout.addWidget(QtWidgets.QLabel("Notes"))
        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setMaximumHeight(100)
        self.notes.textChanged.connect(self._notes_changed)
        layout.addWidget(self.notes)
        self.progress = QtWidgets.QLabel()
        self.progress.setWordWrap(True)
        layout.addWidget(self.progress)
        layout.addStretch(1)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        dock.setWidget(scroll)
        dock.setMinimumWidth(365)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _display_slider(self, layout, row: int, label: str, minimum: int,
                        maximum: int, value: int, suffix: str = ""):
        layout.addWidget(QtWidgets.QLabel(label), row, 0)
        slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.setToolTip(
            "Changes display only; annotations remain in native coordinates.")
        slider.valueChanged.connect(self.refresh_display)
        value_label = QtWidgets.QLabel(f"{value}{suffix}")
        value_label.setMinimumWidth(40)
        slider.valueChanged.connect(
            lambda current, target=value_label, unit=suffix:
            target.setText(f"{current}{unit}"))
        layout.addWidget(slider, row, 1)
        layout.addWidget(value_label, row, 2)
        return slider

    def refresh_display(self):
        self.structural.set_display(
            self.struct_brightness.value(), self.struct_contrast.value())
        self.octa.set_display(
            self.octa_brightness.value(), self.octa_contrast.value())

    def reset_display(self):
        for slider, value in (
                (self.struct_brightness, 0), (self.struct_contrast, 100),
                (self.octa_brightness, 0), (self.octa_contrast, 100)):
            slider.setValue(value)

    def set_mode(self, mode: str):
        for canvas in (self.structural, self.octa):
            canvas.set_mode(mode)
        messages = {
            "navigate": "click en face to inspect a B-scan",
            "cnv_outline": "left-drag a CNV outline; release to close it",
            "cnv_brush": "left/right paints CNV; Ctrl+right erases",
            "vasculature_brush": "left/right paints vasculature; Ctrl+right erases",
            "onh_brush": "left/right paints ONH; Ctrl+right erases",
        }
        self.statusBar().showMessage(messages[mode])

    def set_brush_size(self, value: int):
        for canvas in (self.structural, self.octa):
            canvas.set_brush_size(value)

    def _notes_changed(self):
        if self.scan is not None and not self._loading_controls:
            self.dirty = True

    def _snapshot(self) -> tuple[np.ndarray, ...]:
        return (self.mask.copy(), self.vasculature_mask.copy(),
                self.onh_mask.copy(), self.onh_edge_mask.copy(),
                self.reviewed_targets.copy(), self.vasculature_brush_touched.copy())

    def _restore_snapshot(self, snapshot: tuple[np.ndarray, ...]):
        (self.mask, self.vasculature_mask, self.onh_mask,
         self.onh_edge_mask, self.reviewed_targets, self.vasculature_brush_touched) = (
            item.copy() for item in snapshot)
        self._sync_review_checks()

    def _push_undo(self):
        self.undo_stack.append(self._snapshot())
        self.redo_stack.clear()
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)

    def _set_target_reviewed(self, index: int, value: bool):
        self.reviewed_targets[index] = bool(value)
        self.review_checks[index].blockSignals(True)
        self.review_checks[index].setChecked(bool(value))
        self.review_checks[index].blockSignals(False)

    def _review_changed(self, index: int, checked: bool):
        if self._loading_controls:
            return
        self.reviewed_targets[index] = bool(checked)
        if self.scan is not None:
            self.dirty = True
            self._update_progress()

    def _sync_review_checks(self):
        for index, check in enumerate(self.review_checks):
            check.blockSignals(True)
            check.setChecked(bool(self.reviewed_targets[index]))
            check.blockSignals(False)

    def mark_all_reviewed(self):
        if self.scan is None:
            return
        if not self.reviewed_targets.all():
            self._push_undo()
            self.reviewed_targets[:] = True
            self._sync_review_checks()
            self.dirty = True
            self._update_progress()

    def apply_stroke(self, points, operation: str):
        if self.scan is None:
            return
        changed = None
        target_index = None
        if operation == "cnv_outline_add":
            smooth = _smooth_stroke(points, closed=True)
            if len(smooth) >= 3:
                changed = np.zeros(self.mask.shape, dtype=bool)
                rr, cc = raster_polygon(
                    smooth[:, 1], smooth[:, 0], shape=self.mask.shape)
                changed[rr, cc] = True
                target_index = 0
        else:
            for mode, index in BRUSH_MODES.items():
                prefix = mode + "_"
                if operation.startswith(prefix):
                    changed = _brush_mask(
                        points, self.mask.shape, self.brush_size.value())
                    target_index = index
                    break
        if changed is None or not changed.any() or target_index is None:
            return
        self._push_undo()
        target = (self.mask, self.vasculature_mask, self.onh_mask)[target_index]
        target[changed] = not operation.endswith("_erase")
        if target_index == 1:
            self.vasculature_brush_touched |= changed
        # Editing one part of an automatic mask does not review the whole mask.
        self._set_target_reviewed(
            target_index, not (target_index == 1 and self.vasculature_proposal_path))
        self.dirty = True
        self.redraw_annotations()

    def clear_annotation(self, kind: str):
        targets = {"cnv": (self.mask, 0),
                   "vasculature": (self.vasculature_mask, 1),
                   "onh": (self.onh_mask, 2),
                   "onh_edge": (self.onh_edge_mask, 2)}
        target, index = targets[kind]
        if self.scan is None or not target.any():
            return
        label = ("legacy ONH edge" if kind == "onh_edge"
                 else CL.ANNOTATION_NAMES[index])
        answer = QtWidgets.QMessageBox.question(
            self, f"Clear {label}", f"Clear the entire {label} mask for this scan?")
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._push_undo()
        target[:] = False
        if kind == "vasculature":
            self.vasculature_brush_touched[:] = True
        self._set_target_reviewed(index, True)
        self.dirty = True
        self.redraw_annotations()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self._snapshot())
        self._restore_snapshot(self.undo_stack.pop())
        self.dirty = True
        self.redraw_annotations()

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self._snapshot())
        self._restore_snapshot(self.redo_stack.pop())
        self.dirty = True
        self.redraw_annotations()

    def _surface_label(self, row: int):
        if self.scan is None:
            return None, "unreviewed"
        path = SL.label_path(self.surface_label_dir, self.scan.scan_id, int(row))
        if not path.exists():
            return None, "unreviewed"
        try:
            record = SL.load_label(path)
            if (record.get("cascade_version") != CASCADE_VERSION or
                    tuple(record["surface_names"]) != self.scan.surface_names):
                return None, "unreviewed"
            manual = (record["surfaces"] if record["verdict"] == "corrected"
                      else None)
            return manual, str(record["verdict"])
        except Exception as exc:  # noqa: BLE001
            self.statusBar().showMessage(
                f"could not show surface label {path.name}: {exc}", 6000)
            return None, "unreviewed"

    def refresh_bscan(self):
        if self.scan is None:
            return
        manual, verdict = self._surface_label(self.row)
        self.bscan.set_image(
            self.scan.structural_bscan(self.row), self.col,
            self.scan.surfaces[self.row], manual=manual, verdict=verdict,
            show_surfaces=self.show_surfaces.isChecked())
        self._update_progress(verdict)

    def navigate(self, row: int, col: int):
        if self.scan is None:
            return
        self.row = int(np.clip(row, 0, self.scan.native_shape[0] - 1))
        self.col = int(np.clip(col, 0, self.scan.native_shape[1] - 1))
        for canvas in (self.structural, self.octa):
            canvas.set_cursor(self.row, self.col)
        for widget in (self.bscan_choice, self.bscan_slider):
            widget.blockSignals(True)
            widget.setValue(self.row)
            widget.blockSignals(False)
        self.refresh_bscan()

    def next_bscan(self, step: int):
        if self.scan is not None:
            self.navigate(self.row + step, self.col)

    def show_position(self, row: int, col: int):
        if self.scan is not None:
            self.statusBar().showMessage(
                f"B-scan {row}, A-line {col} | click in Navigate mode to inspect")

    def redraw_annotations(self):
        for canvas in (self.structural, self.octa):
            canvas.set_annotations(
                self.mask, self.vasculature_mask, self.onh_mask,
                self.onh_edge_mask)
        self._update_progress()

    def _update_progress(self, verdict: str | None = None):
        if self.scan is None:
            return
        if verdict is None:
            _manual, verdict = self._surface_label(self.row)
        reviewed = ", ".join(
            name for name, done in zip(CL.ANNOTATION_NAMES,
                                       self.reviewed_targets) if done) or "none"
        saved = ("unsaved changes" if self.dirty else
                 "starting mask loaded" if self.vasculature_new_proposal else "saved")
        if self.vasculature_proposal_path:
            self.vessel_status.setText(
                "<b>Vessels: reviewed starting mask</b>" if self.reviewed_targets[1] else
                "<b>Vessels: automatic starting mask</b><br>"
                "Edit with the Vasculature brush, then tick <b>Vasculature reviewed</b> and save.")
        else:
            self.vessel_status.setText(
                "<b>Vessels: your saved mask</b>" if self.vasculature_mask.any() or self.reviewed_targets[1]
                else "Vessels: no starting mask available")
        legacy = (f"<br>legacy ONH-edge pixels: {int(self.onh_edge_mask.sum()):,}"
                  if self.onh_edge_mask.any() else "")
        self.progress.setText(
            f"Scan {self.index + 1}/{len(self.segmentations)}<br>"
            f"B-scan {self.row}, A-line {self.col}: <b>{verdict}</b><br>"
            f"CNV pixels: {int(self.mask.sum()):,}<br>"
            f"Vasculature pixels: {int(self.vasculature_mask.sum()):,}<br>"
            f"ONH pixels: {int(self.onh_mask.sum()):,}{legacy}<br>"
            f"reviewed classes: {reviewed}<br><b>{saved}</b>")

    def _write_line_review_pack(self, row: int) -> Path:
        if self.scan is None:
            raise RuntimeError("no scan loaded")
        out = self.line_review_dir / (
            f"{self.scan.scan_id}_b{int(row):04d}_pack.npz")
        image = self.scan.structural_bscan(row)
        np.savez_compressed(
            out,
            images=image[None].astype(np.float32),
            surfaces=self.scan.surfaces[row:row + 1].astype(np.float32),
            confidence=self.scan.confidence[row:row + 1].astype(np.float16),
            shadow=self.scan.shadow[row:row + 1].astype(bool),
            bscan_index=np.array([row], dtype=np.int32),
            is_control=np.array([False]),
            suspect_score=np.array([np.nan], dtype=np.float32),
            surface_names=np.array(self.scan.surface_names),
            cascade_version=np.array([CASCADE_VERSION]),
            scan_id=np.array([self.scan.scan_id]),
            px_um=np.array([self.scan.px_um], dtype=np.float32),
            source_segmentation=np.array([str(self.scan.segmentation_path)]),
            selection_role=np.array(["enface_selected"]),
        )
        return out

    def open_surface_editor(self):
        if self.scan is None:
            return
        key = (self.scan.scan_id, self.row)
        existing = self.surface_windows.get(key)
        if existing is not None:
            existing.showNormal()
            existing.raise_()
            existing.activateWindow()
            return
        try:
            pack = self._write_line_review_pack(self.row)
            from eight_surface.label_gui import MainWindow as SurfaceWindow
            window = SurfaceWindow([pack], self.surface_label_dir)
            label_path = SL.label_path(
                self.surface_label_dir, self.scan.scan_id, self.row)
            if label_path.exists():
                record = SL.load_label(label_path)
                if (record.get("cascade_version") == CASCADE_VERSION and
                        tuple(record["surface_names"]) == self.scan.surface_names):
                    # Resuming a correction must preserve the automatic line
                    # that the reviewer originally judged, even if the scan
                    # was later re-segmented under the same cascade name.
                    window.pack.states[0].auto = np.asarray(
                        record["auto_surfaces"], dtype=float)
                    window.redraw_surfaces()
                    window.update_labels()
            window.setWindowTitle(
                f"Check/correct {self.scan.scan_id} - B-scan {self.row}")
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            self.surface_windows[key] = window

            def closed(_object=None, selected=key):
                self.surface_windows.pop(selected, None)
                if (self.scan is not None and
                        (self.scan.scan_id, self.row) == selected):
                    self.refresh_bscan()

            window.destroyed.connect(closed)
            window.show()
            window.raise_()
            window.activateWindow()
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(
                self, "Cannot open surface editor",
                f"B-scan {self.row}\n\n{exc}")

    def save(self):
        if self.scan is None:
            return None
        path = CL.save_label(
            self.label_dir,
            scan_id=self.scan.scan_id,
            cnv_mask=self.mask,
            vasculature_mask=self.vasculature_mask,
            onh_mask=self.onh_mask,
            onh_edge_mask=self.onh_edge_mask,
            source_volume=self.scan.source_volume,
            source_segmentation=self.scan.segmentation_path,
            retina_band=self.scan.retina_band,
            vitreous_at_high_index=self.scan.vitreous_at_high_index,
            animal=self.scan.animal,
            eye=self.scan.eye,
            day_label=self.scan.day_label,
            days_post_laser=self.scan.days_post_laser,
            session_date=self.scan.session_date,
            notes=self.notes.toPlainText(),
            reviewed_targets=self.reviewed_targets,
            vasculature_proposal_path=self.vasculature_proposal_path,
            vasculature_proposal_sha256=self.vasculature_proposal_sha256,
            vasculature_initial_mask=self.vasculature_initial_mask,
            vasculature_brush_touched=self.vasculature_brush_touched,
        )
        self.dirty = False
        self.vasculature_new_proposal = False
        self.statusBar().showMessage(f"saved {path.name}", 5000)
        self._update_progress()
        return path

    def _save_if_dirty(self):
        if self.scan is not None and self.dirty:
            self.save()

    def load_scan(self, index: int):
        if not 0 <= index < len(self.segmentations):
            return
        self._save_if_dirty()
        self.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.statusBar().showMessage(
            "reading structural/OCTA projections and segmentation ...")
        QtWidgets.QApplication.processEvents()
        try:
            self.scan = None
            gc.collect()
            scan = read_scan(self.segmentations[index])
            shape = scan.native_shape
            mask = np.zeros(shape, dtype=bool)
            vasculature = np.zeros(shape, dtype=bool)
            onh = np.zeros(shape, dtype=bool)
            onh_edge = np.zeros(shape, dtype=bool)
            reviewed_targets = np.zeros(len(CL.ANNOTATION_NAMES), dtype=bool)
            notes = ""
            record = None
            existing = CL.label_path(self.label_dir, scan.scan_id)
            if existing.exists():
                record = CL.load_label(existing)
                if record["native_shape"] != shape:
                    raise ValueError(
                        f"saved mask shape {record['native_shape']} does not match "
                        f"volume shape {shape}")
                mask = record["cnv_mask"].copy()
                vasculature = record["vasculature_mask"].copy()
                onh = record["onh_mask"].copy()
                onh_edge = record["onh_edge_mask"].copy()
                reviewed_targets = record["reviewed_targets"].copy()
                notes = str(record["notes"])
            proposal_path = record.get("vasculature_proposal_path", "") if record else ""
            proposal_sha256 = record.get("vasculature_proposal_sha256", "") if record else ""
            initial = record["vasculature_initial_mask"].copy() if record else np.zeros(shape, bool)
            touched = record["vasculature_brush_touched"].copy() if record else np.zeros(shape, bool)
            new_proposal = False
            if self.proposals_dir is not None and not has_saved_vessel_work(record):
                proposal = load_proposal(self.proposals_dir, scan)
                if proposal is not None:
                    vasculature = proposal["mask"].copy()
                    initial = proposal["mask"].copy()
                    proposal_path, proposal_sha256 = proposal["path"], proposal["sha256"]
                    reviewed_targets[1] = False
                    new_proposal = True
            self.scan = scan
            self.index = index
            self.mask = mask
            self.vasculature_mask = vasculature
            self.vasculature_proposal_path = proposal_path
            self.vasculature_proposal_sha256 = proposal_sha256
            self.vasculature_initial_mask = initial
            self.vasculature_brush_touched = touched
            self.vasculature_new_proposal = new_proposal
            self.onh_mask = onh
            self.onh_edge_mask = onh_edge
            self.reviewed_targets = reviewed_targets
            self.dirty = False
            self.undo_stack.clear()
            self.redo_stack.clear()
            self._loading_controls = True
            self.notes.setPlainText(notes)
            self._sync_review_checks()
            self._loading_controls = False
            self.structural.set_image(scan.structural_enface)
            self.octa.set_image(scan.octa_enface)
            for widget in (self.bscan_choice, self.bscan_slider):
                widget.blockSignals(True)
                widget.setRange(0, shape[0] - 1)
                widget.blockSignals(False)
            self.redraw_annotations()
            self.row, self.col = shape[0] // 2, shape[1] // 2
            self.navigate(self.row, self.col)
            day = (f"D{scan.days_post_laser}" if scan.days_post_laser
                   else scan.day_label)
            self.scan_label.setText(
                f"<b>{scan.scan_id}</b><br>{scan.animal} {scan.eye} {day}<br>"
                f"{scan.source_volume.name}")
            self.fit_all()
        except Exception as exc:  # noqa: BLE001
            self._loading_controls = False
            QtWidgets.QMessageBox.critical(
                self, "Cannot load scan",
                f"{self.segmentations[index].name}\n\n{exc}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.setEnabled(True)

    def fit_all(self):
        self.structural.fit()
        self.octa.fit()
        self.bscan.fit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self.load_scan(self.index - 1)
            return
        if event.key() == Qt.Key.Key_Right:
            self.load_scan(self.index + 1)
            return
        if event.key() == Qt.Key.Key_PageUp:
            self.next_bscan(-1)
            return
        if event.key() == Qt.Key.Key_PageDown:
            self.next_bscan(1)
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self._save_if_dirty()
        event.accept()


def collect_segmentations(target: Path) -> list[Path]:
    target = Path(target)
    paths = sorted(target.glob("*.npz")) if target.is_dir() else [target]
    return [path for path in paths if path.is_file()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", default=str(DEFAULT_SEGMENTED),
                        help="eight-boundary segmentation NPZ or directory")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS),
                        help="en-face multi-class label directory")
    parser.add_argument("--surface-labels", default=str(DEFAULT_SURFACE_LABELS),
                        help="manual surface-label directory")
    parser.add_argument("--line-review", default=str(DEFAULT_LINE_REVIEW),
                        help="persistent one-line packs opened from the en-face GUI")
    parser.add_argument("--vessel-proposals", default=str(DEFAULT_PROPOSALS),
                        help="automatic vessel starting-mask directory")
    parser.add_argument("--no-vessel-proposals", action="store_true",
                        help="open without loading automatic vessel starting masks")
    parser.add_argument("--start-scan", help="scan ID to show first")
    args = parser.parse_args()
    segmentations = collect_segmentations(Path(args.target))
    if not segmentations:
        print(f"no segmentation outputs found in {args.target}")
        return 1
    start_index = 0
    if args.start_scan:
        matches = [i for i, path in enumerate(segmentations) if path.stem == args.start_scan]
        if not matches:
            parser.error(f"scan {args.start_scan!r} is not in this queue")
        start_index = matches[0]
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow(
        segmentations, Path(args.labels), Path(args.surface_labels),
        Path(args.line_review),
        None if args.no_vessel_proposals else Path(args.vessel_proposals), start_index)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
