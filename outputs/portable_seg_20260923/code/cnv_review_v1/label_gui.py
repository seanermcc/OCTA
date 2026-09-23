"""Embedded mature boundary editor, saving only to this GUI's output folder."""
from __future__ import annotations

import hashlib
import pickle
import time
import uuid
from pathlib import Path

import numpy as np

from eight_surface import labels as L, provenance as P
from eight_surface.label_gui import MainWindow as BaseEditor, Pack, BscanState, legacy
from eight_surface.cnv_gui import QtCore, QtGui, QtWidgets
from .data import atomic_json, fingerprint, runs

Qt = QtCore.Qt


def curve_path(y, mask=None):
    y = np.asarray(y)
    mask = np.isfinite(y) if mask is None else (np.asarray(mask, bool) & np.isfinite(y))
    path = QtGui.QPainterPath()
    for lo, hi in runs(mask):
        path.moveTo(float(lo), float(y[lo]))
        if hi == lo + 1:
            path.lineTo(lo + 0.35, float(y[lo]))
        for x in range(lo + 1, hi):
            path.lineTo(float(x), float(y[x]))
    return path


class BoundaryEditor(BaseEditor):
    saved = QtCore.Signal()
    stepRequested = QtCore.Signal(int)
    cursorColumn = QtCore.Signal(int)

    def __init__(self, output):
        self.output = Path(output)
        self._saved_signature = None
        self._disk_hash = None
        self.context = {}
        self.show_latest = False
        self._extras = []
        self._vessels = None
        self._lesion = None
        super().__init__([], self.output / "surface_labels")
        self.setWindowFlags(Qt.WindowType.Widget)
        self.canvas.cursorMoved.connect(lambda x, y: self.cursorColumn.emit(round(x)))
        self.canvas.fit = self.fit_image
        dock = self.findChildren(QtWidgets.QDockWidget)[0]
        body = dock.widget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        dock.setWidget(scroll)
        dock.setMinimumWidth(320)
        dock.setMaximumWidth(420)
        self.surface_list.setMinimumHeight(150)
        self.surface_list.setMaximumHeight(190)
        self.source_label = QtWidgets.QLabel("")
        self.source_label.setWordWrap(True)
        body.layout().insertWidget(0, self.source_label)
        self.line_notes = QtWidgets.QPlainTextEdit()
        self.line_notes.setPlaceholderText("Notes for this B-scan (separate from region notes)")
        self.line_notes.setMaximumHeight(65)
        self.line_notes.textChanged.connect(self._notes_changed)
        body.layout().insertWidget(3, self.line_notes)
        save = QtWidgets.QPushButton("Save boundary edits · Ctrl+S")
        save.clicked.connect(self._save_clicked)
        body.layout().insertWidget(4, save)
        self.progress.hide()
        self.info_label.setWordWrap(True)
        self.btn_revert.setToolTip("Restores the original automatic baseline of this annotation, preserving that baseline when resuming older corrections.")

    def _build_side_panel(self):
        dock = QtWidgets.QDockWidget("Boundary editing", self)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(7, 5, 7, 5)
        self.surface_list = QtWidgets.QListWidget()
        self.surface_list.setAlternatingRowColors(True)
        self.surface_list.setStyleSheet("QListWidget {background: #20242a; alternate-background-color: #2b3038; color: #eeeeee;}")
        self.surface_list.currentRowChanged.connect(self.set_surface)
        self.surface_list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.surface_list)
        group = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(group)
        row.setContentsMargins(0, 0, 0, 0)
        self.btn_accept = QtWidgets.QPushButton("Accept")
        self.btn_reject = QtWidgets.QPushButton("Reject")
        self.btn_revert = QtWidgets.QPushButton("Reset all")
        for button, callback in ((self.btn_accept, lambda: self.set_verdict("accepted")),
                                  (self.btn_reject, lambda: self.set_verdict("rejected")),
                                  (self.btn_revert, self.revert_all)):
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addWidget(group)
        self.verdict_label = QtWidgets.QLabel("Unreviewed")
        layout.addWidget(self.verdict_label)
        display = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(display)
        form.setContentsMargins(0, 0, 0, 0)
        self.lo_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.lo_slider.setRange(0, 50)
        self.lo_slider.setValue(2)
        self.hi_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.hi_slider.setRange(50, 100)
        self.hi_slider.setValue(100)
        for label, slider in (("Black %", self.lo_slider), ("White %", self.hi_slider)):
            slider.valueChanged.connect(self.redraw_image)
            form.addRow(label, slider)
        self.taper_spin = QtWidgets.QSpinBox()
        self.taper_spin.setRange(0, 200)
        self.taper_spin.setValue(30)
        form.addRow("Join length (A-lines)", self.taper_spin)
        self.only_active = QtWidgets.QCheckBox("Show selected boundary only")
        self.only_active.toggled.connect(self.redraw_surfaces)
        form.addRow(self.only_active)
        layout.addWidget(display)
        help_button = QtWidgets.QToolButton()
        help_button.setText("Editing gestures & uncertainty marks")
        help_button.setCheckable(True)
        layout.addWidget(help_button)
        help_text = QtWidgets.QLabel(
            "Left-drag: redraw selected boundary\n"
            "Shift+right-drag: cannot identify locally\n"
            "Alt+right-drag: locally unreliable\n"
            "Add Ctrl to those gestures to restore\n"
            "Shift+left-drag: reviewed as correct\n"
            "Right-drag: exclude columns for every boundary\n"
            "Ctrl+right-drag: clear column exclusion\n"
            "Ctrl+Z / Ctrl+Y: undo / redo boundary edit\n"
            "V: whole-boundary visibility · U: clear local marks\n"
            "[ / ]: select boundary · wheel: zoom · Space: pan\n"
            "Checkboxes exclude an unreliable boundary from analysis.")
        help_text.setWordWrap(True)
        help_text.hide()
        help_button.toggled.connect(help_text.setVisible)
        layout.addWidget(help_text)
        self.progress = QtWidgets.QLabel("")
        layout.addWidget(self.progress)
        layout.addStretch()
        dock.setWidget(body)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def fit_image(self):
        if self.pack is None:
            return
        height, width = self.pack.images[0].shape
        lateral_um = 1460.0 / width
        axial_um = self.pack.px_um
        viewport = self.canvas.viewport()
        factor = min(max(1, viewport.width() - 12) / (width * lateral_um),
                     max(1, viewport.height() - 12) / (height * axial_um))
        self.canvas.setTransform(QtGui.QTransform.fromScale(factor * lateral_um, factor * axial_um))
        self.canvas.centerOn(width / 2, height / 2)

    def _bank_time(self):
        now = time.monotonic()
        if self.pack is not None and self.window().isActiveWindow():
            self.pack.states[0].seconds += now - self._t0
        self._t0 = now

    def load_pack(self, *args, **kwargs):
        return False  # the linked main window supplies the selected image in memory

    def _rebuild_surface_list(self):
        # The inherited reader sets tooltips after unblocking QListWidget.
        # Qt emits itemChanged for tooltips too, before its restored checkbox
        # values are applied. Treat the entire rebuild as presentation-only.
        previous = self._updating_surface_list
        self._updating_surface_list = True
        try:
            super()._rebuild_surface_list()
        finally:
            self._updating_surface_list = previous

    def _notes_changed(self):
        if self.pack is not None:
            self.pack.states[0].notes = self.line_notes.toPlainText()

    def signature(self):
        if self.pack is None:
            return None
        s = self.pack.states[0]
        return hashlib.sha256(pickle.dumps((s._snapshot(), s.verdict, s.notes, s.n_strokes), protocol=5)).digest()

    def set_line(self, scan, row, surfaces, confidence, record_pair, auto_source, vessel, lesion):
        self.commit_current()
        self._bank_time()
        # Pack.save is the existing provenance-aware writer. No label file is
        # made to preload a previous annotation or to browse an automatic line.
        pack = object.__new__(Pack)
        pack.path = Path(f"{scan.scan_id}_b{row:04d}_linked_pack.npz")
        pack.label_dir = self.label_dir
        pack.names = list(scan.surface_names)
        pack.retired = []
        pack.images = scan.structural_bscan(row)[None]
        pack.surfaces = surfaces[row:row + 1]
        pack.confidence = confidence[row:row + 1]
        pack.shadow = scan.shadow[row:row + 1]
        pack.bscan_index = np.array([row])
        pack.is_control = np.array([False])
        pack.suspect = np.array([np.nan])
        pack.scan_id, pack.px_um = scan.scan_id, scan.px_um
        pack.selection_role = np.array(["linked_region_review"])
        pack.lesion_zone = None
        pack.zone_names = []
        pack.n_preloaded = int(record_pair is not None)
        state = BscanState(surfaces[row].copy(), len(pack.names))
        previous_path = ""
        saved_geometry = False
        stale_review_columns = 0
        if record_pair:
            previous_path, rec = record_pair
            previous_path = str(previous_path)
            state.current = rec["surfaces"].astype(float).copy()
            state.auto = rec["auto_surfaces"].astype(float).copy()
            for attr, key in (("edited", "surface_edited"), ("displaced", "surface_displaced"),
                              ("visible", "surface_visible"), ("reliable", "surface_reliable"),
                              ("excluded", "region_excluded")):
                setattr(state, attr, np.asarray(rec[key], bool).copy())
            state.local = L.local_arrays(rec)
            state.verdict = rec["verdict"]
            secs = float(rec.get("seconds_active", 0))
            state.seconds = secs if np.isfinite(secs) else 0.0
            state.n_strokes = max(int(rec.get("n_strokes", 0)), 0)
            state.notes = str(rec.get("notes", ""))
            pack.is_control[0] = bool(rec.get("is_control", False))
            saved_geometry = bool(state.edited.any() or state.displaced.any()
                                  or any(state.local[key].any() for key in ("local_drawn", "local_taper", "local_displaced")))
            if not saved_geometry:
                # An accepted/rejected image with no correction is not a manual
                # trace. Show the current provider there, preserving image-level
                # and boundary uncertainty decisions. A previous acceptance of a
                # different automatic position cannot accept a new prediction.
                changed = ~np.isclose(state.current, surfaces[row], atol=1e-5, rtol=0, equal_nan=True)
                stale_review_columns = int((state.local["local_reviewed"] & changed).sum())
                state.local["local_reviewed"][changed] = False
                state.local["local_reliability"][changed & (state.local["local_reliability"] == P.MARK_YES)] = P.MARK_UNKNOWN
                state.current = surfaces[row].astype(float).copy()
                state.auto = surfaces[row].astype(float).copy()
                if changed.any() and state.verdict == "accepted":
                    state.verdict = None
        pack.states = [state]
        self.pack, self.i, self.pi = pack, 0, 0
        self.pack_paths = [pack.path]
        self.context = dict(scan_id=scan.scan_id, bscan=row, source_volume=str(scan.source_volume),
                            retina_band=list(scan.retina_band), canonical_vitreous_at_depth_zero=True,
                            auto_source=auto_source, resumed_label=previous_path,
                            resumed_label_sha256=fingerprint(previous_path) if previous_path else None,
                            saved_manual_geometry_restored=saved_geometry,
                            prior_position_reviews_not_transferred=stale_review_columns,
                            time_scope="active linked-review window (en face and B-scan together)")
        self._disk_hash = fingerprint(L.label_path(self.label_dir, scan.scan_id, row))
        self._saved_signature = self.signature()
        self._t0 = time.monotonic()
        self.line_notes.blockSignals(True)
        self.line_notes.setPlainText(state.notes)
        self.line_notes.blockSignals(False)
        self._rebuild_surface_list()
        self.canvas.ensure_surface_items(len(pack.names), legacy.SURFACE_COLOURS)
        self._vessels, self._lesion = vessel.copy(), lesion.copy()
        self.show_bscan(0, fit=False)
        self.source_label.setText(
            (f"B-scan {row} · saved {state.verdict} traces\n" if saved_geometry else f"B-scan {row} · latest automatic boundaries\n")
            + "Solid: direct strokes · dashed: automatic/joined traces\n"
            + "Blue columns: vessel footprint, depth unknown")
        self.source_label.setToolTip(previous_path or auto_source["path"])
        self.info_label.setText(f"B-scan {row} · {scan.scan_id}")

    def commit_current(self):
        if self.pack is None or self._saved_signature is None:
            return
        self._bank_time()
        if self.signature() == self._saved_signature:
            return
        state = self.pack.states[0]
        destination = L.label_path(self.label_dir, self.pack.scan_id, int(self.pack.bscan_index[0]))
        if fingerprint(destination) != self._disk_hash:
            raise RuntimeError("This boundary annotation changed in another window. Unsaved edits remain here; resolve the other window before saving.")
        if state.verdict is None:
            state.verdict = "corrected"  # explicit local mark or note, never mere viewing
        # Have the established GUI Pack.save serialize in a staging directory,
        # then atomically publish. Existing revisions in this new folder survive.
        staging = self.output / "staging" / uuid.uuid4().hex
        staging.mkdir(parents=True, exist_ok=True)
        original_dir = self.pack.label_dir
        try:
            self.pack.label_dir = staging
            written = self.pack.save(0)
            if destination.exists():
                history = self.output / "surface_history"
                history.mkdir(parents=True, exist_ok=True)
                (history / f"{destination.stem}_{time.time_ns()}.npz").write_bytes(destination.read_bytes())
            Path(written).replace(destination)
        finally:
            self.pack.label_dir = original_dir
            if staging.exists() and not list(staging.iterdir()):
                staging.rmdir()
        self._disk_hash = fingerprint(destination)
        self._saved_signature = self.signature()
        atomic_json(self.output / "surface_context" / f"{destination.stem}.json", self.context)
        self.saved.emit()

    def _save_clicked(self):
        try:
            self.commit_current()
            self.statusBar().showMessage("Boundary edits saved", 2500)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Boundary edits remain unsaved", str(exc))

    def next_bscan(self, step):
        self.stepRequested.emit(step)

    def jump_next_unreviewed(self):
        self.stepRequested.emit(1)

    def set_verdict(self, verdict):
        if self.pack is None:
            return
        self.pack.states[0].verdict = verdict
        self.update_labels()  # rejection remains accessible; no surprise navigation

    def redraw_surfaces(self):
        super().redraw_surfaces()
        if self.pack is None:
            return
        scene = self.canvas.scene()
        for item in self._extras:
            scene.removeItem(item)
        self._extras = []
        state = self.pack.states[0]
        ndepth, width = self.pack.images[0].shape
        for footprint, colour, alpha in ((self._vessels, "#289fff", 0.13), (self._lesion, "#ff625b", 0.05)):
            if footprint is None:
                continue
            path = QtGui.QPainterPath()
            strip = QtGui.QPainterPath()
            for lo, hi in runs(footprint):
                path.addRect(lo - .5, 0, hi - lo, ndepth)
                strip.addRect(lo - .5, 9, hi - lo, 5)
            item = scene.addPath(path, QtGui.QPen(Qt.PenStyle.NoPen), QtGui.QBrush(QtGui.QColor(colour)))
            item.setOpacity(alpha)
            item.setZValue(2)
            self._extras.append(item)
            if footprint is self._vessels:
                item = scene.addPath(strip, QtGui.QPen(Qt.PenStyle.NoPen), QtGui.QBrush(QtGui.QColor(colour)))
                item.setZValue(41)
                self._extras.append(item)
        for k, item in enumerate(self.canvas._surface_items):
            if k >= len(self.pack.names):
                continue
            item.setPath(curve_path(state.current[k]))
            pen = item.pen()
            pen.setStyle(Qt.PenStyle.DashLine)
            item.setPen(pen)
            if not item.isVisible():
                continue
            drawn = state.local["local_drawn"][k]
            uncertain = ((state.local["local_visibility"][k] == P.MARK_NO)
                         | (state.local["local_reliability"][k] == P.MARK_NO)
                         | state.local["local_displaced"][k] | state.excluded
                         | ~state.visible[k] | ~state.reliable[k])
            for mask, colour, style in ((drawn & ~uncertain, legacy.SURFACE_COLOURS[k], Qt.PenStyle.SolidLine),
                                         (drawn & uncertain, "#ffb45c", Qt.PenStyle.DashLine)):
                pen = QtGui.QPen(QtGui.QColor(colour), 2.5, style)
                pen.setCosmetic(True)
                overlay = scene.addPath(curve_path(state.current[k], mask), pen)
                overlay.setZValue(24)
                self._extras.append(overlay)
            if self.show_latest:
                pen = QtGui.QPen(QtGui.QColor(legacy.SURFACE_COLOURS[k]), 1, Qt.PenStyle.DotLine)
                pen.setCosmetic(True)
                overlay = scene.addPath(curve_path(self.pack.surfaces[0, k]), pen)
                overlay.setOpacity(.6)
                overlay.setZValue(8)
                self._extras.append(overlay)

    def set_footprints(self, vessel, lesion):
        self._vessels, self._lesion = vessel, lesion
        self.redraw_surfaces()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_S and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._save_clicked()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        try:
            self.commit_current()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Boundary edits remain unsaved", str(exc))
            event.ignore()
            return
        event.accept()
