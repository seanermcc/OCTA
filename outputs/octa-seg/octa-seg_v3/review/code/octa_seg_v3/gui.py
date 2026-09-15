"""Native v3 reviewer. One navigator switches between en face and thickness."""
import argparse
import json
import random
import time
from pathlib import Path
import numpy as np
from .common import OUT, V2, V3, read, write, reviewer_id, CATEGORIES, ROLES
from .saved import index as saved_index, Browser
from .controls import collapsible
from .data import discover, VolumeCache, THICKNESS_NAMES, THICKNESS_LABELS
from .label_gui import Editor, Qt, QtCore, QtGui, QtWidgets
from .feedback import resolve
from .policy import render
from cnv_review_v1.gui import ReviewCanvas, configure_app
from cnv_review_v1.data import load_enface

GESTURES = '''<b>Editing key</b><br>
Left-click / drag: correct selected boundary<br>
<b>Draw as unreliable ON</b>: dashed best guess<br>
<b>OFF</b>: solid reliable correction<br>
Drawing mode affects only the actual stroke.<br>
Shift + right-drag: <b>not traceable</b><br>
Alt + right-drag: <b>unreliable</b><br>
Ctrl + Shift + right-drag: restore visibility<br>
Ctrl + Alt + right-drag: restore reliability<br>
Shift + left-drag: visible + reliable review<br>
Right-drag: exclude image for all boundaries<br>
Ctrl + right-drag: clear image exclusion<br>
1–8 or [ ]: select boundary<br>
← / → or PgUp / PgDn: previous / next B-scan<br>
Ctrl+Z / Ctrl+Y: undo / redo · Ctrl+S: save<br>
Wheel: zoom · middle-drag / Space: pan · F: fit<br><br>
<b>Case selection key</b><br>
CNV: lesion center, margin or transition<br>
ONH: optic nerve head / nearby tissue<br>
Artifact: shadow, low signal or acquisition artifact<br>
Clear: explicitly readable tissue<br>
Categories can overlap; they are sampling tags.<br>
Especially ambiguous: bookmark the hard subset.<br>
<b>For review</b>: include in the colleagues’ queue.<br>
Case tags do not label any boundary.<br><br>
<b>Boundary key</b><br>
Solid: working measurement (experimental)<br>
Dashes: uncertain position candidate<br>
Gap: no trace, judged absence, or unusable image<br>
Not traceable ≠ anatomically absent.<br>
Joins and moved neighbors keep their reliability.<br>
Missing judgments stay unknown.'''


def configure_v3_app(app):
    configure_app(app)
    app.setStyleSheet(app.styleSheet() + '''
        QWidget {background:#20252c; color:#e6edf3;}
        QLineEdit, QPlainTextEdit, QSpinBox, QComboBox, QListWidget {background:#141a20; color:#e6edf3;}
        QPushButton, QToolButton {padding:4px; background:#343d48; border:1px solid #536170; border-radius:3px;}
        QPushButton:hover, QToolButton:hover {background:#455468;}
        QGroupBox {border:1px solid #45505d; border-radius:4px; margin-top:8px; padding-top:8px;}
        QGroupBox::title {subcontrol-origin:margin; left:7px;}
        QTabBar::tab {padding:5px 12px; background:#303944;}
        QTabBar::tab:selected {background:#436b8b;}
        QCheckBox {spacing:5px;} QScrollArea {border:0;}
        QToolTip {background:#f3f5f7; color:#16202b; border:1px solid #687c91;}
    ''')


class Navigator(ReviewCanvas):
    def review_lines(self, records):
        for item in getattr(self, '_review_lines', []):
            self.scene().removeItem(item)
        self._review_lines = []
        width = self._shape[1]
        for r in records:
            pen = QtGui.QPen(QtGui.QColor('#ffea00'), 2.7,
                Qt.PenStyle.SolidLine if r['status'] == 'Confirmed' else Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            item = self.scene().addLine(0, r['bscan'], width-1, r['bscan'], pen)
            item.setZValue(15)
            item.setToolTip(f'Native B-scan {r["bscan"]} · {r["status"]}')
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._review_lines.append(item)
        self._cursor.setZValue(20)
        pen = QtGui.QPen(QtGui.QColor('#00ffff'), 2, Qt.PenStyle.DashDotLine)
        pen.setCosmetic(True); self._cursor.setPen(pen)

    def show_map(self, values, limits):
        from matplotlib import colormaps
        lo, hi = limits
        finite = np.isfinite(values)
        normalized = np.clip((np.nan_to_num(values, nan=lo) - lo) / max(1., hi - lo), 0, 1)
        rgba = (colormaps['viridis'](normalized) * 255).astype(np.uint8)
        rgba[~finite] = (35, 39, 46, 255)
        rgba = np.ascontiguousarray(rgba)
        q = QtGui.QImage(rgba.data, rgba.shape[1], rgba.shape[0], rgba.strides[0], QtGui.QImage.Format.Format_RGBA8888).copy()
        self._pix.setPixmap(QtGui.QPixmap.fromImage(q))
        self._shape = values.shape
        self.scene().setSceneRect(QtCore.QRectF(q.rect()))
        self._overlay.setVisible(False)


class Window(QtWidgets.QMainWindow):
    ready = QtCore.Signal()

    def __init__(self, reviewer='lead', queue_path=None, entries=None, output=None, autoload=True, cache=None, queue_output=None, read_only=False):
        super().__init__()
        self.read_only = read_only
        self.saved_browser = None
        self.discussion_windows = []
        self.reviewer = reviewer_id(reviewer)
        self.output = Path(output or OUT / 'reviewers' / self.reviewer)
        self.output.mkdir(parents=True, exist_ok=True)
        self.queue_output = Path(queue_output or OUT / 'review_queues')
        self.session_lock = QtCore.QLockFile(str(self.output / 'reviewer_session.lock'))
        self.session_lock.setStaleLockTime(30000)
        if not read_only and not self.session_lock.tryLock(0):
            raise RuntimeError('This reviewer already has a window open. Use that window or a different reviewer ID.')
        self.entries = entries or discover()
        if not self.entries:
            raise FileNotFoundError('No completed segmentation volumes are available.')
        self.by_id = {e['scan_id']: i for i, e in enumerate(self.entries)}
        self.cache = cache or VolumeCache(self.entries)
        self.volume = None
        self.row, self.col, self.scan_index = 256, 256, 0
        self._pending = None
        self._syncing = False
        self._limits = {}
        self._maps = None
        self._last_map_row = None
        self._queue_path = Path(queue_path) if queue_path else None
        self.queue = read(queue_path)['examples'] if queue_path else []
        self.queue_definitions = {(q['scan_id'], q['bscan']): q for q in self.queue}
        self.roles = {}
        old_queue = V2 / 'round_000/review_queue.json'
        if old_queue.exists():
            self.roles.update({(q['scan_id'], q['bscan']): 'assessment' for q in read(old_queue)['examples'] if q['data_role'] == 'assessment'})
        self.roles.update({(q['scan_id'], q['bscan']): q['data_role'] for q in self.queue if q.get('data_role') in ('assessment', 'practice')})
        self.session_path = self.output / 'session.json'
        self.editor = Editor(self.output, self.reviewer)
        self.editor.read_only = read_only
        self.editor.stepRequested.connect(lambda step: self.navigate(self.row + step))
        self.editor.cursorColumn.connect(self.cursor_column)
        self.editor.changed.connect(self.on_editor_changed)
        self.navigator = Navigator('Volume navigator')
        self.navigator.set_mode('navigate')
        self.navigator.navigated.connect(lambda b, x: self.navigate(b, x))
        self.navigator.setMinimumSize(220, 220)
        self.navigator.setMaximumHeight(320)
        left = self.build_left()
        self.build_cases()
        splitter = QtWidgets.QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.editor)
        splitter.setSizes([305, 1375])
        self.setCentralWidget(splitter)
        self.build_navigation()
        if read_only:
            self.editor.tools_box.setEnabled(False)
            self.sampling_box.setEnabled(False)
        self.setWindowTitle(f'octa-seg_v3 review · {self.reviewer} · ' + ('DISCUSSION — READ ONLY' if read_only else 'whole-B-scan confirmation'))
        self.resize(1700, 1030)
        self.poll = QtCore.QTimer(self)
        self.poll.timeout.connect(self.poll_cache)
        self.poll.start(200)
        self.notes_timer = QtCore.QTimer(self)
        self.notes_timer.setSingleShot(True)
        self.notes_timer.timeout.connect(self.save_notes)
        self.started = time.monotonic()
        self.overlay_timer = QtCore.QTimer(self)
        self.overlay_timer.setSingleShot(True)
        self.overlay_timer.timeout.connect(self.refresh_overlays)
        app = QtWidgets.QApplication.instance()
        app.applicationStateChanged.connect(lambda state: self.overlay_timer.start(750) if state == Qt.ApplicationState.ApplicationActive else None)
        self.context_poll = QtCore.QTimer(self)
        self.context_poll.timeout.connect(self.schedule_context_refresh)
        self.context_poll.start(10000)
        self._context_signature = None
        if autoload:
            previous = read(self.session_path) if self.session_path.exists() else {}
            sid = previous.get('scan_id', self.entries[0]['scan_id'])
            self.row = int(previous.get('bscan', 256))
            if self.queue:
                sid = self.queue[0]['scan_id']
                self.row = self.queue[0]['bscan']
            QtCore.QTimer.singleShot(0, lambda: self.goto_queue(1) if self.queue else self.load_scan(self.by_id.get(sid, 0), self.row))

    def build_left(self):
        left = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(left)
        self.left_layout = layout
        layout.setContentsMargins(6, 5, 6, 5)
        self.map_title = QtWidgets.QLabel('<b>Volume navigator</b> · click to select a B-scan')
        self.map_title.setWordWrap(True)
        layout.addWidget(self.map_title)
        layout.addWidget(self.navigator)
        self.review_legend = QtWidgets.QLabel('<b style="color:#ffea00">Yellow — confirmed · - - saved draft / legacy</b><br><span style="color:#00ffff">Cyan: current native B-scan</span>')
        self.review_legend.setWordWrap(True); layout.addWidget(self.review_legend)
        # Both controls are below the same image, as requested.
        self.map_tabs = QtWidgets.QTabBar()
        self.map_tabs.addTab('En face')
        self.map_tabs.addTab('Thickness')
        self.map_tabs.currentChanged.connect(self.change_map_tab)
        layout.addWidget(self.map_tabs)
        self.map_choice = QtWidgets.QComboBox()
        self.map_choice.addItems(['OCT + vessel / CNV / ONH overlays', 'Structural OCT only'])
        self.map_choice.currentIndexChanged.connect(self.update_map)
        layout.addWidget(self.map_choice)
        self.map_scale = QtWidgets.QLabel('')
        self.map_scale.setWordWrap(True)
        layout.addWidget(self.map_scale)
        self.colorbar = QtWidgets.QLabel()
        self.colorbar.setFixedHeight(13)
        self.colorbar.hide()
        layout.addWidget(self.colorbar)
        self.point_value = QtWidgets.QLabel('')
        self.point_value.setWordWrap(True)
        layout.addWidget(self.point_value)
        refresh = QtWidgets.QPushButton('Refresh saved vessel / CNV / ONH overlays')
        refresh.clicked.connect(self.refresh_overlays)
        layout.addWidget(refresh)
        self.experimental_onh = QtWidgets.QCheckBox('Show experimental automatic ONH (v2)')
        self.experimental_onh.setToolTip('The completed learned ONH release has false detections. Opt-in context only; saved human work takes priority.')
        self.experimental_onh.toggled.connect(self.refresh_overlays)
        layout.addWidget(self.experimental_onh)
        self.neighbor_check = QtWidgets.QCheckBox('Show neighboring B-scans')
        self.neighbor_check.toggled.connect(self.show_neighbors)
        layout.addWidget(self.neighbor_check)
        self.neighbors = QtWidgets.QLabel()
        self.neighbors.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.neighbors.setMaximumHeight(180)
        self.neighbors.hide()
        layout.addWidget(self.neighbors)
        key = QtWidgets.QLabel(GESTURES)
        key.setWordWrap(True)
        key.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        key.setStyleSheet('QLabel {font-size:11px;}')
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(key)
        scroll.setMinimumHeight(180)
        layout.addWidget(scroll, 1)
        self.cache_label = QtWidgets.QLabel('Preparing volume cache…')
        self.cache_label.setWordWrap(True)
        self.cache_label.setStyleSheet('QLabel {font-size:11px;color:#9eabb7;}')
        layout.addWidget(self.cache_label)
        left.setMinimumWidth(260)
        left.setMaximumWidth(330)
        return left

    def build_cases(self):
        box = QtWidgets.QGroupBox('This B-scan · sampling and sharing')
        layout = QtWidgets.QVBoxLayout(box)
        layout.setSpacing(3)
        self.category_checks = {}
        grid = QtWidgets.QGridLayout()
        for i, (key, title) in enumerate(CATEGORIES.items()):
            check = QtWidgets.QCheckBox({'artifact': 'Shadow / artifact', 'clear': 'Clear tissue'}.get(key, title))
            check.setToolTip(title)
            check.toggled.connect(self.save_categories)
            grid.addWidget(check, i // 2, i % 2)
            self.category_checks[key] = check
        layout.addLayout(grid)
        self.ambiguous = QtWidgets.QCheckBox('Especially ambiguous')
        self.for_review = QtWidgets.QCheckBox('For review · share with colleagues')
        self.ambiguous.toggled.connect(lambda value: self.set_metadata(especially_ambiguous=value))
        self.for_review.toggled.connect(lambda value: self.set_metadata(for_review=value))
        for check in (self.ambiguous, self.for_review):
            layout.addWidget(check)
        role_row = QtWidgets.QHBoxLayout()
        role_row.addWidget(QtWidgets.QLabel('Data use'))
        self.role = QtWidgets.QComboBox()
        for key, title in ROLES.items():
            self.role.addItem(title, key)
        self.role.currentIndexChanged.connect(lambda index: self.set_metadata(data_role=self.role.itemData(index)))
        role_row.addWidget(self.role)
        layout.addLayout(role_row)
        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setPlaceholderText('Notes: ambiguous boundary, lesion margin, reason…')
        self.notes.setMaximumHeight(45)
        self.notes.textChanged.connect(self.notes_changed)
        layout.addWidget(self.notes)
        self.case_count = QtWidgets.QLabel('')
        self.case_count.setWordWrap(True)
        self.left_layout.insertWidget(3, self.case_count)
        self.sampling_box = box
        collapsible('Sampling, notes and data use', self.editor.body.layout(), box)
        self.editor.body.layout().removeWidget(self.editor.surface_list)
        self.editor.body.layout().insertWidget(0, self.editor.surface_list)

    def build_navigation(self):
        nav = self.addToolBar('Volumes and B-scans')
        nav.setMovable(False)
        nav.addWidget(QtWidgets.QLabel(f'Reviewer: {self.reviewer}  '))
        nav.addAction('< Scan', lambda: self.load_scan(max(0, self.scan_index - 1)))
        self.scan_choice = QtWidgets.QComboBox()
        self.scan_choice.setMinimumWidth(370)
        self.scan_choice.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        for i, entry in enumerate(self.entries):
            self.scan_choice.addItem(f'{i + 1:03d}/{len(self.entries)}  {entry["scan_id"]}')
        self.scan_choice.setEditable(True)
        self.scan_choice.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.scan_choice.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.scan_choice.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.scan_choice.completer().setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self.scan_choice.activated.connect(self.load_scan)
        nav.addWidget(self.scan_choice)
        nav.addAction('Scan >', lambda: self.load_scan(min(len(self.entries) - 1, self.scan_index + 1)))
        nav.addSeparator()
        nav.addAction('< B-scan', lambda: self.navigate(self.row - 1))
        self.bscan = QtWidgets.QSpinBox()
        self.bscan.setPrefix('B ')
        self.bscan.setRange(0, 511)
        self.bscan.setKeyboardTracking(False)
        self.bscan.valueChanged.connect(self.navigate)
        nav.addWidget(self.bscan)
        nav.addAction('B-scan >', lambda: self.navigate(self.row + 1))
        nav.addAction('Fit', self.fit)
        nav.addAction('Save', self.save_all)
        saved_action = nav.addAction('★ My saved reviews', self.show_saved)
        saved_action.setToolTip('Search and resume your drafts, confirmed reviews and historical work')
        nav.addAction('Next unreviewed', self.next_unreviewed)
        self.queue_toggle = nav.addAction('Review lists')
        self.queue_toggle.setCheckable(True)
        self.addToolBarBreak()
        queue = self.addToolBar('Review queue')
        self.queue_toolbar = queue
        queue.setMovable(False)
        self.bscan_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.bscan_slider.setRange(0, 511)
        self.bscan_slider.setTracking(False)
        self.bscan_slider.setMaximumWidth(260)
        self.bscan_slider.valueChanged.connect(self.navigate)
        queue.addWidget(self.bscan_slider)
        self.queue_choice = QtWidgets.QComboBox()
        self.queue_choice.setMinimumWidth(300)
        self.queue_choice.activated.connect(self.goto_queue)
        queue.addWidget(self.queue_choice)
        self.previous_case = queue.addAction('Previous selected B-scan', lambda: self.queue_step(-1))
        self.next_case = queue.addAction('Next selected B-scan', lambda: self.queue_step(1))
        queue.addAction('My flagged cases', self.use_flagged_queue)
        queue.addAction('Export colleagues’ queue', self.export_queue)
        self.progress_label = QtWidgets.QLabel('Independent annotation · saves stay under your reviewer ID')
        queue.addWidget(self.progress_label)
        self.populate_queue()
        settings = QtCore.QSettings('OCTA', 'WholeBscanReview')
        visible = bool(self.queue) or settings.value('review_toolbar', False, type=bool)
        self.queue_toggle.toggled.connect(queue.setVisible)
        self.queue_toggle.toggled.connect(lambda on: settings.setValue('review_toolbar', on))
        self.queue_toggle.setChecked(visible); queue.setVisible(visible)

    def populate_queue(self):
        self.queue_choice.clear()
        self.queue_choice.addItem('Free browsing · all available volumes')
        for i, q in enumerate(self.queue):
            self.queue_choice.addItem(f'{i + 1}/{len(self.queue)} · {q["scan_id"]} · B{q["bscan"]}')
        self.previous_case.setEnabled(bool(self.queue)); self.next_case.setEnabled(bool(self.queue))

    def load_scan(self, index, row=None):
        index = int(index)
        if not 0 <= index < len(self.entries):
            return
        self.save_all()
        target_row = self.row if row is None else int(row)
        entry = self.entries[index]
        # Resolve the case's saved/frozen source before requesting a volume.
        saved = next((r for r in saved_index(self.reviewer, self.output) if r['scan_id'] == entry['scan_id'] and r['bscan'] == target_row), None)
        assignment = self.queue_definitions.get((entry['scan_id'], target_row))
        bound = saved['source'].get('provider') if saved else assignment.get('provider') if assignment else None
        if bound:
            entry = dict(entry, directory=bound)
        if self.cache.entries[entry['scan_id']]['directory'] != entry['directory']:
            with self.cache.lock:
                self.cache.cache.pop(entry['scan_id'], None)
                pending = self.cache.pending.pop(entry['scan_id'], None)
                if pending and not pending.done():
                    pending.cancel()
                self.cache.entries[entry['scan_id']] = entry
        self.editor.setEnabled(False)
        self.scan_choice.setCurrentIndex(index)
        self.statusBar().showMessage('Loading ' + entry['scan_id'] + '…')
        value, future = self.cache.request(entry['scan_id'], foreground=True)
        self._pending = (index, target_row, future)
        if value is not None:
            self.install_volume(value, index, target_row, cached=True)

    def poll_cache(self):
        if self._pending is not None:
            index, row, future = self._pending
            if future is not None and future.done():
                self._pending = None
                try:
                    self.install_volume(future.result(), index, row, cached=False)
                except Exception as exc:
                    self.editor.setEnabled(self.volume is not None)
                    self.scan_choice.setCurrentIndex(self.scan_index)
                    self.statusBar().showMessage(f'Could not load scan: {exc}')
                    QtWidgets.QMessageBox.critical(self, 'Scan unavailable', str(exc))
        state = self.cache.status()
        self.cache_label.setText(f'Cache: {len(state["ready"])} volume(s) ready · {len(state["loading"])} loading\n'
            f'{state["bytes"] / 1024**3:.2f} / {state["budget"] / 1024**3:.1f} GB · next two prefetched when memory permits')
        mins = (time.monotonic() - self.started) / 60
        if mins >= 30:
            self.progress_label.setText(f'{mins:.0f} min · a good point for a break; saved edits remain available')

    def install_volume(self, volume, index, row, cached):
        self._pending = None
        self.volume = volume
        self.scan_index = index
        self._maps = volume.thickness.copy()
        for control in (self.bscan, self.bscan_slider):
            control.blockSignals(True); control.setRange(0, volume.images.shape[0]-1); control.blockSignals(False)
        # Load this reviewer's journals only; other people's strokes never preload.
        for entry in saved_index(self.reviewer, self.output):
            if entry['scan_id'] != volume.scan.scan_id or entry['model_id'] != volume.model_id:
                continue
            path = Path(entry['path'])
            record = read(path)
            if record['reviewer_id'] != self.reviewer or record['model_id'] != volume.model_id:
                raise ValueError('A saved annotation does not match this reviewer/provider')
            b = record['bscan']
            r = resolve(record['events'][:record['cursor']], volume.data['raw_position_branch'][b],
                        int(volume.data['label_offset']), volume.images.shape[1])
            out = render({k: a[b] for k, a in volume.base.items()}, r, int(volume.data['label_offset']),
                         volume.images.shape[1], volume.data['shadow'][b])
            self._maps[b] = out['thickness_um']
        self.editor.setEnabled(True)
        self.navigate(row)
        self.update_map()
        self.refresh_overlays()
        self.fit()
        self.scan_choice.setCurrentIndex(index)
        self.cache.prefetch([e['scan_id'] for e in self.entries[index + 1:index + 3]])
        self.statusBar().showMessage(f'{volume.scan.scan_id} · 512 B-scans · '
            + ('opened from cache' if cached else f'loaded in {volume.seconds:.1f}s') + f' · images in {volume.image_mode}')
        self.ready.emit()

    def navigate(self, row, col=None):
        if self.volume is None or self._pending is not None:
            return
        self.save_all()
        target_row = int(np.clip(row, 0, self.volume.images.shape[0]-1))
        saved = next((r for r in saved_index(self.reviewer, self.output) if r['scan_id'] == self.volume.scan.scan_id and r['bscan'] == target_row), None)
        if saved and saved['model_id'] != self.volume.model_id:
            self.load_scan(self.scan_index, target_row)
            return
        self.row = target_row
        if col is not None:
            self.col = int(np.clip(col, 0, self.volume.images.shape[2]-1))
        key = (self.volume.scan.scan_id, self.row)
        assignment = self.queue_definitions.get(key)
        if assignment and assignment.get('model_id') and assignment['model_id'] != self.volume.model_id:
            self.editor.setEnabled(False)
            raise ValueError('Shared queue provider has changed. Restore the frozen source before independent review.')
        self.notes.clearFocus()
        self.editor.set_volume_line(self.volume, self.row, self.roles.get(key))
        if assignment:
            self.editor.blind_check.setChecked(assignment.get('hide_model', False))
        for widget in (self.bscan, self.bscan_slider):
            widget.blockSignals(True)
            widget.setValue(self.row)
            widget.blockSignals(False)
        self.navigator.set_cursor(self.row, self.col)
        self.show_neighbors(self.neighbor_check.isChecked())
        self.update_point()
        if not self.read_only:
            write(self.session_path, dict(reviewer_id=self.reviewer, scan_id=key[0], bscan=self.row))
        self.update_review_lines()

    def cursor_column(self, col):
        if self.volume is not None:
            self.col = int(np.clip(col, 0, self.volume.images.shape[2]-1))
            self.navigator.set_cursor(self.row, self.col)
            self.update_point()

    def on_editor_changed(self):
        if self.editor.resolved is None or self.volume is None or not hasattr(self, 'role'):
            return
        self._syncing = True
        meta = self.editor.resolved['metadata']
        for key, check in self.category_checks.items():
            check.setChecked(key in meta['categories'])
        self.ambiguous.setChecked(meta['especially_ambiguous'])
        self.for_review.setChecked(meta['for_review'])
        self.role.setCurrentIndex(self.role.findData(meta['data_role']))
        self.role.setEnabled(self.editor.pinned_role is None)
        self.role.setToolTip('Reserved by the assessment/shared manifest; cannot be used for development fitting.' if self.editor.pinned_role else '')
        if self.notes.toPlainText() != meta['notes'] and not self.notes.hasFocus():
            self.notes.setPlainText(meta['notes'])
        self._syncing = False
        self._maps[self.row] = self.editor.rendered['thickness_um']
        self.map_tabs.setTabEnabled(1, not self.editor.blind)
        if self.editor.blind and self.map_tabs.currentIndex() == 1:
            self.map_tabs.setCurrentIndex(0)
        if hasattr(self, 'map_choice') and self.map_tabs.currentIndex() == 1:
            self.update_map()
        self.update_point()
        self.case_count.setText(f'{self.reviewer} · revision {self.editor.journal.data["revision"]} · case tags are separate from boundary marks')
        self.update_review_lines()

    def set_metadata(self, **kwargs):
        if not self._syncing:
            self.editor.metadata(**kwargs)

    def save_categories(self):
        self.set_metadata(categories=[k for k, check in self.category_checks.items() if check.isChecked()])

    def notes_changed(self):
        if not self._syncing and hasattr(self, 'notes_timer'):
            self.notes_timer.start(600)

    def save_notes(self):
        if self.editor.journal is not None and not self._syncing:
            self.editor.metadata(notes=self.notes.toPlainText())

    def save_all(self):
        if self.read_only:
            return
        if hasattr(self, 'notes_timer') and self.notes_timer.isActive():
            self.notes_timer.stop()
            self.save_notes()
        self.editor.commit_current()

    def change_map_tab(self, index):
        self.map_choice.blockSignals(True)
        self.map_choice.clear()
        if index == 0:
            self.map_choice.addItems(['OCT + vessel / CNV / ONH overlays', 'Structural OCT only'])
        else:
            for key in THICKNESS_NAMES:
                self.map_choice.addItem(THICKNESS_LABELS.get(key, key), key)
            self.map_choice.setCurrentIndex(THICKNESS_NAMES.index('TOTAL'))
        self.map_choice.blockSignals(False)
        self.update_map()

    def update_map(self):
        if self.volume is None:
            return
        if self.map_tabs.currentIndex() == 0:
            self.navigator.set_image(self.volume.structural)
            cnv, vessel, onh, edge = self.volume.overlays[:4]
            self.navigator.set_annotations(cnv, vessel, onh, edge)
            self.navigator._overlay.setVisible(self.map_choice.currentIndex() == 0)
            self.map_scale.setText('Red: CNV · blue: vessel · green: ONH\n' + self.volume.overlays[4]['status'])
            self.colorbar.hide()
        else:
            key = self.map_choice.currentData()
            if key not in THICKNESS_NAMES:
                return
            values = self._maps[:, THICKNESS_NAMES.index(key), :]
            identity = (self.volume.scan.scan_id, key)
            if identity not in self._limits:
                finite = values[np.isfinite(values)]
                limits = tuple(np.percentile(finite, [2, 98])) if len(finite) else (0., 300.)
                self._limits[identity] = (float(limits[0]), float(max(limits[0] + 1, limits[1])))
            limits = self._limits[identity]
            self.navigator.show_map(values, limits)
            self.map_scale.setText(f'{limits[0]:.1f} – {limits[1]:.1f} µm · {np.isfinite(values).mean():.0%} coverage\n'
                'Measurements only; uncertain, absent and shadowed locations stay blank. Scale stays fixed while editing.')
            from matplotlib import colormaps
            bar = np.ascontiguousarray((colormaps['viridis'](np.linspace(0, 1, 256))[None, :, :] * 255).astype(np.uint8))
            q = QtGui.QImage(bar.data, 256, 1, bar.strides[0], QtGui.QImage.Format.Format_RGBA8888).copy()
            self.colorbar.setPixmap(QtGui.QPixmap.fromImage(q).scaled(280, 12))
            self.colorbar.show()
        self.navigator.set_cursor(self.row, self.col)
        self.update_review_lines()
        self.update_point()

    def update_point(self):
        if self.volume is None:
            return
        text = f'B-scan {self.row} · A-line {self.col}'
        if self.map_tabs.currentIndex() == 1 and self.map_choice.currentData() in THICKNESS_NAMES:
            key = self.map_choice.currentData()
            value = self._maps[self.row, THICKNESS_NAMES.index(key), self.col]
            text += f' · {value:.2f} µm' if np.isfinite(value) else ' · no reportable thickness'
        if self.editor.resolved is not None:
            r, k = self.editor.resolved, self.editor.s
            state = self.editor.rendered['state'][k, self.col]
            detail = 'anatomically absent/interrupted' if r['anatomy'][k, self.col] == 0 else {1: 'working measurement', 2: 'not traceable', 3: 'uncertain'}[int(state)]
            text += f'\n{self.volume.scan.surface_names[k]}: {detail}'
        self.point_value.setText(text)

    def refresh_overlays(self):
        if self.volume is None:
            return
        if self.editor.canvas._drawing or self.editor.canvas._region_dragging:
            self.overlay_timer.start(500)
            return
        from .common import ROOT, BATCH
        proposal = V2 / 'proposals'
        if not (proposal / f'{self.volume.scan.scan_id}_proposal.npz').exists():
            proposal = BATCH / 'proposals'
        from .providers import context_overlays
        try:
            self.volume.overlays = context_overlays(self.volume, proposal, experimental_onh=self.experimental_onh.isChecked())
        except Exception as exc:
            self.statusBar().showMessage('Context refresh unavailable: ' + str(exc))
            return
        if not self.read_only:
            exposure = self.output / 'context_exposure' / (self.volume.scan.scan_id + '.json')
            old = read(exposure) if exposure.exists() else []
            source = self.volume.overlays[4]
            if not old or old[-1]['source'] != source:
                write(exposure, old + [dict(timestamp=time.time(), source=source, reviewer=self.reviewer)])
        self.editor.set_footprints(self.volume.overlays[1][self.row], self.volume.overlays[0][self.row])
        self.update_map()

    def show_neighbors(self, enabled):
        self.neighbors.setVisible(enabled)
        if enabled and self.volume is not None:
            image = np.concatenate([self.volume.images[max(0, self.row - 1)], self.volume.images[min(self.volume.images.shape[0]-1, self.row + 1)]], axis=0)
            lo, hi = np.percentile(image, [2, 99])
            pixels = np.ascontiguousarray((np.clip((image - lo) / max(.01, hi - lo), 0, 1) * 255).astype(np.uint8))
            q = QtGui.QImage(pixels.data, pixels.shape[1], pixels.shape[0], pixels.strides[0], QtGui.QImage.Format.Format_Grayscale8).copy()
            self.neighbors.setPixmap(QtGui.QPixmap.fromImage(q).scaled(280, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def fit(self):
        self.navigator.fit()
        self.editor.fit_image()

    def flagged(self):
        self.save_all()
        result = []
        for entry in saved_index(self.reviewer, self.output, include_tags=True):
            path = Path(entry['path'])
            record = read(path)
            meta = {}
            for event in record['events'][:record['cursor']]:
                if event['action'] == 'case_metadata':
                    meta.update(event['values'])
            if meta.get('for_review') and record['scan_id'] in self.by_id:
                role = self.roles.get((record['scan_id'], record['bscan']), meta.get('data_role', 'development'))
                result.append(dict(scan_id=record['scan_id'], bscan=record['bscan'], data_role=role,
                    provider=record['source'].get('provider', self.entries[self.by_id[record['scan_id']]]['directory']), model_id=record['model_id'],
                    especially_ambiguous=bool(meta.get('especially_ambiguous')), categories=meta.get('categories', [])))
        return result

    def use_flagged_queue(self):
        self.queue = self.flagged()
        self.populate_queue()
        self.queue_toggle.setChecked(True)
        self.progress_label.setText(f'{len(self.queue)} of your flagged cases · original annotations stay private')

    def export_queue(self):
        rows = self.flagged()
        if not rows:
            self.statusBar().showMessage('Mark at least one B-scan “For review” first.')
            return
        rng = random.Random(20260914)
        ambiguous = [i for i, r in enumerate(rows) if r['especially_ambiguous']]
        other = [i for i in range(len(rows)) if i not in ambiguous]
        hidden = set(rng.sample(ambiguous, min(5, len(ambiguous))) + rng.sample(other, min(5, len(other))))
        # Sampling reasons and the lead's notes/labels are intentionally not delivered.
        examples = [{k: v for k, v in row.items() if k not in ('especially_ambiguous', 'categories')} |
                    dict(hide_model=i in hidden) for i, row in enumerate(rows)]
        rng.shuffle(examples)
        queue = dict(format='octa-seg-v3-independent-queue-1', created_at=time.time(),
                     author=self.reviewer, seed=20260914, examples=examples,
                     annotations_included=False, instructions='Annotate independently before discussion. Use a unique reviewer ID. '
                     'No other reviewer labels preload. Preserve uncertainty; do not infer absence from poor visibility.')
        destination = self.queue_output / f'shared_{self.reviewer}_{time.time_ns()}.json'
        write(destination, queue)
        write(self.queue_output / 'latest_shared.json', dict(path=str(destination)))
        self.statusBar().showMessage(f'Exported {len(rows)} cases. Colleagues can open OPEN_SHARED_REVIEW.cmd with their own reviewer ID.')
        self.progress_label.setText(f'Shared queue: {len(rows)} cases · {len(hidden)} start without the model overlay')
        return destination

    def goto_queue(self, index):
        if index <= 0 or index > len(self.queue):
            return
        q = self.queue[index - 1]
        self.queue_toggle.setChecked(True)
        self.queue_choice.setCurrentIndex(index)
        if q['scan_id'] not in self.by_id:
            QtWidgets.QMessageBox.warning(self, 'Queue source unavailable', q['scan_id'])
            return
        if self.volume is None or self.volume.scan.scan_id != q['scan_id']:
            self.load_scan(self.by_id[q['scan_id']], q['bscan'])
        else:
            self.navigate(q['bscan'])
            self.editor.blind_check.setChecked(q.get('hide_model', False))

    def queue_step(self, step):
        if self.queue:
            index = int(np.clip(self.queue_choice.currentIndex() + step, 1, len(self.queue)))
            self.goto_queue(index)

    def closeEvent(self, event):
        try:
            self.save_all()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, 'Review remains unsaved', str(exc))
            event.ignore()
            return
        self.poll.stop()
        self.editor.timer.stop()
        self.context_poll.stop(); self.overlay_timer.stop()
        self.cache.close()
        if not self.read_only:
            self.session_lock.unlock()
        event.accept()

    def update_review_lines(self):
        if self.volume is None or not hasattr(self, 'case_count'):
            return
        records = saved_index(self.reviewer, self.output)
        current = [r for r in records if r['scan_id'] == self.volume.scan.scan_id]
        self.navigator.review_lines(current)
        confirmed = {(r['scan_id'], r['bscan']) for r in records if r['status'] == 'Confirmed'}
        remaining = sum((q['scan_id'], q['bscan']) not in confirmed for q in self.queue)
        self.case_count.setText(f'{len(records)} saved · {len(confirmed)} confirmed · {remaining} assigned remaining\n'
            f'{len(current)} saved / {self.volume.images.shape[0]} available B-scans in this volume · {len(self.entries)} volumes available')

    def show_saved(self):
        self.save_all()
        if self.saved_browser is None: self.saved_browser = Browser(self)
        self.saved_browser.refresh(); self.saved_browser.show(); self.saved_browser.raise_()

    def open_saved(self, record, discussion=False):
        if discussion or record['reviewer'] != self.reviewer:
            self.save_all()
            if not self.read_only:
                path = self.output / 'discussion_exposure.json'
                entries = read(path) if path.exists() else []
                write(path, entries + [dict(timestamp=time.time(), observer=self.reviewer, owner=record['reviewer'],
                    scan_id=record['scan_id'], bscan=record['bscan'], source_record=record['path'])])
            output = OUT / 'reviewers' / record['reviewer']
            # Isolated synthetic tests keep their reviewer directory, too.
            if record['reviewer'] == self.reviewer: output = self.output
            window = Window(record['reviewer'], entries=self.entries, output=output, autoload=False, read_only=True)
            self.discussion_windows.append(window)
            window.show(); window.load_scan(window.by_id[record['scan_id']], record['bscan'])
        else:
            self.load_scan(self.by_id[record['scan_id']], record['bscan'])

    def next_unreviewed(self):
        records = {(r['scan_id'], r['bscan']): r for r in saved_index(self.reviewer, self.output)}
        if self.queue:
            candidates = [(self.by_id[q['scan_id']], q['bscan']) for q in self.queue if q['scan_id'] in self.by_id
                and records.get((q['scan_id'], q['bscan']), {}).get('status') != 'Confirmed']
        else:
            candidates = [(i, b) for i, entry in enumerate(self.entries) for b in range(self.volume.images.shape[0])
                if (entry['scan_id'], b) not in records]
            candidates.sort(key=lambda pair: (pair <= (self.scan_index, self.row), pair))
        if candidates: self.load_scan(*candidates[0])
        else: self.statusBar().showMessage('No remaining cases in this review list.')

    def schedule_context_refresh(self):
        if self.volume is None: return
        from .providers import context_signature
        signature = context_signature(self.volume.scan.scan_id)
        if signature != self._context_signature:
            self._context_signature = signature
            self.overlay_timer.start(750)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reviewer')
    parser.add_argument('--queue', type=Path)
    parser.add_argument('--shared', action='store_true')
    parser.add_argument('--read-only', action='store_true', help='Inspect real records without writing annotations')
    parser.add_argument('--scan')
    parser.add_argument('--bscan', type=int, default=256)
    args = parser.parse_args()
    app = QtWidgets.QApplication([])
    configure_v3_app(app)
    if args.shared:
        latest = OUT / 'review_queues/latest_shared.json'
        if not latest.exists():
            latest = V3 / 'review_queues/latest_shared.json'
        if not latest.exists():
            QtWidgets.QMessageBox.information(None, 'No shared queue yet', 'The lead reviewer must first flag cases and export a colleagues’ queue.')
            return
        args.queue = Path(read(latest)['path'])
    if not args.reviewer:
        value, ok = QtWidgets.QInputDialog.getText(None, 'Your reviewer ID',
            'Enter your own name/ID. Each reviewer saves independently.\nUse “lead” for your initial selection and corrections.', text='' if args.shared else 'lead')
        if not ok:
            return
        args.reviewer = value
    try:
        window = Window(args.reviewer, args.queue, autoload=not bool(args.scan), read_only=args.read_only)
    except Exception as exc:
        QtWidgets.QMessageBox.critical(None, 'Unable to open reviewer', str(exc))
        return
    window.show()
    screen = window.screen().availableGeometry()
    window.resize(min(1700, screen.width() - 30), min(1030, screen.height() - 60))
    def record_ready():
        import os
        write(OUT / 'runtime' / f'window_{os.getpid()}.json', dict(pid=os.getpid(), reviewer_id=window.reviewer,
            scan_id=window.volume.scan.scan_id, bscan=window.row, visible=window.isVisible(),
            volumes_available=len(window.entries), timestamp=time.time()))
    window.ready.connect(record_ready)
    if args.scan:
        QtCore.QTimer.singleShot(0, lambda: window.load_scan(window.by_id[args.scan], args.bscan))
    QtCore.QTimer.singleShot(150, window.fit)
    app.exec()


if __name__ == '__main__':
    main()
