"""Queue parity and isolated GUI checks; never writes real human annotations."""
from common import *
from proposals import seed_gui_drafts, model_arrays
from review_store import Store, valid_confirmation

def main():
    queue=read(HERE/'queue/queue.json');rows=queue['acquisitions']
    assert len(rows)==57 and len(queue['excluded'])==10
    source_paths=list((MODEL3/'manual_review/decisions').glob('*.json'))
    before={str(p):sha(p) for p in source_paths}
    selected={read(p)['scan_id'] for p in source_paths if read(p)['review_model3'] and not read(p)['confirm_m2']}
    assert selected=={a['scan_id'] for a in rows}
    isolated=HERE/'verification'/('run_'+uuid.uuid4().hex)
    total=0
    for a in rows:
        r=read(a['gallery_review_source']['path'])
        assert a['review_notes']==r['notes'] and a['gallery_review']==r
        store=Store(a,isolated/'drafts/regions',synthetic=True)
        total+=seed_gui_drafts(store)
        assert not store.path.exists() and not valid_confirmation(store.state)
        union=np.zeros((512,512),bool)
        for region in store.state['regions']:
            assert region['state']=='draft';union|=decode(region['runs'])
        assert np.array_equal(union,model_arrays(a)[0]['filtered_mask'])
        assert store.context['review_notes']==r['notes']
    from viewer import Window,W,Q,configure_app
    from PySide6.QtTest import QTest
    app=W.QApplication([]);configure_app(app)
    window=Window(review_directory=isolated/'gui/regions',synthetic=True,autoload=False)
    window.show();app.processEvents();checks=[]
    indices=list(dict.fromkeys([next(i for i,a in enumerate(rows) if a['review_notes']),len(rows)-1]))
    for index in indices:
        window.load(index);started=time.monotonic()
        while window.future is not None:
            app.processEvents();QTest.qWait(40)
            if time.monotonic()-started>240:raise TimeoutError('Provider load timed out')
        assert window.scan and window.scan.acquisition['scan_id']==rows[index]['scan_id']
        assert window.review_notes.toPlainText()==rows[index]['review_notes']
        assert window.store.context['review_notes']==rows[index]['review_notes']
        assert not valid_confirmation(window.store.state)
        for row in (0,511): window.navigate(row,511);assert window.row==row
        window.prediction.setChecked(True);assert window.context['prediction']
        window.prediction.setChecked(False)
        window.navigate(256,256);window.fit();app.processEvents()
        window.grab().save(str(destination(HERE/'verification'/f'gui_{index:02d}.png')))
        # Save/reopen in an explicitly synthetic namespace preserves both notes and edits.
        m=np.zeros((512,512),bool);m[220:230,220:230]=True
        window.store.add(mask=m);assert window.save()
        resumed=Store(rows[index],window.review_directory,synthetic=True)
        assert resumed.state==window.store.state
        assert resumed.context['review_notes']==rows[index]['review_notes']
        assert seed_gui_drafts(resumed)==0
        checks.append(dict(scan_id=rows[index]['scan_id'],notes_visible=True,save_resume=True,
                           alignment_error_db=window.scan.alignment_max_error_db))
        print(json.dumps(checks[-1]),flush=True)
    window.close();app.processEvents()
    assert before=={str(p):sha(p) for p in source_paths}
    assert not list((HERE/'review/regions').glob('*.json'))
    atomic(HERE/'verification/results.json',dict(passed=True,selected=57,excluded=10,proposals=total,
        all_notes_exact=True,all_candidate_masks_exact=True,source_reviews_unchanged=True,
        real_annotations_created=0,gui_checks=checks))
    print('PASS',flush=True)

if __name__=='__main__':main()
