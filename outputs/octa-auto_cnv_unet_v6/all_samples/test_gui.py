"""Isolated GUI interactions; no study labels or model outputs are modified."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from common import *
import unittest,tempfile,time,copy
from types import SimpleNamespace
import v5_editor
from viewer import Window,W,Q,Qt,gui
from review_store import ReviewStore
from cnv_review_v1.data import decode_mask

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=W.QApplication.instance() or W.QApplication([]);gui.configure_app(cls.app)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=dest(HERE/'verification/fixtures/.keep').parent);self.root=Path(self.tmp.name)
        shape=(64,96);yy,xx=np.indices(shape);ends=np.broadcast_to(np.array([10,20,32,52,68,80,120,140])[None,:,None],(64,8,96)).astype(float).copy()
        values=np.stack([(ends[:,b]-ends[:,a])*1.12 for _,a,b in LAYERS]);values[:,:,7]=np.nan
        self.scan=SimpleNamespace(scan_id='TS999_ISOLATED',source_volume=self.root/'source_processedVolumes.mat',native_shape=shape,
            structural_enface=(xx+yy).astype(float),octa=(xx-yy).astype(float),octa_metadata={'channel':'frame_OCTAAvg'},octa_error=None,
            images=np.broadcast_to(np.arange(160)[None,:,None],(64,160,96)).astype(float),thickness=values,endpoints=ends,surface_names=tuple(SURFACES),px_um=1.12,
            shadow=np.zeros(shape,bool),manual_mask=np.zeros(shape,bool),metadata={'reference_review':{'sources':[]}},thickness_metadata={'revision':'isolated fixture'})
        self.props=self.root/'predictions'
        for i,key in enumerate(['B_267','B_268','B_269','C_267','C_268','C_269']):
            labels=np.zeros(shape,int);labels[20:30,35+i:45+i]=1
            save(self.props/key/f'{self.scan.scan_id}.npz',candidate_labels=labels,mask=labels>0,score=(labels>0).astype('float32'))
        self.hashes={str(p):sha(p) for p in self.props.rglob('*.npz')}
        self.store=ReviewStore(self.root/'regions',self.scan,proposal_root=self.props)
        self.old_selected=v5_editor.selected
        v5_editor.selected=lambda:[dict(scan_id=self.scan.scan_id,animal='TS999',eye='OD',session_date='test',day_label='test',scan_no=1,acq_time='test')]
        self.w=Window(autoload=False);self.w.session_directory=self.root/'sessions';self.w.loaded((self.scan,self.store));self.w.show();self.app.processEvents()
    def tearDown(self):
        self.w.close();self.w.deleteLater();self.app.processEvents();v5_editor.selected=self.old_selected
        self.assertEqual(self.hashes,{str(p):sha(p) for p in self.props.rglob('*.npz')});self.tmp.cleanup()
    def draw(self):
        self.w.add_cnv();self.w.diameter.setValue(3);self.w.stroke([(12,10),(30,10),(30,30),(12,30),(12,10)],'cnv_brush_add')
    def test_browsing_all_six_comparison_and_save_creates_no_labels(self):
        for ex in ('B','C'):
            for seed in ('267','268','269'):
                self.w.experiment.setCurrentText(ex);self.w.seed.setCurrentText(seed);self.w.compare.setCurrentIndex(3);self.w.save_all()
                self.assertFalse(self.store.dirty);self.assertFalse(self.store.path.exists())
                self.assertEqual(len(self.w.comparison_masks),5)
    def test_edit_keep_switch_save_reopen_preserves_human_work(self):
        self.w.selected=0;self.w.keep();self.w.save_all();uid=self.store.regions[0].id
        self.w.experiment.setCurrentText('C');self.assertTrue(any(r.id==uid and r.decision=='approved' for r in self.store.regions))
        self.draw();self.w.keep();self.w.save_all()
        reopened=ReviewStore(self.root/'regions',self.scan,'B_268',self.props)
        self.assertEqual(sum(r.decision=='approved' for r in reopened.regions),2)
        self.assertFalse(reopened.scan_review['whole_field_checked'])
        self.assertTrue(any(e.get('action_kind')=='acceptance' for r in reopened.regions for e in r.events))
    def test_draft_unsure_removal_and_whole_field_semantics(self):
        self.draw();self.w.save_all();self.assertEqual(self.w.current_region().record()['reviewed_runs'],[])
        self.w.finish_scan(confirmed=True);self.assertFalse(self.store.scan_review['whole_field_checked'])
        self.w.unsure();self.w.selected=0;self.w.remove();self.w.finish_scan(confirmed=True)
        self.assertTrue(self.store.scan_review['whole_field_checked']);self.assertFalse(self.store.scan_review['reviewed_absence'])
        data=read(self.store.path);self.assertEqual(len(data['scan_review']['uncertainty_region_ids']),1)
    def test_paint_erase_undo_redo_save_reopen(self):
        self.draw();self.assertTrue(self.w.current_region().mask[20,20])
        self.w.brush('erase');self.w.stroke([(20,20)],'cnv_brush_add');self.assertFalse(self.w.current_region().mask[20,20])
        self.w.undo();self.assertTrue(self.w.current_region().mask[20,20]);self.w.redo();self.assertFalse(self.w.current_region().mask[20,20])
        self.w.keep();expected=self.w.current_region().mask.copy();self.w.save_all();reopened=ReviewStore(self.root/'regions',self.scan,'C_269',self.props)
        self.assertTrue(any(r.decision=='approved' and np.array_equal(r.mask,expected) for r in reopened.regions))
    def test_linked_native_coordinates_and_nan_boundaries(self):
        self.w.navigate(16,40,False);self.assertEqual(self.w.row_spin.value(),16);self.assertEqual(self.w.row_slider.value(),16)
        self.w.mode.setCurrentIndex(1)
        for k in range(8):
            self.w.layer.setCurrentIndex(k);top,bottom=self.w.displayed_boundaries
            np.testing.assert_allclose((bottom-top)*1.12,self.scan.thickness[k,16],equal_nan=True)
        self.w.mode.setCurrentIndex(0);self.assertEqual(self.w.boundary_indices,());self.assertEqual(self.w.row,16);self.assertEqual(self.w.col,40)
    def test_pause_and_model_time_attribution(self):
        self.w.isActiveWindow=lambda:True;self.w.review_clock_started=True;self.w.last_activity=time.monotonic();self.w.previous_tick=time.monotonic()-1;self.w.record_time()
        initial=sum(self.w.session_seconds.values());self.assertGreater(initial,.9)
        self.w.pause.setChecked(True);self.w.previous_tick=time.monotonic()-1;self.w.record_time();self.assertAlmostEqual(sum(self.w.session_seconds.values()),initial,delta=.2)
        self.w.pause.setChecked(False);self.w.experiment.setCurrentText('C');self.w.previous_tick=time.monotonic()-1;self.w.record_time()
        self.assertTrue(any('C_267' in k for k in self.w.session_seconds));self.assertFalse(self.store.path.exists())
    def test_opening_alone_does_not_claim_human_review_time(self):
        self.w.review_clock_started=False;self.w.isActiveWindow=lambda:True;self.w.previous_tick=time.monotonic()-1;self.w.record_time()
        self.assertFalse(self.w.session_seconds)
    def test_first_interaction_does_not_credit_prior_idle_time(self):
        self.w.review_clock_started=False;self.w.isActiveWindow=lambda:True;self.w.previous_tick=time.monotonic()-10
        self.w.eventFilter(self.w,Q.QEvent(Q.QEvent.Type.MouseButtonPress));self.w.record_time()
        self.assertLess(sum(self.w.session_seconds.values()),.1)
    def test_no_suggestions_require_explicit_whole_field_finish(self):
        scan=copy.copy(self.scan);scan.scan_id='TS999_EMPTY_ISOLATED'
        for key in ('B_267','B_268','B_269','C_267','C_268','C_269'):
            zeros=np.zeros(scan.native_shape,bool)
            save(self.props/key/f'{scan.scan_id}.npz',candidate_labels=zeros.astype(int),mask=zeros,score=zeros.astype('float32'))
        self.hashes={str(p):sha(p) for p in self.props.rglob('*.npz')}
        store=ReviewStore(self.root/'regions',scan,proposal_root=self.props);self.w.loaded((scan,store));self.w.save_all()
        self.assertFalse(store.path.exists());self.assertFalse(store.scan_review['whole_field_checked'])
        self.w.finish_scan(confirmed=True);data=read(store.path)
        self.assertTrue(data['scan_review']['reviewed_absence']);self.assertTrue(data['scan_review']['whole_field_checked']);self.assertEqual(data['regions'],[])
    def test_later_edit_is_correction_not_second_addition(self):
        self.draw();self.w.keep();self.w.stroke([(32,20)],'cnv_brush_add');self.w.keep()
        actions=[e.get('action_kind') for e in self.w.current_region().events if e['action']=='observed review action']
        self.assertEqual(actions,['addition confirmed','outline correction confirmed'])
    def test_erasing_entire_suggestion_records_removal(self):
        self.w.selected=0;self.w.diameter.setValue(100);self.w.brush('erase');self.w.stroke([(40,25)],'cnv_brush_add')
        self.assertEqual(self.w.current_region().decision,'rejected')
        self.assertTrue(any(e.get('action_kind')=='removal' for e in self.w.current_region().events))
    def test_actual_mouse_paint_on_both_views(self):
        from PySide6.QtTest import QTest
        for canvas in (self.w.structural,self.w.second):
            self.w.add_cnv();self.w.diameter.setValue(3);self.w.fit_all()
            points=[canvas.mapFromScene(Q.QPointF(x,y)) for x,y in [(12,10),(30,10),(30,30),(12,30),(12,10)]]
            QTest.mousePress(canvas.viewport(),Qt.MouseButton.LeftButton,pos=points[0])
            for point in points[1:]:QTest.mouseMove(canvas.viewport(),point)
            QTest.mouseRelease(canvas.viewport(),Qt.MouseButton.LeftButton,pos=points[-1]);self.assertTrue(self.w.current_region().mask[20,20])
        self.w.grab().save(str(dest(HERE/'verification/gui_isolated.png')))

    def test_previous_next_respect_queue_filter(self):
        self.w.visits=[{}, {}, {}, {}, {}]
        self.w.scan_choice.addItems(['second','third','fourth','fifth'])
        self.w.scan_choice.view().setRowHidden(1,True);self.w.scan_choice.view().setRowHidden(3,True)
        loaded=[];original=self.w.load_scan;self.w.load_scan=loaded.append
        self.w.index=0;self.w.step_scan(1);self.assertEqual(loaded,[2])
        self.w.index=4;self.w.step_scan(-1);self.assertEqual(loaded,[2,2])
        self.w.visits=[dict(scan_id=self.scan.scan_id,animal='TS999',eye='OD',session_date='test',day_label='test',scan_no=1,acq_time='test')]
        self.w.index=0;self.w.load_scan=original

    def test_concurrent_review_cannot_overwrite_newer_human_work(self):
        stale=ReviewStore(self.root/'regions',self.scan,proposal_root=self.props)
        self.w.selected=0;self.w.keep();self.w.save_all();saved=sha(self.store.path)
        stale.regions[0].notes='Different window draft'
        with self.assertRaisesRegex(RuntimeError,'Another window changed'):stale.save()
        self.assertEqual(sha(self.store.path),saved);self.assertTrue(stale.dirty)

    def test_failed_save_keeps_model_selector_aligned_with_display(self):
        original=self.w.save_all;self.w.save_all=lambda:False
        try:
            self.w.experiment.setCurrentText('C')
            self.assertEqual(self.w.experiment.currentText(),'B');self.assertEqual(self.w.model_key,'B_267');self.assertEqual(self.store.model,'B_267')
        finally:self.w.save_all=original

    def test_removing_confirmed_added_lesion_is_recorded(self):
        self.draw();self.w.keep();region=self.w.current_region();self.w.remove()
        self.assertTrue(any(e.get('action_kind')=='confirmed lesion removal' for e in region.events))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);result=unittest.TextTestRunner(verbosity=2).run(suite)
    write(HERE/'verification/gui_tests.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),scope='isolated GUI fixtures; no real human review'))
    raise SystemExit(not result.wasSuccessful())
