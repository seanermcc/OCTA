"""Optional octa-seg_v1 integration in the current CNV reviewer.

Only this GUI module writes feedback. Existing label writer and conflict/history
checks serialize human boundary files. Approval of an automatic estimate is a
separate event, never fabricated local_drawn provenance.
"""
import json
import time
import numpy as np
from cnv_review_v1.label_gui import BoundaryEditor,curve_path,Qt,QtGui,QtWidgets,legacy
from cnv_review_v1.data import atomic_json,fingerprint
from eight_surface import provenance as P
from .decisions import REASONS,NOT_TRACEABLE,RELIABLE,UNCERTAIN
from .ilm_preview import load_ilm_preview,ilm_preview_mask
from pathlib import Path

def display_masks(state, automatic_state, candidate):
    vis=P.effective_marks(state.local["local_visibility"],state.visible)
    rel=P.effective_marks(state.local["local_reliability"],state.reliable)
    denied=vis==P.MARK_NO
    blocked=denied | state.excluded[None] | (rel==P.MARK_NO)
    drawn=state.local["local_drawn"] & ~state.local["local_displaced"]
    affirmed=state.local["local_reviewed"] & (vis==P.MARK_YES) & (rel==P.MARK_YES)
    reliable=((automatic_state==RELIABLE)|drawn|affirmed)&~blocked
    # Positive human visibility can replace an automatic not-traceable state,
    # but cannot create an automatic continuation. Only actual new strokes show.
    reliable &= (automatic_state!=NOT_TRACEABLE)|drawn
    uncertain=np.isfinite(candidate)&~denied&~state.excluded[None]&((automatic_state!=NOT_TRACEABLE)|drawn)&~reliable
    if state.verdict=="rejected":reliable[:]=False;uncertain[:]=False
    return reliable,uncertain

def approved_position_mask(label,events):
    """Future-v2 adapter: latest event plus current label must still agree.

    Undo, later denials, displacement and rejection revoke approval. Missing
    events cannot create approvals; local_reviewed alone never suffices.
    """
    mask=np.zeros_like(label["surfaces"],bool)
    for e in events:
        k=list(label["surface_names"]).index(e["boundary"]);cols=np.asarray(e["columns"],int)
        mask[k,cols]=False
        if e["action"]=="approved_for_future_positions":
            mask[k,cols]=np.isclose(label["surfaces"][k,cols],e["positions_crop_px"],atol=1e-4,rtol=0)
    mask &= (P.record_visibility(label)==P.MARK_YES)&(P.record_reliability(label)==P.MARK_YES)
    mask &= ~label["local_displaced"]&~label["region_excluded"][None]&np.isfinite(label["surfaces"])
    if label["verdict"]=="rejected":mask[:]=False
    return mask

class SegBoundaryEditor(BoundaryEditor):
    def __init__(self,output):
        self.seg_data=None;self._seg_path=None;self._column=0;self._feedback=[];self._feedback_dirty=False
        self._feedback_hash=None;self._loading_seg=False
        self._raw_ilm=None;self._ilm_preview_item=None
        super().__init__(output)
        body=self.findChildren(QtWidgets.QDockWidget)[0].widget().widget()
        box=QtWidgets.QGroupBox("octa-seg v1 · experimental estimates")
        layout=QtWidgets.QVBoxLayout(box)
        self.show_estimates=QtWidgets.QCheckBox("Show uncertain candidates (amber dashes)");self.show_estimates.setChecked(True)
        self.show_estimates.toggled.connect(self.redraw_surfaces);layout.addWidget(self.show_estimates)
        self.show_ilm=QtWidgets.QCheckBox("Show model ILM (white dots; view only)");self.show_ilm.setChecked(True)
        self.show_ilm.setToolTip("Saved position prediction before v1's reporting filter. Unvalidated reliability; never added to measurements or approval targets.")
        self.show_ilm.toggled.connect(self.redraw_surfaces);layout.addWidget(self.show_ilm)
        self.state_text=QtWidgets.QLabel("Select a boundary and A-line for its state and reason.");self.state_text.setWordWrap(True);layout.addWidget(self.state_text)
        row=QtWidgets.QHBoxLayout();self.span_lo=QtWidgets.QSpinBox();self.span_hi=QtWidgets.QSpinBox()
        row.addWidget(QtWidgets.QLabel("A-line range"));row.addWidget(self.span_lo);row.addWidget(self.span_hi);layout.addLayout(row)
        for title,action in (("Approve selected estimate for future position training","approved_for_future_positions"),
                             ("Keep selected range uncertain","retained_uncertain"),("Mark selected range not traceable","not_traceable")):
            button=QtWidgets.QPushButton(title);button.clicked.connect(lambda checked=False,a=action:self.feedback_action(a));layout.addWidget(button)
        note=QtWidgets.QLabel("Draw to correct. Corrections here remain uncertain until explicitly approved. Generic Accept never approves estimates. Feedback is for v2.")
        note.setWordWrap(True);layout.addWidget(note);body.layout().insertWidget(1,box)
        self.cursorColumn.connect(self.explain);self.surface_list.currentRowChanged.connect(lambda _:self.explain(self._column))
        self.taper_spin.setValue(0);self.taper_spin.setEnabled(False)

    def set_line(self,scan,row,surfaces,confidence,record_pair,auto_source,vessel,lesion):
        self.commit_current()
        self._loading_seg=True
        path=auto_source["path"]
        if path!=self._seg_path:
            with np.load(path,allow_pickle=False) as d:
                self.seg_data={k:d[k].copy() for k in ("state","reason","probabilities","uncertain_estimates","context_reason")}
            self._raw_ilm,preview_source=load_ilm_preview(path,scan.scan_id,scan.surface_names,self.seg_data["state"].shape)
            self.show_ilm.setEnabled(self._raw_ilm is not None)
            self.show_ilm.setToolTip(f"View only: saved position prediction before reporting; no measurement or training use. Source: {preview_source}"
                if self._raw_ilm is not None else "Saved raw ILM prediction is unavailable for this provider.")
            self._seg_path=path
        self.seg_row=row
        self._feedback_path=self.output/"estimate_feedback"/f"{scan.scan_id}_b{row:04d}.json"
        self._feedback_hash=fingerprint(self._feedback_path)
        self._feedback=json.loads(self._feedback_path.read_text())["events"] if self._feedback_path.exists() else []
        self._feedback_dirty=False
        super().set_line(scan,row,surfaces,confidence,record_pair,auto_source,vessel,lesion)
        if record_pair:
            # A position-specific approval cannot transfer to a new automatic
            # curve, but the separately saved IMAGE state judgment survives.
            # BaseEditor clears stale local_reviewed correctly; retain only the
            # two independent human state planes, never its old auto approval.
            original=record_pair[1]
            self.pack.states[0].local["local_visibility"]=original["local_visibility"].copy()
            self.pack.states[0].local["local_reliability"]=original["local_reliability"].copy()
            self._saved_signature=self.signature()
        self._loading_seg=False
        self.span_lo.setRange(0,surfaces.shape[-1]-1);self.span_hi.setRange(1,surfaces.shape[-1]);self.span_hi.setValue(surfaces.shape[-1])
        self.context["octa_seg_version"]="octa-seg_v1"
        self.context["position_training_approval"]="estimate_feedback event required; generic acceptance does not approve candidates"
        self.source_label.setText("octa-seg_v1 · experimental\nSolid: supported or human-corrected. Amber: optional uncertain candidate. Not traceable: gap.")
        self.redraw_surfaces();self.explain(self._column)

    def candidate_rows(self):
        if self.seg_data is None or self.pack is None:return None
        candidate=self.seg_data["uncertain_estimates"][self.seg_row].copy()
        st=self.pack.states[0]
        # Pending human corrections are themselves review candidates; their
        # position provenance remains human, while reliability stays denied.
        pending=st.local["local_drawn"] & (st.local["local_reliability"]==P.MARK_NO)
        candidate[pending]=st.current[pending]
        return candidate

    def redraw_surfaces(self):
        self._ilm_preview_item=None
        super().redraw_surfaces()
        if self.seg_data is None or self.pack is None or self._loading_seg:return
        state=self.pack.states[0];candidate=self.candidate_rows()
        measured,uncertain=display_masks(state,self.seg_data["state"][self.seg_row],candidate)
        # Delete the old automatic/manual overlay paths, keeping filled vessel
        # context. Rebuild every visible curve with an explicit gap mask.
        for item in list(self._extras):
            if item.pen().style()!=Qt.PenStyle.NoPen:
                self.canvas.scene().removeItem(item);self._extras.remove(item)
        for item in self.canvas._weak_items:item.setPath(QtGui.QPainterPath())
        for item in getattr(self.canvas,"_band_items",{}).values():item.setPath(QtGui.QPainterPath())
        for k,item in enumerate(self.canvas._surface_items):
            item.setPath(curve_path(state.current[k],measured[k]))
            pen=item.pen();pen.setStyle(Qt.PenStyle.SolidLine);item.setPen(pen)
            if self.show_estimates.isChecked() and item.isVisible():
                pen=QtGui.QPen(QtGui.QColor("#ffb45c"),2,Qt.PenStyle.DashLine);pen.setCosmetic(True)
                overlay=self.canvas.scene().addPath(curve_path(candidate[k],uncertain[k]),pen);overlay.setZValue(26);self._extras.append(overlay)
        if self._raw_ilm is not None and self.show_ilm.isChecked():
            k=self.pack.names.index("ILM")
            if self.canvas._surface_items[k].isVisible():
                rows=self._raw_ilm[self.seg_row]
                mask=ilm_preview_mask(rows,state,self.seg_data["state"][self.seg_row],k,self.pack.images.shape[1])
                pen=QtGui.QPen(QtGui.QColor("#f4f4f4"),2,Qt.PenStyle.DotLine);pen.setCosmetic(True)
                self._ilm_preview_item=self.canvas.scene().addPath(curve_path(rows,mask),pen)
                self._ilm_preview_item.setZValue(27);self._extras.append(self._ilm_preview_item)
        self.explain(self._column)

    def explain(self,column):
        self._column=int(column)
        if self.seg_data is None or self.pack is None or not hasattr(self,"state_text"):return
        k=max(0,self.s);x=int(np.clip(column,0,self.pack.surfaces.shape[-1]-1));st=self.pack.states[0]
        vis=P.effective_marks(st.local["local_visibility"],st.visible)[k,x]
        rel=P.effective_marks(st.local["local_reliability"],st.reliable)[k,x]
        code=int(self.seg_data["state"][self.seg_row,k,x]);reason=REASONS[int(self.seg_data["reason"][self.seg_row,k,x])]
        if vis==P.MARK_NO:code=NOT_TRACEABLE;reason="explicit human not-traceable; no continuation"
        elif rel==P.MARK_NO:code=UNCERTAIN;reason="explicit human unreliable; measurement withheld"
        elif (vis==P.MARK_YES and rel==P.MARK_YES and
              (st.local["local_reviewed"][k,x] or st.local["local_drawn"][k,x]) and
              not st.local["local_displaced"][k,x] and np.isfinite(st.current[k,x])):
            code=RELIABLE;reason="explicit human position approval; automatic probabilities shown below"
        if st.excluded[x]:reason="image exclusion; no measurement or candidate"
        if st.verdict=="rejected":reason="rejected B-scan; reporting withheld"
        p=self.seg_data["probabilities"][self.seg_row,k,:,x]
        self.state_text.setText(f"{self.pack.names[k]} · A-line {x}\n{ {1:'Reliable (experimental)',2:'Not traceable',3:'Uncertain'}[code]}\n{reason}\nP(traceable)={p[0]:.3f}; P(reliable)={p[1]:.3f}")
        if self.pack.names[k]=="ILM" and self._raw_ilm is not None and self.show_ilm.isChecked():
            shown=ilm_preview_mask(self._raw_ilm[self.seg_row],st,self.seg_data["state"][self.seg_row],k,self.pack.images.shape[1])[x]
            self.state_text.setText(self.state_text.text()+
                ("\nWhite dots: model position for inspection only; excluded from measurements." if shown else "\nILM preview withheld here by a denial, image exclusion, rejection, or invalid position."))

    def _event(self,action,k,mask,rows=None):
        columns=np.flatnonzero(mask)
        self._feedback.append(dict(action=action,boundary=self.pack.names[k],columns=columns.tolist(),
            positions_crop_px=[float(v) for v in rows[mask]] if rows is not None else None,
            approved_for_position_training=action=="approved_for_future_positions",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),candidate_source=self.context.get("auto_source"),
            original_v1_training_set_unchanged=True))
        self._feedback_dirty=True

    def on_stroke(self,xs,ys):
        if self.pack is None or not len(xs):return
        st=self.pack.states[0];st.push_undo(self.s);w=st.current.shape[-1]
        col=np.clip(np.rint(xs).astype(int),0,w-1);ux,inv=np.unique(col,return_inverse=True)
        uy=np.bincount(inv,weights=np.asarray(ys))/np.bincount(inv)
        mask=np.zeros(w,bool);mask[ux.min():ux.max()+1]=True
        st.current[self.s,mask]=np.clip(np.interp(np.flatnonzero(mask),ux,uy),0,self.pack.images.shape[1]-1)
        st.local["local_drawn"][self.s,mask]=True;st.local["local_displaced"][self.s,mask]=False
        st.local["local_taper"][self.s,mask]=False;st.local["local_visibility"][self.s,mask]=P.MARK_YES
        st.local["local_reliability"][self.s,mask]=P.MARK_NO
        st.sync_surface_flags();st.n_strokes+=1;st.verdict="corrected"
        self.span_lo.setValue(int(ux.min()));self.span_hi.setValue(int(ux.max())+1)
        self._event("corrected_pending_approval",self.s,mask,st.current[self.s])
        self.redraw_surfaces();self.update_labels()

    def feedback_action(self,action):
        if self.pack is None:return
        st=self.pack.states[0];k=self.s;lo=self.span_lo.value();hi=self.span_hi.value()
        if hi<=lo:return
        mask=np.zeros(st.current.shape[-1],bool);mask[lo:hi]=True
        st.push_undo(k)
        if action=="approved_for_future_positions":
            candidate=self.candidate_rows();vis=P.effective_marks(st.local["local_visibility"],st.visible)
            mask &= np.isfinite(candidate[k]) & (vis[k]!=P.MARK_NO) & ~st.excluded
            # No ordering manipulation of the approved position. Reject crossing
            # columns, including the closest finite boundaries across gaps.
            for other in range(8):
                if other<k:mask &= ~np.isfinite(st.current[other])|(candidate[k]>st.current[other])
                if other>k:mask &= ~np.isfinite(st.current[other])|(candidate[k]<st.current[other])
            if not mask.any():
                self.statusBar().showMessage("No eligible candidate in this range. Draw a correction first if needed.",5000);return
            st.current[k,mask]=candidate[k,mask]
            st.local["local_reviewed"][k,mask]=True
            st.local["local_visibility"][k,mask]=P.MARK_YES;st.local["local_reliability"][k,mask]=P.MARK_YES
            self._event(action,k,mask,st.current[k])
        elif action=="not_traceable":
            st.local["local_visibility"][k,mask]=P.MARK_NO;self._event(action,k,mask)
        else:
            st.local["local_reliability"][k,mask]=P.MARK_NO;self._event(action,k,mask)
        st.verdict="corrected";self.redraw_surfaces();self.update_labels();self.commit_current()

    def commit_current(self):
        if self._loading_seg:return
        if self._feedback_dirty and fingerprint(self._feedback_path)!=self._feedback_hash:
            raise RuntimeError("Estimate feedback changed in another window")
        super().commit_current()
        if self._feedback_dirty and self.pack is not None:
            if fingerprint(self._feedback_path)!=self._feedback_hash:raise RuntimeError("Estimate feedback changed in another window")
            atomic_json(self._feedback_path,dict(format="octa-seg-v1-estimate-feedback-1",scan_id=self.pack.scan_id,
                bscan=int(self.pack.bscan_index[0]),model_version="octa-seg_v1",events=self._feedback,
                training_use="future v2 only; latest per-column decision supersedes previous approval; explicit approval required"))
            self._feedback_hash=fingerprint(self._feedback_path);self._feedback_dirty=False

def install_queue(window):
    queue_path=window.config.get("review_queue")
    if not queue_path:return
    queue=json.loads(Path(queue_path).read_text())["examples"]
    bar=window.addToolBar("octa-seg_v1 feedback queue")
    choice=QtWidgets.QComboBox();choice.setMinimumWidth(660)
    for i,item in enumerate(queue):
        choice.addItem(f"{i+1}/{len(queue)} · {item['animal']} · B{item['bscan']:03d} · {item['boundary']} · {item['role']} · {item['hi']-item['lo']} A-lines")
    bar.addWidget(choice)
    previous=bar.addAction("Previous example");next_item=bar.addAction("Next example")
    window._seg_queue_pending=True  # Apply the initial example once loading finishes.
    def navigate():
        item=queue[choice.currentIndex()]
        if window.scan is None:return
        if window.scan.scan_id!=item["scan_id"]:
            window._seg_queue_pending=True
            index=next(i for i,p in enumerate(window.paths) if p.stem==item["scan_id"])
            window.load_scan(index);return
        window._seg_queue_pending=False
        window.navigate(item["bscan"],(item["lo"]+item["hi"])//2)
        window.editor.surface_list.setCurrentRow(window.scan.surface_names.index(item["boundary"]))
        window.editor.span_lo.setValue(item["lo"]);window.editor.span_hi.setValue(item["hi"])
        window.editor.explain((item["lo"]+item["hi"])//2)
    choice.currentIndexChanged.connect(lambda _:navigate())
    # Ordinary volume browsing also emits ready. Only a queue-requested load
    # may navigate back to its example; otherwise Next scan would bounce back.
    window.ready.connect(lambda: navigate() if window._seg_queue_pending else None)
    previous.triggered.connect(lambda:choice.setCurrentIndex(max(0,choice.currentIndex()-1)))
    next_item.triggered.connect(lambda:choice.setCurrentIndex(min(len(queue)-1,choice.currentIndex()+1)))
    window.queue_choice=choice
