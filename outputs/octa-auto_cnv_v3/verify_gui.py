"""Open all pilot acquisitions in the actual GUI; never edit study labels."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from common import *
from viewer import create_window,W,gui

app=W.QApplication([]);gui.configure_app(app)
w=create_window();results=[];initial={str(p):sha(p) for p in (HERE/'review').rglob('*') if p.is_file()}

def fail(message):
    write(HERE/'verification/gui_all_scans.json',dict(passed=False,error=message,scans=results));app.exit(1)
w._load_failed=fail

def check():
    try:
        sid=w.scan.scan_id;print('GUI',sid,flush=True)
        assert w.scan.native_shape==(512,512)
        assert not w.store.dirty
        seed=w.scan.maps['core'].copy();revision=w.store.signature()
        for row,col in [(0,0),(256,256),(511,511)]:
            w._enface_clicked(row,col)
            assert (w.row,w.col)==(row,col)
            assert int(w.editor.pack.bscan_index[0])==row
        w.variant.setCurrentText('narrow_halo');w.contours.setChecked(True);w.map_choice.setCurrentIndex(0)
        assert np.array_equal(seed,w.scan.maps['core']);assert w.store.signature()==revision
        if '_D14_' in sid and '_OD_' in sid:
            w._enface_clicked(230,85)
            assert w.selected_region().seed_ids==[int(w.scan.maps['candidate_labels'][230,85])]
            assert 'ILM crosses RNFL_GCL' in w.reason.text()
        assert len(w.scan.metadata['candidates'])<=4
        if w.manual_components:
            before=w.store.signature();w.manual_choice.setCurrentIndex(1);w.navigate_manual(1)
            assert w.store.signature()==before
        w.auto_check.setChecked(False);assert w.selected==-1
        assert all(w.region_list.item(i).isHidden() for i,r in enumerate(w.store.regions) if r.seed_ids and r.decision=='unreviewed')
        w.auto_check.setChecked(True)
        if '_D28_' in sid and '_OD_' in sid:
            w.grab().save(str(destination(HERE/'verification/D28_integrated_gui.png')))
        results.append(dict(scan_id=sid,opened=True,native_navigation=True,variant_independence=True,no_label_writes=True))
        if w._selected_index+1<len(w.paths):gui.QtCore.QTimer.singleShot(50,lambda:w.load_scan(w._selected_index+1))
        else:
            assert w.save_all()
            final={str(p):sha(p) for p in (HERE/'review').rglob('*') if p.is_file()}
            assert final==initial
            write(HERE/'verification/gui_all_scans.json',dict(passed=True,scans=results,review_files_unchanged=True))
            w.close();app.quit()
    except Exception as exc:fail(repr(exc))
w.ready.connect(lambda:gui.QtCore.QTimer.singleShot(50,check))
w.show();raise SystemExit(app.exec())

