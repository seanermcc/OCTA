"""V2-only GUI event writer and mature native boundary canvas integration."""
import copy
import os
import time
import uuid
import hashlib
from .common import read,write,OUT
from .feedback import resolve
from .policy import apply,geometry_valid
from cnv_review_v1.label_gui import BoundaryEditor,curve_path,Qt,QtCore,QtGui,QtWidgets
from eight_surface import provenance as P
import numpy as np

def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

class FeedbackJournal:
    """Only instantiated by the reviewer. Append audit history, conflict-safe save."""
    def __init__(self,path,scan_id,bscan,model_id,role):
        self.path=path;self.hash=file_hash(path)
        self.data=read(path) if path.exists() else dict(format='octa-seg-v2-regional-1',scan_id=scan_id,bscan=bscan,
            native_width=512,model_id=model_id,data_role=role,revision=0,events=[],cursor=0,history=[],active_seconds=0.)
        if self.data['scan_id']!=scan_id or self.data['bscan']!=bscan:raise ValueError('Feedback identity mismatch')
    @property
    def events(self):return self.data['events'][:self.data['cursor']]
    def change(self,event=None,direction=0,seconds=0):
        before=copy.deepcopy(self.data)
        if event is not None:
            self.data['model_id']=event['model_id']
            discarded=self.data['events'][self.data['cursor']:]
            if discarded:self.data['history'].append(dict(action='discard_redo_branch',events=discarded))
            self.data['events']=self.events+[event];self.data['cursor']=len(self.data['events'])
        else:self.data['cursor']=max(0,min(len(self.data['events']),self.data['cursor']+direction))
        self.data['revision']+=1;self.data['active_seconds']+=seconds
        self.data['history'].append(dict(revision=self.data['revision'],timestamp=time.time(),action='event' if event else 'undo' if direction<0 else 'redo',cursor=self.data['cursor']))
        lock=self.path.with_suffix('.lock');lock.parent.mkdir(parents=True,exist_ok=True)
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:
            self.data=before;raise RuntimeError('Feedback is being saved in another window')
        try:
            os.close(fd)
            if file_hash(self.path)!=self.hash:raise RuntimeError('Feedback changed in another window. Reopen before editing.')
            if self.path.exists():write(self.path.parent/'history'/f'{self.path.stem}_r{before["revision"]}.json',before)
            write(self.path,self.data);self.hash=file_hash(self.path)
        except Exception:self.data=before;raise
        finally:lock.unlink()

class V2Editor(BoundaryEditor):
    def __init__(self,output):
        self.journal=None;self.bundle=None;self.rendered=None;self._loading=True;self._drag_start=None;self.previous=None
        self.show_previous=False;self._strip=None;self.review_role='training';self.offset=0
        super().__init__(output)
        self._loading=False
        dock=self.findChildren(QtWidgets.QDockWidget)[0];body=dock.widget().widget();layout=body.layout()
        # Keep the established native canvas, display controls, and Pack.save writer.
        self.btn_accept.parentWidget().hide();self.verdict_label.hide();self.taper_spin.hide();self.taper_spin.setValue(0)
        form=self.taper_spin.parentWidget().layout()
        if isinstance(form,QtWidgets.QFormLayout):form.labelForField(self.taper_spin).hide()
        self.line_notes.hide();self.source_label.hide()
        self.mode=QtWidgets.QComboBox();self.mode.addItems(['Unreliable region · drag strip','Clear regional mark · drag strip','Edit boundary · established gestures'])
        layout.insertWidget(0,self.mode)
        self.mode.setStyleSheet('QComboBox {background:#6d381e;color:white;padding:7px;font-weight:bold}')
        box=QtWidgets.QWidget();buttons=QtWidgets.QVBoxLayout(box);buttons.setContentsMargins(0,0,0,0)
        span=QtWidgets.QHBoxLayout();self.span_lo=QtWidgets.QSpinBox();self.span_hi=QtWidgets.QSpinBox()
        self.span_lo.setRange(0,511);self.span_hi.setRange(1,512);self.span_hi.setValue(512)
        span.addWidget(QtWidgets.QLabel('A-lines [start, stop)'));span.addWidget(self.span_lo);span.addWidget(self.span_hi);buttons.addLayout(span)
        for title,action in [('Mark whole B-scan unreliable','whole'),('Approve shown measurements','approve_shown'),
            ('Approve selected candidate position','approve_position'),('Affirm selected boundary measurable','affirm_measurable'),
            ('Not traceable · selected boundary','not_traceable'),('Exclude unusable image','exclude_image')]:
            b=QtWidgets.QPushButton(title);b.clicked.connect(lambda checked=False,a=action:self.action(a));buttons.addWidget(b)
        row=QtWidgets.QHBoxLayout()
        for title,step in [('Undo',-1),('Redo',1)]:
            b=QtWidgets.QPushButton(title);b.clicked.connect(lambda checked=False,s=step:self.undo_redo(s));row.addWidget(b)
        buttons.addLayout(row)
        self.show_candidates=QtWidgets.QCheckBox('Show uncertain candidates');self.show_candidates.setChecked(True);self.show_candidates.toggled.connect(self.redraw_surfaces);buttons.addWidget(self.show_candidates)
        self.reason=QtWidgets.QLineEdit();self.reason.setPlaceholderText('Optional reason');buttons.addWidget(self.reason)
        self.status=QtWidgets.QLabel('Drag a strip to withhold all eight measurements. Candidates remain available.');self.status.setWordWrap(True);buttons.addWidget(self.status)
        inspect=QtWidgets.QToolButton();inspect.setText('Inspect scores and provenance');inspect.setCheckable(True)
        self.details=QtWidgets.QLabel('');self.details.setWordWrap(True);self.details.hide();inspect.toggled.connect(self.details.setVisible)
        buttons.addWidget(inspect);buttons.addWidget(self.details);layout.insertWidget(1,box)
        self.canvas.viewport().installEventFilter(self)
        self.cursorColumn.connect(self.explain)
        self.only_active.setText('Show selected boundary only')
        self.surface_list.setToolTip('Checkboxes show/hide boundaries. Hiding a boundary is not an image judgment.')
        self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self._save_clicked);self.timer.start(15000)

    def fit_image(self):
        super().fit_image()
        if self.pack is not None:
            transform=self.canvas.transform();height=self.pack.images.shape[1]
            stretch=min(1.8,max(1.,(self.canvas.viewport().height()-30)/(height*transform.m22())))
            self.canvas.scale(1.,stretch);self.canvas.centerOn(256,height/2)

    def set_bundle(self,bundle,guard,cal,model_id,previous=None):
        self.bundle=bundle;self.guards=guard;self.cal=cal;self.model_id=model_id;self.previous=previous

    def set_line(self,scan,row,surfaces,confidence,record_pair,auto_source,vessel,lesion):
        self.commit_current();self._loading=True;self.journal=None
        # V2 events are authoritative; saved v2 labels are serialized compatibility records.
        super().set_line(scan,row,surfaces,confidence,None,auto_source,vessel,lesion)
        self.row=row;self.offset=int(self.bundle['label_offset']);self._loading=False
        self.journal=FeedbackJournal(self.output/'regional_feedback'/f'{scan.scan_id}_b{row:04d}.json',scan.scan_id,row,self.model_id,self.review_role)
        self.recompute();self._saved_signature=self.signature()
        self.source_label.setText('octa-seg_v2 / '+self.model_id)
        self.status.setText(f'{self.journal.data["data_role"]} evidence · revision {self.journal.data["revision"]}. Solid = working measurement; dashes = candidate.')

    def recompute(self):
        if self.journal is None:return
        self.resolved=resolve(self.journal.events,(8,512),self.model_id)
        b=self.row;g={k:v[b] for k,v in self.guards.items()};g['rejected']=bool(g['rejected'])
        context=self.bundle['uncertain_estimates'][b].copy()
        context[self.bundle['candidate_source'][b]!=1]=np.nan
        self.rendered=apply(self.bundle['raw_position_branch'][b],self.bundle['probabilities'][b],self.cal,
              self.bundle['vessel'][b],self.offset,self.pack.images.shape[1],g,self.resolved,context)
        st=self.pack.states[0];st.current=self.rendered['working_positions']-self.offset
        st.local['local_drawn']=self.resolved['manual'].copy();st.local['local_reviewed']=self.resolved['approved'].copy()
        st.local['local_visibility']=np.where(self.resolved['trace']<0,P.MARK_UNKNOWN,np.where(self.resolved['trace']==1,P.MARK_YES,P.MARK_NO)).astype(np.int8)
        st.local['local_reliability']=np.where(self.resolved['reliability']<0,P.MARK_UNKNOWN,np.where(self.resolved['reliability']==1,P.MARK_YES,P.MARK_NO)).astype(np.int8)
        st.excluded=self.resolved['excluded'].copy();st.local['local_taper'][:]=False;st.local['local_displaced'][:]=False
        st.sync_surface_flags();st.n_strokes=sum(e['action']=='correct' for e in self.journal.events)
        st.verdict='corrected' if self.journal.data['revision'] else None
        self.context.update(model_id=self.model_id,feedback_revision=self.journal.data['revision'],data_role=self.journal.data['data_role'],regional_feedback_path=str(self.journal.path))
        self.canvas.set_excluded(st.excluded);self.redraw_surfaces();self.update_labels()

    def record_event(self,action,lo,hi,boundaries=None,columns=None,positions=None):
        if self.journal is None:return
        self._bank_time();e=dict(id=uuid.uuid4().hex,action=action,lo=int(lo),hi=int(hi),
             boundaries=list(range(8)) if boundaries is None else boundaries,model_id=self.model_id,
             timestamp=time.time(),reason=self.reason.text(),coordinate_system='native A-line; full canonical depth')
        if columns is not None:e['columns']={str(k):list(map(int,v)) for k,v in columns.items()}
        if positions is not None:e['positions']={str(k):list(map(float,v)) for k,v in positions.items()}
        seconds=self.pack.states[0].seconds
        self.journal.change(e,seconds=seconds);self.pack.states[0].seconds=0;self.recompute();self.commit_current()
        self.status.setText(f'Saved {action.replace("_"," ")} · A-lines {lo}–{hi-1} · {self.journal.data["data_role"]}')

    def action(self,action):
        if self.rendered is None:return
        lo,hi=self.span_lo.value(),self.span_hi.value()
        if hi<=lo:return
        if action=='whole':self.record_event('unreliable_region',0,512);return
        if action in ('exclude_image','not_traceable'):
            self.record_event(action,lo,hi,[self.s] if action=='not_traceable' else None);return
        values=self.rendered['reported_positions'] if action=='approve_shown' else self.rendered['uncertain_estimates'] if action=='approve_position' else self.rendered['working_positions']
        ks=[k for k in range(8) if self.canvas._surface_items[k].isVisible()] if action=='approve_shown' else [self.s]
        if action!='approve_shown' and not self.canvas._surface_items[self.s].isVisible():
            self.status.setText('Show the selected boundary before approving it.');return
        if action=='approve_position' and not self.show_candidates.isChecked():return
        columns={};positions={}
        for k in ks:
            ok=np.isfinite(values[k])&geometry_valid(self.rendered['working_positions'],self.offset,self.pack.images.shape[1])[k]
            ok &= self.rendered['state'][k]!=2
            ok &= ~self.resolved['excluded'];ok[:lo]=False;ok[hi:]=False
            cc=np.flatnonzero(ok)
            if len(cc):columns[k]=cc;positions[k]=values[k,cc]
        if not columns:self.status.setText('No eligible displayed segment in this range.');return
        self.record_event(action,lo,hi,list(columns),columns,positions if action=='approve_position' else None)

    def on_stroke(self,xs,ys):
        if self.pack is None or not len(xs):return
        col=np.clip(np.rint(xs).astype(int),0,511);ux,inv=np.unique(col,return_inverse=True);uy=np.bincount(inv,weights=ys)/np.bincount(inv)
        cc=np.arange(ux.min(),ux.max()+1);yy=np.clip(np.interp(cc,ux,uy),0,self.pack.images.shape[1]-1)+self.offset
        self.span_lo.setValue(int(cc[0]));self.span_hi.setValue(int(cc[-1])+1)
        self.record_event('correct',cc[0],cc[-1]+1,[self.s],{self.s:cc},{self.s:yy})

    def on_local_marked(self,x0,x1,action):
        lo,hi=sorted((int(np.clip(round(x0),0,511)),int(np.clip(round(x1),0,511))))
        mapping=dict(not_visible='not_traceable',visible='clear_boundary',unreliable='unreliable_boundary',reliable='affirm_measurable',reviewed='approve_shown')
        if action=='reviewed':
            self.span_lo.setValue(lo);self.span_hi.setValue(hi+1)
            cc=np.arange(lo,hi+1);cc=cc[np.isfinite(self.rendered['reported_positions'][self.s,cc])]
            if len(cc):self.record_event('approve_shown',lo,hi+1,[self.s],{self.s:cc})
        else:self.record_event(mapping[action],lo,hi+1,[self.s])

    def on_region_marked(self,x0,x1,exclude):
        lo,hi=sorted((int(np.clip(round(x0),0,511)),int(np.clip(round(x1),0,511))))
        self.record_event('exclude_image' if exclude else 'clear_exclusion',lo,hi+1)

    def clear_excluded(self):self.record_event('clear_exclusion',0,512)
    def clear_local_marks(self):self.record_event('clear_boundary',0,512,[self.s])
    def toggle_visible(self):self.record_event('not_traceable',0,512,[self.s])
    def _on_item_changed(self,item):
        if not self._updating_surface_list:self.redraw_surfaces()
    def update_labels(self):pass
    def revert_all(self):pass
    def revert_surface(self):pass
    def set_verdict(self,verdict):
        if verdict=='rejected':self.record_event('exclude_image',0,512)

    def undo_redo(self,step):
        if self.journal:self.journal.change(direction=step);self.recompute();self.commit_current()

    def keyPressEvent(self,event):
        ctrl=event.modifiers()&Qt.KeyboardModifier.ControlModifier
        if ctrl and event.key() in (Qt.Key.Key_Z,Qt.Key.Key_Y):self.undo_redo(-1 if event.key()==Qt.Key.Key_Z else 1);return
        if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right):self.stepRequested.emit(-1 if event.key()==Qt.Key.Key_Left else 1);return
        if event.key() in (Qt.Key.Key_V,Qt.Key.Key_U,Qt.Key.Key_R):return
        super().keyPressEvent(event)

    def eventFilter(self,obj,event):
        if obj==self.canvas.viewport() and hasattr(self,'mode') and self.mode.currentIndex()!=2 and self.journal:
            t=event.type()
            if t in (QtCore.QEvent.Type.MouseButtonPress,QtCore.QEvent.Type.MouseMove,QtCore.QEvent.Type.MouseButtonRelease):
                x=int(np.clip(round(self.canvas.mapToScene(event.position().toPoint()).x()),0,511))
                if t==QtCore.QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton:self._drag_start=x;return True
                if self._drag_start is not None:
                    lo,hi=sorted((self._drag_start,x));self.draw_strip(lo,hi+1)
                    if t==QtCore.QEvent.Type.MouseButtonRelease:
                        self._drag_start=None;self.span_lo.setValue(lo);self.span_hi.setValue(hi+1)
                        self.record_event('unreliable_region' if self.mode.currentIndex()==0 else 'clear_region',lo,hi+1)
                    return True
        return super().eventFilter(obj,event)

    def draw_strip(self,lo,hi):
        if self._strip is None:
            self._strip=self.canvas.scene().addRect(0,0,0,0,QtGui.QPen(QtGui.QColor('#ffd58f'),1));self._strip.setZValue(60)
        self._strip.setRect(lo,0,hi-lo,self.pack.images.shape[1])

    def redraw_surfaces(self):
        if self._loading or self.pack is None:return
        super().redraw_surfaces()
        if self.rendered is None or self.journal is None:return
        for item in list(self._extras):
            if item.pen().style()!=Qt.PenStyle.NoPen:self.canvas.scene().removeItem(item);self._extras.remove(item)
        for item in self.canvas._weak_items:item.setPath(QtGui.QPainterPath())
        for item in getattr(self.canvas,'_band_items',{}).values():item.setPath(QtGui.QPainterPath())
        for k,item in enumerate(self.canvas._surface_items):
            visible=(not self.only_active.isChecked() or k==self.s) and self.surface_list.item(k).checkState()==Qt.CheckState.Checked
            item.setVisible(visible);item.setOpacity(1);item.setPath(curve_path(self.rendered['reported_positions'][k]-self.offset))
            pen=item.pen();pen.setStyle(Qt.PenStyle.SolidLine);item.setPen(pen)
            if visible and hasattr(self,'show_candidates') and self.show_candidates.isChecked():
                pen=QtGui.QPen(QtGui.QColor('#ffb45c'),2,Qt.PenStyle.DashLine);pen.setCosmetic(True)
                overlay=self.canvas.scene().addPath(curve_path(self.rendered['uncertain_estimates'][k]-self.offset),pen);overlay.setZValue(26);self._extras.append(overlay)
            if visible and self.show_previous and self.previous is not None:
                pen=QtGui.QPen(QtGui.QColor('#aebeff'),1,Qt.PenStyle.DotLine);pen.setCosmetic(True)
                overlay=self.canvas.scene().addPath(curve_path(self.previous[self.row,k]-self.offset),pen);overlay.setZValue(20);self._extras.append(overlay)
        self.explain(256)

    def explain(self,x):
        if self.rendered is None or not hasattr(self,'details') or self.journal is None:return
        x=int(np.clip(x,0,511));k=max(0,self.s);p=self.bundle['probabilities'][self.row,k,:,x]
        source=['none','registered context','neural proposal','human position'][int(self.rendered['candidate_source'][k,x])]
        self.details.setText(f'{self.pack.names[k]} / A{x}\nState {self.rendered["state"][k,x]}; reason {self.rendered["reason"][k,x]}\nCandidate: {source}\nTrace {p[0]:.3f}; reliability {p[1]:.3f}; entropy {self.bundle["entropy"][self.row,k,x]:.3f}\n{self.model_id}; feedback revision {self.journal.data["revision"]}\nScores remain uncalibrated. ILM default is working policy, not training truth.')
        if 'spike_um' in self.bundle:
            spike=self.bundle['spike_um'][self.row,k,x];jump=self.bundle['jump_um'][self.row,k,x]
            self.details.setText(self.details.text()+f'\nRaw proposal spike {spike:.1f} µm; jump {jump:.1f} µm (>20 µm flagged in queue).')

    def commit_current(self):
        if not self._loading:super().commit_current()

