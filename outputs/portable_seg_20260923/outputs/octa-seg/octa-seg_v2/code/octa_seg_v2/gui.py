"""Focused v2 reviewer: cached native slices with read-only en-face context."""
from types import SimpleNamespace
from .common import *
from .label_gui import V2Editor,Qt,QtCore,QtGui,QtWidgets
from cnv_review_v1.gui import ReviewCanvas,configure_app
from cnv_review_v1.data import load_enface

class Window(QtWidgets.QMainWindow):
    def __init__(self,round_dir=ROUND,feedback_dir=None):
        super().__init__();self.round=Path(round_dir).resolve();self.output=Path(feedback_dir or OUT/'reviewer');self.row=0;self.scan=None
        self.editor=V2Editor(self.output);self.editor.stepRequested.connect(lambda n:self.navigate(self.row+n))
        self.editor.cursorColumn.connect(lambda x:self.enface.set_cursor(self.row,int(np.clip(x,0,511))))
        self.enface=ReviewCanvas('Native structural OCT');self.enface.set_mode('navigate');self.enface.navigated.connect(lambda b,x:self.navigate(b));self.enface.setMaximumHeight(300)
        self.neighbors=QtWidgets.QLabel();self.neighbors.setAlignment(Qt.AlignmentFlag.AlignCenter);self.neighbors.hide()
        self.context_label=QtWidgets.QLabel('');self.context_label.setWordWrap(True)
        left=QtWidgets.QWidget();layout=QtWidgets.QVBoxLayout(left);layout.addWidget(QtWidgets.QLabel('Native en-face navigator · overlays read only'));layout.addWidget(self.enface,1)
        refresh=QtWidgets.QPushButton('Refresh saved CNV / vessel / ONH overlays');refresh.clicked.connect(self.refresh_overlays);layout.addWidget(refresh);layout.addWidget(self.context_label)
        self.neighbor_check=QtWidgets.QCheckBox('Show neighboring slices');self.neighbor_check.toggled.connect(self.show_neighbors);layout.addWidget(self.neighbor_check);layout.addWidget(self.neighbors)
        layout.addStretch();left.setMaximumWidth(315)
        split=QtWidgets.QSplitter();split.addWidget(left);split.addWidget(self.editor);split.setSizes([290,1310]);self.setCentralWidget(split)
        nav=self.addToolBar('Browse');nav.setMovable(False);self.scan_choice=QtWidgets.QComboBox();self.scan_choice.addItems(SCANS);self.scan_choice.activated.connect(self.load_scan);nav.addWidget(self.scan_choice)
        nav.addAction('◀',lambda:self.navigate(self.row-1));self.bscan=QtWidgets.QSpinBox();self.bscan.setRange(0,511);self.bscan.setPrefix('B-scan ');self.bscan.setKeyboardTracking(False);self.bscan.valueChanged.connect(self.navigate);nav.addWidget(self.bscan);nav.addAction('▶',lambda:self.navigate(self.row+1))
        nav.addAction('Fit',self.fit);nav.addAction('Save',self.editor._save_clicked)
        compare=QtWidgets.QCheckBox('Previous model / policy');compare.toggled.connect(self.compare);nav.addWidget(compare)
        nav.addAction('Bookmark',self.bookmark);self.bookmarks=QtWidgets.QComboBox();self.bookmarks.addItem('Bookmarks');self.bookmarks.activated.connect(self.goto_bookmark);nav.addWidget(self.bookmarks)
        self.bookmark_path=self.output/'bookmarks.json';self.bookmark_items=read(self.bookmark_path) if self.bookmark_path.exists() else []
        for p in self.bookmark_items:self.bookmarks.addItem(f'{p["scan_id"].split("_")[0]} B{p["bscan"]}')
        self.queue=read(self.round/'review_queue.json')['examples'] if (self.round/'review_queue.json').exists() else []
        self.addToolBarBreak();bar=self.addToolBar('Short review round');self.queue_choice=QtWidgets.QComboBox();self.queue_choice.addItem('Free browsing')
        for i,q in enumerate(self.queue):self.queue_choice.addItem(f'{i+1}/{len(self.queue)} · {q["scan_id"].split("_")[0]} B{q["bscan"]} · {q["data_role"]}')
        self.queue_choice.activated.connect(self.goto_queue);bar.addWidget(self.queue_choice);bar.addAction('Previous example',lambda:self.queue_step(-1));bar.addAction('Next example',lambda:self.queue_step(1))
        self.session_clock=QtWidgets.QLabel('Review in short rounds: 20–30 minutes; stop by 60.');bar.addWidget(self.session_clock)
        self.elapsed=QtCore.QElapsedTimer();self.elapsed.start();self.clock=QtCore.QTimer(self);self.clock.timeout.connect(self.update_clock);self.clock.start(30000)
        self.setWindowTitle('octa-seg_v2 · focused segmentation review · round_000');self.resize(1650,1030)
        self.load_scan(0)

    def update_clock(self):
        mins=self.elapsed.elapsed()/60000;self.session_clock.setText(f'{mins:.0f} min this session · '+('Take a break; feedback is saved.' if mins>=30 else '20–30 minute review round'))

    def load_scan(self,index):
        self.editor.commit_current();sid=SCANS[index];out=self.round/'volumes'/sid
        self.statusBar().showMessage('Loading '+sid);QtWidgets.QApplication.processEvents()
        prep=read(out/'prepared.json');self.images=np.load(prep['images'],mmap_mode='r');self.data=npz(out/'measurements.npz');self.geometry=npz(out/'geometry.npz')
        g=self.geometry;d=self.data
        diagnostics=out/'diagnostics.npz'
        if diagnostics.exists():
            with np.load(diagnostics,allow_pickle=False) as z:
                d['spike_um']=z['spike_um'];d['jump_um']=z['jump_um']
        self.scan=SimpleNamespace(scan_id=sid,source_volume=Path(prep['source']['path']),native_shape=(512,512),
            retina_band=tuple(g['retina_band']),surface_names=tuple(d['surface_names']),px_um=1.12,shadow=g['shadow'],
            surfaces=d['reported_positions']-int(g['label_offset']),structural_bscan=lambda row:self.images[row])
        previous_path=ROUND/'volumes'/sid/'measurements.npz' if self.round!=ROUND else out/'v1_matched_baseline.npz'
        previous=npz(previous_path)['reported_positions']
        self.editor.set_bundle(d,npz(out/'guards.npz'),read(V1/'calibration/deployment_vessels.json')['thresholds'],str(self.round.relative_to(OUT)),previous)
        self.scan_choice.setCurrentIndex(index);self.enface.set_image(np.mean(self.images,axis=1));self.refresh_overlays();self.navigate(256);self.fit()
        self.statusBar().showMessage(sid+' · all 512 B-scans available')

    def refresh_overlays(self):
        if self.scan is None:return
        proposal=OUT/'proposals' if (OUT/'proposals'/f'{self.scan.scan_id}_proposal.npz').exists() else ROOT/'outputs/eight_surface/vasculature_proposals'
        self.cnv,self.vessel,onh,edge,prov,_=load_enface(self.scan,ROOT/'outputs/cnv_labels',proposal)
        self.enface.set_annotations(self.cnv,self.vessel,onh,edge);self.context_label.setText(prov['status']+'\nRed: CNV · blue: vessel · green: ONH. Refresh updates context; model inputs remain frozen for this round.')
        if self.editor.pack is not None:self.editor.set_footprints(self.vessel[self.row],self.cnv[self.row])

    def navigate(self,row):
        if self.scan is None:return
        self.editor.commit_current();self.row=int(np.clip(row,0,511));self.bscan.blockSignals(True);self.bscan.setValue(self.row);self.bscan.blockSignals(False)
        # Assessment roles are pinned to whole B-scans, including free browsing.
        self.editor.review_role='assessment' if any(q['scan_id']==self.scan.scan_id and q['bscan']==self.row and q['data_role']=='assessment' for q in self.queue) else 'training'
        self.editor.set_line(self.scan,self.row,self.scan.surfaces,np.full_like(self.scan.surfaces,np.nan),None,
            dict(path=str(self.round/'review_packs'/f'{self.scan.scan_id}.npz'),name='octa-seg_v2'),self.vessel[self.row],self.cnv[self.row])
        self.enface.set_cursor(self.row,256);self.show_neighbors(self.neighbor_check.isChecked())

    def show_neighbors(self,enabled):
        self.neighbors.setVisible(enabled)
        if enabled and self.scan is not None:
            a=np.concatenate([self.images[max(0,self.row-1)],self.images[min(511,self.row+1)]],axis=0)
            lo,hi=np.percentile(a,[2,99]);u=np.ascontiguousarray(np.clip((a-lo)/(hi-lo)*255,0,255).astype(np.uint8))
            image=QtGui.QImage(u.data,u.shape[1],u.shape[0],u.strides[0],QtGui.QImage.Format.Format_Grayscale8).copy()
            self.neighbors.setPixmap(QtGui.QPixmap.fromImage(image).scaledToWidth(280,Qt.TransformationMode.SmoothTransformation))

    def fit(self):self.enface.fit();self.editor.fit_image()
    def compare(self,shown):self.editor.show_previous=shown;self.editor.redraw_surfaces()
    def bookmark(self):
        p=dict(scan_id=self.scan.scan_id,bscan=self.row)
        if p not in self.bookmark_items:self.bookmark_items.append(p);self.bookmarks.addItem(f'{p["scan_id"].split("_")[0]} B{self.row}');write(self.bookmark_path,self.bookmark_items)
    def goto_bookmark(self,index):
        if index:
            p=self.bookmark_items[index-1]
            if self.scan.scan_id!=p['scan_id']:self.load_scan(SCANS.index(p['scan_id']))
            self.navigate(p['bscan'])
    def goto_queue(self,index):
        if not index:return
        q=self.queue[index-1]
        if self.scan.scan_id!=q['scan_id']:self.load_scan(SCANS.index(q['scan_id']))
        self.navigate(q['bscan']);self.editor.span_lo.setValue(q['lo']);self.editor.span_hi.setValue(q['hi']);self.editor.draw_strip(q['lo'],q['hi'])
    def queue_step(self,step):
        index=int(np.clip(self.queue_choice.currentIndex()+step,1,len(self.queue)));self.queue_choice.setCurrentIndex(index);self.goto_queue(index)
    def closeEvent(self,event):
        try:self.editor.commit_current();event.accept()
        except Exception as exc:QtWidgets.QMessageBox.critical(self,'Feedback remains unsaved',str(exc));event.ignore()

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--round',type=Path,default=ROUND);a=p.parse_args()
    app=QtWidgets.QApplication([]);configure_app(app);window=Window(a.round);window.show();QtCore.QTimer.singleShot(150,window.fit);app.exec()

if __name__=='__main__':main()
