"""Read-only integration checks on every pilot scan and every displayed layer."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from common import *
from viewer import create_window,W,gui,LAYERS

app=W.QApplication([]);gui.configure_app(app)
w=create_window();results=[]
roots=[HERE/'review',ROOT/'outputs/octa-auto_cnv_v3/review',ROOT/'outputs/cnv_labels']
def label_hashes():return {str(p):sha(p) for root in roots for p in root.rglob('*') if p.is_file()}
initial=label_hashes()

def fail(message):
    write(HERE/'verification/gui_all_scans.json',dict(passed=False,error=message,scans=results));app.exit(1)
w._load_failed=fail

def check():
    try:
        sid=w.scan.scan_id;print('GUI',sid,flush=True)
        a=w.scan.maps;assert a['layer_thickness_um'].shape==(8,512,512)
        assert np.isnan(a['layer_thickness_um'][:,w.scan.shadow]).all()
        assert (a['layer_thickness_um'][np.isfinite(a['layer_thickness_um'])]>0).all()
        assert w.scan.metadata['layer_thickness']['axial_um_per_px']==1.12
        expected=[('Full retina','ILM','RPE'),('RNFL','ILM','RNFL_GCL'),('GCL','RNFL_GCL','GCL_IPL'),
            ('IPL','GCL_IPL','IPL_INL'),('INL','IPL_INL','INL_OPL'),('OPL','INL_OPL','OPL_ONL'),
            ('Photoreceptor composite','OPL_ONL','PR_RPE'),('RPE band','PR_RPE','RPE')]
        assert [tuple(v) for v in w.scan.metadata['layer_thickness']['layers']]==expected
        signature=w.store.signature();full=w.displayed_full.copy();core=a['core'].copy()
        for k in range(7):
            w.layer_choice.setCurrentIndex(k)
            assert np.array_equal(w.displayed_layer,a['layer_thickness_um'][k+1],equal_nan=True)
            assert np.array_equal(w.displayed_full,full,equal_nan=True)
            assert 'Full retina' in w.octa.parentWidget().title()
        for row,col in [(0,0),(256,256),(511,511)]:
            w._enface_clicked(row,col);assert (w.row,w.col)==(row,col)
            assert int(w.editor.pack.bscan_index[0])==row
        w.auto_check.setChecked(False);assert w.selected==-1
        assert all(w.region_list.item(i).isHidden() for i,r in enumerate(w.store.regions) if r.seed_ids and r.decision=='unreviewed')
        assert w.store.signature()==signature and np.array_equal(core,a['core'])
        w.layer_choice.setCurrentText('GCL');w.fit_all()
        if '_D14_' in sid and '_OD_' in sid:
            w._enface_clicked(230,85)
            w.grab().save(str(destination(HERE/'verification/v4_manual_review.png')))
        results.append(dict(scan_id=sid,layers_verified=7,full_retina_fixed=True,native_navigation=True,
            shadows_missing=True,no_review_changes=True,finite_fraction=[float(np.isfinite(v).mean()) for v in a['layer_thickness_um']]))
        if w._selected_index+1<len(w.paths):gui.QtCore.QTimer.singleShot(50,lambda:w.load_scan(w._selected_index+1))
        else:
            assert w.save_all() and label_hashes()==initial
            write(HERE/'verification/gui_all_scans.json',dict(passed=True,scans=results,review_files_unchanged=True))
            w.close();app.quit()
    except Exception:
        import traceback
        fail(traceback.format_exc())
w.ready.connect(lambda:gui.QtCore.QTimer.singleShot(400,check))
w.show();raise SystemExit(app.exec())
