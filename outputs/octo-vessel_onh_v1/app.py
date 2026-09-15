"""Flagged major-vessel / ONH review, using the existing en-face brush canvas."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from canvas import EnfaceCanvas, QtCore, QtGui, QtWidgets, _brush_mask, _smooth_stroke, raster_polygon
import label_store as CL
from eight_surface.vasculature_proposals import has_saved_vessel_work

BATCH = ROOT / 'outputs' / 'octa-vessel_seg_v1-batch'
LABELS = HERE / 'labels'
Qt = QtCore.Qt


def configure_app(app):
    font_id=QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    families=QtGui.QFontDatabase.applicationFontFamilies(font_id)
    app.setFont(QtGui.QFont(families[0] if families else 'Segoe UI',10))
    app.setStyle('Fusion')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_queue(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if data.get('format') != 'octa-vessel-gallery-flags-v1':
        raise ValueError('Choose the JSON exported by the vessel gallery.')
    inventory = {r['scan_id']: r for r in json.loads((BATCH / 'inventory.json').read_text())}
    rows, seen = [], set()
    for r in data['scans']:
        sid = r['scan_id']
        if sid not in inventory or sid in seen:
            raise ValueError(f'Unknown or repeated scan: {sid}')
        if any(type(r.get(k)) is not bool for k in ('onh_present', 'vessel_issue')):
            raise ValueError('Queue flags must be boolean')
        seen.add(sid)
        if r['onh_present'] or r['vessel_issue']:
            for folder, suffix in (('proposals', '_proposal.npz'), ('projections', '.npz')):
                if not (BATCH / folder / (sid + suffix)).exists():
                    raise ValueError(f'Missing {folder} for {sid}')
            rows.append(dict(r, metadata=inventory[sid]))
    if not rows:
        raise ValueError('This queue has no flagged scans.')
    return data, rows


def load_scan(row, label_dir=LABELS):
    sid = row['scan_id']
    proposal = BATCH / 'proposals' / f'{sid}_proposal.npz'
    projection = BATCH / 'projections' / f'{sid}.npz'
    with np.load(proposal, allow_pickle=False) as p, np.load(projection, allow_pickle=False) as q:
        image = q['structural_enface'].copy()
        source = str(p['source_volume'][0]); band = p['retina_band'].copy()
        if str(p['scan_id'][0]) != sid or Path(source) != Path(row['metadata']['source']):
            raise ValueError('Proposal source identity mismatch')
        if (str(q['source'][0]) != source or not np.array_equal(q['retina_band'], band)
                or p['predicted_vasculature_mask'].shape != image.shape
                or not np.isfinite(image).all()):
            raise ValueError('Projection and proposal geometry mismatch')
        automatic = p['predicted_vasculature_mask'].copy()
        seed_onh = p['human_onh_exclusion_mask'].copy()
    saved = CL.label_path(label_dir, sid)
    legacy = CL.label_path(ROOT / 'outputs/cnv_labels', sid)
    inherited = saved if saved.exists() else legacy if legacy.exists() else None
    record = CL.load_label(inherited) if inherited else None
    if record:
        if record['native_shape'] != image.shape or Path(record['source_volume']) != Path(source):
            raise ValueError('Saved annotation has incompatible source or grid')
    blank = np.zeros(image.shape, bool)
    manual = has_saved_vessel_work(record)
    state = dict(image=image, source=source, band=band, automatic=automatic,
                 vessel=record['vasculature_mask'].copy() if manual else automatic.copy(),
                 onh=record['onh_mask'].copy() if record else seed_onh.copy(),
                 cnv=record['cnv_mask'].copy() if record else blank.copy(),
                 edge=record['onh_edge_mask'].copy() if record else blank.copy(),
                 reviewed=record['reviewed_targets'].copy() if record else np.zeros(3, bool),
                 vessel_touched=record['vasculature_brush_touched'].copy() if manual else blank.copy(),
                 onh_touched=blank.copy(), vessel_excluded=blank.copy(), onh_excluded=blank.copy(),
                 vessel_removed_by_onh=blank.copy(),
                 initial_vessel=record['vasculature_initial_mask'].copy() if manual else automatic.copy(),
                 initial_onh=record['onh_mask'].copy() if record else seed_onh.copy(),
                 proposal_path=record['vasculature_proposal_path'] if manual else str(proposal),
                 proposal_hash=record['vasculature_proposal_sha256'] if manual else digest(proposal),
                 inherited_path=str(inherited or ''), inherited_hash=digest(inherited) if inherited else '',
                 notes=record['notes'] if record else '', onh_state='Not assessed',
                 origin='Saved correction' if saved.exists() else 'Existing human vessel work' if manual else 'Automatic vessel starting mask')
    # Legacy flags remain provenance; only explicit review in this editor resolves queue tasks.
    if not saved.exists():
        state['reviewed'][1:] = False
    else:
        with np.load(saved, allow_pickle=False) as z:
            for target, key in [('onh_touched','onh_brush_touched'), ('initial_onh','onh_initial_mask'),
                                ('vessel_excluded','vessel_region_excluded'), ('onh_excluded','onh_region_excluded'),
                                ('vessel_removed_by_onh','vessel_removed_by_onh')]:
                if key in z:
                    if z[key].shape != image.shape: raise ValueError('Invalid saved editor geometry')
                    state[target] = z[key].copy()
            state['onh_state'] = str(z['onh_visibility'][0])
            state['inherited_path'] = str(z['inherited_label_path'][0])
            state['inherited_hash'] = str(z['inherited_label_sha256'][0])
    return state


class Window(QtWidgets.QMainWindow):
    def __init__(self, queue_path, label_dir=LABELS):
        super().__init__()
        self.queue_path=Path(queue_path); self.queue_hash=digest(queue_path)
        _,self.rows=read_queue(queue_path)
        self.label_dir=Path(label_dir); self.index=-1; self.state=None; self.dirty=False
        self.history=[];self.future=[]; self.tool='Vessel brush'
        self.setWindowTitle('octo-vessel_onh_v1 — flagged scan correction')
        self.resize(1450,950)
        self.canvas=EnfaceCanvas('Vessels and ONH'); self.setCentralWidget(self.canvas)
        self.canvas.strokeFinished.connect(self.stroke)
        toolbar=self.addToolBar('Drawing')
        self.tools=QtWidgets.QComboBox(); self.tools.addItems(['Vessel brush','ONH brush','ONH outline','Vessel uncertain area','ONH uncertain area','Navigate'])
        self.tools.currentTextChanged.connect(self.set_tool);toolbar.addWidget(self.tools)
        self.erase=toolbar.addAction('Erase')
        self.erase.setCheckable(True);self.erase.setShortcut('E')
        self.erase.setToolTip('Toggle eraser for the selected vessel / ONH tool (E). Left-drag to erase.')
        self.erase.toggled.connect(lambda _:self.set_tool(self.tool))
        toolbar.addWidget(QtWidgets.QLabel('  Brush diameter '))
        self.size=QtWidgets.QSpinBox();self.size.setRange(1,150);self.size.setValue(18)
        self.size.valueChanged.connect(self.canvas.set_brush_size);toolbar.addWidget(self.size)
        for label, shortcut, callback in [('Undo','Ctrl+Z',self.undo),('Redo','Ctrl+Y',self.redo),('Fit','F',self.canvas.fit),('Save draft','Ctrl+S',self.safe_save)]:
            action=toolbar.addAction(label);action.setShortcut(shortcut);action.triggered.connect(callback)
        self.show_overlay=QtWidgets.QCheckBox('Show masks');self.show_overlay.setChecked(True)
        self.show_overlay.toggled.connect(self.redraw);toolbar.addWidget(self.show_overlay)
        dock=QtWidgets.QDockWidget('Review queue',self); dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setMinimumWidth(350);dock.setMaximumWidth(430)
        body=QtWidgets.QWidget(); layout=QtWidgets.QVBoxLayout(body)
        self.summary=QtWidgets.QLabel();self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.choice=QtWidgets.QComboBox();self.choice.addItems([r['scan_id'] for r in self.rows]);self.choice.currentIndexChanged.connect(self.load);layout.addWidget(self.choice)
        nav=QtWidgets.QHBoxLayout()
        for title,step in [('Previous',-1),('Save + next',1)]:
            b=QtWidgets.QPushButton(title);b.clicked.connect(lambda _,s=step:self.load(self.index+s));nav.addWidget(b)
        layout.addLayout(nav)
        helptext=QtWidgets.QLabel('Vessel: blue · ONH: green · uncertain areas: orange\nErase (E): toggle, then left-drag. Ctrl + right drag also erases.\nONH paint/outline removes vessels underneath.\nONH outline: draw a closed outline; Erase uses a round brush.\nScroll to zoom; middle-drag to pan. F fits the image.');helptext.setWordWrap(True);layout.addWidget(helptext)
        self.vreview=QtWidgets.QCheckBox('Vessel mask fully reviewed')
        self.oreview=QtWidgets.QCheckBox('ONH assessment reviewed')
        self.vreview.toggled.connect(lambda checked:self.review(1,checked));self.oreview.toggled.connect(lambda checked:self.review(2,checked))
        layout.addWidget(self.vreview);layout.addWidget(QtWidgets.QLabel('ONH visibility'))
        self.onh_state=QtWidgets.QComboBox();self.onh_state.addItems(['Not assessed','Visible — outlined','Partially visible — outlined','Outside image','Cannot judge'])
        self.onh_state.currentTextChanged.connect(self.visibility);layout.addWidget(self.onh_state);layout.addWidget(self.oreview)
        layout.addWidget(QtWidgets.QLabel('Notes'))
        self.notes=QtWidgets.QPlainTextEdit();self.notes.setMaximumHeight(150);self.notes.textChanged.connect(self.note_changed);layout.addWidget(self.notes)
        b=QtWidgets.QPushButton('Save draft');b.clicked.connect(self.safe_save);layout.addWidget(b)
        training_note=QtWidgets.QLabel('Painting does not approve a whole mask. Uncertain painted areas must be excluded from future training.');training_note.setWordWrap(True);layout.addWidget(training_note)
        layout.addStretch();dock.setWidget(body);self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,dock)
        self.set_tool(self.tool)
        start=0
        for i,row in enumerate(self.rows):
            p=CL.label_path(self.label_dir,row['scan_id'])
            if not p.exists():start=i;break
            r=CL.load_label(p)['reviewed_targets']
            if row['vessel_issue'] and not r[1] or row['onh_present'] and not r[2]:start=i;break
        self.load(start)

    def set_tool(self, tool):
        self.tool=tool
        mode='cnv_outline' if tool=='ONH outline' else 'navigate' if tool=='Navigate' else 'onh_brush' if tool.startswith('ONH') else 'vasculature_brush'
        erasing=hasattr(self,'erase') and self.erase.isChecked()
        if erasing and tool=='ONH outline':mode='onh_brush'
        self.canvas.force_erase=erasing
        self.canvas.set_mode(mode)

    def enforce_onh(self):
        overlap=self.state['vessel'] & self.state['onh']
        if overlap.any():
            self.state['vessel'][overlap]=False
            self.state['vessel_removed_by_onh'] |= overlap
            self.state['reviewed'][1]=False
            return True
        return False

    def snapshot(self):
        return {k:v.copy() if isinstance(v,np.ndarray) else v for k,v in self.state.items() if k!='image'}

    def push(self):
        self.history.append(self.snapshot()); self.history=self.history[-50:];self.future=[]

    def undo(self):
        if self.history:
            self.future.append(self.snapshot());self.state.update(self.history.pop());self.dirty=True;self.sync()

    def redo(self):
        if self.future:
            self.history.append(self.snapshot());self.state.update(self.future.pop());self.dirty=True;self.sync()

    def stroke(self, points, operation):
        if not self.state:return
        erasing=self.erase.isChecked() or operation.endswith('_erase')
        target='onh' if self.tool.startswith('ONH') else 'vessel'
        if self.tool=='ONH outline' and not erasing:
            polygon=_smooth_stroke(points,closed=True)
            if len(polygon)<3:return
            footprint=np.zeros(self.state[target].shape,bool)
            rr,cc=raster_polygon(polygon[:,1],polygon[:,0],shape=footprint.shape);footprint[rr,cc]=True
        else:footprint=_brush_mask(points,self.state[target].shape,self.size.value())
        if not footprint.any():return
        self.push()
        if 'uncertain' in self.tool:
            self.state[target+'_excluded'][footprint]=not erasing
        else:
            if target=='vessel' and not erasing:footprint &= ~self.state['onh']
            self.state[target][footprint]=not erasing
            self.state[target+'_touched'] |= footprint
            if target=='onh' and erasing:
                self.state['edge'][footprint]=False
            self.enforce_onh()
        self.state['reviewed'][2 if target=='onh' else 1]=False
        self.dirty=True;self.sync()

    def review(self,index,checked):
        if self.state:
            self.push();self.state['reviewed'][index]=checked;self.dirty=True

    def visibility(self,text):
        if self.state:
            self.push();self.state['onh_state']=text;self.state['reviewed'][2]=False;self.dirty=True;self.sync()

    def note_changed(self):
        if self.state:self.state['notes']=self.notes.toPlainText();self.dirty=True

    def sync(self):
        for widget,value in [(self.vreview,bool(self.state['reviewed'][1])),(self.oreview,bool(self.state['reviewed'][2]))]:
            widget.blockSignals(True);widget.setChecked(value);widget.blockSignals(False)
        self.onh_state.blockSignals(True);self.onh_state.setCurrentText(self.state['onh_state']);self.onh_state.blockSignals(False)
        self.notes.blockSignals(True);self.notes.setPlainText(self.state['notes']);self.notes.blockSignals(False)
        self.redraw()

    def redraw(self):
        if self.state:
            s=self.state;blank=np.zeros(s['vessel'].shape,bool)
            self.canvas.set_annotations(blank,s['vessel'],s['onh'],s['edge'])
            self.canvas._overlay.setVisible(self.show_overlay.isChecked())
            # Uncertain areas are a separate overlay; never vessel or ONH foreground.
            rgba=np.zeros((*blank.shape,4),np.uint8);rgba[s['vessel_excluded']|s['onh_excluded']]=(255,175,30,130)
            h,w=blank.shape
            q=QtGui.QImage(rgba.data,w,h,w*4,QtGui.QImage.Format.Format_RGBA8888).copy()
            if not hasattr(self,'excluded_item'):
                self.excluded_item=self.canvas.scene().addPixmap(QtGui.QPixmap());self.excluded_item.setZValue(6)
            self.excluded_item.setPixmap(QtGui.QPixmap.fromImage(q));self.excluded_item.setVisible(self.show_overlay.isChecked())

    def load(self,index):
        if not 0<=index<len(self.rows):
            if self.dirty:self.safe_save()
            return
        try:
            if self.dirty:self.save()
            state=load_scan(self.rows[index],self.label_dir)
        except Exception as e:
            self.choice.blockSignals(True);self.choice.setCurrentIndex(self.index);self.choice.blockSignals(False)
            QtWidgets.QMessageBox.critical(self,'Could not change scan',str(e));return
        self.state=state;self.index=index;self.history=[];self.future=[];self.dirty=False
        self.dirty=self.enforce_onh()
        self.choice.blockSignals(True);self.choice.setCurrentIndex(index);self.choice.blockSignals(False)
        row=self.rows[index]
        flags=', '.join(label for key,label in [('vessel_issue','Vessel issue'),('onh_present','ONH present')] if row[key])
        self.summary.setText(f'{index+1} / {len(self.rows)} · {flags}\n{state["origin"]}\n{row["scan_id"]}')
        self.canvas.set_image(state['image']);self.sync();self.canvas.fit()
        self.statusBar().showMessage('Drafts save when changing scans or closing. Review flags require your explicit decision.')

    def safe_save(self):
        try:return self.save()
        except Exception as e:QtWidgets.QMessageBox.critical(self,'Cannot save draft',str(e))

    def save(self):
        if not self.state:return
        self.enforce_onh()
        s=self.state; row=self.rows[self.index];meta=row['metadata']
        if s['reviewed'][2]:
            if s['onh_state']=='Not assessed':raise ValueError('Choose an ONH visibility assessment before marking it reviewed.')
            if 'outlined' in s['onh_state'] and not s['onh'].any():raise ValueError('Draw the visible ONH region before marking it reviewed.')
            if s['onh_state']=='Outside image' and (s['onh'].any() or s['edge'].any()):raise ValueError('ONH marked outside image, but an ONH mask/edge is present.')
        # Two-dimensional review does not infer depth orientation; record that explicitly.
        p=CL.save_label(self.label_dir,scan_id=row['scan_id'],cnv_mask=s['cnv'],vasculature_mask=s['vessel'],
            onh_mask=s['onh'],onh_edge_mask=s['edge'],source_volume=s['source'],source_segmentation='',
            retina_band=s['band'],vitreous_at_high_index=False,animal=meta['animal'],eye=meta['eye'],
            day_label=meta['day_label'],days_post_laser=meta['days_post_laser'],session_date=meta['session_date'],
            notes=s['notes'],reviewed_targets=s['reviewed'],vasculature_proposal_path=s['proposal_path'],
            vasculature_proposal_sha256=s['proposal_hash'],vasculature_initial_mask=s['initial_vessel'],
            vasculature_brush_touched=s['vessel_touched'],editor_provenance=dict(
                editor_version=np.array(['octo-vessel_onh_v1']),depth_orientation_applicable=np.array([False]),
                vessel_removed_by_onh=s['vessel_removed_by_onh'],
                onh_initial_mask=s['initial_onh'],onh_brush_touched=s['onh_touched'],
                vessel_region_excluded=s['vessel_excluded'],onh_region_excluded=s['onh_excluded'],
                onh_visibility=np.array([s['onh_state']]),queue_source=np.array([str(self.queue_path)]),
                queue_sha256=np.array([self.queue_hash]),gallery_flags_json=np.array([json.dumps({k:row[k] for k in ('onh_present','vessel_issue')})]),
                inherited_label_path=np.array([s['inherited_path']]),inherited_label_sha256=np.array([s['inherited_hash']]),
                frozen_batch_mask=s['automatic']))
        self.dirty=False;self.statusBar().showMessage(f'Saved {p.name}',10000)
        return p

    def closeEvent(self,event):
        try:
            if self.dirty:self.save()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self,'Cannot save draft',str(e));event.ignore();return
        event.accept()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('queue',nargs='?');args=parser.parse_args()
    app=QtWidgets.QApplication(sys.argv);configure_app(app)
    from PySide6 import QtNetwork
    server_name='octo-vessel-onh-'+hashlib.sha256(str(HERE).encode()).hexdigest()[:16]
    lock=QtCore.QLockFile(str(HERE/'editor.lock'))
    if not lock.tryLock(0):
        client=QtNetwork.QLocalSocket()
        client.connectToServer(server_name)
        if client.waitForConnected(2000):
            client.write(b'activate');client.flush();client.waitForBytesWritten(1000)
            client.disconnectFromServer();return 0
        QtWidgets.QMessageBox.warning(None,'Editor could not be reached',
            'A previous editor process is running but did not respond. Close that editor before reopening.');return 1
    saved_queue=HERE/'review_queue.json'
    queue=args.queue or (str(saved_queue) if saved_queue.exists() else '')
    if not queue:
        queue,_=QtWidgets.QFileDialog.getOpenFileName(None,'Select exported vessel review queue',str(ROOT),'Review queue (*.json)')
    if not queue:return 0
    try:
        data,_=read_queue(queue)
        if Path(queue).resolve()!=saved_queue.resolve():saved_queue.write_text(json.dumps(data,indent=2),encoding='utf-8')
        window=Window(saved_queue)
    except Exception as e:
        QtWidgets.QMessageBox.critical(None,'Cannot open review queue',str(e));return 1
    window.showMaximized()
    server=QtNetwork.QLocalServer()
    QtNetwork.QLocalServer.removeServer(server_name)
    if not server.listen(server_name):
        raise RuntimeError('Cannot start editor activation listener: '+server.errorString())
    def activate_existing():
        while server.hasPendingConnections():
            connection=server.nextPendingConnection()
            connection.disconnectFromServer();connection.deleteLater()
        if window.isMinimized():window.showNormal()
        window.showMaximized();window.raise_();window.activateWindow()
    server.newConnection.connect(activate_existing)
    def ready():
        window.canvas.fit();window.grab().save(str(HERE/'gui_ready.png'))
        (HERE/'gui_ready.json').write_text(json.dumps(dict(queue_length=len(window.rows),scan_id=window.rows[window.index]['scan_id'],visible=window.isVisible()),indent=2))
    QtCore.QTimer.singleShot(1000,ready)
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
