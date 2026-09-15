"""Behavioral tests use disposable fixtures, never study annotations."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from common import *
import unittest,tempfile,copy
from types import SimpleNamespace
from viewer import Window,W,Q,G,Qt,gui,LAYERS
from review_store import ReviewStore
from cnv_review_v1.data import decode_mask
from engine import measure

def fixture(root):
    shape=(64,96);y,x=np.indices(shape)
    ends=np.broadcast_to(np.array([10,20,32,52,68,80,120,140])[None,:,None],(64,8,96)).astype(float).copy()
    ends[16,2,40]=np.nan
    shadow=np.zeros(shape,bool);shadow[:,7]=True
    values=measure(ends,np.ones_like(ends),shadow)[0]
    core=np.zeros(shape,bool);core[20:28,35:45]=True
    scan=SimpleNamespace(scan_id='TS999_TEST',source_volume=root/'source_processedVolumes.mat',native_shape=shape,
        structural_enface=(x+y).astype(float),images=np.broadcast_to(np.arange(160)[None,:,None],(64,160,96)).astype(float),
        thickness=values,endpoints=ends,surface_names=('ILM','RNFL_GCL','GCL_IPL','IPL_INL','INL_OPL','OPL_ONL','PR_RPE','RPE'),
        px_um=1.12,shadow=shadow,manual_mask=np.zeros(shape,bool),maps={'core':core},metadata={'reference_review':{'sources':[]}},
        thickness_metadata={'revision':'fixture','correction_fingerprints':{}},octa=(x-y).astype(float),octa_metadata={'channel':'frame_OCTAAvg'},octa_error=None)
    seed=root/'seed.npz';np.savez(seed,candidate_labels=core.astype(int))
    store=ReviewStore(root/'review/regions',scan,core,str(seed),previous_directory=root/'empty')
    return scan,store,seed

class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=W.QApplication.instance() or W.QApplication([]);gui.configure_app(cls.app)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=destination(HERE/'verification/fixtures/.keep').parent)
        self.root=Path(self.temp.name);self.scan,self.store,self.seed=fixture(self.root)
        self.w=Window(manual=True,autoload=False);self.w.mode.setCurrentIndex(1);self.w.loaded((self.scan,self.store));self.w.show();self.app.processEvents();self.w.fit_all()
    def tearDown(self):
        self.store.saved_signature=self.store.signature();self.w.close();self.w.deleteLater();self.app.processEvents();self.temp.cleanup()
    def draw(self):
        self.w.add_cnv();self.w.diameter.setValue(3)
        self.w.stroke([(12,10),(30,10),(30,30),(12,30),(12,10)],'cnv_brush_add')

    def test_two_panels_and_no_boundary_editor(self):
        self.assertEqual(self.w.top.count(),3) # two image panels and the CNV list
        self.assertFalse(hasattr(self.w,'editor'));self.assertFalse(hasattr(self.w,'target'))
        self.assertEqual(self.w.split.count(),2)

    def test_each_layer_uses_exact_map_endpoints_only(self):
        self.w.navigate(16,40,False)
        for k,(_,a,b) in enumerate(LAYERS):
            self.w.layer.setCurrentIndex(k)
            self.assertEqual(self.w.boundary_indices,(a,b));self.assertEqual(len(self.w.boundary_items),2)
            top,bottom=self.w.displayed_boundaries
            self.assertTrue(np.array_equal((bottom-top)*1.12,self.scan.thickness[k,16],equal_nan=True))
            self.assertTrue(np.isnan(top[7]) and np.isnan(bottom[7]))
        self.w.layer.setCurrentIndex(2)
        self.assertTrue(all(np.isnan(v[40]) for v in self.w.displayed_boundaries))

    def test_octa_switch_removes_all_layer_lines_and_does_not_edit(self):
        sig=self.store.signature();self.w.mode.setCurrentIndex(0)
        self.assertEqual(self.w.boundary_indices,());self.assertEqual(len(self.w.boundary_items),0)
        self.assertFalse(self.w.layer.isEnabled());self.assertIn('OCTA',self.w.second_group.title())
        self.w.mode.setCurrentIndex(1);self.assertTrue(self.w.layer.isEnabled());self.assertEqual(sig,self.store.signature())

    def test_closed_paint_fill_save_and_reload(self):
        self.draw();r=self.w.current_region();self.assertTrue(r.mask[20,20]);self.assertTrue(r.touched[20,20]);self.assertFalse(r.core.any())
        self.assertEqual(r.record()['reviewed_runs'],[]);self.w.keep();self.w.save_all()
        re=ReviewStore(self.store.path.parent,self.scan,self.scan.maps['core'],str(self.seed),previous_directory=self.root/'empty')
        self.assertTrue(decode_mask(re.regions[-1].record()['reviewed_runs'],self.scan.native_shape)[20,20]);self.assertFalse(re.scan_review['whole_field_checked'])

    def test_actual_mouse_circle_on_both_panels(self):
        from PySide6.QtTest import QTest
        for canvas in (self.w.structural,self.w.second):
            self.w.add_cnv();self.w.diameter.setValue(3);self.w.fit_all()
            points=[canvas.mapFromScene(Q.QPointF(x,y)) for x,y in [(12,10),(30,10),(30,30),(12,30),(12,10)]]
            QTest.mousePress(canvas.viewport(),Qt.MouseButton.LeftButton,pos=points[0])
            for point in points[1:]:QTest.mouseMove(canvas.viewport(),point)
            QTest.mouseRelease(canvas.viewport(),Qt.MouseButton.LeftButton,pos=points[-1])
            self.assertTrue(self.w.current_region().mask[20,20])

    def test_open_stroke_erase_and_undo_redo(self):
        self.w.add_cnv();self.w.diameter.setValue(3);self.w.stroke([(12,10),(30,10),(30,30)],'cnv_brush_add')
        self.assertFalse(self.w.current_region().mask[20,20])
        self.w.stroke([(30,30),(12,30),(12,10)],'cnv_brush_add');self.assertTrue(self.w.current_region().mask[20,20])
        self.w.brush('erase');self.w.stroke([(20,20)],'cnv_brush_add');self.assertFalse(self.w.current_region().mask[20,20])
        self.w.undo();self.assertTrue(self.w.current_region().mask[20,20]);self.w.redo();self.assertFalse(self.w.current_region().mask[20,20])

    def test_add_creates_separate_regions_and_remove_retains_history(self):
        self.draw();first=self.w.current_region().id;self.draw();self.assertNotEqual(first,self.w.current_region().id)
        count=len(self.store.regions);self.w.remove();self.assertEqual(len(self.store.regions),count);self.assertEqual(self.store.regions[-1].decision,'rejected')
        self.w.undo();self.assertEqual(self.w.current_region().decision,'unreviewed')

    def test_save_partial_never_marks_unknown_field_negative(self):
        self.draw();self.w.keep();self.w.save_all();record=read(self.store.path)
        self.assertFalse(record['scan_review']['whole_field_checked']);self.assertEqual(record['scan_review']['status'],'in_progress')

    def test_finished_positive_review_and_edit_invalidates_completion(self):
        self.draw();self.w.keep();self.w.finish_scan(confirmed=True)
        self.assertTrue(self.store.scan_review['whole_field_checked']);self.assertFalse(self.store.scan_review['reviewed_absence'])
        self.w.brush('paint');self.w.stroke([(32,20)],'cnv_brush_add');self.assertFalse(self.store.scan_review['whole_field_checked'])
        self.w.undo();self.assertTrue(self.store.scan_review['whole_field_checked'])

    def test_finished_negative_is_explicit_and_drafts_block(self):
        self.assertFalse(self.store.scan_review['whole_field_checked']);self.w.finish_scan(confirmed=True)
        self.assertTrue(self.store.scan_review['reviewed_absence'])
        self.draw();self.w.finish_scan(confirmed=True);self.assertFalse(self.store.scan_review['whole_field_checked'])

    def test_unsure_region_is_not_cnv_or_reviewed_absence(self):
        self.draw();self.w.unsure();self.w.finish_scan(confirmed=True)
        self.assertEqual(self.store.scan_review['confirmed_cnv_count'],0);self.assertFalse(self.store.scan_review['reviewed_absence'])
        self.assertEqual(self.store.scan_review['uncertainty_region_ids'],[self.w.current_region().id])

    def test_suggestions_exposure_persists_without_approval(self):
        self.w.auto_check.setChecked(True);self.w.auto_check.setChecked(False)
        self.assertTrue(self.store.review_context['automatic_proposals_seen']);self.assertFalse(self.store.dirty)
        self.draw();self.w.save_all();rec=read(self.store.path)
        self.assertTrue(rec['review_context']['automatic_proposals_seen']);self.assertEqual(rec['regions'][0]['reviewed_runs'],[])

    def test_saved_manual_copy_and_remove_do_not_change_original(self):
        mask=np.zeros(self.scan.native_shape,bool);mask[4:10,5:12]=True;self.w.manual_components=[mask.copy()];self.w.refresh_regions()
        self.w.region_list.setCurrentRow(0);self.assertEqual(self.w.reference,0)
        self.w.remove();self.assertEqual(len(self.w.untouched_manual()),0);self.assertTrue(np.array_equal(mask,self.w.manual_components[0]))
        self.w.undo();self.assertEqual(len(self.w.untouched_manual()),1)

    def test_prior_review_continues_in_new_folder_only(self):
        self.draw();self.w.keep();self.w.save_all();digest=sha(self.store.path)
        re=ReviewStore(self.root/'vnext/regions',self.scan,self.scan.maps['core'],str(self.seed),previous_directory=self.store.path.parent)
        self.assertEqual(re.regions[-1].decision,'approved');self.assertFalse(re.dirty)
        re.regions[-1].notes='new revision';re.save();self.assertEqual(sha(self.store.path),digest);self.assertTrue(re.path.exists())

    def test_conflicting_save_keeps_original_revision(self):
        self.draw();self.w.save_all()
        other=ReviewStore(self.store.path.parent,self.scan,self.scan.maps['core'],str(self.seed),previous_directory=self.root/'empty')
        self.w.keep();self.w.save_all();other.regions[-1].notes='conflict'
        with self.assertRaises(RuntimeError):other.save()

    def test_read_only_bscan_mouse_and_navigation_write_nothing(self):
        from PySide6.QtTest import QTest
        sig=self.store.signature();endpoints=self.scan.endpoints.copy()
        for row,col in [(0,0),(32,48),(63,95)]:self.w.navigate(row,col,False);self.assertEqual((self.w.row,self.w.col),(row,col))
        QTest.mouseDClick(self.w.bscan.viewport(),Qt.MouseButton.LeftButton,pos=self.w.bscan.mapFromScene(Q.QPointF(40,40)))
        self.assertTrue(np.array_equal(endpoints,self.scan.endpoints,equal_nan=True));self.assertEqual(sig,self.store.signature())
        self.w.save_all();self.assertFalse(self.store.path.exists())

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(__import__('__main__')))
    write(HERE/'verification/tests.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=[str(x) for x in result.failures],errors=[str(x) for x in result.errors]))
    raise SystemExit(0 if result.wasSuccessful() else 1)
