#!/usr/bin/env python3
"""Linked structural/OCTA en-face editor for CNV footprint masks.

Run from ``code`` after activating ``octa``::

    python eight_surface/cnv_gui.py ../outputs/eight_surface/segmented

The two en-face panels use the same native ``[B-scan, A-line]`` coordinates.
Navigation updates the structural B-scan below them.  CNV footprints are drawn
as closed freehand contours and smoothed before rasterising.  ONH edges are
freehand lines, which is intentional: an ONH commonly enters from a field
edge and has no meaningful closed in-frame footprint.  No thickness or
RPE-elevation map is displayed.
"""

from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, gaussian_filter1d
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
from eight_surface.cnv_data import CnvScan, read_scan  # noqa: E402


Qt = QtCore.Qt
DEFAULT_SEGMENTED = Path("../outputs/eight_surface/segmented")
DEFAULT_LABELS = Path("../outputs/cnv_labels")


def _to_gray(image: np.ndarray, brightness: int = 0,
             contrast: int = 100) -> QtGui.QImage:
    """Return a display-only brightness/contrast rendering of an en-face image."""
    finite = image[np.isfinite(image)]
    if finite.size:
        lo, hi = np.percentile(finite, [1.0, 99.0])
    else:
        lo, hi = 0.0, 1.0
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((image - lo) / (hi - lo), 0, 1)
    # Brightness is a midpoint shift; contrast expands/contracts around the
    # midpoint.  These settings affect only the display, never a label.
    scaled = (scaled - 0.5) * (float(contrast) / 100.0) + 0.5
    scaled += float(brightness) / 200.0
    scaled = np.clip(scaled, 0, 1)
    pixels = np.ascontiguousarray((scaled * 255).astype(np.uint8))
    height, width = pixels.shape
    return QtGui.QImage(
        pixels.data, width, height, width,
        QtGui.QImage.Format.Format_Grayscale8).copy()


def _annotation_overlay(cnv_mask: np.ndarray, onh_edge_mask: np.ndarray) -> QtGui.QImage:
    """Red translucent CNV regions and a bright green ONH edge overlay."""
    rgba = np.zeros((*cnv_mask.shape, 4), dtype=np.uint8)
    rgba[cnv_mask] = np.array([255, 45, 35, 105], dtype=np.uint8)
    rgba[onh_edge_mask] = np.array([60, 255, 105, 245], dtype=np.uint8)
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
    mode = "wrap" if closed else "nearest"
    return gaussian_filter1d(smooth, sigma=sigma_px, axis=0, mode=mode)


def _rasterize_edge(points: list[tuple[float, float]], shape: tuple[int, int]) -> np.ndarray:
    """Rasterise a smoothed freehand ONH edge as a one-pixel native-grid line."""
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


class EnfaceCanvas(QtWidgets.QGraphicsView):
    navigated = QtCore.Signal(int, int)
    strokeFinished = QtCore.Signal(object, str)  # [(x,y)], annotation mode
    cursorMoved = QtCore.Signal(int, int)

    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setBackgroundBrush(QtGui.QColor("#101014"))
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
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
        draft_pen = QtGui.QPen(QtGui.QColor("#ffe119"), 2.0,
                               Qt.PenStyle.DashLine)
        draft_pen.setCosmetic(True)
        self._draft.setPen(draft_pen)
        self._draft.setZValue(20)
        self.mode = "navigate"
        self.points: list[tuple[float, float]] = []
        self._drawing = False
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

    def set_annotations(self, cnv_mask: np.ndarray, onh_edge_mask: np.ndarray):
        self._overlay.setPixmap(QtGui.QPixmap.fromImage(
            _annotation_overlay(cnv_mask, onh_edge_mask)))

    def set_mode(self, mode: str):
        self.mode = mode
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.cancel_stroke()

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
        self.points.clear()
        self._draft.setPath(QtGui.QPainterPath())

    def commit_stroke(self):
        if self.mode.startswith("cnv") and len(self.points) >= 3:
            self.strokeFinished.emit(list(self.points), self.mode)
        elif self.mode.startswith("onh") and len(self.points) >= 2:
            self.strokeFinished.emit(list(self.points), self.mode)
        self.cancel_stroke()

    def _scene_pixel(self, event) -> tuple[int, int, float, float]:
        point = self.mapToScene(event.position().toPoint())
        height, width = self._shape
        col = int(np.clip(round(point.x()), 0, width - 1))
        row = int(np.clip(round(point.y()), 0, height - 1))
        return row, col, float(point.x()), float(point.y())

    def _append_point(self, x: float, y: float):
        if self.points and np.hypot(x - self.points[-1][0],
                                    y - self.points[-1][1]) < 0.5:
            return
        self.points.append((x, y))
        path = QtGui.QPainterPath()
        path.moveTo(*self.points[0])
        for point in self.points[1:]:
            path.lineTo(*point)
        if self.mode.startswith("cnv") and len(self.points) > 2:
            path.lineTo(*self.points[0])
        self._draft.setPath(path)

    def mousePressEvent(self, event):
        row, col, x, y = self._scene_pixel(event)
        if event.button() == Qt.MouseButton.RightButton:
            self.cancel_stroke()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mode == "navigate":
                self.navigated.emit(row, col)
            else:
                self.cancel_stroke()
                self._drawing = True
                self._append_point(x, y)
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            _row, _col, x, y = self._scene_pixel(event)
            self._append_point(x, y)
            self.commit_stroke()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        row, col, _x, _y = self._scene_pixel(event)
        self.cursorMoved.emit(row, col)
        if self._drawing and self.mode != "navigate" and (
                event.buttons() & Qt.MouseButton.LeftButton):
            self._append_point(_x, _y)
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        factor = 1.0015 ** event.angleDelta().y()
        self.scale(factor, factor)

    def fit(self):
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(),
                           Qt.AspectRatioMode.KeepAspectRatio)


class BscanCanvas(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setBackgroundBrush(QtGui.QColor("#101014"))
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._pix = self.scene().addPixmap(QtGui.QPixmap())
        self._aline = self.scene().addLine(QtCore.QLineF())
        pen = QtGui.QPen(QtGui.QColor("#00ffff"), 1.2)
        pen.setCosmetic(True)
        self._aline.setPen(pen)
        self._aline.setZValue(5)

    def set_image(self, image: np.ndarray, aline: int):
        qimage = _to_gray(image, 2.0, 99.5)
        self._pix.setPixmap(QtGui.QPixmap.fromImage(qimage))
        self.scene().setSceneRect(QtCore.QRectF(qimage.rect()))
        self._aline.setLine(aline + 0.5, 0, aline + 0.5, image.shape[0])

    def wheelEvent(self, event):
        factor = 1.0015 ** event.angleDelta().y()
        self.scale(factor, factor)

    def fit(self):
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(),
                           Qt.AspectRatioMode.KeepAspectRatio)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, segmentations: list[Path], label_dir: Path):
        super().__init__()
        self.segmentations = segmentations
        self.label_dir = Path(label_dir)
        self.label_dir.mkdir(parents=True, exist_ok=True)
        self.index = -1
        self.scan: CnvScan | None = None
        self.mask = np.zeros((1, 1), dtype=bool)
        self.onh_edge_mask = np.zeros((1, 1), dtype=bool)
        self.row = 0
        self.col = 0
        self.dirty = False
        self.reviewed = False
        self.undo_stack: list[tuple[np.ndarray, np.ndarray]] = []
        self.redo_stack: list[tuple[np.ndarray, np.ndarray]] = []

        self.structural = EnfaceCanvas("Structural OCT")
        self.octa = EnfaceCanvas("OCTA")
        self.bscan = BscanCanvas()
        for canvas in (self.structural, self.octa):
            canvas.navigated.connect(self.navigate)
            canvas.strokeFinished.connect(self.apply_stroke)
            canvas.cursorMoved.connect(self.show_position)

        top = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        top.addWidget(self._panel("Structural OCT en face", self.structural))
        top.addWidget(self._panel("OCTA en face", self.octa))
        split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        split.addWidget(top)
        split.addWidget(self._panel("Linked structural B-scan", self.bscan))
        split.setSizes([500, 380])
        self.setCentralWidget(split)
        self._build_toolbar()
        self._build_dock()
        self.resize(1500, 950)
        self.setWindowTitle("CNV en-face footprint annotation")
        self.load_scan(0)

    @staticmethod
    def _panel(title: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(widget)
        return box

    def _build_toolbar(self):
        toolbar = self.addToolBar("CNV annotation")
        group = QtGui.QActionGroup(self)
        group.setExclusive(True)
        for label, mode, shortcut in (
            ("Navigate", "navigate", "N"),
            ("Draw CNV", "cnv_add", "D"),
            ("Erase CNV", "cnv_erase", "E"),
            ("Draw ONH edge", "onh_add", "O"),
            ("Erase ONH edge", "onh_erase", "Shift+O"),
        ):
            action = QtGui.QAction(label, self)
            action.setCheckable(True)
            action.setChecked(mode == "navigate")
            action.setShortcut(shortcut)
            action.triggered.connect(lambda _checked=False, m=mode: self.set_mode(m))
            group.addAction(action)
            toolbar.addAction(action)
        toolbar.addSeparator()
        undo = toolbar.addAction("Undo")
        undo.setShortcut(QtGui.QKeySequence.StandardKey.Undo)
        undo.triggered.connect(self.undo)
        redo = toolbar.addAction("Redo")
        redo.setShortcut(QtGui.QKeySequence.StandardKey.Redo)
        redo.triggered.connect(self.redo)
        clear = toolbar.addAction("Clear CNV")
        clear.triggered.connect(lambda: self.clear_annotation("cnv"))
        clear_onh = toolbar.addAction("Clear ONH edge")
        clear_onh.triggered.connect(lambda: self.clear_annotation("onh"))
        toolbar.addSeparator()
        save = toolbar.addAction("Save reviewed")
        save.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        save.triggered.connect(self.save)
        fit = toolbar.addAction("Fit")
        fit.setShortcut("F")
        fit.triggered.connect(self.fit_all)

    def _build_dock(self):
        dock = QtWidgets.QDockWidget("scan", self)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        self.scan_label = QtWidgets.QLabel()
        self.scan_label.setWordWrap(True)
        layout.addWidget(self.scan_label)
        row = QtWidgets.QHBoxLayout()
        previous = QtWidgets.QPushButton("Previous scan")
        previous.clicked.connect(lambda: self.load_scan(self.index - 1))
        following = QtWidgets.QPushButton("Next scan")
        following.clicked.connect(lambda: self.load_scan(self.index + 1))
        row.addWidget(previous)
        row.addWidget(following)
        layout.addLayout(row)
        layout.addWidget(QtWidgets.QLabel(
            "Navigate: click either en-face panel.\n"
            "Draw CNV: hold the left mouse button and trace a closed lesion outline; "
            "release to close and smooth it.\n"
            "Draw ONH edge: hold the left button and trace the visible retinal/ONH "
            "border; release to save the line.\n"
            "Right-click cancels an unfinished trace.\n"
            "A saved empty CNV mask means reviewed: no CNV footprint."))
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
        self.notes.textChanged.connect(self._notes_changed)
        layout.addWidget(self.notes)
        self.progress = QtWidgets.QLabel()
        self.progress.setWordWrap(True)
        layout.addWidget(self.progress)
        layout.addStretch(1)
        dock.setWidget(body)
        dock.setMinimumWidth(330)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _display_slider(self, layout, row: int, label: str, minimum: int,
                        maximum: int, value: int, suffix: str = ""):
        layout.addWidget(QtWidgets.QLabel(label), row, 0)
        slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.setToolTip("Changes display only; annotations are always native coordinates.")
        slider.valueChanged.connect(self.refresh_display)
        value_label = QtWidgets.QLabel()
        value_label.setMinimumWidth(40)
        slider.valueChanged.connect(
            lambda current, target=value_label, unit=suffix: target.setText(f"{current}{unit}"))
        value_label.setText(f"{value}{suffix}")
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
        self.statusBar().showMessage(
            {"navigate": "click en face to inspect a B-scan",
             "cnv_add": "hold the left mouse button and trace a CNV outline; release to close it",
             "cnv_erase": "hold the left mouse button around CNV to erase; release to close it",
             "onh_add": "hold the left mouse button and trace the retinal/ONH edge",
             "onh_erase": "hold the left mouse button over an ONH edge to erase"}[mode])

    def _notes_changed(self):
        if self.scan is not None:
            self.dirty = True

    def _push_undo(self):
        self.undo_stack.append((self.mask.copy(), self.onh_edge_mask.copy()))
        self.redo_stack.clear()
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)

    def apply_stroke(self, points, mode: str):
        if self.scan is None:
            return
        self._push_undo()
        if mode.startswith("cnv"):
            xy = _smooth_stroke(points, closed=True)
            if len(xy) < 3:
                self.undo_stack.pop()
                return
            rr, cc = raster_polygon(xy[:, 1], xy[:, 0], shape=self.mask.shape)
            self.mask[rr, cc] = mode == "cnv_add"
        elif mode.startswith("onh"):
            edge = _rasterize_edge(points, self.mask.shape)
            if not edge.any():
                self.undo_stack.pop()
                return
            if mode == "onh_add":
                self.onh_edge_mask |= edge
            else:
                # A one-pixel stored edge is precise for analysis, but a
                # slightly wider erase brush is usable at normal zoom.
                self.onh_edge_mask &= ~binary_dilation(
                    edge, structure=np.ones((5, 5), dtype=bool))
        else:
            self.undo_stack.pop()
            return
        self.dirty = True
        self.redraw_annotations()

    def clear_annotation(self, kind: str):
        target = self.mask if kind == "cnv" else self.onh_edge_mask
        label = "CNV footprint" if kind == "cnv" else "ONH edge"
        if self.scan is None or not target.any():
            return
        answer = QtWidgets.QMessageBox.question(
            self, f"Clear {label}", f"Clear the entire {label} for this scan?")
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._push_undo()
        target[:] = False
        self.dirty = True
        self.redraw_annotations()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append((self.mask.copy(), self.onh_edge_mask.copy()))
        self.mask, self.onh_edge_mask = self.undo_stack.pop()
        self.dirty = True
        self.redraw_annotations()

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append((self.mask.copy(), self.onh_edge_mask.copy()))
        self.mask, self.onh_edge_mask = self.redo_stack.pop()
        self.dirty = True
        self.redraw_annotations()

    def navigate(self, row: int, col: int):
        if self.scan is None:
            return
        self.row = int(np.clip(row, 0, self.scan.native_shape[0] - 1))
        self.col = int(np.clip(col, 0, self.scan.native_shape[1] - 1))
        for canvas in (self.structural, self.octa):
            canvas.set_cursor(self.row, self.col)
        self.bscan.set_image(self.scan.structural_bscan(self.row), self.col)
        self._update_progress()

    def show_position(self, row: int, col: int):
        if self.scan is not None:
            self.statusBar().showMessage(
                f"B-scan {row}, A-line {col} | click in Navigate mode to inspect")

    def redraw_annotations(self):
        for canvas in (self.structural, self.octa):
            canvas.set_annotations(self.mask, self.onh_edge_mask)
        self._update_progress()

    def _update_progress(self):
        if self.scan is None:
            return
        saved = "saved/reviewed" if self.reviewed and not self.dirty else "unsaved"
        self.progress.setText(
            f"Scan {self.index + 1}/{len(self.segmentations)}<br>"
            f"B-scan {self.row}, A-line {self.col}<br>"
            f"CNV pixels: {int(self.mask.sum()):,}<br>"
            f"ONH-edge pixels: {int(self.onh_edge_mask.sum()):,}<br>{saved}")

    def save(self):
        if self.scan is None:
            return None
        path = CL.save_label(
            self.label_dir,
            scan_id=self.scan.scan_id,
            cnv_mask=self.mask,
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
            reviewed=True,
        )
        self.reviewed = True
        self.dirty = False
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
        self.statusBar().showMessage("reading structural and OCTA data ...")
        QtWidgets.QApplication.processEvents()
        try:
            self.scan = None
            gc.collect()
            scan = read_scan(self.segmentations[index])
            mask = np.zeros(scan.native_shape, dtype=bool)
            onh_edge_mask = np.zeros(scan.native_shape, dtype=bool)
            reviewed = False
            notes = ""
            existing = CL.label_path(self.label_dir, scan.scan_id)
            if existing.exists():
                record = CL.load_label(existing)
                if record["native_shape"] != scan.native_shape:
                    raise ValueError(
                        f"saved mask shape {record['native_shape']} does not match "
                        f"volume shape {scan.native_shape}")
                mask = record["cnv_mask"].copy()
                onh_edge_mask = record["onh_edge_mask"].copy()
                reviewed = bool(record["reviewed"])
                notes = str(record["notes"])
            self.scan = scan
            self.index = index
            self.mask = mask
            self.onh_edge_mask = onh_edge_mask
            self.reviewed = reviewed
            self.dirty = False
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.notes.blockSignals(True)
            self.notes.setPlainText(notes)
            self.notes.blockSignals(False)
            self.structural.set_image(scan.structural_enface)
            self.octa.set_image(scan.octa_enface)
            self.redraw_annotations()
            self.row, self.col = scan.native_shape[0] // 2, scan.native_shape[1] // 2
            self.navigate(self.row, self.col)
            self.scan_label.setText(
                f"<b>{scan.scan_id}</b><br>{scan.animal} {scan.eye} "
                f"{scan.day_label}<br>{scan.source_volume.name}")
            self.fit_all()
        except Exception as exc:  # noqa: BLE001 - GUI must report load failures
            QtWidgets.QMessageBox.critical(
                self, "Cannot load scan", f"{self.segmentations[index].name}\n\n{exc}")
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
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self._save_if_dirty()
        event.accept()


def collect_segmentations(target: Path) -> list[Path]:
    target = Path(target)
    paths = sorted(target.glob("*.npz")) if target.is_dir() else [target]
    return [path for path in paths if path.is_file()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default=str(DEFAULT_SEGMENTED),
                        help="eight-boundary segmentation NPZ or directory")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS))
    args = parser.parse_args()
    segmentations = collect_segmentations(Path(args.target))
    if not segmentations:
        print(f"no segmentation outputs found in {args.target}")
        return 1
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow(segmentations, Path(args.labels))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
