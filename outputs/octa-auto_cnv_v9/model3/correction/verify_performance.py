"""Regression checks and timings. Real human records are read-only throughout."""
from common import *
from review_store import Store, progress, valid_confirmation
import copy
from types import SimpleNamespace

def main():
    review=HERE/'review';files=list(review.rglob('*'));before={str(p):sha(p) for p in files if p.is_file()}
    rows=read(HERE/'queue/queue.json')['acquisitions'];cache={}
    start=time.perf_counter();cold=progress(rows,cache=cache);cold_s=time.perf_counter()-start
    start=time.perf_counter()
    for _ in range(15):assert progress(rows,cache=cache)==cold
    warm_s=(time.perf_counter()-start)/15
    assert not cold['errors']
    original=[]
    for a in rows:
        p=review/'regions'/(a['scan_id']+'.json')
        if p.exists():original.append(Store(a))
    for store in original:
        for runs in read(store.path)['masks'].values():
            mask=decode(runs)
            assert encode(mask)==runs
    rng=np.random.default_rng(812)
    for mask in [np.zeros((512,512),bool),np.ones((512,512),bool),rng.random((512,512))>.6]:
        assert encode(mask)==[[y,a,b] for y,row in enumerate(mask) for a,b in intervals(row)]

    from viewer import Window,W,Q,Qt,configure_app
    from PySide6.QtTest import QTest
    app=W.QApplication([]);configure_app(app)
    isolated=HERE/'verification'/('performance_'+uuid.uuid4().hex)
    window=Window(review_directory=isolated/'regions',synthetic=True,autoload=False)
    # Suppress native-volume prefetch; this test exercises editing with realistic saved masks.
    window.cache.request=lambda a:None
    sid=read(review/'session.json')['scan_id'];index=next(i for i,a in enumerate(rows) if a['scan_id']==sid)
    saved=next(s for s in original if s.acquisition['scan_id']==sid)
    native=np.broadcast_to(np.linspace(0,1,512,dtype=np.float32),(512,390,512))
    optical=np.broadcast_to(np.linspace(0,1,512,dtype=np.float32),(512,512))
    scan=SimpleNamespace(acquisition=rows[index],images=native,structural=optical,octa=optical,metadata={'canonical_crop_offset':300})
    window.pending=index;window.loaded(scan)
    window.store.state=copy.deepcopy(saved.state);window.store.context=copy.deepcopy(saved.context)
    window.store.undo_stack=copy.deepcopy(saved.undo_stack);window.store.redo_stack=copy.deepcopy(saved.redo_stack)
    window.selected=next((i for i,r in enumerate(window.store.state['regions']) if r['state']!='removed'),-1)
    window.show();window.refresh();app.processEvents()
    assert window.review_notes.toPlainText()==rows[index]['review_notes']
    start=time.perf_counter()
    for _ in range(20):window.refresh()
    refresh_s=(time.perf_counter()-start)/20
    # Navigation must preserve existing en-face image items; overlay edits preserve B-scan image.
    enface_items=list(window.structural.items);base=next(i for i in window.bscan.scene().items() if isinstance(i,W.QGraphicsPixmapItem))
    for c in range(30):window.navigate(window.row,c)
    assert window.structural.items==enface_items
    assert base in window.bscan.scene().items()
    if window.selected<0:window.add()
    window.mode('paint')
    region_before=copy.deepcopy(window.current());stroke=np.zeros((512,512),bool);stroke[220:235,220:235]=True
    start=time.perf_counter()
    for _ in range(100):window.stroke_preview(stroke)
    preview_s=(time.perf_counter()-start)/100
    window.stroke(stroke)
    assert decode(window.current()['runs'])[225,225]
    assert not valid_confirmation(window.store.state)
    window.undo();assert window.current()==region_before
    window.redo();assert decode(window.current()['runs'])[225,225]
    # Exercise mouse strokes, not only method calls.
    pos=window.structural.mapFromScene(Q.QPointF(240,240))
    QTest.mousePress(window.structural.viewport(),Qt.MouseButton.LeftButton,pos=pos)
    QTest.mouseRelease(window.structural.viewport(),Qt.MouseButton.LeftButton,pos=pos)
    assert decode(window.current()['runs'])[240,240]
    start=time.perf_counter();assert window.save();save_s=time.perf_counter()-start
    resumed=Store(rows[index],window.review_directory,synthetic=True)
    assert resumed.state==window.store.state and resumed.context==window.store.context
    assert resumed.undo_stack==window.store.undo_stack and resumed.redo_stack==window.store.redo_stack
    assert read(window.session_path)['scan_id']==sid
    # Warm progress must notice edits, confirmations, malformed records, and deletion.
    pc={};test_rows=[rows[index]]
    assert progress(test_rows,window.review_directory,verify_synthetic=True,cache=pc)['draft']==1
    for r in window.store.state['regions']:r['state']='removed'
    window.store.state['absence']=True;window.store.confirm();assert window.save()
    assert progress(test_rows,window.review_directory,verify_synthetic=True,cache=pc)['negative']==1
    fixture=read(window.store.path);fixture['masks']['positive']=[[0,0,1]]
    atomic(window.store.path,fixture)
    assert progress(test_rows,window.review_directory,verify_synthetic=True,cache=pc)['errors']
    # Restore synthetic file from its immutable saved history; never touch real reviews.
    history=sorted((window.review_directory/'history'/sid).glob('*.json'))[-1]
    atomic(window.store.path,read(history));window.store.disk_hash=sha(window.store.path)
    assert progress(test_rows,window.review_directory,verify_synthetic=True,cache=pc)['negative']==1
    window.grab().save(str(destination(isolated/'editor.png')))
    window.close();app.processEvents()
    assert before=={str(p):sha(p) for p in files if p.is_file()}
    result=dict(passed=True,real_review_files_unchanged=len(before),saved_scans=len(original),
        confirmed=cold['positive']+cold['negative'],cold_progress_seconds=cold_s,warm_progress_seconds=warm_s,
        gui_refresh_seconds=refresh_s,preview_event_seconds=preview_s,save_seconds=save_s,
        notes_edits_undo_redo_resume=True,cache_invalidation_and_corruption_detection=True,encoding_exact=True)
    atomic(HERE/'verification/performance_after.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
