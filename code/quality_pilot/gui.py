"""Small explicit review mode in the existing GUI; no new annotation writer."""
import numpy as np
from pathlib import Path
from PySide6 import QtCore,QtGui,QtWidgets
from octa_seg_v1.reviewer import SegBoundaryEditor
from .common import read
from .review_store import QualityStore,strip_rating

Qt=QtCore.Qt

class QualityEditor(SegBoundaryEditor):
    def __init__(self,output):
        self.quality_store=None;self.suggestion=None;self.quality_model=[];self._quality_start=None
        self._quality_rect=None;self._line_args=None
        super().__init__(output)
        body=self.findChildren(QtWidgets.QDockWidget)[0].widget().widget()
        self.quality_box=QtWidgets.QGroupBox('Regional quality review')
        layout=QtWidgets.QVBoxLayout(self.quality_box)
        self.quality_mode=QtWidgets.QCheckBox('Quality review mode · drag a vertical strip')
        self.quality_mode.setChecked(True);layout.addWidget(self.quality_mode)
        self.rating=QtWidgets.QComboBox();self.rating.addItems(['Bad','Good','Unsure']);layout.addWidget(self.rating)
        self.quality_reason=QtWidgets.QComboBox();self.quality_reason.addItems(['','obscured image','misplaced lines','inappropriate solid/dashed labeling']);layout.addWidget(self.quality_reason)
        for text,callback in [('Rate suggested strip',self.rate_suggestion),('Undo quality rating',self.undo_quality),('Clear this B-scan’s quality ratings',self.clear_quality)]:
            btn=QtWidgets.QPushButton(text);btn.clicked.connect(callback);layout.addWidget(btn)
        self.quality_status=QtWidgets.QLabel('Default: Bad. Drag left-to-right or right-to-left across all boundaries. Ratings do not edit lines.');self.quality_status.setWordWrap(True);layout.addWidget(self.quality_status)
        body.layout().insertWidget(0,self.quality_box)
        self._quality_controls=[body.layout().itemAt(i).widget() for i in range(body.layout().count()) if body.layout().itemAt(i).widget() is not None and body.layout().itemAt(i).widget()!=self.quality_box]
        self.canvas.viewport().installEventFilter(self)
        self.quality_mode.toggled.connect(self.toggle_quality);self.toggle_quality(True)

    def toggle_quality(self,enabled):
        for widget in self._quality_controls:widget.setEnabled(not enabled)
        self.state_text.setVisible(not enabled)
        if self._line_args is not None:
            self.commit_current();self.set_line(*self._line_args)
        self.refresh_quality()

    def set_line(self,scan,row,surfaces,confidence,record_pair,auto_source,vessel,lesion):
        self._line_args=(scan,row,surfaces,confidence,record_pair,auto_source,vessel,lesion)
        active=hasattr(self,'quality_mode') and self.quality_mode.isChecked()
        super().set_line(scan,row,surfaces,confidence,None if active else record_pair,auto_source,vessel,lesion)
        self.quality_store=QualityStore(self.output/'quality_reviews',scan.scan_id,row,surfaces.shape[-1],self.quality_model)
        self.refresh_quality()

    def keyPressEvent(self,event):
        if hasattr(self,'quality_mode') and self.quality_mode.isChecked():
            if event.key() in (Qt.Key.Key_Right,Qt.Key.Key_Down):self.stepRequested.emit(1)
            elif event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Up):self.stepRequested.emit(-1)
            elif event.matches(QtGui.QKeySequence.StandardKey.Undo):self.undo_quality()
            event.accept();return
        super().keyPressEvent(event)

    def eventFilter(self,obj,event):
        if obj==self.canvas.viewport() and hasattr(self,'quality_mode') and self.quality_mode.isChecked() and self.pack is not None:
            kind=event.type()
            if kind in (QtCore.QEvent.Type.MouseButtonPress,QtCore.QEvent.Type.MouseMove,QtCore.QEvent.Type.MouseButtonRelease,QtCore.QEvent.Type.MouseButtonDblClick):
                x=int(np.clip(round(self.canvas.mapToScene(event.position().toPoint()).x()),0,self.pack.surfaces.shape[-1]-1))
                if kind==QtCore.QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton:self._quality_start=x
                elif kind==QtCore.QEvent.Type.MouseButtonRelease and self._quality_start is not None:
                    lo,hi=sorted((self._quality_start,x));self._quality_start=None;self.rate_range(lo,hi+1)
                elif kind==QtCore.QEvent.Type.MouseMove and self._quality_start is not None:
                    lo,hi=sorted((self._quality_start,x));self.draw_strip(lo,hi+1)
                return True  # Never forward quality gestures to boundary/exclusion tools.
        return super().eventFilter(obj,event)

    def matching_suggestion(self):
        s=self.suggestion
        return s if s and self.pack is not None and s['scan_id']==self.pack.scan_id and s['bscan']==int(self.pack.bscan_index[0]) else None

    def rate_range(self,lo,hi):
        if self.quality_store is None:return
        s=self.matching_suggestion()
        revealed=bool(s and strip_rating(self.quality_store.data['records'],s['lo'],s['hi']))
        try:
            self.quality_store.rate(lo,hi,self.rating.currentText(),self.quality_reason.currentText(),s['id'] if s else None,revealed)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self,'Quality rating was not saved',str(exc));return
        self.refresh_quality();self.draw_strip(lo,hi)

    def rate_suggestion(self):
        s=self.matching_suggestion()
        if s:self.rate_range(s['lo'],s['hi'])

    def undo_quality(self):
        if self.quality_store:self.quality_store.undo();self.refresh_quality()

    def clear_quality(self):
        if self.quality_store:self.quality_store.clear();self.refresh_quality()

    def draw_strip(self,lo,hi):
        if self.pack is None:return
        if self._quality_rect is None or self._quality_rect.scene()!=self.canvas.scene():
            self._quality_rect=self.canvas.scene().addRect(0,0,0,0,QtGui.QPen(QtGui.QColor('#d7dcff'),1))
            self._quality_rect.setZValue(60)
        self._quality_rect.setRect(lo,0,hi-lo,self.pack.images.shape[1])
        self._quality_rect.setVisible(True)

    def refresh_quality(self):
        if not hasattr(self,'quality_status'):return
        s=self.matching_suggestion()
        if s and self.quality_store:
            rating=strip_rating(self.quality_store.data['records'],s['lo'],s['hi'])
            if rating:
                m=s['metrics'];self.quality_status.setText(f"Recorded: {rating}. Sampling: {s['role']} / {s['driver']}.\nEntropy P95 {m['entropy_p95']:.3f}; spike maximum {m['spike_max_um'] or 0:.1f} µm; jump maximum {m['jump_max_um'] or 0:.1f} µm. Warnings are not correctness labels.")
            else:self.quality_status.setText(f"Suggested A-lines {s['lo']}–{s['hi']-1}. Metrics hidden until rated. Drag to rate any strip, or use Rate suggested strip.")
            self.draw_strip(s['lo'],s['hi'])
        else:
            self.quality_status.setText('Free browsing. Choose Good / Bad / Unsure, then drag across a vertical strip. Ratings save separately from boundary edits.')
            if self._quality_rect is not None:self._quality_rect.setVisible(False)

def install_queue(window):
    payload=read(window.config['quality_review_queue']);queue=payload['examples'];window.editor.quality_model=payload['model_identity']
    bar=window.addToolBar('Regional quality review');choice=QtWidgets.QComboBox();choice.setMinimumWidth(570)
    for i,q in enumerate(queue):choice.addItem(f"{i+1}/24 · {q['scan_id'].split('_')[0]} · B{q['bscan']:03d} · A-lines {q['lo']}–{q['hi']-1}")
    bar.addWidget(choice);back=bar.addAction('Previous strip');forward=bar.addAction('Next strip')
    window._quality_pending=True
    def navigate():
        q=queue[choice.currentIndex()];window.editor.suggestion=q
        if window.scan is None:return
        if window.scan.scan_id!=q['scan_id']:
            window._quality_pending=True
            window.load_scan(next(i for i,p in enumerate(window.paths) if p.stem==q['scan_id']));return
        window._quality_pending=False;window.navigate(q['bscan'],(q['lo']+q['hi'])//2)
        window.editor.refresh_quality()
    choice.currentIndexChanged.connect(lambda _:navigate())
    window.ready.connect(lambda:navigate() if window._quality_pending else None)
    back.triggered.connect(lambda:choice.setCurrentIndex(max(0,choice.currentIndex()-1)))
    forward.triggered.connect(lambda:choice.setCurrentIndex(min(len(queue)-1,choice.currentIndex()+1)))
    window.quality_queue_choice=choice
