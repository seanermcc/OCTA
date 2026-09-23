"""Isolated synthetic annotation tests and real optical GUI checks."""
from common import *
from review_store import Store, valid_confirmation, targets, progress
from proposals import seed_gui_drafts, model_arrays
from measure import run, lesion_measurements, PX_UM

def main():
    queue=read(HERE/'queue/queue.json')['acquisitions']
    real_before={str(p):sha(p) for p in (HERE/'review/regions').glob('*.json')}
    old_paths=list((V7/'review').rglob('*.json'))+list((V8/'predictions/model1').glob('*'))
    before={str(p):sha(p) for p in old_paths}
    isolated=HERE/'verification'/uuid.uuid4().hex
    directory=isolated/'regions';out=isolated/'reports'
    count=0
    for a in queue:
        s=Store(a,directory,synthetic=True);n=seed_gui_drafts(s);count+=n
        mask=np.zeros((512,512),bool)
        for r in s.state['regions']:
            assert r['state']=='draft';mask|=decode(r['runs'])
        z,_=model_arrays(a);assert np.array_equal(mask,z['filtered_mask'])
        assert not s.path.exists() and not valid_confirmation(s.state)
        assert not targets(s.state,s.shape)[0].any()
    assert count==read(HERE/'reports/setup.json')['proposals']
    a=queue[0];s=Store(a,directory,synthetic=True)
    mask=np.zeros((512,512),bool);mask[100:110,200:220]=True
    i=s.add(mask=mask);s.set_region(i,state='kept');s.save()
    assert run(directory,out,True)['confirmed_images']==0
    s.confirm();s.save();summary=run(directory,out,True)
    assert summary['confirmed_images']==1 and summary['confirmed_lesion_regions']==1
    assert abs(summary['total_observed_cnv_area_um2']-200*PX_UM**2)<1e-8
    assert summary['complete_lesion_size_distribution']['n']==1
    assert len(read(out/'training_manifest.json')['records'])==1
    modified=mask.copy();modified[105,210]=False;s.set_region(i,mask=modified);s.save()
    assert run(directory,out,True)['confirmed_images']==0
    assert not read(out/'training_manifest.json')['records']
    s.undo();s.save();assert run(directory,out,True)['confirmed_images']==1
    reopened=Store(a,directory,synthetic=True);assert reopened.state==s.state
    # Overlap is counted once in a scan and excluded from complete-lesion distribution.
    j=s.add(mask=mask);s.set_region(j,state='kept');s.confirm();s.save()
    summary=run(directory,out,True)
    assert summary['total_observed_cnv_area_um2']==200*PX_UM**2
    assert summary['complete_lesion_size_distribution']['n']==0
    # Boundary clipping is visible area, never an unqualified full-lesion size.
    edge=np.zeros((512,512),bool);edge[:3,:4]=True
    s.set_region(j,mask=edge);s.confirm()
    rr,*_=lesion_measurements(s.state,s.shape);assert rr[1]['touches_fov_edge']
    # Explicit negatives count towards the 30 completed scans.
    for k in range(len(s.state['regions'])):s.set_region(k,state='removed')
    s.absence(True);s.confirm();s.save()
    summary=run(directory,out,True);assert summary['confirmed_negative_images']==1
    assert summary['confirmed_lesion_regions']==0
    # A later draft cannot be replaced by model proposals on reopen.
    s.absence(False);s.add(mask=mask);s.save();state=read(s.path)['state']
    reopened=Store(a,directory,synthetic=True);seed_gui_drafts(reopened);assert reopened.state==state

    from viewer import Window,W,Q,Qt,G,configure_app,COLORS
    from PySide6.QtTest import QTest
    app=W.QApplication([]);configure_app(app)
    window=Window(review_directory=isolated/'gui/regions',synthetic=True,autoload=False)
    window.setWindowTitle('SYNTHETIC QA · Model 1 correction editor');window.show();app.processEvents()
    checks=[]
    # Check first training case and first/last newly reviewed acquisition through actual provider.
    indices=[0,next(i for i,a in enumerate(queue) if not a['model1_training_exposure']),29]
    for index in indices:
        window.load(index);started=time.monotonic()
        while window.future is not None:
            app.processEvents();QTest.qWait(40)
            if time.monotonic()-started>240:raise TimeoutError('Real provider timed out')
        assert window.scan and window.scan.acquisition['scan_id']==queue[index]['scan_id']
        assert all(r['state']=='draft' for r in window.store.state['regions'])
        assert not valid_confirmation(window.store.state)
        for row in (0,511):window.navigate(row,511);assert window.row==row and window.col==511
        window.prediction.setChecked(True);assert window.context['prediction']
        window.prediction.setChecked(False)
        window.navigate(256,256);window.fit();app.processEvents()
        window.grab().save(str(destination(HERE/'verification'/f'gui_{index:02d}.png')))
        checks.append(dict(scan_id=queue[index]['scan_id'],shape=list(window.scan.images.shape),projection_error_db=window.scan.alignment_max_error_db,proposals=len(window.store.state['regions'])))
        print(json.dumps(checks[-1]),flush=True)
    # GUI editing invalidation, native bands, save/reopen and splitting.
    window.add();window.mode('paint')
    points=[(210,225),(290,225),(290,285),(210,285),(210,225)]
    pos=[window.structural.mapFromScene(Q.QPointF(x,y)) for x,y in points]
    QTest.mousePress(window.structural.viewport(),Qt.MouseButton.LeftButton,pos=pos[0])
    for p in pos[1:]:QTest.mouseMove(window.structural.viewport(),p,20)
    QTest.mouseRelease(window.structural.viewport(),Qt.MouseButton.LeftButton,pos=pos[-1]);app.processEvents()
    assert decode(window.current()['runs'])[256,256]
    window.classify('kept');window.navigate(256,256)
    assert any(c==COLORS['kept'] for _,_,c,_ in window.band_geometry)
    m=np.zeros((512,512),bool);m[50:60,50:60]=True;m[90:100,90:100]=True
    window.store.set_region(window.selected,mask=m);window.split_disconnected()
    assert sum(r['origin']['kind']=='human_split' for r in window.store.state['regions'])==2
    assert window.save();saved=Store(window.scan.acquisition,window.review_directory,synthetic=True)
    assert saved.state==window.store.state
    window.close();app.processEvents()
    assert before=={str(p):sha(p) for p in old_paths}
    assert real_before=={str(p):sha(p) for p in (HERE/'review/regions').glob('*.json')}
    atomic(HERE/'verification/results.json',dict(passed=True,at=now(),proposal_acquisitions=30,proposals=count,
        tests=['proposal identity/union/draft status','confirmed-only measurement/export','area conversion','deduplicated scan union',
            'edit invalidation and stale-target exclusion','undo/save/reopen','edge and overlap flags','explicit negative','resume priority',
            'real optical loading','native row endpoints','raw Model 1 context','Qt mouse painting','B-scan bands','split disconnected'],
        real_gui=checks,unchanged_input_files=len(old_paths),real_annotations_unchanged=True))
    print('PASS: correction workflow, size export, real GUI, and input preservation',flush=True)

if __name__=='__main__':main()
