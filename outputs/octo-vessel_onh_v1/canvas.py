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

CODE_DIR = Path(__file__).resolve().parents[2] / 'code'
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
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_position = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
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
            self._erase = bool(getattr(self, 'force_erase', False)) or bool(
                event.button() == Qt.MouseButton.RightButton and
                event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self._append_point(x, y)
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.cancel_stroke()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_position = None
            self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return
        if self._drawing and event.button() == self._draw_button:
            _row, _col, x, y = self._scene_pixel(event)
            self._append_point(x, y)
            self.commit_stroke()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_pan_position', None) is not None:
            point = event.position().toPoint()
            delta = point - self._pan_position
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_position = point
            event.accept()
            return
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
