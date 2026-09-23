"""Linked en-face regions, native B-scan navigation and embedded boundary editing."""
from __future__ import annotations

import copy
import uuid
from pathlib import Path

import numpy as np
from skimage.draw import polygon

from eight_surface.cnv_data import read_scan
from eight_surface.cnv_gui import EnfaceCanvas, QtCore, QtGui, QtWidgets
from .data import (CATEGORIES, AutoSource, Region, RegionStore, SurfaceIndex,
                   atomic_json, load_enface, runs)
from .label_gui import BoundaryEditor

Qt = QtCore.Qt
COLOURS = {"Unclassified": "#ffd166", "Full Lesion": "#ff6464", "Normal": "#65d69a", "Other": "#d299ff"}


def configure_app(app):
    """Load an explicit Windows font, including when Qt renders offscreen."""
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        font_id = QtGui.QFontDatabase.addApplicationFont(str(font_path))
        families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QtGui.QFont(families[0], 9))
    app.setStyle("Fusion")
    app.setStyleSheet("QGroupBox {font-weight: 600;} QToolBar {spacing: 6px; padding: 4px;} QPlainTextEdit, QListWidget {font-size: 12px;} QLabel {font-size: 12px;}")


class ReviewCanvas(EnfaceCanvas):
    def __init__(self, title):
        super().__init__(title)
        self.review_items = []
        self.setToolTip("Click a row or region to inspect it. Yellow segments mark recorded manual strokes. Wheel zooms; middle-drag pans.")
        self._pan = None

    def _scene_pixel(self, event):
        point = self.mapToScene(event.position().toPoint())
        row = int(np.clip(np.floor(point.y()), 0, self._shape[0] - 1))
        col = int(np.clip(np.floor(point.x()), 0, self._shape[1] - 1))
        return row, col, float(point.x()), float(point.y())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = event.position().toPoint()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan is not None:
            point = event.position().toPoint()
            delta = point - self._pan
            self._pan = point
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = None
            return
        super().mouseReleaseEvent(event)

    def set_reviews(self, regions, selected, index, rows, show_lines):
        scene = self.scene()
        for item in self.review_items:
            scene.removeItem(item)
        self.review_items = []
        for i, region in enumerate(regions):
            # Mask edges have exact native coordinates; no smoothed geometry is saved.
            from scipy.ndimage import binary_erosion
            edge = region.mask & ~binary_erosion(region.mask)
            path = QtGui.QPainterPath()
            for row in np.flatnonzero(edge.any(axis=1)):
                for lo, hi in runs(edge[row]):
                    path.addRect(lo, row, hi - lo, 1)
            colour = QtGui.QColor(COLOURS[region.category])
            item = scene.addPath(path, QtGui.QPen(Qt.PenStyle.NoPen), QtGui.QBrush(colour))
            item.setZValue(7)
            item.setOpacity(1 if i == selected else .65)
            self.review_items.append(item)
            yy, xx = np.where(region.mask)
            if len(yy):
                label = scene.addSimpleText(f"{i + 1}: {region.category}" if i == selected else str(i + 1))
                label.setBrush(colour)
                label.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                label.setPos(max(0, float(np.median(xx)) - 14), max(0, int(yy.min()) - 13))
                label.setZValue(19)
                self.review_items.append(label)
        if show_lines:
            for row in rows:
                rec = index.records[row][1]
                colour = "#ff8282" if rec["verdict"] == "rejected" else "#eed981"
                pen = QtGui.QPen(QtGui.QColor(colour), .8, Qt.PenStyle.DotLine)
                pen.setCosmetic(True)
                item = scene.addLine(0, row + .5, self._shape[1], row + .5, pen)
                item.setOpacity(.42)
                item.setZValue(8)
                self.review_items.append(item)
                path = QtGui.QPainterPath()
                for lo, hi in runs(index.footprint(row, self._shape[1])):
                    path.moveTo(lo, row + .5)
                    path.lineTo(hi, row + .5)
                pen = QtGui.QPen(QtGui.QColor(colour), 2.1)
                pen.setCosmetic(True)
                item = scene.addPath(path, pen)
                item.setZValue(9)
                self.review_items.append(item)


class Loader(QtCore.QThread):
    loaded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, path, config):
        super().__init__()
        self.path, self.config = path, config

    def run(self):
        try:
            scan = read_scan(self.path)
            surfaces, confidence, meta = AutoSource(self.config["auto_sources"]).load(scan)
            enface = load_enface(scan, self.config["enface_labels"], self.config["proposals"])
            index = SurfaceIndex([Path(self.config["output"]) / "surface_labels", *self.config["manual_sources"]])
            index.refresh(scan)
            region_dir = Path(self.config["output"]) / "regions"
            store = RegionStore(region_dir, scan, enface[0], enface[-1])
            if not store.path.exists():
                for source in self.config.get("region_sources", []):
                    if (Path(source) / f"{scan.scan_id}_regions.json").exists():
                        store = RegionStore(source, scan, enface[0], enface[-1])
                        store.path = region_dir / store.path.name
                        store.disk_hash = None
                        break
            self.loaded.emit((scan, surfaces, confidence, meta, enface, index, store))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MainWindow(QtWidgets.QMainWindow):
    ready = QtCore.Signal()

    def __init__(self, config, paths=None, start_index=0, autoload=True):
        super().__init__()
        self.config = copy.deepcopy(config)
        self.output = Path(config["output"])
        self.paths = paths or sorted(Path(config["segmentations"]).glob("*.npz"))
        if not self.paths:
            raise FileNotFoundError("No scans in configured segmentation directory")
        self.scan = None
        self.store = None
        self.loader = None
        self.row, self.col, self.selected = 0, 0, -1
        self.undo_regions, self.redo_regions = [], []
        self._loading_controls = False
        self._replace_outline = False
        self._selected_index = -1
        editor_class = BoundaryEditor
        if config.get("octa_seg_version") == "octa-seg_v1":
            from octa_seg_v1.reviewer import SegBoundaryEditor
            editor_class = SegBoundaryEditor
        if config.get("quality_review_queue"):
            from quality_pilot.gui import QualityEditor
            editor_class = QualityEditor
        self.editor = editor_class(self.output)
        self.editor.saved.connect(self._boundary_saved)
        self.editor.stepRequested.connect(lambda step: self.navigate(self.row + step, self.col))
        self.editor.cursorColumn.connect(self._cursor_column)
        self.structural = ReviewCanvas("Structural OCT")
        self.octa = ReviewCanvas("OCTA")
        for canvas in (self.structural, self.octa):
            canvas.navigated.connect(self._enface_clicked)
            canvas.strokeFinished.connect(self._outline_drawn)
        self.top = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.top.addWidget(self.panel("Structural OCT en face", self.structural))
        self.top.addWidget(self.panel("OCTA en face", self.octa))
        self.top.addWidget(self._region_panel())
        self.top.setSizes([490, 490, 330])
        self.split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.split.addWidget(self.top)
        self.split.addWidget(self.editor)
        self.split.setSizes([460, 470])
        self.setCentralWidget(self.split)
        self._toolbar()
        if config.get("octa_seg_version") == "octa-seg_v1":
            from octa_seg_v1.reviewer import install_queue
            install_queue(self)
        if config.get("quality_review_queue"):
            from quality_pilot.gui import install_queue as install_quality_queue
            install_quality_queue(self)
        self.setWindowTitle("octa-seg_v1 · CNV boundary evidence review · EXPERIMENTAL"
                            if config.get("octa_seg_version") == "octa-seg_v1"
                            else "CNV region review · separate workspace v1")
        self.resize(1550, 1050)
        self.autosave = QtCore.QTimer(self)
        self.autosave.setSingleShot(True)
        self.autosave.timeout.connect(self.save_all)
        if autoload:
            QtCore.QTimer.singleShot(0, lambda: self.load_scan(start_index))

    @staticmethod
    def panel(title, widget):
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(5, 7, 5, 4)
        layout.addWidget(widget)
        return group

    def _toolbar(self):
        nav = self.addToolBar("Scan and B-scan")
        nav.setMovable(False)
        self.scan_choice = QtWidgets.QComboBox()
        self.scan_choice.setMinimumWidth(350)
        for i, path in enumerate(self.paths):
            self.scan_choice.addItem(f"{i + 1:02d}  {path.stem}")
        self.scan_choice.activated.connect(self.load_scan)
        nav.addWidget(self.scan_choice)
        nav.addAction("Previous scan", lambda: self.load_scan(max(0, self._selected_index - 1)))
        nav.addAction("Next scan", lambda: self.load_scan(min(len(self.paths) - 1, self._selected_index + 1)))
        nav.addSeparator()
        nav.addAction("◀ B-scan", lambda: self.navigate(self.row - 1, self.col))
        self.bscan_choice = QtWidgets.QSpinBox()
        self.bscan_choice.setPrefix("B-scan ")
        self.bscan_choice.setKeyboardTracking(False)
        self.bscan_choice.valueChanged.connect(lambda row: self.navigate(row, self.col))
        nav.addWidget(self.bscan_choice)
        self.bscan_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.bscan_slider.setMinimumWidth(160)
        self.bscan_slider.setTracking(False)
        self.bscan_slider.valueChanged.connect(lambda row: self.navigate(row, self.col))
        nav.addWidget(self.bscan_slider)
        nav.addAction("B-scan ▶", lambda: self.navigate(self.row + 1, self.col))
        nav.addAction("Fit views", self.fit_all)
        self.save_action = nav.addAction("Save all", self.save_all)
        self.addToolBarBreak()
        sources = self.addToolBar("Sources")
        sources.setMovable(False)
        self.auto_label = QtWidgets.QLabel("Loading automatic boundaries…")
        sources.addWidget(self.auto_label)
        sources.addAction("Choose newer auto folder…", self.choose_auto)
        sources.addAction("Reload sources", self.reload_sources)
        self.latest_check = QtWidgets.QCheckBox("Compare latest auto (dotted)")
        self.latest_check.toggled.connect(self._compare_auto)
        self.latest_check.setChecked(bool(self.config.get("compare_latest_auto", False)))
        sources.addWidget(self.latest_check)
        self.nav_bar, self.sources_bar = nav, sources
        shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        shortcut.activated.connect(self.save_all)
        for seq, step in (("PgUp", -1), ("PgDown", 1)):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(seq), self)
            shortcut.activated.connect(lambda s=step: self.navigate(self.row + s, self.col))

    def _region_panel(self):
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        title = QtWidgets.QLabel("<b>Regions & classification</b>")
        layout.addWidget(title)
        self.region_list = QtWidgets.QListWidget()
        self.region_list.setMinimumHeight(75)
        self.region_list.setMaximumHeight(95)
        self.region_list.setStyleSheet("QListWidget {background: #20242a; color: #eeeeee;}")
        self.region_list.currentRowChanged.connect(self.select_region)
        layout.addWidget(self.region_list)
        buttons = QtWidgets.QHBoxLayout()
        for label, callback in (("Draw region", lambda: self.outline_mode(False)),
                                ("Redraw", lambda: self.outline_mode(True)), ("Remove", self.remove_region)):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.mode_label = QtWidgets.QLabel("Click an outline or a B-scan row to inspect.")
        self.mode_label.setWordWrap(True)
        layout.addWidget(self.mode_label)
        self.category = QtWidgets.QComboBox()
        self.category.addItems(CATEGORIES)
        self.category.currentTextChanged.connect(self._category_changed)
        layout.addWidget(self.category)
        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setPlaceholderText("Notes for this region. Other requires an explanation.")
        self.notes.setMinimumHeight(65)
        self.notes.setMaximumHeight(100)
        self.notes.textChanged.connect(self._region_notes_changed)
        layout.addWidget(self.notes)
        self.region_status = QtWidgets.QLabel("")
        self.region_status.setWordWrap(True)
        layout.addWidget(self.region_status)
        undo = QtWidgets.QHBoxLayout()
        for label, fn in (("Undo region edit", self.undo_region), ("Redo", self.redo_region)):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(fn)
            undo.addWidget(button)
        layout.addLayout(undo)
        self.lines_check = QtWidgets.QCheckBox("Show saved B-scan rows / manual strokes")
        self.lines_check.setChecked(True)
        self.lines_check.toggled.connect(self.refresh_overlays)
        layout.addWidget(self.lines_check)
        row = QtWidgets.QHBoxLayout()
        self.near_check = QtWidgets.QCheckBox("Near selected region")
        self.near_check.setChecked(False)
        self.near_check.toggled.connect(self.refresh_manual_list)
        row.addWidget(self.near_check)
        self.margin = QtWidgets.QSpinBox()
        self.margin.setRange(0, 511)
        self.margin.setValue(20)
        self.margin.setSuffix(" rows")
        self.margin.valueChanged.connect(self.refresh_manual_list)
        row.addWidget(self.margin)
        layout.addLayout(row)
        self.manual_list = QtWidgets.QListWidget()
        self.manual_list.setMinimumHeight(90)
        self.manual_list.itemClicked.connect(lambda item: self.navigate(item.data(Qt.ItemDataRole.UserRole), self.col))
        layout.addWidget(self.manual_list)
        self.vessel_status = QtWidgets.QLabel("")
        self.vessel_status.setWordWrap(True)
        self.vessel_status.setStyleSheet("color: #75bfff")
        layout.addWidget(self.vessel_status)
        legend = QtWidgets.QLabel("Yellow: recorded manual stroke spans\nDotted rows: saved reviews (may be untouched)\nBlue: major-vessel footprint in both views\nBoundary editor: left-drag to redraw; H for help.")
        legend.setWordWrap(True)
        layout.addWidget(legend)
        brightness = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        brightness.setRange(-60, 60)
        brightness.valueChanged.connect(lambda v: [c.set_display(v, 110) for c in (self.structural, self.octa)])
        layout.addWidget(QtWidgets.QLabel("En face brightness"))
        layout.addWidget(brightness)
        layout.addStretch()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setMinimumWidth(295)
        return scroll

    def load_scan(self, index):
        if self.loader is not None and self.loader.isRunning():
            return
        if not self.save_all():
            self.scan_choice.setCurrentIndex(max(self._selected_index, 0))
            return
        if not 0 <= index < len(self.paths):
            return
        self.pending_index = index
        self.split.setEnabled(False)
        self.nav_bar.setEnabled(False)
        self.sources_bar.setEnabled(False)
        self.statusBar().showMessage(f"Loading {self.paths[index].stem}: structural/OCTA projections and saved corrections…")
        self.loader = Loader(self.paths[index], self.config)
        self.loader.loaded.connect(self._loaded)
        self.loader.failed.connect(self._load_failed)
        self.loader.start()

    def _loaded(self, result):
        self.scan, self.surfaces, self.confidence, self.auto_meta, enface, self.index, self.store = result
        self.cnv, self.vessels, self.onh, self.onh_edge, self.vessel_meta, _ = enface
        self._selected_index = self.pending_index
        self.scan_choice.setCurrentIndex(self._selected_index)
        self.row, self.col, self.selected = 0, self.scan.native_shape[1] // 2, -1
        self.undo_regions.clear()
        self.redo_regions.clear()
        self.structural.set_image(self.scan.structural_enface)
        self.octa.set_image(self.scan.octa_enface)
        self.auto_label.setText("Auto: " + self.auto_meta["name"] + "   ")
        self.auto_label.setToolTip(self.auto_meta["path"])
        self.vessel_status.setText("Vessels: " + self.vessel_meta["status"])
        self.vessel_status.setToolTip(self.vessel_meta["path"])
        for widget in (self.bscan_choice, self.bscan_slider):
            widget.blockSignals(True)
            widget.setRange(0, self.scan.native_shape[0] - 1)
            widget.setValue(0)
            widget.blockSignals(False)
        self.refresh_regions()
        if self.store.regions:
            self.select_region(0)
        else:
            self.select_region(-1, navigate=False)
            preferred = next((r for r in self.index.records if self.index.footprint(r, self.scan.native_shape[1]).any()), 0)
            self.navigate(preferred, self.col)
        self.split.setEnabled(True)
        self.nav_bar.setEnabled(True)
        self.sources_bar.setEnabled(True)
        date = self.scan.days_post_laser or self.scan.day_label
        self.statusBar().showMessage(f"Ready · {self.scan.scan_id} · day {date} · {len(self.index.records)} saved B-scan reviews")
        def finish_layout():
            self.fit_all()
            self.ready.emit()
        QtCore.QTimer.singleShot(100, finish_layout)

    def _load_failed(self, message):
        self.split.setEnabled(self.scan is not None)
        self.nav_bar.setEnabled(True)
        self.sources_bar.setEnabled(True)
        self.scan_choice.setCurrentIndex(max(self._selected_index, 0))
        self.statusBar().showMessage("Scan could not load; previous review remains available")
        QtWidgets.QMessageBox.critical(self, "Cannot load this scan", message)

    def selected_region(self):
        if self.store is not None and 0 <= self.selected < len(self.store.regions):
            return self.store.regions[self.selected]
        return None

    def selected_footprint(self):
        region = self.selected_region()
        return region.mask[self.row] if region is not None else np.zeros(self.scan.native_shape[1], bool)

    def _enface_clicked(self, row, col):
        if self.scan is None:
            return
        for i, region in enumerate(self.store.regions):
            if region.mask[row, col]:
                self.select_region(i, navigate=False)
                break
        # Snap only close to a displayed saved row; spin/slider retain exact navigation.
        visible = self.visible_rows() if self.lines_check.isChecked() else []
        if visible:
            nearest = min(visible, key=lambda r: abs(r - row))
            if abs(nearest - row) <= 2:
                row = nearest
        self.navigate(row, col)

    def navigate(self, row, col, force=False):
        if self.scan is None:
            return
        row = int(np.clip(row, 0, self.scan.native_shape[0] - 1))
        col = int(np.clip(col, 0, self.scan.native_shape[1] - 1))
        same_line = (self.editor.pack is not None and self.editor.pack.scan_id == self.scan.scan_id
                     and int(self.editor.pack.bscan_index[0]) == row)
        try:
            if not same_line or force:
                self.editor.commit_current()
            self.row, self.col = row, col
            if same_line and not force:
                self.editor.set_footprints(self.vessels[self.row], self.selected_footprint())
            else:
                self.editor.set_line(self.scan, self.row, self.surfaces, self.confidence,
                                     self.index.records.get(self.row), self.auto_meta,
                                     self.vessels[self.row], self.selected_footprint())
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Could not change B-scan", str(exc))
            return
        for widget in (self.bscan_choice, self.bscan_slider):
            widget.blockSignals(True)
            widget.setValue(self.row)
            widget.blockSignals(False)
        for canvas in (self.structural, self.octa):
            canvas.set_cursor(self.row, self.col)
        for i in range(self.manual_list.count()):
            if self.manual_list.item(i).data(Qt.ItemDataRole.UserRole) == self.row:
                self.manual_list.setCurrentRow(i)
                break

    def _cursor_column(self, col):
        if self.scan is not None:
            self.col = int(np.clip(col, 0, self.scan.native_shape[1] - 1))
            for canvas in (self.structural, self.octa):
                canvas.set_cursor(self.row, self.col)

    def select_region(self, index, navigate=True):
        if self._loading_controls or self.store is None:
            return
        self.selected = index
        self._loading_controls = True
        region = self.selected_region()
        self.region_list.setCurrentRow(index)
        self.category.setEnabled(region is not None)
        self.notes.setEnabled(region is not None)
        self.category.setCurrentText(region.category if region else "Unclassified")
        self.notes.setPlainText(region.notes if region else "")
        self._loading_controls = False
        self._classification_status()
        self.refresh_manual_list()
        if region is not None and navigate:
            rows, cols = np.where(region.mask)
            candidates = [r for r in self.index.records if rows.min() - self.margin.value() <= r <= rows.max() + self.margin.value()]
            drawn = [r for r in candidates if self.index.footprint(r, self.scan.native_shape[1]).any()]
            row = min(drawn, key=lambda r: abs(r - np.median(rows))) if drawn else int(np.median(rows))
            self.navigate(row, int(np.median(cols)))
        elif self.scan is not None and self.editor.pack is not None:
            self.editor.set_footprints(self.vessels[self.row], self.selected_footprint())

    def refresh_regions(self):
        if self.store is None:
            return
        self._loading_controls = True
        self.region_list.clear()
        for i, region in enumerate(self.store.regions):
            item = QtWidgets.QListWidgetItem(f"{i + 1} · {region.category}" + (" · needs notes" if region.category == "Other" and not region.complete else ""))
            item.setForeground(QtGui.QColor(COLOURS[region.category]))
            item.setToolTip(region.notes or region.origin)
            self.region_list.addItem(item)
        self.region_list.setCurrentRow(self.selected)
        self._loading_controls = False
        self.refresh_manual_list()

    def visible_rows(self):
        if self.scan is None:
            return []
        rows = sorted(self.index.records)
        region = self.selected_region()
        if self.near_check.isChecked() and region is not None:
            rr = np.flatnonzero(region.mask.any(axis=1))
            rows = [r for r in rows if rr.min() - self.margin.value() <= r <= rr.max() + self.margin.value()]
        return rows

    def refresh_manual_list(self, *args):
        if self.scan is None:
            return
        self.manual_list.clear()
        for row in self.visible_rows():
            path, rec = self.index.records[row]
            drawn = int(self.index.footprint(row, self.scan.native_shape[1]).sum())
            desc = f"B{row:03d} · {rec['verdict']} · {drawn} drawn columns"
            if not rec.get("local_provenance_available"):
                desc = f"B{row:03d} · {rec['verdict']} · legacy, span unknown"
            item = QtWidgets.QListWidgetItem(desc)
            item.setData(Qt.ItemDataRole.UserRole, row)
            item.setToolTip(str(path))
            self.manual_list.addItem(item)
        self.refresh_overlays()

    def refresh_overlays(self, *args):
        if self.scan is None:
            return
        combined = np.zeros(self.scan.native_shape, bool)
        for region in self.store.regions:
            combined |= region.mask
        for canvas in (self.structural, self.octa):
            canvas.set_annotations(combined, self.vessels, self.onh, self.onh_edge)
            canvas.set_reviews(self.store.regions, self.selected, self.index, self.visible_rows(), self.lines_check.isChecked())

    def outline_mode(self, replace):
        if self.scan is None or (replace and self.selected_region() is None):
            return
        self._replace_outline = replace
        for canvas in (self.structural, self.octa):
            canvas.set_mode("cnv_outline")
        self.mode_label.setText("Left-drag a closed outline on either en face view; release to finish. Escape cancels.")

    def _outline_drawn(self, points, operation):
        if self.scan is None or len(points) < 3:
            return
        mask = np.zeros(self.scan.native_shape, bool)
        xy = np.array(points, dtype=float)
        rr, cc = polygon(xy[:, 1], xy[:, 0], shape=mask.shape)
        mask[rr, cc] = True
        if mask.sum() < 3:
            return
        self._push_region_undo()
        if self._replace_outline and self.selected_region() is not None:
            self.selected_region().mask = mask
            self.selected_region().origin = "outline redrawn in lesion review GUI"
        else:
            self.store.regions.append(Region(uuid.uuid4().hex[:12], mask))
            self.selected = len(self.store.regions) - 1
        self.cancel_outline()
        self.refresh_regions()
        self.select_region(self.selected)
        self._schedule_save()

    def cancel_outline(self):
        for canvas in (self.structural, self.octa):
            canvas.set_mode("navigate")
        self.mode_label.setText("Click an outline or a B-scan row to inspect.")

    def _push_region_undo(self):
        self.undo_regions.append((copy.deepcopy(self.store.regions), self.selected))
        self.undo_regions = self.undo_regions[-30:]
        self.redo_regions.clear()

    def remove_region(self):
        if self.selected_region() is None:
            return
        self._push_region_undo()
        self.store.regions.pop(self.selected)
        self.selected = min(self.selected, len(self.store.regions) - 1)
        self.refresh_regions()
        self.select_region(self.selected)
        self._schedule_save()

    def undo_region(self):
        self._history_region(self.undo_regions, self.redo_regions)

    def redo_region(self):
        self._history_region(self.redo_regions, self.undo_regions)

    def _history_region(self, source, destination):
        if self.store is None or not source:
            return
        destination.append((copy.deepcopy(self.store.regions), self.selected))
        self.store.regions, self.selected = source.pop()
        self.refresh_regions()
        self.select_region(self.selected)
        self._schedule_save()

    def _category_changed(self, value):
        region = self.selected_region()
        if self._loading_controls or region is None or region.category == value:
            return
        self._push_region_undo()
        region.category = value
        self.refresh_regions()
        self._classification_status()
        self._schedule_save()

    def _region_notes_changed(self):
        region = self.selected_region()
        if self._loading_controls or region is None:
            return
        if region.notes != self.notes.toPlainText():
            self._push_region_undo()
        region.notes = self.notes.toPlainText()
        self._classification_status()
        self._schedule_save()

    def _classification_status(self):
        region = self.selected_region()
        if region is None:
            self.region_status.setText("Draw a region to classify it.")
        elif region.category == "Other" and not region.notes.strip():
            self.region_status.setText("Other saved as a draft until you add an explanation.")
        elif region.complete:
            self.region_status.setText("Classification complete for this region.")
        else:
            self.region_status.setText("Category awaiting your review.")

    def _schedule_save(self):
        self.statusBar().showMessage("Unsaved changes…")
        self.autosave.start(1000)

    def _boundary_saved(self):
        if self.scan is not None:
            self.index.refresh(self.scan)
            self.refresh_manual_list()

    def save_all(self):
        try:
            self.editor.commit_current()
            if self.store is not None:
                self.store.save(self.auto_meta, [str(p) for p in self.index.roots], self.vessel_meta)
                self.statusBar().showMessage(f"Saved · {self.scan.scan_id} · new review folder")
            return True
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Changes remain unsaved", str(exc))
            return False

    def _compare_auto(self, checked):
        self.editor.show_latest = checked
        self.editor.redraw_surfaces()

    def choose_auto(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Folder containing full-volume automatic boundary NPZs")
        if not directory or self.scan is None or not self.save_all():
            return
        candidate = {"name": Path(directory).name + " (selected automatic source)", "directory": directory}
        previous = self.config["auto_sources"]
        try:
            # Validate the current scan before persisting any source selection.
            AutoSource([candidate]).load(self.scan)
            self.config["auto_sources"] = [candidate] + [s for s in previous if Path(s["directory"]).resolve() != Path(directory).resolve()]
            atomic_json(self.output / "settings.json", self.config)
            self.reload_sources()
        except Exception as exc:
            self.config["auto_sources"] = previous
            QtWidgets.QMessageBox.critical(self, "Automatic folder not selected", str(exc))

    def reload_sources(self):
        if self.scan is None or not self.save_all():
            return
        try:
            surfaces, confidence, meta = AutoSource(self.config["auto_sources"]).load(self.scan)
            _, vessels, onh, edge, vessel_meta, _ = load_enface(self.scan, self.config["enface_labels"], self.config["proposals"])
            self.index.refresh(self.scan)
            self.surfaces, self.confidence, self.auto_meta = surfaces, confidence, meta
            self.vessels, self.onh, self.onh_edge, self.vessel_meta = vessels, onh, edge, vessel_meta
            self.auto_label.setText("Auto: " + meta["name"] + "   ")
            self.auto_label.setToolTip(meta["path"])
            self.vessel_status.setText("Vessels: " + vessel_meta["status"])
            self.refresh_manual_list()
            self.navigate(self.row, self.col, force=True)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Could not reload sources", str(exc))

    def fit_all(self):
        for canvas in (self.structural, self.octa, self.editor.canvas):
            canvas.fit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_outline()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.loader is not None and self.loader.isRunning():
            self.statusBar().showMessage("Volume is still loading; close again when it finishes.")
            event.ignore()
        elif self.save_all():
            self.autosave.stop()
            event.accept()
        else:
            event.ignore()
