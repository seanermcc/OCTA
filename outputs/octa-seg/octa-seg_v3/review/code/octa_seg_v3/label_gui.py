"""GUI-only annotation writer, using the original eight-surface editing canvas."""
import copy
import os
import time
import uuid
from pathlib import Path
import numpy as np
from cnv_review_v1.label_gui import BoundaryEditor, curve_path as inherited_curve_path, Qt, QtCore, QtGui, QtWidgets, legacy
from eight_surface import provenance as P
from .common import V3, read, write, writable, fingerprint, reviewer_id, CATEGORIES, ROLES
from .feedback import resolve
from .policy import render


def curve_path(y, mask=None):
    """Keep single-A-line corrections visible without bridging missing columns."""
    path = inherited_curve_path(y, mask)
    valid = np.isfinite(y)
    if mask is not None:
        valid &= np.asarray(mask, bool)
    single = valid & ~np.r_[False, valid[:-1]] & ~np.r_[valid[1:], False]
    for x in np.flatnonzero(single):
        path.moveTo(float(x) - .5, float(y[x]))
        path.lineTo(float(x) + .5, float(y[x]))
    return path


def reviewer_pack_save(pack, i):
    """The established label serializer, called only by the GUI's staged save."""
    from eight_surface import labels as labels
    from eight_surface.config import CASCADE_VERSION
    state = pack.states[i]
    if state.verdict is None:
        return None
    return labels.save_label(pack.label_dir, scan_id=pack.scan_id, bscan=int(pack.bscan_index[i]),
        verdict=state.verdict, surfaces=state.current, auto_surfaces=state.auto,
        surface_names=pack.names, surface_edited=state.edited, surface_displaced=state.displaced,
        surface_visible=state.visible, surface_reliable=state.reliable, region_excluded=state.excluded,
        local=state.local, px_um=pack.px_um, cascade_version=CASCADE_VERSION,
        seconds_active=state.seconds, n_strokes=state.n_strokes, is_control=bool(pack.is_control[i]),
        labeller=pack.reviewer_id, source_pack=pack.path.name, notes=state.notes)


class Journal:
    """An authoritative, revisioned journal; compatibility NPZs use Pack.save below."""
    def __init__(self, path, identity, legacy_path=None, read_only=False):
        self.read_only = read_only
        self.identity = identity
        self.path = writable(path)
        self.hash = fingerprint(path)
        self.legacy_path = Path(legacy_path) if legacy_path and Path(legacy_path).exists() and not self.hash else None
        self.legacy_hash = fingerprint(self.legacy_path) if self.legacy_path else None
        self.data = read(path) if self.hash else read(self.legacy_path) if self.legacy_path else dict(format='octa-seg-v3-human-events-2',
            **identity, revision=0, events=[], cursor=0, active_seconds=0., history=[])
        for key in ('reviewer_id', 'scan_id', 'bscan', 'model_id'):
            if self.data[key] != identity[key]:
                raise ValueError(f'Annotation {key} differs from this frozen provider. No annotations were changed.')

    @property
    def events(self):
        return self.data['events'][:self.data['cursor']]

    def change(self, event=None, direction=0, seconds=0.):
        if self.read_only:
            return
        # Browsing historical work must never turn into adoption through a timer.
        if self.legacy_path and event is None and direction == 0:
            return
        if event is None and direction == 0 and (seconds <= 0 or not self.data['events']):
            return
        # Existing events/snapshots are immutable. Copy only the containers we edit.
        proposed = self.data.copy()
        proposed['history'] = self.data['history'].copy()
        if self.identity.get('pinned_data_role'):
            proposed['pinned_data_role'] = self.identity['pinned_data_role']
        if self.legacy_path:
            if fingerprint(self.legacy_path) != self.legacy_hash:
                raise RuntimeError('Historical review changed in the older GUI. Reopen it before adopting.')
            proposed['adopted_from'] = dict(path=str(self.legacy_path), sha256=self.legacy_hash,
                legacy_revision=self.data['revision'], timestamp=time.time(), reason='explicit new GUI edit/confirmation')
            proposed['format'] = 'octa-seg-v3-human-events-2'
        if event is not None:
            if proposed['cursor'] < len(proposed['events']):
                proposed['history'].append(dict(action='discarded_redo', events=proposed['events'][proposed['cursor']:]))
            proposed['events'] = proposed['events'][:proposed['cursor']] + [copy.deepcopy(event)]
            proposed['cursor'] = len(proposed['events'])
        else:
            proposed['cursor'] = max(0, min(len(proposed['events']), proposed['cursor'] + direction))
        proposed['revision'] += 1
        proposed['active_seconds'] += max(0., seconds)
        proposed['history'].append(dict(revision=proposed['revision'], timestamp=time.time(), cursor=proposed['cursor'],
            action='event' if event else 'undo' if direction < 0 else 'redo' if direction > 0 else 'active_time'))
        lock = QtCore.QLockFile(str(self.path.with_suffix('.lock')))
        lock.setStaleLockTime(30000)
        if not lock.tryLock(0):
            raise RuntimeError('This review is being saved in another window. Your edits remain here.')
        try:
            if fingerprint(self.path) != self.hash:
                raise RuntimeError('The saved review changed in another window. Reopen before editing; nothing was overwritten.')
            if self.path.exists():
                write(self.path.parent / 'history' / f'{self.path.stem}_r{self.data["revision"]}.json', self.data, compact=True)
            elif self.legacy_path:
                write(self.path.parent / 'history' / f'{self.path.stem}_legacy_original.json', self.data)
            write(self.path, proposed, compact=True)
            self.hash = fingerprint(self.path)
            self.data = proposed
            self.legacy_path = None
        finally:
            lock.unlock()


class Editor(BoundaryEditor):
    changed = QtCore.Signal()

    def __init__(self, output, reviewer):
        self.journal = None
        self.volume = None
        self.resolved = None
        self.rendered = None
        self._loading = True
        self._pending_seconds = 0.
        self.reviewer = reviewer_id(reviewer)
        self.blind = False
        self.read_only = False
        self.width = 512
        self.n_boundaries = 8
        self.pinned_role = None
        super().__init__(output)
        self._loading = False
        self.btn_accept.parentWidget().hide()
        self.verdict_label.hide()
        self.source_label.hide()
        self.line_notes.hide()
        self.info_label.hide()
        self.taper_spin.setValue(30)
        self.taper_spin.setToolTip('Original editor joins. Only the stroke itself becomes manual evidence; joined columns do not.')
        self.only_active.setText('Show selected boundary only')
        self.surface_list.setToolTip('Select a boundary here or use 1–8 / [ ]. Checkboxes only control display.')
        dock = self.findChildren(QtWidgets.QDockWidget)[0]
        dock.setMinimumWidth(300)
        dock.setMaximumWidth(355)
        self.body = dock.widget().widget()
        for button in self.body.findChildren(QtWidgets.QToolButton):
            if 'gestures' in button.text():
                button.hide()
        from .controls import build
        build(self)
        self.canvas.viewport().installEventFilter(self)
        self.canvas.installEventFilter(self)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._save_when_idle)
        self.timer.start(15000)
        self.compatibility_timer = QtCore.QTimer(self)
        self.compatibility_timer.setSingleShot(True)
        self.compatibility_timer.timeout.connect(self._save_when_idle)

    def _save_when_idle(self):
        if self.canvas._drawing or self.canvas._region_dragging:
            self.compatibility_timer.start(500)
            return
        self._save_clicked()

    def fit_image(self):
        super().fit_image()
        if self.pack is not None:
            height = self.pack.images.shape[1]
            scale = self.canvas.transform().m22()
            stretch = min(1.8, max(1., (self.canvas.viewport().height() - 30) / max(1., height * scale)))
            self.canvas.scale(1., stretch)
            self.canvas.centerOn(self.width / 2, height / 2)

    def update_drawing_mode(self, *_):
        uncertain = self.unreliable_draw.isChecked()
        self.unreliable_draw.setText('Draw as unreliable: ' + ('ON' if uncertain else 'OFF'))
        self.unreliable_draw.setStyleSheet('background:#79501f; border:2px solid #ffb020;' if uncertain else '')
        self.drawing_mode_hint.setText('Left-click / drag: ' +
            ('uncertain correction (dashed).' if uncertain else 'reliable correction (solid).') +
            ' Draws new coordinates; right-drag marking keeps existing coordinates.')

    def update_range_summary(self, *_):
        if not hasattr(self, 'range_summary'):
            return
        lo, hi = self.span_lo.value(), self.span_hi.value()
        count = max(0, hi - lo)
        text = (f'Buttons affect {count} A-line' + ('s' if count != 1 else '')
                + (f': {lo}' if count == 1 else f': {lo}–{hi - 1}') + ' on the selected boundary.')
        if self.resolved is not None and self.rendered is not None:
            marked = int((self.resolved['reliability'][self.s] == 0).sum())
            dashed = int(np.isfinite(self.rendered['uncertain_estimates'][self.s]).sum())
            text += f' Across this boundary: {marked} A-lines marked unreliable; {dashed} shown as uncertain candidates.'
        self.range_summary.setText(text)

    def _bank_time(self):
        now = time.monotonic()
        if hasattr(self, '_t0') and self.journal is not None and self.window().isActiveWindow():
            self._pending_seconds += max(0., now - self._t0)
        self._t0 = now
        if self.pack is not None and self.journal is not None:
            self.pack.states[0].seconds = self.journal.data['active_seconds'] + self._pending_seconds

    def set_volume_line(self, volume, row, pinned_role=None):
        self.commit_current()
        self._loading = True
        self.journal = None
        self.rendered = None
        self.resolved = None
        self.volume = volume
        self.row = int(row)
        self.offset = int(volume.data['label_offset'])
        self.width = volume.images.shape[2]
        self.n_boundaries = len(volume.scan.surface_names)
        self.span_lo.setRange(0, self.width - 1)
        self.span_hi.setRange(1, self.width)
        self.pinned_role = pinned_role
        surfaces = volume.data['raw_position_branch'] - self.offset
        self._pending_seconds = 0.
        super().set_line(volume.scan, row, surfaces, np.broadcast_to(np.float32(np.nan), surfaces.shape), None,
            dict(path=volume.entry['directory'], name='frozen raw model · v2 display policy'),
            volume.overlays[1][row], volume.overlays[0][row])
        from types import MethodType
        self.pack.reviewer_id = self.reviewer
        self.pack.save = MethodType(reviewer_pack_save, self.pack)
        identity = dict(reviewer_id=self.reviewer, scan_id=volume.scan.scan_id, bscan=row,
                        model_id=volume.model_id, coordinate_system='native A-line; full canonical depth',
                        source=volume.provenance, boundary_names=list(volume.scan.surface_names), pinned_data_role=pinned_role,
                        training_eligible=not volume.scan.scan_id.startswith('SYNTHETIC'))
        name = f'{volume.scan.scan_id}_b{row:04d}.json'
        self.journal = Journal(self.output / 'journals' / name, identity,
            legacy_path=V3 / 'reviewers' / self.reviewer / 'journals' / name, read_only=self.read_only)
        self._loading = False
        self.recompute()
        self._saved_signature = self.signature()
        self._t0 = time.monotonic()
        self.show_status()

    def show_status(self):
        if self.journal is not None:
            status = 'Legacy · inspect and confirm to adopt' if self.journal.legacy_path else self.resolved['review_status']
            self.status.setText(('Discussion · read only · ' if self.read_only else '') +
                f'B-scan {self.row} · {status}' + (' · existing saved work' if self.journal.data['events'] else ''))

    def recompute(self, resolved=None):
        if self.journal is None:
            return
        self.resolved = resolved if resolved is not None else resolve(
            self.journal.events, self.volume.data['raw_position_branch'][self.row],
            self.offset, self.pack.images.shape[1])
        r = self.resolved
        if self.pinned_role:
            r['metadata']['data_role'] = self.pinned_role
        base = {key: value[self.row] for key, value in self.volume.base.items()}
        self.rendered = render(base, r, self.offset, self.pack.images.shape[1], self.volume.data['shadow'][self.row])
        st = self.pack.states[0]
        st.current = r['positions'] - self.offset
        st.local['local_drawn'] = r['drawn'].copy()
        st.local['local_taper'] = r['taper'].copy()
        st.local['local_displaced'] = r['displaced'].copy()
        st.local['local_reviewed'] = r['reviewed'].copy()
        effective_trace = np.where(r['anatomy'] == 0, 0, r['trace'])
        st.local['local_visibility'] = np.where(effective_trace < 0, P.MARK_UNKNOWN,
            np.where(effective_trace == 1, P.MARK_YES, P.MARK_NO)).astype(np.uint8)
        st.local['local_reliability'] = np.where(r['reliability'] < 0, P.MARK_UNKNOWN,
            np.where(r['reliability'] == 1, P.MARK_YES, P.MARK_NO)).astype(np.uint8)
        st.excluded = r['excluded'].copy()
        st.sync_surface_flags()
        boundary_events = [e for e in self.journal.events if e['action'] != 'case_metadata']
        st.verdict = 'corrected' if boundary_events else None
        st.n_strokes = r['n_strokes']
        st.notes = r['metadata']['notes']
        st.seconds = self.journal.data['active_seconds'] + self._pending_seconds
        self.context.update(reviewer_id=self.reviewer, model_id=self.volume.model_id,
            journal=str(self.journal.path), revision=self.journal.data['revision'],
            metadata=r['metadata'], anatomical_absence_source='v3 journal only; compatibility visibility also denies the boundary')
        self.canvas.set_excluded(st.excluded)
        self.redraw_surfaces()
        self.changed.emit()

    def record_event(self, action, lo=0, hi=None, boundaries=None, **payload):
        if self.journal is None or self.read_only:
            return
        hi = self.width if hi is None else hi
        self._bank_time()
        event = dict(id=uuid.uuid4().hex, timestamp=time.time(), action=action, semantics=3,
                     lo=int(lo), hi=int(hi), boundaries=[self.s] if boundaries is None else boundaries, **payload)
        # Validate before the irreversible file replacement, including metadata inputs.
        resolved = resolve(self.journal.events + [event], self.volume.data['raw_position_branch'][self.row],
                self.offset, self.pack.images.shape[1])
        self.journal.change(event, seconds=self._pending_seconds)
        self._pending_seconds = 0.
        self.recompute(resolved)
        if action == 'stroke':
            # The authoritative journal is already durable. Batch the derived NPZ
            # between gestures; navigation, confirmation, Save and close flush it.
            self.compatibility_timer.start(500)
        else:
            self.commit_current()
        self.show_status()

    def metadata(self, **values):
        if self._loading or self.journal is None:
            return
        if 'categories' in values and any(x not in CATEGORIES for x in values['categories']):
            raise ValueError('Unknown case category')
        if 'data_role' in values and values['data_role'] not in ROLES:
            raise ValueError('Unknown data role')
        if self.pinned_role and 'data_role' in values:
            values['data_role'] = self.pinned_role
        values = {key: value for key, value in values.items() if self.resolved['metadata'].get(key) != value}
        if values:
            self.record_event('case_metadata', boundaries=[], values=values)

    def on_stroke(self, xs, ys):
        if self.journal is None or not len(xs):
            return
        xs = np.clip(xs, 0, self.width - 1)
        ys = np.clip(ys, 0, self.pack.images.shape[1] - 1) + self.offset
        lo, hi = int(np.rint(xs).min()), int(np.rint(xs).max()) + 1
        self.span_lo.setValue(lo)
        self.span_hi.setValue(hi)
        self.record_event('stroke', lo, hi, xs=xs.astype(float).tolist(), ys=ys.astype(float).tolist(),
                   taper=float(self.taper_spin.value()), model_overlay_hidden=self.blind,
                   drawing_reliability='unreliable' if self.unreliable_draw.isChecked() else 'reliable')

    def on_local_marked(self, x0, x1, action):
        lo, hi = sorted((int(np.clip(round(x0), 0, self.width - 1)), int(np.clip(round(x1), 0, self.width - 1))))
        self.span_lo.setValue(lo)
        self.span_hi.setValue(hi + 1)
        mapping = dict(not_visible='not_traceable', visible='traceable', unreliable='unreliable',
                       reliable='reliable', reviewed='reviewed')
        self.action(mapping[action])

    def on_region_marked(self, x0, x1, exclude):
        lo, hi = sorted((int(np.clip(round(x0), 0, self.width - 1)), int(np.clip(round(x1), 0, self.width - 1))))
        self.span_lo.setValue(lo)
        self.span_hi.setValue(hi + 1)
        self.record_event('exclude_image' if exclude else 'clear_exclusion', lo, hi + 1, boundaries=list(range(self.n_boundaries)))

    def displayed(self, k):
        mask = np.isfinite(self.rendered['reported_positions'][k])
        if self.show_candidates.isChecked():
            mask |= np.isfinite(self.rendered['uncertain_estimates'][k])
        if self.blind:
            mask &= self.resolved['drawn'][k] & ~self.resolved['displaced'][k]
        shown = self.surface_list.item(k).checkState() == Qt.CheckState.Checked
        shown &= not self.only_active.isChecked() or k == self.s
        return mask & shown

    def action(self, action):
        if self.journal is None:
            return
        lo, hi = self.span_lo.value(), self.span_hi.value()
        if hi <= lo:
            self.status.setText('Stop A-line must be greater than start.')
            return
        ks = list(range(self.n_boundaries)) if action in ('review_all', 'unreliable_region', 'clear_region', 'exclude_image', 'clear_exclusion') else [self.s]
        if action in ('reviewed', 'review_all', 'approve_position'):
            columns, positions = {}, {}
            for k in ks:
                ok = self.displayed(k) & self.rendered['valid_geometry'][k]
                ok &= ~self.resolved['excluded'] & (self.resolved['anatomy'][k] != 0)
                if action == 'approve_position':
                    ok &= np.isfinite(self.rendered['uncertain_estimates'][k]) & ~self.resolved['displaced'][k]
                cc = np.flatnonzero(ok & (np.arange(self.width) >= lo) & (np.arange(self.width) < hi))
                if len(cc):
                    columns[str(k)] = cc.tolist()
                    positions[str(k)] = self.resolved['positions'][k, cc].astype(float).tolist()
            if not columns:
                self.status.setText('No displayed, valid boundary in this range. Restore visibility explicitly if needed.')
                return
            self.record_event('reviewed' if action == 'review_all' else action, lo, hi,
                       [int(k) for k in columns], columns=columns, positions=positions,
                       model_overlay_hidden=self.blind)
        else:
            self.record_event(action, lo, hi, ks)

    def undo_redo(self, step):
        if self.journal is not None and not self.read_only:
            self._bank_time()
            self.journal.change(direction=step, seconds=self._pending_seconds)
            self._pending_seconds = 0.
            self.recompute()
            self.commit_current()
            self.show_status()

    def set_blind(self, enabled):
        self.blind = enabled
        if not self._loading:
            self.metadata(blinded=bool(enabled))
        self.redraw_surfaces()
        self.changed.emit()

    def eventFilter(self, obj, event):
        if self.read_only and obj in (self.canvas, self.canvas.viewport()) and event.type() in (
                QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseMove, QtCore.QEvent.Type.MouseButtonRelease):
            if event.buttons() & (Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton) or (
                    event.type() == QtCore.QEvent.Type.MouseButtonRelease and event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton)):
                return True
        if obj == self.canvas and event.type() in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
            keys = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Comma, Qt.Key.Key_Period,
                    Qt.Key.Key_PageUp, Qt.Key.Key_PageDown, Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight,
                    Qt.Key.Key_Space, Qt.Key.Key_F, Qt.Key.Key_U, Qt.Key.Key_E)
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            handled = event.key() in keys or Qt.Key.Key_1 <= event.key() <= Qt.Key.Key_8
            handled |= ctrl and event.key() in (Qt.Key.Key_Z, Qt.Key.Key_Y, Qt.Key.Key_S)
            if handled:
                if event.type() == QtCore.QEvent.Type.KeyPress:
                    self.keyPressEvent(event)
                elif event.key() == Qt.Key.Key_Space:
                    self.canvas.set_space(False)
                return True
        if (obj == self.canvas.viewport() and self.journal is not None
                and event.type() == QtCore.QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() == Qt.KeyboardModifier.NoModifier
                and not self.canvas._space and self.auto_pick.isChecked()):
            point = self.canvas.mapToScene(event.position().toPoint())
            x = int(np.clip(round(point.x()), 0, self.width - 1))
            distances = [abs(float(self.resolved['positions'][k, x]) - self.offset - point.y())
                         if self.displayed(k)[x] else np.inf for k in range(self.n_boundaries)]
            k = int(np.argmin(distances))
            tolerance = 12 / max(.01, abs(self.canvas.transform().m22()))
            if distances[k] <= tolerance:
                self.surface_list.setCurrentRow(k)
        return super().eventFilter(obj, event)

    def redraw_surfaces(self):
        if self._loading or self.pack is None:
            return
        super().redraw_surfaces()
        if self.rendered is None:
            return
        for item in list(self._extras):
            if item.pen().style() != Qt.PenStyle.NoPen:
                self.canvas.scene().removeItem(item)
                self._extras.remove(item)
        for item in self.canvas._weak_items:
            item.setPath(QtGui.QPainterPath())
        for k, item in enumerate(self.canvas._surface_items):
            shown = self.surface_list.item(k).checkState() == Qt.CheckState.Checked
            shown &= not self.only_active.isChecked() or k == self.s
            item.setVisible(shown)
            mask = np.ones(self.width, bool) if not self.blind else self.resolved['drawn'][k] & ~self.resolved['displaced'][k]
            item.setPath(curve_path(self.rendered['reported_positions'][k] - self.offset, mask))
            pen = QtGui.QPen(QtGui.QColor(legacy.SURFACE_COLOURS[k]), 2.5 if k == self.s else 1.4)
            pen.setCosmetic(True)
            item.setPen(pen)
            if shown and hasattr(self, 'show_candidates') and self.show_candidates.isChecked():
                pen = QtGui.QPen(QtGui.QColor(legacy.SURFACE_COLOURS[k]), 2.5 if k == self.s else 1.5, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                overlay = self.canvas.scene().addPath(curve_path(self.rendered['uncertain_estimates'][k] - self.offset, mask), pen)
                overlay.setZValue(26)
                self._extras.append(overlay)
        self.update_range_summary()
        # Geometry errors are visible; software movement alone is not uncertainty.
        for k in range(self.n_boundaries):
            bad = self.resolved['unresolved'][k]
            if bad.any():
                pen = QtGui.QPen(QtGui.QColor('#ff3d65'), 3); pen.setCosmetic(True)
                yy = np.full(self.width, 3 + k * 5, dtype=float)
                overlay = self.canvas.scene().addPath(curve_path(yy, bad), pen)
                overlay.setToolTip(f'{self.pack.names[k]}: missing or invalid geometry; correct or mark an exception')
                overlay.setZValue(45); self._extras.append(overlay)

    def update_labels(self):
        pass

    def _on_item_changed(self, item):
        if not self._updating_surface_list:
            self.redraw_surfaces()

    def commit_current(self):
        if hasattr(self, 'compatibility_timer'):
            self.compatibility_timer.stop()
        if self._loading or self.journal is None or self.read_only or self.journal.legacy_path:
            return
        self._bank_time()
        if self.journal.data['events'] and self._pending_seconds >= 1:
            self.journal.change(seconds=self._pending_seconds)
            self._pending_seconds = 0.
        # Merely assigning a case category is not a surface annotation.
        if not any(e['action'] != 'case_metadata' for e in self.journal.data['events']):
            return
        self.context.update(revision=self.journal.data['revision'])
        super().commit_current()

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if ctrl and key in (Qt.Key.Key_Z, Qt.Key.Key_Y):
            self.undo_redo(-1 if key == Qt.Key.Key_Z else 1)
        elif ctrl and key == Qt.Key.Key_S:
            self._save_clicked()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Comma, Qt.Key.Key_PageUp):
            self.stepRequested.emit(-1)
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Period, Qt.Key.Key_PageDown):
            self.stepRequested.emit(1)
        elif key in (Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight):
            self.surface_list.setCurrentRow((self.s + (-1 if key == Qt.Key.Key_BracketLeft else 1)) % self.n_boundaries)
        elif Qt.Key.Key_1 <= key <= Qt.Key.Key_8:
            self.surface_list.setCurrentRow(key - Qt.Key.Key_1)
        elif key == Qt.Key.Key_Space:
            self.canvas.set_space(True)
        elif key == Qt.Key.Key_F:
            self.fit_image()
        elif key == Qt.Key.Key_U:
            self.record_event('clear_marks', 0, self.width)
        elif key == Qt.Key.Key_E:
            self.record_event('clear_exclusion', 0, self.width, list(range(self.n_boundaries)))
        else:
            QtWidgets.QMainWindow.keyPressEvent(self, event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.canvas.set_space(False)
        super().keyReleaseEvent(event)
