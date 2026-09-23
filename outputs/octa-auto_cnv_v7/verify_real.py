"""Real native loading + Qt event tests. Generated drawings are SYNTHETIC ONLY."""
from common import *
from viewer import Window, W, Q, G, Qt, COLORS, configure_app
from review_store import Store, valid_confirmation
from PySide6.QtTest import QTest

def wait(app,predicate,seconds=240):
    started=time.monotonic()
    while not predicate():
        app.processEvents();QTest.qWait(30)
        if time.monotonic()-started>seconds:raise TimeoutError('Real GUI load/operation timed out')
    app.processEvents()

def preservation_paths(acquisitions):
    paths=set()
    for n in range(1,6):
        root=ROOT/f'outputs/octa-auto_cnv_v{n}'
        paths.update(p for p in root.rglob('*') if p.is_file() and (p.suffix in ('.py','.cmd','.md') or 'regions' in p.parts and p.suffix in ('.json','.npz')))
    v6=V6.parent
    paths.update(p for p in v6.rglob('*') if p.is_file() and (p.suffix in ('.py','.cmd','.md','.pt') or 'regions' in p.parts and p.suffix=='.json'))
    paths.update((ROOT/'outputs/cnv_labels').glob('*.npz'))
    paths.update((ROOT/'outputs/cnv_review_v1/regions').glob('*.json'))
    for a in acquisitions:
        sid=a['scan_id'];paths.add(Path(a['input_manifest']['path']))
        for key in ('B_267','B_268','B_269','C_267','C_268','C_269'):paths.add(V6/'predictions'/key/(sid+'.npz'))
        paths.add(V6/'predictions/provenance'/(sid+'.json'))
    return sorted(paths)

def run():
    queue=read(HERE/'queue/queue.json')['acquisitions']
    sids=[queue[0]['scan_id'],'TS267_OD_2025-03-05_D14_s01_104048','TS336_OD_2026-07-28_D56_s01_143412']
    sids += [next(a['scan_id'] for a in queue if a['animal']=='TS241')]
    selected=[next(a for a in queue if a['scan_id']==sid) for sid in sids]
    paths=preservation_paths(selected);print('Hashing preservation scope:',len(paths),flush=True)
    before={str(p):sha(p) for p in paths};atomic(HERE/'verification/preservation_before.json',before)
    real_before={str(p):sha(p) for p in (HERE/'review/regions').glob('*.json')}
    app=W.QApplication([]);configure_app(app)
    window=Window(autoload=False);window.show();app.processEvents();results=[]
    for a in selected:
        start=time.monotonic();index=next(i for i,r in enumerate(queue) if r['scan_id']==a['scan_id'])
        window.load(index,manual=True);wait(app,lambda:window.future is None)
        assert window.scan is not None and window.scan.acquisition['scan_id']==a['scan_id']
        assert not window.store.path.exists() and not window.store.dirty
        window.fit();QTest.qWait(120);app.processEvents()
        screen=HERE/'verification'/('real_'+a['animal']+'.png');window.grab().save(str(destination(screen)))
        result=dict(scan_id=a['scan_id'],load_seconds=round(time.monotonic()-start,2),
            max_projection_error_db=window.scan.alignment_max_error_db,shape=list(window.scan.images.shape),
            screenshot=str(screen),historical_evidence=len(a['historical_evidence']))
        window.navigate(0,0);assert window.row==0 and window.col==0
        window.navigate(511,511);assert window.row==511 and window.col==511
        window.navigate(256,256);row=window.row;col=window.col
        window.prediction.setChecked(True);assert window.context.get('prediction')
        window.historical.setChecked(True)
        assert window.row==row and window.col==col and not window.store.dirty
        window.prediction.setChecked(False);window.historical.setChecked(False)
        assert not window.store.path.exists()
        results.append(result);print(json.dumps(result),flush=True)
    # Reuse a real native provider, but ALL edit gestures below use isolated synthetic records.
    synthetic=HERE/'verification/gui'/uuid.uuid4().hex/'regions'
    window.review_directory=synthetic;window.synthetic=True;window.session_path=synthetic.parent/'session.json'
    window.store=Store(window.scan.acquisition,synthetic,synthetic=True)
    window.setWindowTitle('SYNTHETIC SOFTWARE TEST on real native OCT — NOT human annotation')
    window.navigate(256,256);window.add();window.mode('paint')
    # Actual mouse gestures on the Qt canvas: a closed native loop.
    points=[(210,225),(290,225),(290,285),(210,285),(210,225)]
    positions=[window.structural.mapFromScene(G.QPolygonF([Q.QPointF(x,y)])[0]) for x,y in points]
    QTest.mousePress(window.structural.viewport(),Qt.MouseButton.LeftButton,pos=positions[0])
    for p in positions[1:]:QTest.mouseMove(window.structural.viewport(),p,20)
    QTest.mouseRelease(window.structural.viewport(),Qt.MouseButton.LeftButton,pos=positions[-1]);app.processEvents()
    mask=decode(window.current()['runs']);assert mask[256,256], 'closed gesture must fill interior'
    assert window.row==256 and window.col==256
    window.classify('kept');window.confirm();assert valid_confirmation(window.store.state)
    window.navigate(256,256);assert window.band_geometry and window.band_geometry[0][2]==COLORS['kept']
    window.grab().save(str(destination(HERE/'verification/synthetic_kept_bands.png')))
    # Disconnected row runs and both image edges must map to exact A-line rectangles.
    m=np.zeros((512,512),bool);m[0,[0,1,6,511]]=True;m[511,20:25]=True;m[256,0:3]=True;m[256,90:110]=True;m[256,500:512]=True
    i=window.store.add(mask=m);window.selected=i;window.refresh();window.navigate(0,0)
    assert [(l,r) for l,r,c,s in window.band_geometry if c==COLORS['draft']]==[(0,2),(6,7),(511,512)]
    window.navigate(511,511);assert [(l,r) for l,r,c,s in window.band_geometry if c==COLORS['draft']]==[(20,25)]
    window.navigate(256,256);window.fit();window.structural.scale(1.5,1.5);window.bscan.scale(1.3,1.3)
    transform=window.bscan.transform();window.classify('unsure');assert window.bscan.transform()==transform
    assert any(c==COLORS['unsure'] for _,_,c,_ in window.band_geometry)
    window.grab().save(str(destination(HERE/'verification/synthetic_multiple_intervals.png')))
    window.classify('removed');assert not any(c==COLORS['removed'] for _,_,c,_ in window.band_geometry)
    window.removed.setChecked(True);assert any(c==COLORS['removed'] for _,_,c,_ in window.band_geometry)
    window.removed.setChecked(False);window.undo();assert window.current()['state']=='unsure';window.redo();assert window.current()['state']=='removed'
    window.selected=0;window.mode('erase');stroke=np.zeros((512,512),bool);stroke[250:260,250:260]=True
    window.stroke(stroke);assert not decode(window.current()['runs'])[255,255];assert not valid_confirmation(window.store.state)
    window.undo();assert decode(window.current()['runs'])[255,255]
    window.save();reopened=Store(window.scan.acquisition,synthetic,synthetic=True);assert reopened.state==window.store.state
    window.selected=0;window.classify('removed');window.absence.setChecked(True);window.confirm()
    assert valid_confirmation(window.store.state) and not window.band_geometry
    window.add();assert not window.absence.isChecked() and not valid_confirmation(window.store.state)
    window.undo();assert window.absence.isChecked() and valid_confirmation(window.store.state)
    window.save();window.close();app.processEvents()
    after={str(p):sha(p) for p in paths};assert before==after
    real_after={str(p):sha(p) for p in (HERE/'review/regions').glob('*.json')};assert real_before==real_after
    atomic(HERE/'verification/preservation_result.json',dict(passed=True,files=len(paths),bytes=sum(p.stat().st_size for p in paths),
        scope='Full file SHA256 of v1-v6 code/docs/launchers, v6 checkpoints, original CNV labels, region records/history, and six-model predictions/provenance for four tested acquisitions. Other predictions and giant source volumes not freshly full-hashed.',
        real_annotation_records_before=len(real_before),real_annotation_records_after=len(real_after),at=now()))
    atomic(HERE/'verification/real_gui.json',dict(passed=True,acquisitions=results,qt_mouse_closed_loop=True,
        native_edge_intervals=True,zoom_preserved=True,context_visibility_and_cursor=True,save_reopen=True,
        absent_add_undo=True,synthetic_only_edits=True,at=now()))
    print('Real GUI verification passed; old files unchanged and zero fabricated human annotations.',flush=True)

if __name__=='__main__':run()
