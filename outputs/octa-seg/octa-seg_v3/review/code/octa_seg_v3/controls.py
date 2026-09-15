"""Visible review tools; all annotation mutations go through Editor.record_event."""
import time
import numpy as np
from PySide6 import QtCore, QtWidgets
from .feedback import CONTRACT, STATE_KEYS, state_digest

KEY = ('<b>Confirm entire B-scan approves the final segmentation, including unchanged automatic curves. '
       'Your unreliable and not-traceable marks remain exceptions.</b><br><br>'
       'This confirms every boundary across the B-scan. Uncertain and untraceable areas are useful '
       'training judgments without becoming reliable positional targets.')


def collapsible(title, parent_layout, widget):
    toggle = QtWidgets.QToolButton()
    toggle.setText('▸ ' + title)
    toggle.setCheckable(True)
    toggle.toggled.connect(widget.setVisible)
    toggle.toggled.connect(lambda on: toggle.setText(('▾ ' if on else '▸ ') + title))
    parent_layout.addWidget(toggle)
    parent_layout.addWidget(widget)
    widget.hide()
    return toggle


def build(editor):
    e = editor
    box = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    row = QtWidgets.QHBoxLayout()
    e.mark_buttons = {}
    for title, mode in [('Unreliable', 'unreliable'), ('Not traceable', 'not_visible')]:
        button = QtWidgets.QPushButton(title)
        button.setObjectName('mark_' + mode)
        button.setCheckable(True)
        button.setStyleSheet('QPushButton:checked {background:#855b13; border:2px solid #ffdb55;}')
        button.toggled.connect(lambda checked, m=mode: set_mark_mode(e, m, checked))
        e.mark_buttons[mode] = button
        row.addWidget(button)
    layout.addLayout(row)
    e.mark_mode = None
    e.mark_hint = QtWidgets.QLabel('Right-drag: unusable image for every boundary')
    e.mark_hint.setWordWrap(True)
    layout.addWidget(e.mark_hint)
    e.unreliable_draw = QtWidgets.QPushButton()
    e.unreliable_draw.setCheckable(True)
    e.unreliable_draw.toggled.connect(e.update_drawing_mode)
    layout.addWidget(e.unreliable_draw)
    e.drawing_mode_hint = QtWidgets.QLabel('')
    e.drawing_mode_hint.setWordWrap(True)
    layout.addWidget(e.drawing_mode_hint)
    e.update_drawing_mode()
    buttons = QtWidgets.QHBoxLayout()
    for title, callback in [('Clear marks in last span', lambda: e.action('clear_marks')),
                            ('Undo', lambda: e.undo_redo(-1)), ('Redo', lambda: e.undo_redo(1))]:
        b = QtWidgets.QPushButton(title); b.clicked.connect(callback); buttons.addWidget(b)
    layout.addLayout(buttons)
    e.confirm_button = QtWidgets.QPushButton('Confirm entire B-scan')
    e.confirm_button.setObjectName('confirm_bscan')
    e.confirm_button.setStyleSheet('font-weight:bold; font-size:15px; padding:10px; background:#285f44; border:2px solid #7ecb97;')
    e.confirm_button.clicked.connect(lambda: confirm(e))
    layout.addWidget(e.confirm_button)
    e.status = QtWidgets.QLabel('Draft · left-drag corrects the selected boundary')
    e.status.setWordWrap(True); layout.addWidget(e.status)
    e.confirm_key = QtWidgets.QLabel(KEY)
    e.confirm_key.setWordWrap(True)
    e.confirm_key.setStyleSheet('font-size:12px; padding:6px; background:#29333d;')
    layout.addWidget(e.confirm_key)
    advanced = QtWidgets.QWidget()
    adv = QtWidgets.QVBoxLayout(advanced)
    adv.setContentsMargins(0, 0, 0, 0)
    e.auto_pick = QtWidgets.QCheckBox('Nearest boundary picking: OFF')
    e.auto_pick.setChecked(False)
    e.auto_pick.toggled.connect(lambda on: e.auto_pick.setText('Nearest boundary picking: ' + ('ON' if on else 'OFF')))
    adv.addWidget(e.auto_pick)
    e.show_candidates = QtWidgets.QCheckBox('Show uncertain positions (dashes)')
    e.show_candidates.setChecked(True); e.show_candidates.toggled.connect(e.redraw_surfaces)
    adv.addWidget(e.show_candidates)
    e.blind_check = QtWidgets.QCheckBox('Draw without model overlay')
    e.blind_check.toggled.connect(e.set_blind); adv.addWidget(e.blind_check)
    e.span_lo, e.span_hi = QtWidgets.QSpinBox(), QtWidgets.QSpinBox()
    e.span_lo.setRange(0, 511); e.span_hi.setRange(1, 512); e.span_hi.setValue(512)
    span = QtWidgets.QHBoxLayout()
    span.addWidget(QtWidgets.QLabel('Native start / stop'))
    span.addWidget(e.span_lo); span.addWidget(e.span_hi); adv.addLayout(span)
    e.range_summary = QtWidgets.QLabel(''); e.range_summary.setWordWrap(True); adv.addWidget(e.range_summary)
    e.span_lo.valueChanged.connect(e.update_range_summary); e.span_hi.valueChanged.connect(e.update_range_summary)
    for title, action in [('Anatomically absent / interrupted', 'absent'), ('Clear anatomical absence', 'clear_absence'),
                          ('All boundaries unreliable in span', 'unreliable_region'), ('Clear regional mark', 'clear_region'),
                          ('Exclude image in span (all boundaries)', 'exclude_image'), ('Clear image exclusion', 'clear_exclusion'),
                          ('Reset selected boundary in span', 'reset_boundary')]:
        b = QtWidgets.QPushButton(title); b.clicked.connect(lambda _, a=action: e.action(a)); adv.addWidget(b)
    collapsible('Advanced boundary tools and display', layout, advanced)
    e.body.layout().insertWidget(0, box)
    e.tools_box = box
    # Keep mature mouse handling, but inject latched intent only for unmodified right drag.
    original = e.canvas._intent
    def intent(button, mods, space):
        if not space and button == QtCore.Qt.MouseButton.RightButton and mods == QtCore.Qt.KeyboardModifier.NoModifier:
            return e.mark_mode or original(button, mods, space)
        return original(button, mods, space)
    e.canvas._intent = intent


def set_mark_mode(e, mode, checked):
    if checked:
        for name, button in e.mark_buttons.items():
            if name != mode:
                button.blockSignals(True); button.setChecked(False); button.blockSignals(False)
        e.mark_mode = mode
    elif e.mark_mode == mode:
        e.mark_mode = None
    e.mark_hint.setText('Right-drag: ' + {'unreliable': 'mark selected boundary unreliable (dashes)',
        'not_visible': 'mark selected boundary not traceable (gap)', None: 'unusable image for every boundary'}[e.mark_mode])


def json_array(a):
    if np.issubdtype(a.dtype, np.floating):
        return np.where(np.isfinite(a), a, None).tolist()
    return a.tolist()


def confirm(e):
    if e.journal is None or e.read_only:
        return False
    hidden = (e.only_active.isChecked() or e.blind or not e.show_candidates.isChecked() or
              any(e.surface_list.item(k).checkState() != QtCore.Qt.CheckState.Checked for k in range(e.n_boundaries)))
    if hidden:
        e.only_active.setChecked(False); e.blind_check.setChecked(False); e.show_candidates.setChecked(True)
        for k in range(e.n_boundaries):
            e.surface_list.item(k).setCheckState(QtCore.Qt.CheckState.Checked)
        e.redraw_surfaces(); e.fit_image()
        e.status.setText('All boundaries are now visible. Inspect the full B-scan, then Confirm entire B-scan.')
        return False
    r = e.resolved
    if r['unresolved'].any():
        k, x = np.argwhere(r['unresolved'])[0]
        e.surface_list.setCurrentRow(int(k))
        e.canvas.centerOn(float(x), float(np.clip(np.nan_to_num(r['positions'][k, x] - e.offset), 0, e.pack.images.shape[1]-1)))
        e.status.setText(f'Needs a judgment: {e.pack.names[k]}, A-line {x}. Red indicators show missing/out-of-image/crossing positions. Draw a correction, or mark uncertainty, no trace, absence or unusable image.')
        e.redraw_surfaces()
        return False
    approved = r['valid_geometry'] & (r['trace'] != 0) & (r['reliability'] != 0) & (r['anatomy'] != 0) & ~r['excluded'][None]
    snapshot = {k: json_array(r[k]) for k in STATE_KEYS}
    snapshot['approved'] = approved.tolist()
    try:
        e.record_event('confirm_bscan', 0, e.width, list(range(e.n_boundaries)), contract=CONTRACT,
            state_digest=state_digest(r), geometry_revision=r['geometry_revision'], scope=[e.n_boundaries, e.width],
            snapshot=snapshot, reviewer_id=e.reviewer, scan_id=e.volume.scan.scan_id, bscan=e.row,
            boundary_names=list(e.pack.names), source=e.journal.data['source'], model_id=e.journal.data['model_id'],
            annotation_revision=e.journal.data['revision'] + 1, data_role=r['metadata']['data_role'],
            native_geometry=dict(width=e.width, depth=e.pack.images.shape[1], crop_offset=e.offset, orientation='vitreous_at_depth_zero'),
            affirmation='I reviewed all boundaries across this B-scan. The remaining positions are acceptable except where I explicitly marked uncertainty, lack of traceability, or unusable image.')
    except Exception as exc:
        e.status.setText('Confirmation was not completed: ' + str(exc))
        return False
    return True
