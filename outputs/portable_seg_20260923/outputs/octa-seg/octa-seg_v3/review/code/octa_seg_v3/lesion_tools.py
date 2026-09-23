"""Lesion tools on the existing B-scan canvas; all writes stay in Editor.record_event."""
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from . import lesions as L
from .context_policy import vessel_columns

Qt = QtCore.Qt


class LesionTools:
    def __init__(self, editor):
        self.editor = editor
        self.mode = None
        self.gesture = None
        self.buttons = {}
        for key, title in [('cnv_region', 'CNV region'), ('cnv_edge', 'CNV edge'), ('hyper_ref', 'Hyper_Ref')]:
            button = QtWidgets.QPushButton(title)
            button.setCheckable(True)
            button.setObjectName(key)
            button.setStyleSheet('QPushButton:checked {background:#52527e; border:2px solid #d9aaff;}')
            button.toggled.connect(lambda checked, k=key: self.select(k if checked else None))
            self.buttons[key] = button
        self.buttons['cnv_region'].setToolTip('Left-drag across the lesion: mark full-depth columns. Ctrl+drag clears. Separate from image exclusion and automatic CNV context.')
        self.buttons['cnv_edge'].setToolTip('Tentative: bottom edge of the dark outer-retinal lesion above RPE. Left-drag traces; Ctrl+drag erases. No joins to other curves or ordering changes.')
        self.buttons['hyper_ref'].setToolTip('Tentative: hyperreflective dots inside the CNV lesion, above/separate from RPE. Left-drag paints; E or Ctrl+drag erases.')
        self.dial = QtWidgets.QDial()
        self.dial.setRange(1, 80)
        self.dial.setValue(9)
        self.dial.setFixedSize(32, 32)
        self.dial.setAccessibleName('Hyper_Ref brush diameter')
        self.dial.setNotchesVisible(True)
        self.size_label = QtWidgets.QLabel('9 px')
        self.size_label.setMinimumWidth(34)
        self.dial.valueChanged.connect(self.size_changed)
        self.buttons['hyper_ref'].setMaximumWidth(130)
        self.erase = QtWidgets.QPushButton('Erase')
        self.erase.setCheckable(True)
        self.erase.setFixedWidth(55)
        self.erase.setToolTip('Erase on/off (E). Left-drag removes the selected retinal boundary, CNV region, CNV edge or Hyper_Ref. Undo restores it.')
        self.erase.setStyleSheet('QPushButton:checked {background:#9a3942; border:2px solid #ff9098;}')
        self.dial.setToolTip('Brush diameter in native image pixels (9 px); unaffected by zoom.')
        self.erase.toggled.connect(lambda _: self.cancel())
        self.show = QtWidgets.QCheckBox('Show manual CNV / Hyper_Ref')
        self.show.setChecked(True)
        self.show.toggled.connect(self.visibility_changed)
        scene = editor.canvas.scene()
        self.region_item = scene.addPath(QtGui.QPainterPath())
        self.region_item.setPen(QtGui.QPen(Qt.PenStyle.NoPen))
        self.region_item.setBrush(QtGui.QColor(172, 107, 235, 35))
        self.region_item.setZValue(4)
        self.mask_item = scene.addPixmap(QtGui.QPixmap())
        self.mask_item.setZValue(22)
        self.edge_items = [scene.addPath(QtGui.QPainterPath()) for _ in range(2)]
        for item in self.edge_items:
            item.setZValue(32)
        self.preview = scene.addPath(QtGui.QPainterPath())
        self.preview.setZValue(51)
        self.cursor_item = scene.addEllipse(QtCore.QRectF())
        self.cursor_item.setZValue(52)
        self.cursor_item.hide()
        for item in [self.region_item, self.mask_item, *self.edge_items, self.preview, self.cursor_item]:
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        editor.surface_list.currentRowChanged.connect(lambda _: self.select(None))
        editor.surface_list.itemClicked.connect(lambda _: self.select(None))

    def size_changed(self, size):
        self.size_label.setText(f'{size} px')
        self.dial.setToolTip(f'Brush diameter in native image pixels ({size} px); unaffected by zoom.')
        self.cursor_item.hide()

    def visibility_changed(self, visible):
        if not visible:
            self.cancel()
        self.render()
        from .controls import sync_all_boundaries
        sync_all_boundaries(self.editor)

    def select(self, mode):
        self.cancel()
        self.mode = mode
        if mode == 'cnv_region':
            # Tool precedence only: never replay a reliability/traceability edit here.
            self.editor.mark_mode = None
            for button in self.editor.mark_buttons.values():
                button.blockSignals(True)
                button.setChecked(False)
                button.blockSignals(False)
            if hasattr(self.editor, 'unreliable_draw'):
                self.editor.unreliable_draw.setChecked(False)
        for key, button in self.buttons.items():
            button.blockSignals(True)
            button.setChecked(mode == key)
            button.blockSignals(False)
        self.dial.setEnabled(mode == 'hyper_ref')
        if hasattr(self.editor, 'mark_buttons'):
            for button in self.editor.mark_buttons.values():
                button.setEnabled(mode in (None, 'cnv_edge'))
        if hasattr(self.editor, 'unreliable_draw'):
            self.editor.unreliable_draw.setEnabled(mode in (None, 'cnv_edge'))
        if mode is not None:
            self.show.setChecked(True)
        self.editor.canvas.setFocus()
        if hasattr(self.editor, 'mark_hint'):
            from .controls import set_mark_mode
            set_mark_mode(self.editor, self.editor.mark_mode, self.editor.mark_mode is not None)
            if mode in ('cnv_region', 'hyper_ref'):
                self.editor.mark_hint.setText('Left-drag: ' + ('mark CNV columns; Ctrl+drag clears' if mode == 'cnv_region' else 'paint Hyper_Ref; E toggles erase'))
        if self.editor.rendered is not None:
            self.editor.redraw_surfaces()

    def cancel(self):
        if self.gesture is not None:
            self.editor.canvas._drawing = False
        self.gesture = None
        self.preview.setPath(QtGui.QPainterPath())
        self.cursor_item.hide()

    def handle_event(self, obj, event):
        e, c = self.editor, self.editor.canvas
        if obj != c.viewport():
            return False
        typ = event.type()
        if typ == QtCore.QEvent.Type.Leave:
            self.cursor_item.hide()
        mode = self.mode or ('retinal_erase' if self.erase.isChecked() else None)
        if mode is None or e.journal is None:
            return False
        if typ not in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseMove, QtCore.QEvent.Type.MouseButtonRelease):
            return False
        if c._space or (event.buttons() & Qt.MouseButton.MiddleButton):
            return False
        p = c.mapToScene(event.position().toPoint())
        height = e.pack.images.shape[1]
        inside = 0 <= p.x() <= e.width-1 and 0 <= p.y() <= height-1
        x, y = float(np.clip(p.x(), 0, e.width-1)), float(np.clip(p.y(), 0, height-1))
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        if self.mode == 'hyper_ref' and inside:
            radius = self.dial.value() / 2.
            pen = QtGui.QPen(QtGui.QColor('#ff7070' if ctrl or self.erase.isChecked() else '#ffffff'), 1.3)
            pen.setCosmetic(True)
            self.cursor_item.setPen(pen)
            self.cursor_item.setRect(x-radius, y-radius, 2*radius, 2*radius)
            self.cursor_item.show()
        else:
            self.cursor_item.hide()
        if typ == QtCore.QEvent.Type.MouseButtonPress:
            if mode == 'retinal_erase' and event.button() != Qt.MouseButton.LeftButton:
                return False
            if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
                return False
            if not inside:
                return True
            mark = None
            if self.mode == 'cnv_edge' and event.button() == Qt.MouseButton.RightButton:
                if shift:
                    mark = 'traceable' if ctrl else 'not_traceable'
                elif alt:
                    mark = 'reliable' if ctrl else 'unreliable'
                elif not ctrl:
                    mark = {'not_visible': 'not_traceable', 'unreliable': 'unreliable'}.get(e.mark_mode)
                    if mark is None:
                        return False  # Existing whole-image exclusion gesture.
            self.gesture = dict(points=[(x, y)], mode=mode, mark=mark, boundary=e.s,
                                erase=ctrl or self.erase.isChecked(),
                                diameter=self.dial.value(), unreliable=e.unreliable_draw.isChecked())
            c._drawing = True
            self.draw_preview()
            return True
        if self.gesture is not None:
            self.gesture['points'].append((x, y))
            self.draw_preview()
            c.cursorMoved.emit(x, y)
            if typ == QtCore.QEvent.Type.MouseButtonRelease:
                gesture = self.gesture
                self.cancel()
                points = np.asarray(gesture.pop('points'))
                lo, hi = int(np.rint(points[:, 0]).min()), int(np.rint(points[:, 0]).max()) + 1
                e.span_lo.setValue(lo); e.span_hi.setValue(hi)
                mode, mark = gesture.pop('mode'), gesture.pop('mark')
                boundary = gesture.pop('boundary')
                if mode == 'retinal_erase':
                    e.record_event('erase_boundary', lo, hi, boundaries=[boundary])
                    return True
                payload = dict(lesion_definition=L.DEFINITION_VERSION)
                if mark:
                    mode = 'cnv_edge_mark'
                    payload['mark'] = mark
                else:
                    payload.update(gesture, xs=points[:, 0].tolist(), ys=(points[:, 1]+e.offset).tolist())
                e.record_event(mode, lo, hi, boundaries=[], **payload)
            return True
        return False

    def draw_preview(self):
        g = self.gesture
        points = g['points']
        path = QtGui.QPainterPath()
        if g['mode'] in ('cnv_region', 'retinal_erase') or g['mark'] or (g['mode'] == 'cnv_edge' and g['erase']):
            xs = [p[0] for p in points]
            path.addRect(min(xs), 0, max(1., max(xs)-min(xs)), self.editor.pack.images.shape[1])
        else:
            path.moveTo(*points[0])
            for p in points[1:]:
                path.lineTo(*p)
        pen = QtGui.QPen(QtGui.QColor('#ff7070' if g['erase'] else '#ffd870'),
                        g['diameter'] if g['mode'] == 'hyper_ref' else 2.)
        pen.setCosmetic(g['mode'] != 'hyper_ref')
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.preview.setPen(pen)
        self.preview.setOpacity(.5)
        self.preview.setPath(path)

    def render(self):
        e = self.editor
        if e.resolved is None or e._loading:
            return
        state = e.resolved['lesions']
        visible = self.show.isChecked()
        for item in [self.region_item, self.mask_item, *self.edge_items]:
            item.setVisible(visible)
        path = QtGui.QPainterPath()
        for lo, hi in L.runs(state['cnv_region']):
            path.addRect(lo-.5, 0, hi-lo, state['hyper_ref'].shape[0])
        self.region_item.setPath(path)
        rgba = np.zeros((*state['hyper_ref'].shape, 4), np.uint8)
        rgba[state['hyper_ref']] = (255, 202, 59, 110)
        image = QtGui.QImage(rgba.data, rgba.shape[1], rgba.shape[0], rgba.strides[0], QtGui.QImage.Format.Format_RGBA8888).copy()
        self.mask_item.setPixmap(QtGui.QPixmap.fromImage(image))
        from .label_gui import curve_path
        edge_state = state['cnv_edge_state'].copy()
        shadowed = vessel_columns(e.volume, e.row) | e.rendered['effective_shadow_mask']
        edge_state[(edge_state == 1) & shadowed] = 2
        for code, item in zip((1, 2), self.edge_items):
            pen = QtGui.QPen(QtGui.QColor('#f59cff'), 2.7 if self.mode == 'cnv_edge' else 1.8,
                            Qt.PenStyle.SolidLine if code == 1 else Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            item.setPen(pen)
            item.setPath(curve_path(state['cnv_edge']-e.offset, edge_state == code))
        if self.mode:
            # Hide the inherited selected-layer judgment ruler while a lesion tool is active.
            for item in [*e.canvas._band_items.values(), *e.canvas._ruler_items.values()]:
                item.setPath(QtGui.QPainterPath())
