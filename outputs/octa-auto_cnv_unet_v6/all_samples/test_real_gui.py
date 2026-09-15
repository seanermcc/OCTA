import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from common import *
from loader import load_scan
from viewer import Window,W,Q,gui
from review_store import ReviewStore
import tempfile

def run(requested_sid=None,prefix='gui_real_data'):
    app=W.QApplication.instance() or W.QApplication([]);gui.configure_app(app)
    sid=requested_sid or next(r['scan_id'] for r in selected() if (HERE/'records'/f"{r['scan_id']}.json").exists() and read(HERE/'records'/f"{r['scan_id']}.json")['status']=='completed')
    with tempfile.TemporaryDirectory(dir=dest(HERE/'verification/real_fixture/.keep').parent) as tmp:
        directory=Path(tmp);scan,store=load_scan(sid,review_directory=directory/'regions')
        sources=scan.metadata['reference_review']['sources'];before={fp['path']:sha(fp['path']) for fp in sources}
        proposal_before={str(p):sha(p) for p in (HERE/'predictions').glob(f'*/{sid}.npz')}
        index=next(i for i,r in enumerate(selected()) if r['scan_id']==sid)
        w=Window(index,autoload=False);w.session_directory=directory/'sessions';w.loaded((scan,store));w.show();app.processEvents();w.fit_all()
        w.navigate(213,347,False);assert w.row==213 and w.col==347 and np.array_equal(w.scan.images[213],scan.images[213])
        # Explicit actions use the actual editor and its isolated annotation writer.
        if store.regions:w.selected=0
        else:
            w.add_cnv();w.diameter.setValue(3);w.stroke([(70,70),(82,70),(82,82),(70,82),(70,70)],'cnv_brush_add')
        w.keep();w.save_all();uid=store.regions[0].id
        w.experiment.setCurrentText('C');w.seed.setCurrentText('269');w.compare.setCurrentIndex(1)
        assert any(r.id==uid and r.decision=='approved' for r in store.regions)
        w.add_cnv();w.diameter.setValue(3);w.stroke([(16,16),(27,16),(27,27),(16,27),(16,16)],'cnv_brush_add');w.keep();w.save_all()
        reopened=ReviewStore(directory/'regions',scan,'B_268')
        assert sum(r.decision=='approved' for r in reopened.regions)==2
        w.grab().save(str(dest(HERE/'verification'/f'{prefix}.png')))
        for ex in ('B','C'):
            for seed in ('267','268','269'):w.experiment.setCurrentText(ex);w.seed.setCurrentText(seed);assert store.model==ex+'_'+seed
        w.close();app.processEvents()
        clean_scan,clean_store=load_scan(sid,review_directory=directory/'clean_regions')
        clean=Window(index,autoload=False);clean.session_directory=directory/'clean_sessions';clean.loaded((clean_scan,clean_store));clean.show();app.processEvents();clean.compare.setCurrentIndex(1);clean.fit_all();app.processEvents()
        ready='gui_ready' if prefix=='gui_real_data' else prefix+'_ready'
        clean.grab().save(str(dest(HERE/'verification'/f'{ready}.png')));clean.close();app.processEvents()
        assert not clean_store.path.exists()
        assert before=={p:sha(p) for p in before}
        assert proposal_before=={p:sha(p) for p in proposal_before}
        write(HERE/'verification'/f'{prefix}.json',dict(passed=True,scan_id=sid,all_six_switches=True,linked_native_coordinate=[213,347],
            isolated_edit_save_reopen=True,original_reference_hashes_unchanged=True,reference_sources_checked=len(before),proposals_unchanged=True,human_evaluation=False))
    print('Real-data GUI verification passed; all edits isolated',flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--first-new',action='store_true');args=parser.parse_args()
    if args.first_new:
        sid=next(r['scan_id'] for r in selected() if Path(r['upstream_volume']).is_relative_to(HERE))
        run(sid,'gui_new_acquisition')
    else:run()
