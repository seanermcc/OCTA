"""One native-coordinate map, lesion brush/outline and B-scan reviewer."""
import argparse, copy, uuid
from common import *
from loader import ProposalLoader
from cnv_review_v1 import gui
from review_store import ReviewRegion
from eight_surface.cnv_gui import _brush_mask
from skimage.draw import polygon
from scipy import ndimage as ndi
from algorithm import VARIANTS, quantify
from matplotlib import colormaps
Qt=gui.Qt; W=gui.QtWidgets

class Window(gui.MainWindow):
    def __init__(self, config, **kw):
        gui.Loader=ProposalLoader
        self.extra_ready=False; self.edit_operation='paint'
        super().__init__(config,**kw)
        self.setWindowTitle('octa-auto_cnv_v2 · Lesion assessment and manual review · Experimental')
        self.sources_bar.hide()
        self.lines_check.setChecked(False)
        self.addToolBarBreak(); bar=self.addToolBar('Lesion tools')
        self.target=W.QComboBox(); self.target.addItems(['Structural footprint','Candidate core']); bar.addWidget(self.target)
        for name,fn in [('Paint',lambda:self.brush('paint')),('Erase',lambda:self.brush('erase')),('Split by stroke',lambda:self.brush('split')),('Merge with…',self.merge),('Approve footprint',self.approve),('Reject candidate',self.remove_region),('Reload saved',self.reload_saved)]:
            bar.addAction(name,fn)
        self.diameter=W.QSpinBox(); self.diameter.setRange(1,100); self.diameter.setValue(12); self.diameter.setSuffix(' px brush'); bar.addWidget(self.diameter)
        self.addToolBarBreak(); maps=self.addToolBar('Map display')
        self.variant=W.QComboBox(); self.variant.addItems(list(VARIANTS)); maps.addWidget(self.variant)
        self.map_choice=W.QComboBox(); self.map_choice.addItems(['Signed deficit (%)','Full retina (um)','Geometry / structural evidence','Reference sensitivity (pp)','Estimated background (um): includes extrapolation','Background samples / support','Missing / artifact flags']); maps.addWidget(self.map_choice)
        self.contours=W.QCheckBox('10 / 20 / 30% contours'); maps.addWidget(self.contours)
        self.assisted=W.QCheckBox('Assisted thickness'); maps.addWidget(self.assisted)
        maps.addAction('Recompute assisted from reviewed footprints',self.recompute)
        self.evidence=gui.ReviewCanvas('Lesion evidence'); self.evidence.navigated.connect(self._enface_clicked); self.evidence.strokeFinished.connect(self._outline_drawn)
        self.top.insertWidget(1,self.panel('Evidence · geometry red / structure amber',self.evidence))
        self.top.setSizes([420,420,420,300])
        self.reason=W.QLabel(); self.reason.setWordWrap(True)
        dock=W.QDockWidget('Selected point / candidate evidence',self); dock.setWidget(self.reason); self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,dock)
        for control in (self.variant,self.map_choice): control.currentIndexChanged.connect(self.render_maps)
        self.contours.toggled.connect(self.render_maps); self.assisted.toggled.connect(self.render_maps)
        self.bscan_cursor=self.editor.canvas.scene().addLine(0,0,0,1,gui.QtGui.QPen(gui.QtGui.QColor('#44eeff'),1))
        self.bscan_cursor.setZValue(40)
        bar.addAction('Complete region review',self.complete_review)
        self.extra_ready=True

    def _loaded(self,result):
        self.user_maps=None; self.user_thickness=None
        super()._loaded(result)
        self.evidence.set_image(self.scan.maps['structural_context'])
        saved=HERE/'assisted_review'/self.scan.scan_id
        if (saved/'provenance.json').exists() and (saved/'maps.npz').exists():
            p=read(saved/'provenance.json')
            maps_path=HERE/'scans'/self.scan.scan_id/'maps.npz'
            review_hash=sha(self.store.path) if self.store.path.exists() else None
            corrections=p.get('viewer_metadata',{}).get('correction_fingerprints',{})
            if (p['source_maps_sha256']==sha(maps_path) and p['review_sha256']==review_hash
                and p.get('review_inputs')==self.assistance_inputs()
                and all(Path(path).exists() and sha(path)==digest for path,digest in corrections.items())):
                restored=npz(saved/'maps.npz')
                self.user_thickness=restored.pop('viewer_thickness_um');self.user_maps=restored
        self.render_maps(); self.evidence.fit()

    def current(self):
        a=self.scan.maps
        prefix='assisted' if self.assisted.isChecked() else self.variant.currentText()
        if self.assisted.isChecked() and self.user_maps is not None: return self.user_maps
        return {key:a[prefix+'__'+key] for key in ('deficit_percent','background_um','background_supported','background_regions','footprint')}

    def _schedule_save(self):
        # Explicit save, plus safe save-on-navigation inherited from RegionStore.
        self.user_maps=None
        self.statusBar().showMessage('Draft edits · Save all or Ctrl+S; untouched automatic pixels remain unreviewed')

    def assistance_inputs(self):
        self.index.refresh(self.scan)
        paths={p for p,_ in self.index.records.values()}
        for p in list(paths):
            context=p.parent.parent/'surface_context'/f'{p.stem}.json'
            if context.exists():paths.add(context)
        paths.update((HERE/'review/estimate_feedback').glob(f'{self.scan.scan_id}_b*.json'))
        return {str(p):sha(p) for p in sorted(paths)}

    def _boundary_saved(self):
        super()._boundary_saved()
        self.user_maps=None

    def navigate(self,row,col,force=False):
        super().navigate(row,col,force)
        if self.extra_ready and self.scan is not None:
            self.evidence.set_cursor(self.row,self.col)
            self.bscan_cursor.setLine(self.col,0,self.col,self.editor.canvas.scene().sceneRect().height())
            self.show_reason()

    def _enface_clicked(self,row,col):
        if self.scan is None: return
        for i,r in enumerate(self.store.regions):
            if r.mask[row,col] or r.core[row,col]: self.select_region(i,navigate=False); break
        self.navigate(row,col)

    def _cursor_column(self,col):
        super()._cursor_column(col)
        if self.extra_ready and self.scan:
            self.evidence.set_cursor(self.row,self.col)
            self.bscan_cursor.setLine(self.col,0,self.col,self.editor.canvas.scene().sceneRect().height())
            self.show_reason()

    def select_region(self,index,navigate=True):
        super().select_region(index,navigate)
        if self.extra_ready and self.scan: self.render_maps()

    def refresh_overlays(self,*args):
        if self.extra_ready and self.scan: self.render_maps()

    def _classification_status(self):
        r=self.selected_region()
        self.region_status.setText('No region selected' if r is None else 'Review: '+getattr(r,'decision','unreviewed')+' · category alone does not approve pixels')

    def brush(self,operation):
        if self.scan is None:return
        self.edit_operation=operation
        for c in (self.structural,self.octa,self.evidence): c.set_mode('cnv_brush'); c.set_brush_size(self.diameter.value())
        self.mode_label.setText(operation+' on '+self.target.currentText()+'; Escape returns to navigation')

    def outline_mode(self,replace):
        super().outline_mode(replace)
        if self.extra_ready: self.evidence.set_mode('cnv_outline')

    def cancel_outline(self):
        super().cancel_outline()
        if self.extra_ready:self.evidence.set_mode('navigate')

    def _outline_drawn(self,points,operation):
        if self.scan is None or not points:return
        is_brush='brush' in operation; r=self.selected_region(); field='core' if self.target.currentIndex() else 'mask'
        if is_brush and r is None and (self.edit_operation in ('erase','split') or operation.endswith('erase')):return
        mask=np.zeros(self.scan.native_shape,bool)
        if is_brush: mask=_brush_mask(points,self.scan.native_shape,self.diameter.value())
        elif len(points)>=3:
            xy=np.array(points); rr,cc=polygon(xy[:,1],xy[:,0],shape=mask.shape); mask[rr,cc]=True
        if not mask.any():return
        self._push_region_undo()
        if (not is_brush and not self._replace_outline) or r is None:
            r=ReviewRegion(uuid.uuid4().hex[:12],np.zeros_like(mask),origin='added in v2 GUI').initialize()
            self.store.regions.append(r); self.selected=len(self.store.regions)-1
        old=getattr(r,field).copy()
        if is_brush and (self.edit_operation in ('erase','split') or operation.endswith('erase')): new=old & ~mask
        elif is_brush:new=old | mask
        else:new=mask
        if not new.any():
            self.undo_regions.pop(); self.statusBar().showMessage('Use Reject candidate to remove the entire region.'); return
        setattr(r,field,new)
        if field=='core' and not r.mask.any(): r.mask=new.copy()  # unreviewed editing scaffold
        touched='core_touched' if field=='core' else 'touched'
        setattr(r,touched,getattr(r,touched)|mask|(old^new))
        r.decision='unreviewed'; r.event('brush '+self.edit_operation if is_brush else 'outline redraw',target=field,edited_pixels=int((old^new).sum()))
        if is_brush and self.edit_operation=='split' and field=='mask':
            labels,n=ndi.label(new,np.ones((3,3)))
            if n>1:
                self.store.regions.pop(self.selected)
                for k in range(1,n+1):
                    child=copy.deepcopy(r); child.id=uuid.uuid4().hex[:12]
                    child.mask=r.mask & (labels==k) if field=='mask' else labels==k
                    child.core=r.core & (labels==k)
                    child.event('split',parent=r.id); self.store.regions.append(child)
                self.selected=len(self.store.regions)-n
        self.refresh_regions(); self.select_region(self.selected,navigate=False); self._schedule_save()
        if not is_brush:self.cancel_outline()

    def merge(self,other=None):
        r=self.selected_region()
        if r is None:return
        options=[(i,v) for i,v in enumerate(self.store.regions) if v is not r]
        if not options:return
        if not isinstance(other,int):
            labels=[f'{i+1}: {v.id}' for i,v in options]
            value,ok=W.QInputDialog.getItem(self,'Merge regions','Merge selected with',labels,0,False)
            if not ok:return
            other=options[labels.index(value)][0]
        q=self.store.regions[other]; self._push_region_undo()
        r.mask|=q.mask; r.core|=q.core; r.touched|=q.touched; r.core_touched|=q.core_touched
        r.seed_ids=sorted(set(r.seed_ids+q.seed_ids)); r.decision='unreviewed'; r.event('merge',other=q.id,other_events=copy.deepcopy(q.events))
        self.store.regions.pop(other); self.selected=next(i for i,v in enumerate(self.store.regions) if v is r)
        self.refresh_regions(); self.select_region(self.selected,navigate=False); self._schedule_save()

    def approve(self):
        r=self.selected_region()
        if r is None:return
        self._push_region_undo(); r.decision='approved'; r.category='Full Lesion'; r.event('explicit footprint approval')
        self.refresh_regions(); self.select_region(self.selected,navigate=False); self._schedule_save()

    def complete_review(self):
        r=self.selected_region()
        if r is None:return
        if r.category=='Unclassified' or (r.category=='Other' and not r.notes.strip()):
            self.statusBar().showMessage('Choose a category and explain Other before completing review.');return
        self._push_region_undo();r.decision='approved';r.event('explicit region review completion',category=r.category)
        self.refresh_regions();self.select_region(self.selected,navigate=False);self._schedule_save()

    def fit_all(self):
        super().fit_all()
        if self.extra_ready:self.evidence.fit()

    def refresh_regions(self):
        super().refresh_regions()
        if self.store is not None:
            for i,r in enumerate(self.store.regions):
                self.region_list.item(i).setText(f'{i+1}: {r.category} | {getattr(r, "decision", "unreviewed")}')

    def remove_region(self):
        r=self.selected_region()
        if r is None:return
        self._push_region_undo(); r.decision='rejected'; r.category='Other'; r.notes=r.notes or 'Rejected candidate'; r.event('explicit rejection')
        self.refresh_regions(); self.select_region(self.selected,navigate=False); self._schedule_save()

    def _category_changed(self,value):
        if not self._loading_controls and self.selected_region() and self.selected_region().category!=value:
            super()._category_changed(value); self.selected_region().decision='unreviewed'
            self.selected_region().event('category change',category=value); self._classification_status()

    def reload_saved(self):
        if self.scan is None:return
        if self.store.dirty:
            answer=W.QMessageBox.question(self,'Reload saved revision','Discard unsaved region edits and load the saved revision?')
            if answer!=W.QMessageBox.StandardButton.Yes:return
        from review_store import ReviewStore
        self.store=ReviewStore(HERE/'review/regions',self.scan,self.scan.maps['core'],str(HERE/'proposals'/f'{self.scan.scan_id}.npz'))
        self.undo_regions.clear();self.redo_regions.clear();self.refresh_regions();self.select_region(0 if self.store.regions else -1)

    def recompute(self):
        try:self._recompute()
        except Exception as exc:W.QMessageBox.critical(self,'Assisted measurement could not be recomputed',str(exc))

    def _recompute(self):
        if self.scan is None or not self.save_all():return
        excluded=np.zeros(self.scan.native_shape,bool); background_core=np.zeros_like(excluded)
        for r in self.store.regions:
            if r.decision!='rejected' and not (r.decision=='approved' and r.category=='Normal'):background_core|=r.core
            if r.decision=='approved' and r.category=='Full Lesion':excluded|=r.mask
        import engine
        engine.HERE=HERE/'viewer_cache'
        config=read(LONG/'v2/launch_config.json')
        config['manual_sources']=[str(Path(config['output'])/'surface_labels'),*config['manual_sources']]
        config['output']=str(HERE/'review')
        fresh=engine.Volume(volume_path(self.scan.scan_id),config)
        self.user_thickness=fresh.maps[0][0][0].copy()
        m,d=quantify(self.scan.maps,{'core':self.scan.maps['core'],'background_core':background_core},thickness=self.user_thickness,extra_excluded=__import__('algorithm').grow(excluded,150))
        folder=HERE/'assisted_review'/self.scan.scan_id
        save_npz(folder/'maps.npz',**m,viewer_thickness_um=self.user_thickness)
        write(folder/'provenance.json',dict(kind='human-assisted thickness and background; automatic candidates unchanged',viewer_metadata=fresh.metadata(),review_inputs=self.assistance_inputs(),review_sha256=sha(self.store.path) if self.store.path.exists() else None,source_maps_sha256=sha(HERE/'scans'/self.scan.scan_id/'maps.npz'),diagnostics=d))
        self.user_maps=m;self.assisted.setChecked(True);self.render_maps()

    def colour(self,canvas,values,cmap,lo,hi):
        rgba=(colormaps[cmap](np.clip((np.nan_to_num(values,nan=lo)-lo)/(hi-lo),0,1))*255).astype('uint8')
        rgba[~np.isfinite(values)]=[75,75,82,255]
        h,w=values.shape
        img=gui.QtGui.QImage(rgba.data,w,h,4*w,gui.QtGui.QImage.Format.Format_RGBA8888).copy()
        canvas._pix.setPixmap(gui.QtGui.QPixmap.fromImage(img));canvas._shape=values.shape
        canvas.scene().setSceneRect(0,0,w,h)

    def overlay(self,canvas,mask,color):
        edge=mask & ~ndi.binary_erosion(mask)
        from cnv_review_v1.data import runs
        path=gui.QtGui.QPainterPath()
        for y in np.flatnonzero(edge.any(1)):
            for lo,hi in runs(edge[y]):path.addRect(lo,y,hi-lo,1)
        item=canvas.scene().addPath(path,gui.QtGui.QPen(Qt.PenStyle.NoPen),gui.QtGui.QBrush(gui.QtGui.QColor(color)))
        item.setZValue(8);canvas.review_items.append(item)

    def render_maps(self,*args):
        if not self.extra_ready or self.scan is None:return
        a=self.scan.maps;m=self.current(); choice=self.map_choice.currentIndex()
        t=(self.user_thickness if self.user_maps is not None else a['viewer_thickness_um']) if self.assisted.isChecked() else a['automatic_thickness_um']
        values,cmap,lo,hi=[(m['deficit_percent'],'coolwarm',-30,40),(t,'viridis',180,360),(a['geometry_any'].astype(float)*3+a['structural_context'],'magma',0,6),(a['deficit_sensitivity_span'],'magma',0,15),(m['background_um'],'viridis',180,360),(m['background_regions'].astype(float)+m['background_supported'],'viridis',0,2),(a['low_signal'].astype(float)+2*a['shadow']+2*a['vessel']+4*(~np.isfinite(t)),'tab10',0,8)][choice]
        self.colour(self.octa,values,cmap,lo,hi)
        self.octa.parentWidget().setTitle(self.map_choice.currentText()+f' · scale {lo} to {hi}')
        self.colour(self.evidence,a['structural_context'],'magma',0,5)
        for c in (self.structural,self.octa,self.evidence):
            empty=np.zeros(self.scan.native_shape,bool)
            c.set_annotations(empty,empty,empty,empty)
            c.set_reviews(self.store.regions,self.selected,self.index,self.visible_rows(),self.lines_check.isChecked())
            self.overlay(c,a['core'],'#ff7b28'); self.overlay(c,a['manual_cnv'],'#44eeff')
            self.overlay(c,a['vessel']|a['shadow'],'#4488ff')
            selected=self.selected_region()
            if selected and selected.core_touched.any():self.overlay(c,selected.core,'#ff30dd')
            c.set_cursor(self.row,self.col)
        self.overlay(self.evidence,a['geometry_any'],'#ff3535')
        self.overlay(self.octa,~np.isfinite(t),'#ff7da9')
        self.overlay(self.octa,m['background_supported'],'#cccccc')
        if selected:
            self.overlay(self.evidence,__import__('algorithm').grow(selected.core,15) & ~m['background_supported'],'#c787ff')
        self.overlay(self.evidence,a['low_signal'],'#b89628')
        if self.contours.isChecked():
            for threshold,color in [(10,'#ffe144'),(20,'#ffaa22'),(30,'#ff3322')]:self.overlay(self.octa,m['deficit_percent']>=threshold,color)
        self.show_reason()

    def show_reason(self):
        if self.scan is None:return
        a=self.scan.maps;m=self.current();y,x=self.row,self.col;names=a['surface_names'];reasons=[]
        for j,(u,v) in enumerate(a['geometry_pairs']):
            if a['geometry_crossing'][y,j,x]:reasons.append(f'{names[u]} crosses {names[v]} ({a["geometry_crossing_size_px"][y,j,x]:.2f} px)')
        for key,label in [('geometry_nonfinite','nonfinite'),('geometry_out_of_crop','out of crop')]:
            reasons.extend(f'{names[j]} {label}' for j in np.flatnonzero(a[key][y,:,x]))
        flags=[name for name in ('vessel','shadow','low_signal','seam','automatic_trace_loss') if a[name][y,x]]
        r=self.selected_region(); record=next((rec for rec in self.scan.metadata['candidates'] if r and rec['id'] in r.seed_ids),None)
        self.reason.setText(f'Native B-scan {y}, A-line {x} | '+('; '.join(reasons) or 'No automatic geometry failure')+' | '+(', '.join(flags) or 'No artifact flags')+f'\nThickness {a["automatic_thickness_um"][y,x]:.1f} um; signed deficit {m["deficit_percent"][y,x]:.1f}%; reference '+('supported' if m['background_supported'][y,x] else 'UNSUPPORTED — quantitative value unavailable')+f' | '+(f'Candidate {record["id"]}: {record["priority"]}; persists {record["persistence_rows"]} rows; clipped={record["fov_clipped"]}' if record else 'No original candidate selected')+'\nOrange: immutable automatic core · magenta: edited core · cyan: existing manual · pink: missing thickness · blue: vessel/shadow · gray edge: reference support. Draft structural outlines are separate from numerical contours.')


def create_window(sid=None):
    config=dict(output=str(HERE/'review'),segmentations=str(HERE/'proposals'),enface_labels=str(ROOT/'outputs/cnv_labels'),proposals=str(LONG/'v2/proposals'),manual_sources=read(LONG/'v2/launch_config.json')['manual_sources'],auto_sources=[],region_sources=[])
    paths=[HERE/'proposals'/f'{v["scan_id"]}.npz' for v in selected() if (HERE/'proposals'/f'{v["scan_id"]}.npz').exists()]
    index=next((i for i,p in enumerate(paths) if p.stem==sid),0)
    return Window(config,paths=paths,start_index=index)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scan');p.add_argument('--capture',action='store_true');args=p.parse_args()
    app=W.QApplication([]);gui.configure_app(app);window=create_window(args.scan)
    if args.capture:
        def capture():
            window._enface_clicked(230,85)
            gui.QtCore.QTimer.singleShot(700,lambda:(window.grab().save(str(destination(HERE/'verification/integrated_gui.png'))),app.quit()))
        window.ready.connect(capture)
    window.show();raise SystemExit(app.exec())



