"""Read-only checks on all 17 acquisitions, OCTA, and every boundary pair."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from common import *
from viewer import Window,W,Q,gui,LAYERS
app=W.QApplication([]);gui.configure_app(app);window=Window(manual=True,autoload=False);results=[]
roots=[HERE/'review',ROOT/'outputs/octa-auto_cnv_v4/review',ROOT/'outputs/octa-auto_cnv_v3/review',ROOT/'outputs/cnv_labels']
def files():return {str(p):sha(p) for root in roots for p in root.rglob('*') if p.is_file()}
initial=files()
def fail(message):
    print(message,flush=True);write(HERE/'verification/gui_all_scans.json',dict(passed=False,error=message,scans=results));app.exit(1)
window.load_failed=fail
def check():
    try:
        scan=window.scan;print('GUI',scan.scan_id,flush=True);sig=window.store.signature()
        assert window.top.count()==3 and not hasattr(window,'editor')
        assert scan.octa is not None and not scan.octa_error
        assert scan.octa.shape==scan.native_shape==(512,512)
        assert scan.octa_metadata['channel']=='frame_OCTAAvg'
        assert scan.octa_metadata['orientation_detected']==scan.thickness_metadata['raw_vitreous_high']
        assert window.mode.currentIndex()==0 and not window.boundary_items
        window.mode.setCurrentIndex(1)
        for k,(_,top,bottom) in enumerate(LAYERS):
            window.layer.setCurrentIndex(k)
            assert window.boundary_indices==(top,bottom) and len(window.boundary_items)==2
            for row,col in [(0,0),(230,85),(256,256),(511,511)]:
                window.navigate(row,col,False);a,b=window.displayed_boundaries
                assert np.allclose((b-a)*1.12,scan.thickness[k,row],equal_nan=True)
                assert np.isnan(a[scan.shadow[row]]).all() and np.isnan(b[scan.shadow[row]]).all()
                assert (window.row,window.col)==(row,col)
        assert window.store.signature()==sig
        window.mode.setCurrentIndex(0);assert not window.boundary_items and not window.layer.isEnabled()
        window.fit_all()
        fits=[c.viewport().rect().contains(c.mapFromScene(c.scene().sceneRect()).boundingRect()) for c in (window.structural,window.second)]
        assert all(fits)
        assert window.save_all() and window.store.signature()==sig
        results.append(dict(scan_id=scan.scan_id,octa_verified=True,layers_verified=8,matching_endpoints=True,
            native_navigation=True,read_only_bscan=True,no_review_writes=True,maps_fit=True))
        if window.index+1<len(window.visits):Q.QTimer.singleShot(100,lambda:window.load_scan(window.index+1))
        else:
            assert files()==initial
            write(HERE/'verification/gui_all_scans.json',dict(passed=True,scans=results,review_files_unchanged=True))
            window.close();app.quit()
    except Exception:
        import traceback
        fail(traceback.format_exc())
window.octa_ready.connect(lambda:Q.QTimer.singleShot(500,check));window.show();window.load_scan(0)
Q.QTimer.singleShot(600000,lambda:fail('GUI verification timed out'))
raise SystemExit(app.exec())
