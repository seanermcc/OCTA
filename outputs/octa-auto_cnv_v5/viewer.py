"""CNV-only reviewer: two linked maps and one read-only B-scan."""
import argparse,copy,time,uuid
from common import *
from cnv_review_v1 import gui
from cnv_review_v1.data import runs
from eight_surface.cnv_gui import _brush_mask
from review_store import ReviewRegion
from loader import Loader,OctaLoader
from thickness import LAYERS,limits,paint_filled
from matplotlib import colormaps
from scipy import ndimage as ndi
W=gui.QtWidgets;Qt=gui.Qt;Q=gui.QtCore;G=gui.QtGui

class Window(W.QMainWindow):
    ready=Q.Signal();octa_ready=Q.Signal()
    def __init__(self,start=0,manual=False,autoload=True):
        super().__init__();self.setWindowTitle('CNV review · v5');self.resize(1420,1000)
        self.visits=selected();self.scan=None;self.store=None;self.loader=None;self.octa_loader=None
        self.index=start;self.row=0;self.col=0;self.selected=-1;self.reference=-1
        self.undo_stack=[];self.redo_stack=[];self.operation='paint';self.loading=False;self.started=time.monotonic()
        self.review_seconds=0.;self.previous_tick=time.monotonic()
        self.tick=Q.QTimer(self);self.tick.timeout.connect(self.record_time);self.tick.start(1000)
        nav=self.addToolBar('Scan');nav.setMovable(False)
        nav.addAction('Previous',lambda:self.load_scan(self.index-1))
        self.scan_choice=W.QComboBox();self.scan_choice.setMinimumWidth(350)
        for visit in self.visits:self.scan_choice.addItem(visit['scan_id'])
        self.scan_choice.setCurrentIndex(start);self.scan_choice.activated.connect(self.load_scan);nav.addWidget(self.scan_choice)
        nav.addAction('Next',lambda:self.load_scan(self.index+1));nav.addSeparator()
        self.save_action=nav.addAction('Save',self.save_all);self.save_action.setShortcut('Ctrl+S')
        nav.addAction('Finish scan',self.finish_scan)
        self.scan_status=W.QLabel('');nav.addWidget(self.scan_status)
        self.addToolBarBreak();edit=self.addToolBar('CNV');edit.setMovable(False)
        for title,fn,key in [('Add CNV',self.add_cnv,'N'),('Paint',lambda:self.brush('paint'),'B'),('Erase',lambda:self.brush('erase'),'E'),
                ('Keep CNV',self.keep,'K'),('Remove',self.remove,'Delete'),('Unsure',self.unsure,'U'),('Undo',self.undo,'Ctrl+Z'),('Redo',self.redo,'Ctrl+Shift+Z')]:
            act=edit.addAction(title,fn);act.setShortcut(key)
        self.diameter=W.QSpinBox();self.diameter.setRange(1,100);self.diameter.setValue(12);self.diameter.setSuffix(' px brush');edit.addWidget(self.diameter)
        self.diameter.valueChanged.connect(lambda v:[c.set_brush_size(v) for c in (self.structural,self.second)])
        edit.addAction('Fit views',self.fit_all)
        central=W.QWidget();layout=W.QVBoxLayout(central);layout.setContentsMargins(8,4,8,6);self.setCentralWidget(central)
        self.split=W.QSplitter(Qt.Orientation.Vertical);layout.addWidget(self.split)
        self.top=W.QSplitter(Qt.Orientation.Horizontal)
        self.structural=gui.ReviewCanvas('Structural OCT');self.second=gui.ReviewCanvas('OCTA or thickness')
        self.structural_group=self.panel('Structural OCT',self.structural)
        self.second_group=self.panel('OCTA',self.second)
        controls=W.QHBoxLayout();self.mode=W.QComboBox();self.mode.addItems(['OCTA','Layer thickness']);controls.addWidget(self.mode)
        self.layer=W.QComboBox();self.layer.addItems([n for n,_,_ in LAYERS]);self.layer.setEnabled(False);self.layer.hide();controls.addWidget(self.layer)
        self.second_group.layout().insertLayout(0,controls)
        spacer=W.QLabel('Click to inspect · wheel to zoom · middle-drag to pan');spacer.setMinimumHeight(self.mode.sizeHint().height())
        self.structural_group.layout().insertWidget(0,spacer)
        self.scale=W.QLabel('OCTA: saved retinal crop');self.second_group.layout().addWidget(self.scale)
        self.tool_hint=W.QLabel('Add CNV, then paint a closed loop. Release to fill.');self.structural_group.layout().addWidget(self.tool_hint)
        self.top.addWidget(self.structural_group);self.top.addWidget(self.second_group)
        side=W.QWidget();side.setMaximumWidth(240);side.setMinimumWidth(190);sv=W.QVBoxLayout(side)
        sv.addWidget(W.QLabel('CNVs'))
        self.auto_check=W.QCheckBox('Show suggestions');self.auto_check.setChecked(not manual);sv.addWidget(self.auto_check)
        self.region_list=W.QListWidget();sv.addWidget(self.region_list)
        self.summary=W.QLabel();self.summary.setWordWrap(True);sv.addWidget(self.summary)
        self.notes=W.QPlainTextEdit();self.notes.setPlaceholderText('Optional note for this region');self.notes.setMaximumHeight(80);sv.addWidget(self.notes)
        self.show_removed=W.QCheckBox('Show removed');sv.addWidget(self.show_removed)
        self.top.addWidget(side);self.top.setSizes([600,600,220]);self.split.addWidget(self.top)
        self.bscan=W.QGraphicsView();self.bscan.setScene(W.QGraphicsScene());self.bscan.setBackgroundBrush(G.QColor('#14161a'))
        self.bscan_group=self.panel('B-scan · read-only',self.bscan)
        rowbar=W.QHBoxLayout();self.row_spin=W.QSpinBox();self.row_spin.setPrefix('B-scan ');self.row_spin.setKeyboardTracking(False);rowbar.addWidget(self.row_spin)
        self.row_slider=W.QSlider(Qt.Orientation.Horizontal);self.row_slider.setTracking(False);rowbar.addWidget(self.row_slider)
        self.point=W.QLabel();rowbar.addWidget(self.point);self.bscan_group.layout().insertLayout(0,rowbar)
        self.split.addWidget(self.bscan_group);self.split.setSizes([570,340])
        self.boundary_items=[];self.boundary_indices=()
        for canvas in (self.structural,self.second):
            canvas.navigated.connect(self.navigate);canvas.strokeFinished.connect(self.stroke)
        self.mode.currentIndexChanged.connect(self.mode_changed);self.layer.currentIndexChanged.connect(self.layer_changed)
        self.region_list.currentRowChanged.connect(self.select_item);self.notes.textChanged.connect(self.notes_changed)
        self.auto_check.toggled.connect(self.suggestions_changed);self.show_removed.toggled.connect(self.refresh_regions)
        self.row_spin.valueChanged.connect(lambda row:self.navigate(row,self.col,False));self.row_slider.valueChanged.connect(lambda row:self.navigate(row,self.col,False))
        if autoload:Q.QTimer.singleShot(0,lambda:self.load_scan(start))

    @staticmethod
    def panel(title,widget):
        group=W.QGroupBox(title);box=W.QVBoxLayout(group);box.setContentsMargins(5,7,5,4);box.addWidget(widget);return group

    def record_time(self):
        now=time.monotonic()
        if self.scan is not None and self.isActiveWindow() and not self.loading:self.review_seconds+=min(now-self.previous_tick,2.)
        self.previous_tick=now

    def load_scan(self,index):
        if not 0<=index<len(self.visits) or self.loading:return
        if self.octa_loader is not None and self.octa_loader.isRunning():
            self.statusBar().showMessage('OCTA is loading; wait for it to finish before changing scans.');return
        if not self.save_all():return
        self.loading=True;self.pending=index;self.centralWidget().setEnabled(False)
        self.statusBar().showMessage('Loading saved scan and matching thickness boundaries…')
        self.loader=Loader(self.visits[index]['scan_id']);self.loader.loaded.connect(self.loaded);self.loader.failed.connect(self.load_failed);self.loader.start()

    def load_failed(self,error):
        self.loading=False;self.centralWidget().setEnabled(True);self.scan_choice.setCurrentIndex(self.index)
        self.statusBar().showMessage(error);W.QMessageBox.critical(self,'Could not load scan',error)

    def loaded(self,result):
        self.scan,self.store=result;self.index=getattr(self,'pending',self.index);self.scan_choice.setCurrentIndex(self.index)
        self.loading=False;self.centralWidget().setEnabled(True);self.selected=-1;self.reference=-1
        self.undo_stack.clear();self.redo_stack.clear();self.review_seconds=0.;self.previous_tick=time.monotonic()
        self.prior_review_seconds=self.store.review_context.get('active_review_seconds',0.)
        labs,n=ndi.label(self.scan.manual_mask,np.ones((3,3)));self.manual_components=[labs==k for k in range(1,n+1)]
        self.row=self.scan.native_shape[0]//2;self.col=self.scan.native_shape[1]//2
        for c in (self.structural,self.second):c.set_image(self.scan.structural_enface)
        for control in (self.row_spin,self.row_slider):control.setRange(0,self.scan.native_shape[0]-1)
        self.refresh_regions();self.navigate(self.row,self.col);self.mode_changed()
        self.statusBar().showMessage('Add or select a CNV. Closed paint loops fill; Escape returns to inspection.')
        Q.QTimer.singleShot(150,self.fit_all);Q.QTimer.singleShot(700,self.fit_all);self.ready.emit()

    def current_region(self):
        return self.store.regions[self.selected] if self.store and 0<=self.selected<len(self.store.regions) else None

    def visible_regions(self):
        if not self.store:return []
        return [(i,r) for i,r in enumerate(self.store.regions) if (r.decision!='rejected' or self.show_removed.isChecked())
            and (self.auto_check.isChecked() or not r.seed_ids or r.decision!='unreviewed')]

    def untouched_manual(self):
        used={ev['component'] for r in self.store.regions for ev in r.events if ev['action']=='copy saved manual' and 'component' in ev}
        return [(i,m) for i,m in enumerate(self.manual_components) if i not in used]

    def refresh_regions(self,*args):
        if self.store is None:return
        self.region_list.blockSignals(True);self.region_list.clear();self.entries=[];active=-1
        for i,r in self.visible_regions():
            title='Removed' if r.decision=='rejected' else 'Unsure' if r.category=='Other' else 'CNV' if r.decision=='approved' else 'Suggestion' if r.seed_ids else 'Draft CNV'
            self.region_list.addItem(f'{title} {i+1}');self.entries.append(('region',i))
            if i==self.selected:active=len(self.entries)-1
        for i,m in self.untouched_manual():
            self.region_list.addItem(f'Saved manual {i+1}');self.entries.append(('manual',i))
            if i==self.reference:active=len(self.entries)-1
        self.region_list.setCurrentRow(active);self.region_list.blockSignals(False)
        self.update_summary();self.render_maps()

    def update_summary(self):
        r=self.current_region();self.notes.blockSignals(True);self.notes.setPlainText(r.notes if r else '');self.notes.setEnabled(r is not None);self.notes.blockSignals(False)
        n=sum(r.decision=='approved' and r.category=='Full Lesion' for r in self.store.regions)
        self.summary.setText(f'{n} confirmed CNV'+('s' if n!=1 else '')+'\n'+('Whole scan reviewed' if self.store.scan_review.get('whole_field_checked') else 'Scan review in progress'))
        self.scan_status.setText(('Unsaved changes' if self.store.dirty else 'Saved' if self.store.path.exists() else 'Previous work loaded' if self.store.loaded_review_path else 'No edits yet'))

    def select_item(self,index):
        if index<0 or index>=len(self.entries):return
        kind,k=self.entries[index];self.selected=k if kind=='region' else -1;self.reference=k if kind=='manual' else -1
        mask=self.current_region().mask if self.selected>=0 else self.manual_components[k]
        yy,xx=np.nonzero(mask)
        if len(yy):self.navigate(int(np.median(yy)),int(np.median(xx)),False)
        self.update_summary();self.render_maps()

    def checkpoint(self):
        self.undo_stack.append((copy.deepcopy(self.store.regions),copy.deepcopy(self.store.scan_review),self.selected,self.reference));self.redo_stack.clear()

    def edited(self):
        self.store.invalidate_complete();self.refresh_regions();self.statusBar().showMessage('Edited · Save or Ctrl+S')

    def undo(self):self.history(self.undo_stack,self.redo_stack)
    def redo(self):self.history(self.redo_stack,self.undo_stack)
    def history(self,source,target):
        if self.store is None or not source:return
        target.append((copy.deepcopy(self.store.regions),copy.deepcopy(self.store.scan_review),self.selected,self.reference))
        self.store.regions,self.store.scan_review,self.selected,self.reference=source.pop();self.refresh_regions()

    def add_cnv(self):
        self.selected=-1;self.reference=-1;self.refresh_regions();self.brush('paint');self.tool_hint.setText('New CNV: paint a closed loop, then Keep CNV.')

    def brush(self,operation):
        self.operation=operation
        for c in (self.structural,self.second):c.set_mode('cnv_brush');c.set_brush_size(self.diameter.value())
        self.tool_hint.setText(('Paint: close the loop and release to fill.' if operation=='paint' else 'Erase: trim the selected CNV.')+' Esc: inspect')

    def ensure_region(self):
        r=self.current_region()
        if r is not None:return r
        mask=self.manual_components[self.reference].copy() if self.reference>=0 else np.zeros(self.scan.native_shape,bool)
        r=ReviewRegion(uuid.uuid4().hex[:12],mask,origin='hand drawn in v5').initialize();r.core[:]=False
        if self.reference>=0:
            r.origin='copy of saved manual';r.event('copy saved manual',component=self.reference,sources=self.scan.metadata.get('reference_review',{}).get('sources',[]))
        self.store.regions.append(r);self.selected=len(self.store.regions)-1;self.reference=-1;return r

    def stroke(self,points,operation):
        if self.scan is None or not points:return
        erasing=self.operation=='erase' or operation.endswith('erase')
        if erasing and self.current_region() is None and self.reference<0:return
        self.checkpoint();r=self.ensure_region();old=r.mask.copy()
        stroke=_brush_mask(points,self.scan.native_shape,self.diameter.value())
        r.mask=old&~stroke if erasing else paint_filled(old,stroke)
        if not r.mask.any():
            r.mask=old;r.decision='rejected';r.event('erased entire CNV')
        else:
            r.touched|=old^r.mask;r.decision='unreviewed';r.event('erase' if erasing else 'filled paint',edited_pixels=int((old^r.mask).sum()))
        self.edited()

    def keep(self):self.classify('Full Lesion')
    def unsure(self):self.classify('Other')
    def classify(self,category):
        if self.current_region() is None and self.reference<0:return
        self.checkpoint();r=self.ensure_region();r.category=category;r.decision='approved';r.event('explicit CNV review',category=category);self.edited()

    def remove(self):
        if self.current_region() is None and self.reference<0:return
        self.checkpoint();r=self.ensure_region();r.decision='rejected';r.event('explicit remove CNV');self.selected=-1;self.edited()

    def notes_changed(self):
        r=self.current_region()
        if r is None:return
        r.notes=self.notes.toPlainText();self.store.invalidate_complete();self.update_status_only()

    def update_status_only(self):
        self.scan_status.setText('Unsaved changes');self.summary.setText('Scan review in progress')

    def suggestions_changed(self,visible):
        if self.store is None:return
        if visible:self.store.review_context['automatic_proposals_seen']=True
        r=self.current_region()
        if not visible and r and r.seed_ids and r.decision=='unreviewed':self.selected=-1
        self.refresh_regions()

    def render_maps(self):
        if self.scan is None:return
        self.colour(self.structural,self.scan.structural_enface,'gray')
        if self.mode.currentIndex()==0:
            values=self.scan.octa
            self.colour(self.second,values if values is not None else np.full(self.scan.native_shape,np.nan),'gray')
            self.second_group.setTitle('OCTA · saved retinal crop')
            self.scale.setStyleSheet('')
            self.scale.setText('OCTA loading…' if values is None and not self.scan.octa_error else 'OCTA unavailable: '+self.scan.octa_error if self.scan.octa_error else 'Real OCTA · mean projection of saved retinal crop')
        else:
            k=self.layer.currentIndex();values=self.scan.thickness[k];lo,hi=limits(values)
            self.colour(self.second,values,'viridis');self.second_group.setTitle(LAYERS[k][0]+' thickness (µm)')
            self.scale.setStyleSheet('padding:3px;color:white;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #440154,stop:0.5 #21918c,stop:1 #fde725);')
            self.scale.setText(f'{lo:.1f} → {hi:.1f} µm · gray: unavailable · experimental')
        visible=self.visible_regions()
        if self.auto_check.isChecked() and any(r.seed_ids for _,r in visible):self.store.review_context['automatic_proposals_seen']=True
        for canvas in (self.structural,self.second):
            for item in canvas.review_items:canvas.scene().removeItem(item)
            canvas.review_items=[]
            for i,r in visible:
                color='#92969c' if r.decision=='rejected' else '#bc98ed' if r.category=='Other' else '#55d5a0' if r.decision=='approved' else '#ffbb55'
                self.mask_overlay(canvas,r.mask,color,i==self.selected)
            for i,m in self.untouched_manual():self.mask_overlay(canvas,m,'#4ce0ff',i==self.reference)
            canvas.set_cursor(self.row,self.col)

    def colour(self,canvas,values,cmap):
        lo,hi=limits(values);norm=np.clip((np.nan_to_num(values,nan=lo)-lo)/(hi-lo),0,1)
        rgba=(colormaps[cmap](norm)*255).astype('uint8');rgba[~np.isfinite(values)]=[62,66,72,255]
        h,w=values.shape;img=G.QImage(rgba.data,w,h,w*4,G.QImage.Format.Format_RGBA8888).copy()
        canvas._pix.setPixmap(G.QPixmap.fromImage(img));canvas._shape=values.shape;canvas.scene().setSceneRect(0,0,w,h)

    def mask_overlay(self,canvas,mask,color,selected=False):
        edge=mask&~ndi.binary_erosion(mask)
        for pixels,opacity,z in ((mask,.18,5),(edge,1.,7)) if selected else ((edge,.8,7),):
            path=G.QPainterPath()
            for row in np.flatnonzero(pixels.any(1)):
                for lo,hi in runs(pixels[row]):path.addRect(lo,row,hi-lo,1)
            item=canvas.scene().addPath(path,G.QPen(Qt.PenStyle.NoPen),G.QBrush(G.QColor(color)));item.setOpacity(opacity);item.setZValue(z);canvas.review_items.append(item)

    def mode_changed(self,*args):
        self.layer.setEnabled(self.mode.currentIndex()==1)
        self.layer.setVisible(self.mode.currentIndex()==1)
        if self.scan is None:return
        if self.mode.currentIndex()==0 and self.scan.octa is None and not self.scan.octa_error:
            if self.octa_loader is None or not self.octa_loader.isRunning():
                self.octa_loader=OctaLoader(self.scan.scan_id);self.octa_loader.loaded.connect(self.octa_loaded);self.octa_loader.failed.connect(self.octa_failed);self.octa_loader.start()
        self.render_maps();self.render_bscan();Q.QTimer.singleShot(80,self.fit_all)

    def octa_loaded(self,result):
        self.scan.octa,self.scan.octa_metadata=result;self.render_maps();self.octa_ready.emit()
    def octa_failed(self,error):
        self.scan.octa_error=error;self.render_maps();self.octa_ready.emit()
    def layer_changed(self,*args):
        if self.scan:self.render_maps();self.render_bscan()

    def navigate(self,row,col,select_hit=True):
        if self.scan is None:return
        self.row=int(np.clip(row,0,self.scan.native_shape[0]-1));self.col=int(np.clip(col,0,self.scan.native_shape[1]-1))
        for control in (self.row_spin,self.row_slider):control.blockSignals(True);control.setValue(self.row);control.blockSignals(False)
        # Clicked CNV selection is exact; no snapping to a different B-scan.
        if select_hit:
            hit=next((i for i,r in self.visible_regions() if r.mask[self.row,self.col]),None)
            if hit is not None:self.selected=hit;self.reference=-1
            else:
                ref=next((i for i,m in self.untouched_manual() if m[self.row,self.col]),None)
                if ref is not None:self.selected=-1;self.reference=ref
        key=('region',self.selected) if self.selected>=0 else ('manual',self.reference)
        self.region_list.blockSignals(True);self.region_list.setCurrentRow(self.entries.index(key) if key in self.entries else -1);self.region_list.blockSignals(False)
        self.render_maps();self.render_bscan();self.update_summary()

    def render_bscan(self):
        if self.scan is None:return
        scene=self.bscan.scene();scene.clear();self.boundary_items=[];self.boundary_indices=()
        image=self.scan.images[self.row];lo,hi=limits(image)
        pixels=np.ascontiguousarray((np.clip((image-lo)/(hi-lo),0,1)*255).astype('uint8'));h,w=pixels.shape
        qimage=G.QImage(pixels.data,w,h,w,G.QImage.Format.Format_Grayscale8).copy();scene.addPixmap(G.QPixmap.fromImage(qimage));scene.setSceneRect(0,0,w,h)
        if self.mode.currentIndex()==1:
            k=self.layer.currentIndex();name,top,bottom=LAYERS[k];self.boundary_indices=(top,bottom)
            valid=np.isfinite(self.scan.thickness[k,self.row]);self.displayed_boundaries=[]
            for boundary,color in ((top,'#55d5ff'),(bottom,'#ffd166')):
                ys=np.where(valid,self.scan.endpoints[self.row,boundary],np.nan);self.displayed_boundaries.append(ys.copy())
                path=G.QPainterPath();started=False
                for x,y in enumerate(ys):
                    if not np.isfinite(y):started=False;continue
                    if started:path.lineTo(x+.5,float(y))
                    else:path.moveTo(x+.5,float(y));started=True
                pen=G.QPen(G.QColor(color),1.5);pen.setCosmetic(True);self.boundary_items.append(scene.addPath(path,pen))
            self.bscan_group.setTitle(f'B-scan · {name} · cyan: {self.scan.surface_names[top]} · gold: {self.scan.surface_names[bottom]}')
            value=self.scan.thickness[k,self.row,self.col];self.point.setText(f'A-line {self.col} · '+(f'{value:.1f} µm' if np.isfinite(value) else 'Thickness unavailable'))
        else:
            self.displayed_boundaries=[];self.bscan_group.setTitle('B-scan · OCTA inspection · read-only');self.point.setText(f'A-line {self.col}')
        pen=G.QPen(G.QColor('#4ce0ff'),1);pen.setCosmetic(True);scene.addLine(self.col+.5,0,self.col+.5,h,pen)
        self.fit_bscan()

    def fit_bscan(self):
        if self.scan is None:return
        rect=self.bscan.scene().sceneRect();v=self.bscan.viewport();sx=1460/self.scan.native_shape[1];sy=1.12
        scale=min(max(1,v.width()-16)/(rect.width()*sx),max(1,v.height()-16)/(rect.height()*sy))
        self.bscan.setTransform(G.QTransform.fromScale(scale*sx,scale*sy));self.bscan.centerOn(rect.center())

    def fit_all(self):
        for canvas in (self.structural,self.second):
            rect=canvas.scene().sceneRect();v=canvas.viewport()
            if rect.isEmpty():continue
            scale=min(max(1,v.width()-16)/rect.width(),max(1,v.height()-16)/rect.height());canvas.setTransform(G.QTransform.fromScale(scale,scale));canvas.centerOn(rect.center())
        self.fit_bscan()

    def save_all(self):
        if self.store is None:return True
        try:
            self.store.review_context['active_review_seconds']=round(self.review_seconds+self.prior_review_seconds,2)
            self.store.review_context['thickness_revision']=self.scan.thickness_metadata.get('revision')
            self.store.save(dict(name='unchanged v3 CNV suggestions',path=str(DATA/'proposals'/f'{self.scan.scan_id}.npz')),
                list(self.scan.thickness_metadata.get('correction_fingerprints',{})),{})
            self.update_summary();return True
        except Exception as exc:W.QMessageBox.critical(self,'Could not save; edits remain here',str(exc));return False

    def finish_scan(self,confirmed=False):
        if self.store is None:return
        drafts=[r for _,r in self.visible_regions() if r.decision=='unreviewed']
        if drafts or self.untouched_manual():
            self.statusBar().showMessage('Keep, remove, or mark unsure each visible region before finishing. You can save partial edits anytime.');return
        if not confirmed:
            result=W.QMessageBox.question(self,'Finish whole-scan review',
                'Have you inspected the entire image and added all CNVs you can identify?\n\nMark unreadable or ambiguous areas Unsure first. Unmarked areas will be recorded as reviewed background. Unsure regions stay excluded from training.',
                W.QMessageBox.StandardButton.Yes|W.QMessageBox.StandardButton.Cancel,W.QMessageBox.StandardButton.Cancel)
            if result!=W.QMessageBox.StandardButton.Yes:return
        self.checkpoint();self.store.scan_review=dict(status='complete',whole_field_checked=True,
            confirmed_cnv_count=sum(r.decision=='approved' and r.category=='Full Lesion' for r in self.store.regions),
            uncertainty_region_ids=[r.id for r in self.store.regions if r.decision=='approved' and r.category=='Other'],
            automatic_suggestions_visible=self.auto_check.isChecked(),reviewed_absence=not any(r.decision=='approved' and r.category in ('Full Lesion','Other') for r in self.store.regions))
        self.save_all();self.refresh_regions()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:
            for c in (self.structural,self.second):c.set_mode('navigate')
            self.tool_hint.setText('Inspect: click an image or move the B-scan slider.')
        else:super().keyPressEvent(event)

    def closeEvent(self,event):
        if any(worker is not None and worker.isRunning() for worker in (self.loader,self.octa_loader)):
            self.statusBar().showMessage('Loading is still running. Close again when it finishes.');event.ignore()
        elif self.save_all():event.accept()
        else:event.ignore()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scan');p.add_argument('--manual',action='store_true');p.add_argument('--capture',action='store_true');args=p.parse_args()
    app=W.QApplication([]);gui.configure_app(app)
    index=next((i for i,v in enumerate(selected()) if v['scan_id']==args.scan),0);window=Window(index,args.manual)
    if args.capture:
        def capture_error(error):
            print('CAPTURE LOAD ERROR:',error,flush=True);app.exit(1)
        window.load_failed=capture_error
        Q.QTimer.singleShot(90000,lambda:(print('Capture timed out',flush=True),app.exit(2)))
        def capture():
            def finish():window.fit_all();window.grab().save(str(destination(HERE/'verification/v5_octa.png')));window.mode.setCurrentIndex(1);window.layer.setCurrentIndex(2);Q.QTimer.singleShot(300,thickness_capture)
            Q.QTimer.singleShot(800,finish)
        def thickness_capture():window.fit_all();window.grab().save(str(destination(HERE/'verification/v5_thickness.png')));app.quit()
        window.octa_ready.connect(capture)
    window.show();raise SystemExit(app.exec())
