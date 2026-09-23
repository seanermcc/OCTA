"""Manual whole-field footprint editor with exact native lateral B-scan bands."""
from common import *
from review_store import Store, progress, valid_confirmation, targets
from loader import Cache, context_overlays
from PySide6 import QtCore as Q, QtGui as G, QtWidgets as W
from scipy.ndimage import binary_fill_holes, binary_erosion
from proposals import seed_gui_drafts
import argparse, copy
Qt=Q.Qt
COLORS=dict(kept='#55d88a',draft='#ffa448',unsure='#c38afa',excluded='#c38afa',removed='#999999')

def configure_app(app):
    # The offscreen Qt platform on this workstation needs an explicit font file.
    font_id=G.QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    families=G.QFontDatabase.applicationFontFamilies(font_id)
    app.setFont(G.QFont(families[0] if families else 'Segoe UI',9));app.setStyle('Fusion')
    app.setStyleSheet('QToolBar {spacing: 6px; padding: 3px;} QGroupBox {font-weight: 600;}')

def paint_filled(old,stroke):
    old_holes=binary_fill_holes(old)&~old
    painted=old|binary_fill_holes(stroke)
    return painted|(binary_fill_holes(painted)&~painted&~old_holes)

def brush_segment(mask,start,end,diameter):
    y0,x0=start;y1,x1=end
    for t in np.linspace(0,1,max(2,int(max(abs(x1-x0),abs(y1-y0))*2)+1)):
        y=y0+(y1-y0)*t;x=x0+(x1-x0)*t;r=diameter/2
        ya=max(0,int(y-r));yb=min(mask.shape[0],int(y+r)+2);xa=max(0,int(x-r));xb=min(mask.shape[1],int(x+r)+2)
        yy,xx=np.ogrid[ya:yb,xa:xb];mask[ya:yb,xa:xb]|=(yy-y)**2+(xx-x)**2<=r*r

def pixmap(values):
    values=np.asarray(values);valid=values[np.isfinite(values)]
    lo,hi=np.percentile(valid,[2,98]) if len(valid) else (0,1)
    pixels=np.ascontiguousarray((np.clip((np.nan_to_num(values,nan=lo)-lo)/max(hi-lo,1e-6),0,1)*255).astype('uint8'))
    h,w=pixels.shape
    return G.QPixmap.fromImage(G.QImage(pixels.data,w,h,w,G.QImage.Format.Format_Grayscale8).copy())

class Canvas(W.QGraphicsView):
    navigate=Q.Signal(int,int);painted=Q.Signal(object);preview=Q.Signal(object)
    def __init__(self):
        super().__init__();self.setScene(W.QGraphicsScene(self));self.setBackgroundBrush(G.QColor('#11151c'))
        self.shape=(512,512);self.mode='inspect';self.diameter=12;self.stroke=None;self.pan=None;self.items=[];self.cursor_items=[]
        self.setTransformationAnchor(W.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumSize(180,150)

    def image(self,values):
        self.scene().clear();self.items=[];self.cursor_items=[];self.shape=values.shape
        self.scene().addPixmap(pixmap(values));self.scene().setSceneRect(0,0,values.shape[1],values.shape[0])

    def point(self,event):
        p=self.mapToScene(event.position().toPoint())
        return int(np.clip(np.floor(p.y()),0,self.shape[0]-1)),int(np.clip(np.floor(p.x()),0,self.shape[1]-1))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.MiddleButton:self.pan=event.position().toPoint();return
        if event.button()==Qt.MouseButton.LeftButton:
            p=self.point(event)
            if self.mode=='inspect':self.navigate.emit(*p)
            else:
                self.stroke=np.zeros(self.shape,bool);self.last=p;brush_segment(self.stroke,p,p,self.diameter);self.preview.emit(self.stroke)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.pan is not None:
            p=event.position().toPoint();delta=p-self.pan;self.pan=p
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x());self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y());return
        if self.stroke is not None:
            p=self.point(event);brush_segment(self.stroke,self.last,p,self.diameter);self.last=p;self.preview.emit(self.stroke);return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.MiddleButton:self.pan=None;return
        if self.stroke is not None:
            p=self.point(event);brush_segment(self.stroke,self.last,p,self.diameter);s=self.stroke;self.stroke=None;self.painted.emit(s);return
        super().mouseReleaseEvent(event)

    def wheelEvent(self,event):
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        if .1<self.transform().m11()*factor<20:self.scale(factor,factor)

    def fit(self):
        self.fitInView(self.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)

    def overlays(self,regions):
        for item in self.items:self.scene().removeItem(item)
        self.items=[]
        for mask,color,selected in regions:
            edge=mask&~binary_erosion(mask);rgba=np.zeros((*mask.shape,4),np.uint8);c=G.QColor(color)
            rgba[mask]=[c.red(),c.green(),c.blue(),65 if selected else 28];rgba[edge]=[c.red(),c.green(),c.blue(),255]
            h,w=mask.shape;img=G.QImage(rgba.data,w,h,w*4,G.QImage.Format.Format_RGBA8888).copy()
            item=self.scene().addPixmap(G.QPixmap.fromImage(img));item.setZValue(5);self.items.append(item)

    def cursor(self,row,col):
        for item in self.cursor_items:self.scene().removeItem(item)
        p=G.QPen(G.QColor('#70dcf8'),1,Qt.PenStyle.DotLine);p.setCosmetic(True)
        self.cursor_items=[self.scene().addLine(0,row+.5,self.shape[1],row+.5,p),self.scene().addLine(col+.5,0,col+.5,self.shape[0],p)]
        for item in self.cursor_items:item.setZValue(9)

class Window(W.QMainWindow):
    ready=Q.Signal()
    def __init__(self,start=None,review_directory=None,synthetic=False,autoload=True):
        super().__init__();self.setWindowTitle('V8 Model 1 conservative · correct 30 scans · v7 editor');self.resize(1510,980)
        self.queue=read(HERE/'queue/queue.json')['acquisitions'];self.filtered=list(range(len(self.queue)))
        self.review_directory=Path(review_directory or HERE/'review/regions');self.synthetic=synthetic
        self.session_path=(self.review_directory.parent/'session.json') if synthetic else HERE/'review/session.json'
        self.session_id=uuid.uuid4().hex
        self.index=0;self.queue_cursor=0;self.row=256;self.col=256;self.selected=-1;self.scan=None;self.store=None
        self.cache=Cache();self.future=None;self.pending=None;self.preview_mask=None;self.context={};self.operation='inspect';self.last_tick=time.monotonic();self.closing=False
        self.scan_seconds=0.;self.session_exposures=[];self.view_log=dict(focused_seconds=0.,exposures=[]);self.milestone_shown=False
        session=read(self.session_path) if self.session_path.exists() else {}
        self.queue_cursor=min(session.get('queue_cursor',0),len(self.queue)-1)
        self.resume_row=session.get('row',256)
        initial=next((i for i,a in enumerate(self.queue) if a['scan_id']==(start or session.get('scan_id'))),0)
        self.toolbar();central=W.QWidget();layout=W.QVBoxLayout(central);self.setCentralWidget(central)
        self.progress_label=W.QLabel();self.progress_label.setWordWrap(True);self.progress_label.setStyleSheet('font-size: 17px; font-weight: 600; padding: 3px;');layout.addWidget(self.progress_label)
        self.coverage=W.QLabel();self.coverage.setWordWrap(True);layout.addWidget(self.coverage)
        self.identity=W.QLabel();self.identity.setWordWrap(True);layout.addWidget(self.identity)
        legend=W.QLabel('<span style="color:#269d55">Green: kept CNV</span> · <span style="color:#c77515">Orange: Model 1 draft / new draft</span> · <span style="color:#199aa8">Cyan: historical reference</span> · <span style="color:#985aca">Purple: unsure / excluded</span> · Gray: removed · Gold: Model 1 before filtering');legend.setWordWrap(True);layout.addWidget(legend)
        splitter=W.QSplitter(Qt.Orientation.Vertical);layout.addWidget(splitter,1)
        top=W.QSplitter();self.structural=Canvas();self.octa=Canvas()
        top.addWidget(self.panel('Structural OCT en face',self.structural));top.addWidget(self.panel('Actual OCTA · saved retinal crop projection, not a layer slab',self.octa))
        side=W.QWidget();sv=W.QVBoxLayout(side);side.setMinimumWidth(265);side.setMaximumWidth(310)
        sv.addWidget(W.QLabel('Separate CNV regions / uncertain areas'))
        self.region_list=W.QListWidget();self.region_list.currentRowChanged.connect(self.select);sv.addWidget(self.region_list)
        self.absence=W.QCheckBox('No-CNV present');self.absence.setToolTip('The entire image is assessable and contains no CNV. Confirm entire image commits this absence.');sv.addWidget(self.absence);self.absence.toggled.connect(self.absence_changed)
        self.confirm_button=W.QPushButton('Confirm entire image');self.confirm_button.clicked.connect(self.confirm);sv.addWidget(self.confirm_button)
        meaning=W.QLabel('After full inspection: kept CNVs are positive; all other assessable pixels are negative. Unsure / excluded pixels stay ignored. Save alone keeps a Draft.');meaning.setWordWrap(True);sv.addWidget(meaning)
        self.status=W.QLabel();self.status.setWordWrap(True);sv.addWidget(self.status)
        self.prediction=W.QCheckBox('Reference: Model 1 before filtering');sv.addWidget(self.prediction)
        self.historical=W.QCheckBox('Reference: historical manual');sv.addWidget(self.historical)
        self.removed=W.QCheckBox('Show removed');sv.addWidget(self.removed)
        for box in (self.prediction,self.historical):box.toggled.connect(self.context_changed)
        self.removed.toggled.connect(self.render)
        self.context_note=W.QLabel('Correct orange proposals, Keep real CNVs, Remove false detections, and Add missed CNVs. Inspect the whole field before confirming.');self.context_note.setWordWrap(True);sv.addWidget(self.context_note)
        self.reviewer=W.QLineEdit(os.environ.get('USERNAME','reviewer'));self.reviewer.setPlaceholderText('Reviewer ID');sv.addWidget(W.QLabel('Reviewer'));sv.addWidget(self.reviewer)
        self.reviewer.editingFinished.connect(self.reviewer_changed)
        top.addWidget(side);top.setSizes([590,590,280]);splitter.addWidget(top)
        self.bscan=Canvas();self.bscan_group=self.panel('Native structural B-scan · lateral footprint bands, NOT axial lesion extent',self.bscan)
        rowbar=W.QHBoxLayout();self.spin=W.QSpinBox();self.spin.setRange(0,511);self.spin.setPrefix('B-scan ');rowbar.addWidget(self.spin)
        self.slider=W.QSlider(Qt.Orientation.Horizontal);self.slider.setRange(0,511);rowbar.addWidget(self.slider)
        self.point_label=W.QLabel();rowbar.addWidget(self.point_label);self.bscan_group.layout().insertLayout(0,rowbar);splitter.addWidget(self.bscan_group);splitter.setSizes([545,285])
        for c in (self.structural,self.octa):
            c.navigate.connect(self.navigate);c.painted.connect(self.stroke);c.preview.connect(self.stroke_preview)
        self.spin.valueChanged.connect(lambda b:self.navigate(b,self.col));self.slider.valueChanged.connect(lambda b:self.navigate(b,self.col))
        self.poll=Q.QTimer(self);self.poll.timeout.connect(self.poll_load);self.poll.start(75)
        self.tick=Q.QTimer(self);self.tick.timeout.connect(self.timer);self.tick.start(1000)
        self.autosave=Q.QTimer(self);self.autosave.setSingleShot(True);self.autosave.timeout.connect(self.save)
        self.update_progress();self.refresh_choices()
        if autoload:Q.QTimer.singleShot(0,lambda:self.load(initial))

    @staticmethod
    def panel(title,widget):
        p=W.QGroupBox(title);v=W.QVBoxLayout(p);v.setContentsMargins(5,6,5,4);v.addWidget(widget);return p

    def toolbar(self):
        nav=self.addToolBar('Queue');nav.setMovable(False)
        nav.addAction('Previous',lambda:self.step(-1));nav.addAction('Next',lambda:self.step(1));nav.addAction('Next pending',self.next_pending)
        self.choice=W.QComboBox();self.choice.setMinimumWidth(450);self.choice.setEditable(True);self.choice.setInsertPolicy(W.QComboBox.InsertPolicy.NoInsert)
        self.choice.completer().setFilterMode(Qt.MatchFlag.MatchContains);nav.addWidget(self.choice);self.choice.activated.connect(lambda i:self.load(self.choice.itemData(i),manual=True))
        nav.addAction('Return to fixed queue',self.return_queue)
        self.addToolBarBreak();filters=self.addToolBar('Filters');filters.setMovable(False)
        self.animal=W.QComboBox();self.animal.addItems(['All animals']+sorted({a['animal'] for a in self.queue},key=lambda a:int(a[2:])))
        self.day=W.QComboBox();self.day.addItems(['All days']+sorted({a['day_label'] for a in self.queue}));filters.addWidget(self.animal);filters.addWidget(self.day)
        self.animal.currentTextChanged.connect(self.apply_filter);self.day.currentTextChanged.connect(self.apply_filter)
        filters.addAction('Skip / defer',self.defer)
        save=filters.addAction('Save',self.save);save.setShortcut('Ctrl+S')
        filters.addAction('Export confirmed sizes',self.export_sizes)
        self.hint=W.QLabel('Manual mode · Add CNV, paint a closed loop; Escape to inspect.');filters.addWidget(self.hint)
        self.addToolBarBreak();edit=self.addToolBar('CNV');edit.setMovable(False)
        for title,fn,key in [('Add CNV',self.add,'N'),('Paint',lambda:self.mode('paint'),'B'),('Erase',lambda:self.mode('erase'),'E'),('Keep CNV',lambda:self.classify('kept'),'K'),('Remove',lambda:self.classify('removed'),'Delete'),('Unsure',lambda:self.classify('unsure'),'U'),('Exclude area',lambda:self.classify('excluded'),''),('Undo',self.undo,'Ctrl+Z'),('Redo',self.redo,'Ctrl+Shift+Z')]:
            act=edit.addAction(title,fn)
            if key:act.setShortcut(key)
        self.diameter=W.QSpinBox();self.diameter.setRange(1,150);self.diameter.setValue(12);self.diameter.setSuffix(' px brush');edit.addWidget(self.diameter)
        self.diameter.valueChanged.connect(lambda v:[setattr(c,'diameter',v) for c in (self.structural,self.octa)])
        edit.addAction('Inspect',lambda:self.mode('inspect'));edit.addAction('Fit views',self.fit)
        edit.addAction('Split disconnected',self.split_disconnected)

    def refresh_choices(self):
        self.choice.blockSignals(True);self.choice.clear()
        for i in self.filtered:
            a=self.queue[i];self.choice.addItem(f'{i+1:03d} · {a["animal"]} {a["eye"]} · {a["session_date"]} {a["day_label"]} · scan {a["scan_no"]} {a["acq_time"]}',i)
        self.choice.setCurrentIndex(self.choice.findData(self.index));self.choice.blockSignals(False)

    def apply_filter(self):
        self.filtered=[i for i,a in enumerate(self.queue) if (self.animal.currentIndex()==0 or a['animal']==self.animal.currentText()) and (self.day.currentIndex()==0 or a['day_label']==self.day.currentText())]
        self.refresh_choices();self.statusBar().showMessage(f'{len(self.filtered)} candidates match; fixed queue order unchanged')

    def return_queue(self):
        self.animal.setCurrentIndex(0);self.day.setCurrentIndex(0);self.load(self.queue_cursor)

    def step(self,delta):
        if self.index not in self.filtered:return
        k=self.filtered.index(self.index)+delta
        if 0<=k<len(self.filtered):self.load(self.filtered[k])
        else:self.statusBar().showMessage('End of this queue/filter. Deferred and completed cases remain available.')

    def next_pending(self):
        for i in [x for x in self.filtered if x>self.index]+[x for x in self.filtered if x<=self.index]:
            p=self.review_directory/(self.queue[i]['scan_id']+'.json')
            if not p.exists():self.load(i);return
            state=read(p)['state']
            if not valid_confirmation(state) and not state.get('defer_reason'):self.load(i);return
        self.statusBar().showMessage('No pending candidate in this filter; deferred cases remain accessible.')

    def load(self,index,manual=False):
        if not 0<=index<len(self.queue) or self.future is not None:return
        if not self.save():return
        self.autosave.stop()
        self.pending=index
        if not manual:self.queue_cursor=index
        following=self.queue[index:index+2];self.cache.plan(following);self.future=self.cache.request(self.queue[index])
        self.centralWidget().setEnabled(False);self.statusBar().showMessage('Loading validated native OCT and actual OCTA…')
        for bar in self.findChildren(W.QToolBar):bar.setEnabled(False)

    def poll_load(self):
        if self.future is None or not self.future.done():return
        future=self.future;self.future=None;self.centralWidget().setEnabled(True)
        for bar in self.findChildren(W.QToolBar):bar.setEnabled(True)
        try:self.loaded(future.result())
        except Exception as exc:
            self.statusBar().showMessage('Recoverable load failure; retry from dropdown: '+str(exc))
            atomic(HERE/'logs'/('load_'+self.queue[self.pending]['scan_id']+'.json'),dict(at=now(),error=str(exc),status='provider unavailable; not negative'))
            self.refresh_choices()
        self.cache.release_done()

    def loaded(self,scan):
        store=Store(scan.acquisition,self.review_directory,self.reviewer.text(),self.synthetic)
        seed_gui_drafts(store)
        self.scan=scan;self.store=store;self.index=self.pending;self.selected=-1;self.preview_mask=None;self.context={};self.scan_seconds=0.;self.session_exposures=[];self.view_log=dict(focused_seconds=0.,exposures=[])
        self.row=int(np.clip(self.resume_row,0,511));self.resume_row=256;self.col=256
        for box in (self.historical,self.prediction):box.blockSignals(True);box.setChecked(False);box.blockSignals(False)
        self.structural.image(scan.structural);self.octa.image(scan.octa);self.mode('inspect')
        a=scan.acquisition
        self.identity.setText(f'{a["animal"]} · {a["eye"]} · {a["session_date"]} · {a["day_label"]} ({a["eligibility_day_basis"]}) · acquisition {a["scan_no"]} at {a["acq_time"]}\n'+a.get('metadata_note','')+'  '+a['scan_id'])
        self.refresh_choices();self.refresh();self.navigate(self.row,self.col);self.fit();Q.QTimer.singleShot(150,self.fit)
        self.identity.setText(self.identity.text()+' · '+a['preview_role'])
        if store.state['regions']:self.selected=0;self.refresh()
        self.save_session();self.statusBar().showMessage('Ready · Model 1 proposals require your review; saved corrections resume automatically');self.ready.emit()
        if self.index+1<len(self.queue):self.cache.request(self.queue[self.index+1])

    def save_session(self):
        if self.scan:
            atomic(self.session_path,dict(scan_id=self.queue[self.index]['scan_id'],queue_cursor=self.queue_cursor,row=self.row,updated=now()))
            # Viewing/timing logs have no annotation decisions and never enter counts.
            atomic(self.session_path.parent/'sessions'/f'{self.session_id}_{self.queue[self.index]["scan_id"]}.json',
                dict(kind='viewing log, not annotation',synthetic=self.synthetic,scan_id=self.queue[self.index]['scan_id'],
                    reviewer=self.reviewer.text(),at=now(),row=self.row,focused_seconds=self.view_log['focused_seconds'],
                    reference_exposures=self.view_log['exposures']))

    def timer(self):
        t=time.monotonic()
        if self.scan and self.isActiveWindow() and self.future is None:
            elapsed=min(t-self.last_tick,2.);self.scan_seconds+=elapsed;self.view_log['focused_seconds']+=elapsed
        self.last_tick=t

    def reviewer_changed(self):
        if self.store:self.store.reviewer=self.reviewer.text().strip() or os.environ.get('USERNAME','unknown')

    def current(self):
        return self.store.state['regions'][self.selected] if self.store and 0<=self.selected<len(self.store.state['regions']) else None

    def mode(self,mode):
        if mode!='inspect' and self.current() is None:self.statusBar().showMessage('Choose Add CNV, or select a region first.');return
        if mode!='inspect' and self.current()['state']=='removed':self.statusBar().showMessage('Restore this removed region with Keep CNV or Unsure before painting.');return
        self.operation=mode
        for c in (self.structural,self.octa):c.mode=mode
        self.hint.setText('Inspect · click either en-face panel to navigate' if mode=='inspect' else f'{mode.title()} selected region · closed paint loops fill · Escape to inspect')

    def add(self):
        if not self.store or self.future:return
        self.selected=self.store.add();self.changed();self.mode('paint')

    def classify(self,state):
        if not self.store or self.future:return
        if self.current() is None:
            if state in ('unsure','excluded'):self.add()
            else:return
        try:self.store.set_region(self.selected,state=state)
        except ValueError as exc:W.QMessageBox.information(self,'Resolve absence conflict',str(exc));return
        self.changed()
        if state=='removed':self.mode('inspect')

    def stroke_preview(self,stroke):
        r=self.current()
        if r is None:return
        old=decode(r['runs']);self.preview_mask=old&~stroke if self.operation=='erase' else old|stroke;self.render()

    def stroke(self,stroke):
        r=self.current()
        if r is None:return
        old=decode(r['runs']);mask=old&~stroke if self.operation=='erase' else paint_filled(old,stroke)
        self.preview_mask=None;self.store.set_region(self.selected,mask=mask);self.changed()

    def absence_changed(self,checked):
        if not self.store:return
        try:self.store.absence(checked);self.changed()
        except ValueError as exc:W.QMessageBox.information(self,'Resolve absence conflict',str(exc));self.refresh()

    def undo(self):
        if self.store:self.store.undo();self.selected=min(self.selected,len(self.store.state['regions'])-1);self.changed()

    def redo(self):
        if self.store:self.store.redo();self.changed()

    def changed(self):
        self.refresh();self.autosave.start(1500)

    def refresh(self):
        if not self.store:return
        self.region_list.blockSignals(True);self.region_list.clear()
        for i,r in enumerate(self.store.state['regions']):
            pixels=sum(b-a for _,a,b in r['runs'])
            self.region_list.addItem(f'{i+1}. {r["state"].title()} · {pixels*(1460/512)**2/1e6:.4f} mm²')
            self.region_list.item(i).setForeground(G.QColor(COLORS[r['state']]))
        self.region_list.setCurrentRow(self.selected);self.region_list.blockSignals(False)
        self.absence.blockSignals(True);self.absence.setChecked(self.store.state['absence']);self.absence.blockSignals(False)
        self.status.setText(('Confirmed entire image' if valid_confirmation(self.store.state) else 'Deferred: '+self.store.state['defer_reason'] if self.store.state['defer_reason'] else 'Draft — background not confirmed')+ (' · unsaved' if self.store.dirty else ' · saved' if self.store.path.exists() else ' · no decisions'))
        self.render();self.update_progress()

    def select(self,index):
        self.selected=index;self.render() # Selection never moves the row/cursor.

    def displayed(self):
        out=[]
        if not self.store:return out
        for i,r in enumerate(self.store.state['regions']):
            if r['state']=='removed' and not self.removed.isChecked():continue
            mask=self.preview_mask if i==self.selected and self.preview_mask is not None else decode(r['runs'])
            out.append((mask,COLORS[r['state']],i==self.selected))
        for kind,box in [('prediction',self.prediction),('historical',self.historical)]:
            if box.isChecked():out.extend((r['mask'],r['color'],False) for r in self.context.get(kind,[]))
        return out

    def context_changed(self):
        if not self.scan:return
        for kind,box in [('prediction',self.prediction),('historical',self.historical)]:
            if box.isChecked() and kind not in self.context:
                try:self.context[kind]=context_overlays(self.queue[self.index],kind)
                except Exception as exc:
                    box.blockSignals(True);box.setChecked(False);box.blockSignals(False);self.statusBar().showMessage('Reference unavailable: '+str(exc));continue
            if box.isChecked():
                exposure=dict(kind=kind,at=now(),sources=[r['source'] for r in self.context.get(kind,[])])
                self.session_exposures.append(exposure)
                self.view_log['exposures'].append(exposure)
        self.save_session()
        self.render() # No state edit or invalidation.

    def navigate(self,row,col):
        if not self.scan:return
        self.row=int(np.clip(row,0,511));self.col=int(np.clip(col,0,511))
        for control in (self.spin,self.slider):control.blockSignals(True);control.setValue(self.row);control.blockSignals(False)
        self.render()

    def render(self,*args):
        if not self.scan:return
        overlays=self.displayed()
        for canvas in (self.structural,self.octa):canvas.overlays(overlays);canvas.cursor(self.row,self.col)
        self.bscan.image(self.scan.images[self.row]);scene=self.bscan.scene();height=self.scan.images.shape[1];self.band_geometry=[]
        for mask,color,selected in overlays:
            c=G.QColor(color);c.setAlpha(62 if selected else 38);pen=G.QPen(G.QColor(color),1.5 if selected else .8);pen.setCosmetic(True)
            for left,right in intervals(mask[self.row]):
                item=scene.addRect(left,0,right-left,height,pen,G.QBrush(c));item.setZValue(4)
                scene.addRect(left,0,right-left,4,G.QPen(Qt.PenStyle.NoPen),G.QBrush(G.QColor(color))).setZValue(5)
                self.band_geometry.append((left,right,color,selected))
        pen=G.QPen(G.QColor('#70dcf8'),1,Qt.PenStyle.DotLine);pen.setCosmetic(True);scene.addLine(self.col+.5,0,self.col+.5,height,pen).setZValue(7)
        offset=self.scan.metadata['canonical_crop_offset']
        self.point_label.setText(f'A-line {self.col} · {len(self.band_geometry)} footprint intervals · canonical depth crop {offset}–{offset+height} px')

    def fit(self):
        self.structural.fit();self.octa.fit()
        if self.scan:
            rect=self.bscan.sceneRect();v=self.bscan.viewport();sx=1460/512;sy=1.12
            scale=min(max(v.width()-12,1)/(rect.width()*sx),max(v.height()-12,1)/(rect.height()*sy))
            self.bscan.setTransform(G.QTransform.fromScale(scale*sx,scale*sy));self.bscan.centerOn(rect.center())

    def update_progress(self):
        p=progress(self.queue,self.review_directory,self.store)
        prefix='SYNTHETIC SOFTWARE TEST — drawings are not human annotations\n' if self.synthetic else ''
        self.progress_label.setText(prefix+f'Reviewed: {p["positive"]+p["negative"]} / {len(self.queue)}     CNV: {p["positive"]} · No CNV: {p["negative"]}     Draft: {p["draft"]} · Deferred: {p["deferred"]}     Queue {self.index+1} / {len(self.queue)}')
        self.coverage.setText('Per animal, positive / negative: '+ '   ·   '.join(f'{a}: {c["positive"]}/{c["negative"]}' for a,c in p['per_animal'].items())+('   ALL 30 REVIEWED — confirmed size report is ready.' if p['target_reached'] else ''))
        if p['errors']:self.statusBar().showMessage('Some saved records require repair; excluded from counts. See record validation.')
        return p

    def save(self):
        if not self.store:return True
        try:
            self.reviewer_changed()
            if self.store.dirty or self.store.path.exists():
                self.store.context['focused_seconds']+=self.scan_seconds;self.scan_seconds=0.
                self.store.context['exposures'].extend(self.session_exposures);self.session_exposures=[]
            saved=self.store.save();self.save_session();self.refresh()
            if saved and not self.synthetic:
                try:
                    from measure import run
                    run()
                except Exception as exc:self.statusBar().showMessage('Annotations saved; size report needs refresh: '+str(exc))
            return True
        except Exception as exc:
            W.QMessageBox.critical(self,'Save failed — edits retained in this window',str(exc));return False

    def confirm(self,ignore_conflicts=False):
        if not self.store:return
        try:
            self.reviewer_changed();self.store.confirm(ignore_conflicts);self.refresh()
            if self.save():
                p=self.update_progress()
                if p['target_reached'] and not self.milestone_shown:
                    self.milestone_shown=True;W.QMessageBox.information(self,'All 30 reviewed',f'{p["positive"]} positive images and {p["negative"]} negative images saved. Confirmed sizes are in reports/quantification. No training starts automatically.')
        except ValueError as exc:
            if 'overlap pixels' in str(exc):
                answer=W.QMessageBox.question(self,'Overlapping positive / unsure pixels',str(exc)+'\nConfirm the image with these conflict pixels explicitly ignored?',W.QMessageBox.StandardButton.Yes|W.QMessageBox.StandardButton.Cancel,W.QMessageBox.StandardButton.Cancel)
                if answer==W.QMessageBox.StandardButton.Yes:self.confirm(True)
            else:W.QMessageBox.information(self,'Image remains Draft',str(exc))

    def export_sizes(self):
        if not self.save() or self.synthetic:return
        try:
            from measure import run
            summary=run()
            W.QMessageBox.information(self,'Confirmed CNV sizes',f'{summary["confirmed_images"]}/30 images confirmed; {summary["confirmed_lesion_regions"]} CNV regions.\nSaved lesions.csv, scans.csv, summary.json and derived training_manifest.json in:\n'+str(HERE/'reports/quantification'))
        except Exception as exc:W.QMessageBox.critical(self,'Size export failed',str(exc))

    def split_disconnected(self):
        from scipy import ndimage as ndi
        r=self.current()
        if r is None or r['state']=='removed':return
        labels,n=ndi.label(decode(r['runs']),structure=np.ones((3,3)))
        if n<2:self.statusBar().showMessage('One connected region. Erase a connecting bridge first, then split.');return
        original=copy.deepcopy(r)
        def split(state):
            state['regions'][self.selected]['state']='removed'
            for i in range(1,n+1):
                state['regions'].append(dict(id=uuid.uuid4().hex[:12],state='draft',runs=encode(labels==i),
                    origin=dict(kind='human_split',parent=original),created_at=now()))
        self.store.edit(split);self.selected=len(self.store.state['regions'])-n;self.changed()

    def defer(self):
        if not self.store:return
        reason,ok=W.QInputDialog.getText(self,'Defer image','Reason (uncertain, unreadable, inspect later…):')
        if ok and reason.strip():self.store.defer(reason);self.changed();self.save();self.step(1)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:self.mode('inspect')
        else:super().keyPressEvent(event)

    def closeEvent(self,event):
        if self.save():self.cache.close();event.accept()
        else:event.ignore()

def main():
    p=argparse.ArgumentParser();p.add_argument('--scan');p.add_argument('--capture');args=p.parse_args()
    app=W.QApplication([]);configure_app(app)
    window=Window(args.scan);window.show()
    if args.capture:
        def capture():
            def finish():
                window.grab().save(str(destination(HERE/'verification'/args.capture)));window.close();app.quit()
            Q.QTimer.singleShot(800,finish)
        window.ready.connect(capture)
    return app.exec()

if __name__=='__main__':sys.exit(main())
