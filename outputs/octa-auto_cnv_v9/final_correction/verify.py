"""Exact queue, export, and isolated GUI checks. Synthetic records are not labels."""
from common import *
from proposals import seed_gui_drafts
from review_store import Store, valid_confirmation, targets
from dataset import run as export_dataset

def main():
    queue=read(HERE/'queue/queue.json');rows=queue['acquisitions']
    assert len(rows)==len({a['scan_id'] for a in rows})==14
    assert sum(len([r for r in a['assessment_records'].values() if r['status']=='review']) for a in rows)==15
    isolated=HERE/'verification'/('run_'+uuid.uuid4().hex)
    originals={str(p):sha(p) for p in (MODEL3/'correction/review/regions').glob('*.json')}
    for a in rows:
        store=Store(a,isolated/'completed/regions',synthetic=True)
        seed_gui_drafts(store)
        assert not store.path.exists() and not valid_confirmation(store.state)
        drafts=np.zeros((512,512),bool)
        for r in store.state['regions']:
            if r['state']=='draft': drafts|=decode(r['runs'])
        assert np.array_equal(drafts,decode(a['selected_reference']['runs']))
        assert store.context['review_notes']==a['review_notes']
        # Synthetic positives and one negative exercise completed dataset export.
        for i in range(len(store.state['regions'])):
            store.set_region(i,state='removed' if a['selected_reference']['source']=='m2' else ('kept' if store.state['regions'][i]['state']=='draft' else 'unsure'))
        if a['selected_reference']['source']=='m2':store.absence(True)
        store.confirm(ignore_conflicts=True);store.save()
        resumed=Store(a,isolated/'completed/regions',synthetic=True)
        assert resumed.state==store.state and seed_gui_drafts(resumed)==0
        assert valid_confirmation(resumed.state)
    summary=export_dataset(isolated/'completed/regions',isolated/'dataset',synthetic=True)
    assert summary['assessable_dataset_complete'] and not summary['all_324_have_definitive_labels']
    assert summary['counts']==dict(confirmed_positive=216,confirmed_negative=106,excluded_poor_image=2)
    manifest=read(isolated/'dataset/manifest.json')
    duplicate=next(r for r in manifest['records'] if r['scan_id']=='TS267_OD_2025-02-19_D0_s02_112013')
    assert duplicate['ignored_pixels']==3832
    with np.load(duplicate['targets']['path']) as z:assert not z['known'][z['ignored']].any()
    # Real native-image rendering and GUI save/resume remain isolated.
    from viewer import Window,W,Q,configure_app
    from PySide6.QtTest import QTest
    app=W.QApplication([]);configure_app(app)
    window=Window(review_directory=isolated/'gui/regions',synthetic=True,autoload=False)
    window.show();app.processEvents();checks=[]
    for index in (0,next(i for i,a in enumerate(rows) if len(a['assessment_references'])>1),next(i for i,a in enumerate(rows) if a['selected_reference']['source']=='m2')):
        window.load(index);start=time.monotonic()
        while window.future is not None:
            app.processEvents();QTest.qWait(50)
            if time.monotonic()-start>240:raise TimeoutError('Native provider load timed out')
        assert window.scan and window.scan.acquisition['scan_id']==rows[index]['scan_id']
        assert window.review_notes.toPlainText()==rows[index]['review_notes']
        window.historical.setChecked(True);assert len(window.context['historical'])==len(rows[index]['assessment_references'])
        window.historical.setChecked(False)
        for y in (0,511):window.navigate(y,511);assert window.row==y
        window.navigate(256,256);window.fit();app.processEvents()
        window.grab().save(str(destination(HERE/'verification'/f'gui_{index:02d}.png')))
        assert window.save()
        saved=Store(rows[index],window.review_directory,synthetic=True)
        assert saved.state==window.store.state and not valid_confirmation(saved.state)
        checks.append(dict(scan_id=rows[index]['scan_id'],alignment_error_db=window.scan.alignment_max_error_db,save_resume=True))
        print(json.dumps(checks[-1]),flush=True)
    window.close();app.processEvents()
    assert originals=={p:sha(p) for p in originals}
    assert not list((HERE/'review/regions').glob('*.json'))
    atomic(HERE/'verification/results.json',dict(passed=True,at=now(),queued=14,flagged_entries=15,
        exact_initial_masks=True,synthetic_export=summary,original_corrections_unchanged=True,
        real_annotations_created=0,gui_checks=checks))
    print('PASS',flush=True)

if __name__=='__main__':main()
