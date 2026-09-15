"""Isolated GUI and cache verification; no study decisions are generated."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from common import *
import unittest,tempfile,time,copy,threading,itertools
from types import SimpleNamespace
import v5_editor
from viewer import Window,W,Q,Qt,gui
from review_store import ReviewStore
from loader import SampleCache,CancelledError

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=W.QApplication.instance() or W.QApplication([]);gui.configure_app(cls.app)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=dest(REVIEW/'verification/fixtures/.keep').parent);self.root=Path(self.tmp.name)
        shape=(64,96);yy,xx=np.indices(shape);ends=np.broadcast_to(np.array([10,20,32,52,68,80,120,140])[None,:,None],(64,8,96)).astype(float).copy()
        values=np.stack([(ends[:,b]-ends[:,a])*1.12 for _,a,b in LAYERS]);values[:,:,7]=np.nan
        manual=np.zeros(shape,bool);manual[40:48,70:82]=True
        self.scan=SimpleNamespace(scan_id='TS999_ISOLATED',source_volume=self.root/'source_processedVolumes.mat',native_shape=shape,
            structural_enface=(xx+yy).astype(float),octa=(xx-yy).astype(float),octa_metadata={'channel':'frame_OCTAAvg'},octa_error=None,
            images=np.broadcast_to(np.arange(160)[None,:,None],(64,160,96)).astype(float),thickness=values,endpoints=ends,surface_names=tuple(SURFACES),px_um=1.12,
            shadow=np.zeros(shape,bool),manual_mask=manual,reference_uncertain=np.zeros(shape,bool),reference_removed=np.zeros(shape,bool),
            metadata={'reference_review':{'sources':[]}},thickness_metadata={'revision':'isolated fixture'})
        self.props=self.root/'predictions'
        for i,key in enumerate(['B_267','B_268','B_269','C_267','C_268','C_269']):
            labels=np.zeros(shape,int);labels[20:30,35+i:45+i]=1
            save(self.props/key/f'{self.scan.scan_id}.npz',candidate_labels=labels,mask=labels>0,score=(labels>0).astype('float32'))
        self.hashes={str(p):sha(p) for p in self.props.rglob('*.npz')}
        self.store=ReviewStore(self.root/'regions',self.scan,proposal_root=self.props)
        self.old_selected=v5_editor.selected
        v5_editor.selected=lambda:[dict(scan_id=self.scan.scan_id,animal='TS999',eye='OD',session_date='test',day_label='test',scan_no=1,acq_time='test')]
        self.w=Window(autoload=False,review_directory=self.root);self.w.loaded((self.scan,self.store));self.w.show();self.app.processEvents()
    def tearDown(self):
        self.w.close();self.w.deleteLater();self.app.processEvents();v5_editor.selected=self.old_selected
        self.assertEqual(self.hashes,{str(p):sha(p) for p in self.props.rglob('*.npz')});self.tmp.cleanup()
    def draw(self):
        self.w.add_cnv();self.w.diameter.setValue(3);self.w.stroke([(12,10),(30,10),(30,30),(12,30),(12,10)],'cnv_brush_add')
    def rate(self,ex,value):
        if value is None:
            for val in ('acceptable','unacceptable'):self.w.rating_checks[ex,val].setChecked(False)
        else:self.w.rating_checks[ex,value].setChecked(True)
    def value(self,key):return self.store.ratings.get(key,{}).get('value')
    def test_all_nine_rating_combinations_clearing_seed_and_restart(self):
        for b,c in itertools.product((None,'acceptable','unacceptable'),repeat=2):
            self.rate('B',b);self.rate('C',c)
            self.assertEqual((self.value('B_267'),self.value('C_267')),(b,c))
            self.w.save_all();again=ReviewStore(self.root/'regions',self.scan,'B_267',self.props)
            self.assertEqual(tuple(again.ratings.get(k,{}).get('value') for k in ('B_267','C_267')),(b,c))
        self.w.seed.setCurrentText('268');self.assertFalse(any(x.isChecked() for x in self.w.rating_checks.values()))
        self.rate('B','acceptable');self.w.seed.setCurrentText('267')
        self.assertTrue(self.w.rating_checks['B','unacceptable'].isChecked())
        self.assertEqual(self.store.ratings['B_268']['seed'],268)
        self.assertEqual(self.store.ratings['B_268']['original_output']['sha256'],self.hashes[str(self.props/'B_268'/f'{self.scan.scan_id}.npz')])
    def test_browsing_never_rates_or_creates_regions(self):
        for ex in ('B','C'):
            for seed in ('267','268','269'):
                self.w.experiment.setCurrentText(ex);self.w.seed.setCurrentText(seed);self.w.compare.setCurrentIndex(3)
                self.w.manual_check.setChecked(True);self.w.manual_check.setChecked(False);self.w.save_all()
        self.assertEqual(self.store.ratings,{});self.assertFalse(self.store.path.exists())
        self.assertEqual(self.store.review_events,[])
    def test_manual_is_optional_readonly_never_listed_and_never_blocks_finish(self):
        colors=[];original=self.w.mask_overlay
        self.w.mask_overlay=lambda canvas,mask,color,selected=False:(colors.append(color),original(canvas,mask,color,selected))[-1]
        self.w.render_maps();self.assertNotIn('#4ce0ff',colors)
        self.w.manual_check.setChecked(True);self.assertIn('#4ce0ff',colors)
        self.assertTrue(all(kind=='region' for kind,k in self.w.entries))
        self.w.selected=-1;self.w.navigate(44,75);self.assertIsNone(self.w.current_region());self.assertEqual(self.w.reference,-1)
        self.w.keep();self.assertEqual(self.store.ratings,{})
        colors.clear();self.w.manual_check.setChecked(False);self.assertNotIn('#4ce0ff',colors)
        self.w.finish_scan();self.assertTrue(self.store.scan_review['rating_review_finished'])
        self.assertFalse(self.store.scan_review['whole_field_checked']);self.assertFalse(self.store.scan_review['reviewed_absence'])
        self.assertEqual(read(self.store.path)['regions'],[])
    def test_delete_false_suggestion_attributes_own_model_and_undo_redo(self):
        self.rate('B','acceptable');self.rate('C','acceptable');self.w.selected=0;original=self.store.regions[0].mask.copy()
        self.w.remove();self.assertEqual(self.value('B_267'),'unacceptable');self.assertEqual(self.value('C_267'),'acceptable')
        error=next(e for e in self.store.review_events if e['action']=='false suggestion')
        np.testing.assert_array_equal(decode(error['footprints']['original_runs'],self.scan.native_shape),original)
        self.assertEqual(error['suggestion_id'],'B_267:1');self.assertIsNone(error['training_label'])
        event_id=error['id'];self.w.undo();self.assertEqual(self.value('B_267'),'acceptable');self.assertNotIn(event_id,self.store.active_error_ids)
        self.assertIn(event_id,[e['id'] for e in self.store.review_events]);self.w.redo();self.assertEqual(self.value('B_267'),'unacceptable')
        self.assertIn(event_id,self.store.active_error_ids)
    def test_added_miss_single_and_both_share_one_human_footprint(self):
        self.draw();self.assertIsNone(self.value('B_267'));self.w.confirm_missed();uid=self.w.current_region().id
        self.assertEqual(self.value('B_267'),'unacceptable');self.assertIsNone(self.value('C_267'))
        self.w.attribution.setCurrentIndex(1);self.w.confirm_missed();self.w.confirm_missed()
        self.assertEqual(self.value('C_267'),'unacceptable')
        self.assertEqual(len([r for r in self.store.regions if not r.seed_ids]),1)
        self.assertEqual(len([e for e in self.store.review_events if e['action']=='missed lesion']),2)
        self.w.undo();self.assertIsNone(self.value('C_267'));self.assertEqual(self.value('B_267'),'unacceptable')
        self.w.redo();self.w.experiment.setCurrentText('C');self.w.seed.setCurrentText('269')
        self.assertTrue(any(r.id==uid for r in self.store.regions));self.assertIsNone(self.value('C_269'))
        again=ReviewStore(self.root/'regions',self.scan,'B_269',self.props)
        self.assertEqual(len([r for r in again.regions if not r.seed_ids]),1)
    def test_gross_correction_requires_explicit_action_and_targets_own_model(self):
        self.w.selected=0;self.w.diameter.setValue(3);self.w.stroke([(36,22)],'cnv_brush_erase')
        self.assertIsNone(self.value('B_267'));self.w.confirm_correction()
        self.assertEqual(self.value('B_267'),'unacceptable');self.assertIsNone(self.value('C_267'))
        self.assertTrue(any(e['action']=='gross outline correction' for e in self.store.review_events))
        self.w.undo();self.assertIsNone(self.value('B_267'));self.w.redo();self.assertEqual(self.value('B_267'),'unacceptable')
    def test_accepting_both_creates_no_duplicate_human_lesions(self):
        self.rate('B','acceptable');self.rate('C','acceptable');self.w.save_all()
        self.assertEqual(read(self.store.path)['regions'],[])
    def test_keep_original_outline_is_not_model_rating(self):
        self.w.selected=0;self.w.keep();self.assertEqual(self.store.ratings,{})
        again=ReviewStore(self.root/'regions',self.scan,'C_267',self.props);self.assertEqual(again.ratings,{})
    def test_finish_saves_unresolved_drafts_without_whole_field_labels(self):
        self.draw();self.w.finish_scan();d=read(self.store.path)
        self.assertTrue(d['scan_review']['rating_review_finished']);self.assertFalse(d['scan_review']['whole_field_checked'])
        self.assertFalse(d['training_export_enabled']);self.assertEqual(d['regions'][0]['reviewed_runs'],[])
    def test_erasing_entire_prediction_marks_only_its_model(self):
        self.w.selected=0;self.w.diameter.setValue(100);self.w.brush('erase');self.w.stroke([(40,25)],'cnv_brush_add')
        self.assertEqual(self.value('B_267'),'unacceptable');self.assertIsNone(self.value('C_267'))
        self.w.undo();self.assertIsNone(self.value('B_267'));self.w.redo();self.assertEqual(self.value('B_267'),'unacceptable')
    def test_linked_native_coordinates_and_nan_boundaries(self):
        self.w.navigate(16,40,False);self.assertEqual(self.w.row_spin.value(),16);self.assertEqual(self.w.row_slider.value(),16)
        self.w.mode.setCurrentIndex(1)
        for k in range(8):
            self.w.layer.setCurrentIndex(k);top,bottom=self.w.displayed_boundaries
            np.testing.assert_allclose((bottom-top)*1.12,self.scan.thickness[k,16],equal_nan=True)
        self.w.mode.setCurrentIndex(0);self.assertEqual(self.w.boundary_indices,());self.assertEqual((self.w.row,self.w.col),(16,40))
    def test_actual_mouse_paint_on_both_views(self):
        from PySide6.QtTest import QTest
        for canvas in (self.w.structural,self.w.second):
            self.w.add_cnv();self.w.diameter.setValue(3);self.w.fit_all()
            points=[canvas.mapFromScene(Q.QPointF(x,y)) for x,y in [(12,10),(30,10),(30,30),(12,30),(12,10)]]
            QTest.mousePress(canvas.viewport(),Qt.MouseButton.LeftButton,pos=points[0])
            for point in points[1:]:QTest.mouseMove(canvas.viewport(),point)
            QTest.mouseRelease(canvas.viewport(),Qt.MouseButton.LeftButton,pos=points[-1]);self.assertTrue(self.w.current_region().mask[20,20])
        self.w.grab().save(str(dest(REVIEW/'verification/isolated_gui.png')))
    def test_time_excludes_load_idle_pause_and_prefetch(self):
        self.w.isActiveWindow=lambda:True;self.w.review_clock_started=False;self.w.previous_tick=time.monotonic()-10;self.w.record_time()
        self.assertFalse(self.w.session_seconds)
        self.w.eventFilter(self.w,Q.QEvent(Q.QEvent.Type.MouseButtonPress));self.w.record_time();self.assertLess(sum(self.w.session_seconds.values()),.1)
        self.w.previous_tick=time.monotonic()-1;self.w.loading=True;self.w.record_time();self.assertLess(sum(self.w.session_seconds.values()),.1)
        self.w.loading=False;self.w.paused=True;self.w.previous_tick=time.monotonic()-1;self.w.record_time();self.assertLess(sum(self.w.session_seconds.values()),.1)
    def test_model_switch_reuses_sources_and_keeps_human_edits(self):
        self.draw();uid=self.w.current_region().id;self.w.save_all();images=self.scan.images
        for ex in 'BC':
            self.w.experiment.setCurrentText(ex)
            for seed in ('267','268','269'):self.w.seed.setCurrentText(seed)
        self.assertIs(self.scan.images,images);self.assertEqual(sum(r.id==uid for r in self.store.regions),1)
        self.assertEqual(self.w.cache.stats['loads'],0)
    def test_failed_save_does_not_switch_model(self):
        original=self.w.save_all;self.w.save_all=lambda:False
        try:self.w.experiment.setCurrentText('C');self.assertEqual(self.w.experiment.currentText(),'B');self.assertEqual(self.store.model,'B_267')
        finally:self.w.save_all=original
    def test_concurrent_save_cannot_overwrite_newer_work(self):
        stale=ReviewStore(self.root/'regions',self.scan,proposal_root=self.props);self.rate('B','acceptable');saved=sha(self.store.path)
        stale.regions[0].notes='Different window draft'
        with self.assertRaisesRegex(RuntimeError,'Another window changed'):stale.save()
        self.assertEqual(sha(self.store.path),saved)
    def test_undo_across_model_switch_keeps_seed_attribution(self):
        self.rate('B','acceptable');self.w.seed.setCurrentText('268');self.rate('C','unacceptable');self.w.experiment.setCurrentText('C')
        self.w.undo();self.assertIsNone(self.value('C_268'));self.assertEqual(self.value('B_267'),'acceptable')
        self.w.redo();self.assertEqual(self.value('C_268'),'unacceptable');self.assertEqual(self.store.model,'C_268')
    def test_filtered_prefetch_queue_only_next_two(self):
        self.w.visits=[dict(self.w.visits[0],scan_id=f'S{i}') for i in range(6)]
        self.w.scan_choice.addItems(['1','2','3','4','5']);self.w._completion={f'S{i}':True for i in range(6)}
        self.w.scan_choice.view().setRowHidden(1,True);self.w.scan_choice.view().setRowHidden(3,True)
        self.assertEqual(self.w.queue_after(0),['S2','S4']);self.assertEqual(self.w.queue_after(2),['S4','S5'])

    def test_async_navigation_reopens_ratings_without_prefetch_review_records(self):
        from concurrent.futures import Future
        scan2=copy.copy(self.scan);scan2.scan_id='TS999_SECOND'
        store2=ReviewStore(self.root/'regions',self.scan,proposal_root=self.props)
        original_review=self.w.review_directory
        self.w.visits.append(dict(self.w.visits[0],scan_id=scan2.scan_id));self.w.scan_choice.addItem('second')
        self.w._completion.update({self.scan.scan_id:True,scan2.scan_id:True})
        for key in ('B_267','B_268','B_269','C_267','C_268','C_269'):
            source=self.props/key/f'{self.scan.scan_id}.npz';target=self.props/key/f'{scan2.scan_id}.npz'
            target.write_bytes(source.read_bytes());self.hashes[str(target)]=sha(target)
        # Use the real poll/navigation path with an isolated native-input worker and proposal root.
        import viewer
        old_store=viewer.ReviewStore
        viewer.ReviewStore=lambda directory,scan,model:old_store(directory,scan,model,self.props)
        self.w.cache.close();self.w.cache=SampleCache(lambda sid,cancel:self.scan if sid==self.scan.scan_id else scan2)
        try:
            self.rate('B','acceptable');self.w.schedule_prefetch()
            self.w.cache.request(scan2.scan_id).result(3)
            self.assertFalse((self.root/'regions'/f'{scan2.scan_id}_regions.json').exists())
            self.assertNotIn(scan2.scan_id,[e.get('scan_id') for e in self.w.session_events])
            self.w.load_scan(1)
            self.w.pending_future.result(3);self.w.poll_load()
            self.assertEqual(self.w.scan.scan_id,scan2.scan_id);self.assertFalse(self.w.store.ratings)
            self.w.load_scan(0);self.w.pending_future.result(3);self.w.poll_load()
            self.assertEqual(self.w.store.ratings['B_267']['value'],'acceptable')
            self.assertTrue(self.w.rating_checks['B','acceptable'].isChecked())
            self.assertFalse(self.w.review_clock_started)
        finally:viewer.ReviewStore=old_store

    def test_history_zip_preserves_prior_saved_revision(self):
        import zipfile
        self.rate('B','acceptable');before=self.store.path.read_bytes();revision=self.store.revision
        self.rate('C','unacceptable')
        history=self.store.path.parent/'history'/f'{self.store.path.stem}_revisions.zip'
        with zipfile.ZipFile(history) as z:self.assertEqual(z.read(f'r{revision:06d}.json'),before)

class CacheTests(unittest.TestCase):
    def test_rolling_cache_reuses_cancels_and_bounds_memory(self):
        calls=[];gate=threading.Event();entered=threading.Event()
        def load(sid,cancel):
            calls.append(sid)
            if sid=='obsolete':
                entered.set();gate.wait(3)
                if cancel():raise CancelledError()
            return SimpleNamespace(scan_id=sid,image=np.zeros(100,dtype=np.uint8))
        cache=SampleCache(load,max_bytes=300)
        try:
            cache.plan(['A','obsolete','C']);a=cache.request('A').result(3)
            stale=cache.request('obsolete');entered.wait(3);queued=cache.request('C')
            cache.plan(['A','D','E']);gate.set()
            with self.assertRaises(CancelledError):stale.result(3)
            self.assertTrue(queued.cancelled());self.assertIs(cache.request('A').result(),a)
            cache.request('D').result(3);cache.request('E').result(3)
            self.assertEqual(set(cache.cache),{'A','D','E'});self.assertNotIn('C',calls)
            cache.plan(['D','E','F']);cache.request('F').result(3);self.assertEqual(set(cache.cache),{'D','E','F'})
            self.assertEqual(calls.count('A'),1);self.assertGreaterEqual(cache.stats['cancelled'],2)
        finally:gate.set();cache.close()
    def test_memory_limit_discards_oversize_without_failing_foreground(self):
        cache=SampleCache(lambda sid,cancel:SimpleNamespace(image=np.zeros(100)),max_bytes=1)
        try:
            cache.plan(['A']);self.assertIsNotNone(cache.request('A').result(3));self.assertEqual(len(cache.cache),0)
        finally:cache.close()

if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (Tests,CacheTests)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    write(REVIEW/'verification/tests.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),human_evaluation=False))
    raise SystemExit(not result.wasSuccessful())
