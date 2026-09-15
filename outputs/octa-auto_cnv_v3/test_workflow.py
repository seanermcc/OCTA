import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from common import *
import unittest,tempfile,copy
from unittest.mock import patch
from types import SimpleNamespace
from scipy import ndimage as ndi
from algorithm import geometry,detect,quantify,VARIANTS
from review_store import ReviewStore,ReviewRegion
from cnv_review_v1.data import decode_mask,encode_mask,SurfaceIndex
from eight_surface.config import SURFACE_NAMES


def fixture(shape=(512,512)):
    y,x=np.indices(shape); rows=np.broadcast_to(np.arange(8)[None,:,None]*25.+10,(shape[0],8,shape[1])).copy()
    a=dict(automatic_thickness_um=(220+.02*x+.01*y).astype('float32'),enface=(20+.001*x).astype('float32'),surface_names=np.array(SURFACE_NAMES))
    for k in ('vessel','shadow','low_signal','automatic_trace_loss'):a[k]=np.zeros(shape,bool)
    a.update(geometry(rows,0,300));return a,rows

class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from viewer import W,gui
        cls.app=W.QApplication.instance() or W.QApplication([]);gui.configure_app(cls.app)

    def setUp(self):
        from viewer import Window
        from cnv_review_v1.test_review import fake_scan
        self.temp=tempfile.TemporaryDirectory(dir=destination(HERE/'verification/fixtures'))
        self.root=Path(self.temp.name);scan=fake_scan(self.root);shape=scan.native_shape
        a,rows=fixture(shape);e,rec=detect(a);a.update(e)
        a.update(viewer_thickness_um=a['automatic_thickness_um'].copy(),manual_cnv=np.zeros(shape,bool),deficit_sensitivity_span=np.zeros(shape),automatic_surfaces_crop_px=rows)
        base=dict(deficit_percent=np.zeros(shape),background_um=np.ones(shape)*220,background_supported=np.ones(shape,bool),background_regions=np.ones(shape,bool),footprint=np.zeros(shape,bool))
        for name in [*VARIANTS,'assisted']:
            for k,v in base.items():a[name+'__'+k]=v.copy()
        a['core'][3:8,12:25]=True;a['candidate_labels'][3:8,12:25]=1
        scan.maps=a;scan.metadata=dict(candidates=[]);self.scan=scan
        seed=self.root/'seed.npz';np.savez(seed,candidate_labels=a['candidate_labels'])
        self.seed=seed;self.store=ReviewStore(self.root/'review/regions',scan,a['core'],str(seed))
        config=dict(output=str(self.root/'review'),segmentations=str(self.root),manual_sources=[],auto_sources=[],proposals=str(self.root),enface_labels=str(self.root))
        self.window=Window(config,paths=[scan.segmentation_path],autoload=False);self.window.pending_index=0
        idx=SurfaceIndex([]);idx.refresh(scan);blank=np.zeros(shape,bool)
        self.window._loaded((scan,scan.surfaces,scan.confidence,dict(name='fixture',path=''),(blank,blank,blank,blank,dict(status='fixture',path=''),''),idx,self.store))
        self.window.show();self.app.processEvents()

    def tearDown(self):
        self.window.store.saved_signature=self.window.store.signature()
        self.window.close();self.window.deleteLater();self.app.processEvents();self.temp.cleanup()

    def test_open_navigate_click_no_writes(self):
        from PySide6.QtTest import QTest
        from viewer import gui,Qt
        self.window.evidence.fit();point=self.window.evidence.mapFromScene(gui.QtCore.QPointF(20.5,6.5))
        QTest.mouseClick(self.window.evidence.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual((self.window.row,self.window.col),(6,20));self.assertEqual(int(self.window.editor.pack.bscan_index[0]),6)
        self.window.save_all();self.assertFalse(self.store.path.exists())

    def test_paint_erase_core_separation_undo_redo(self):
        w=self.window;r=w.selected_region();seed=r.core.copy();contour=self.scan.maps['default__deficit_percent'].copy()
        w.diameter.setValue(4);w.brush('paint');w._outline_drawn([(26,6),(29,6)],'cnv_brush_add')
        self.assertTrue(r.mask[6,28]);self.assertTrue(np.array_equal(r.core,seed));self.assertTrue(r.touched[6,28]);self.assertEqual(r.record()['reviewed_runs'],[])
        w.undo_region();self.assertFalse(w.selected_region().mask[6,28]);w.redo_region();self.assertTrue(w.selected_region().mask[6,28])
        w.brush('erase');w._outline_drawn([(28,6)],'cnv_brush_add');self.assertFalse(w.selected_region().mask[6,28])
        w.target.setCurrentIndex(1);w.brush('paint');before=w.selected_region().mask.copy();w._outline_drawn([(30,6)],'cnv_brush_add')
        self.assertTrue(np.array_equal(before,w.selected_region().mask));self.assertTrue(w.selected_region().core[6,30]);self.assertTrue(np.array_equal(contour,self.scan.maps['default__deficit_percent']))

    def test_add_redraw_split_merge_and_reject(self):
        w=self.window;w.outline_mode(False);w._outline_drawn([(2,2),(10,2),(10,9),(2,9)],'cnv_outline_add')
        self.assertEqual(len(w.store.regions),2);new_id=w.selected_region().id
        w.outline_mode(True);w._outline_drawn([(2,2),(10,2),(10,8),(2,8)],'cnv_outline_add');self.assertEqual(w.selected_region().id,new_id)
        w.diameter.setValue(2);w.brush('split');w._outline_drawn([(6,0),(6,11)],'cnv_brush_add');self.assertEqual(len(w.store.regions),3)
        w.merge(2);self.assertEqual(len(w.store.regions),2)
        w.remove_region();self.assertEqual(w.selected_region().decision,'rejected');self.assertEqual(len(w.store.regions),2)
        w.undo_region();self.assertEqual(w.selected_region().decision,'unreviewed');w.redo_region();self.assertEqual(w.selected_region().decision,'rejected')

    def test_roundtrip_explicit_approval_revision_conflict(self):
        w=self.window;w.diameter.setValue(3);w.brush('paint');w._outline_drawn([(28,6)],'cnv_brush_add');self.assertTrue(w.save_all())
        re=ReviewStore(self.store.path.parent,self.scan,self.scan.maps['core'],str(self.seed));self.assertEqual(re.regions[0].record()['reviewed_runs'],[])
        self.assertTrue(re.regions[0].touched.any());w.approve();self.assertTrue(w.save_all());self.assertTrue(list((self.store.path.parent/'history').glob('*.json')))
        re.regions[0].notes='concurrent edit'
        with self.assertRaises(RuntimeError):re.save({},[],{})
        latest=ReviewStore(self.store.path.parent,self.scan,self.scan.maps['core'],str(self.seed));self.assertTrue(latest.regions[0].complete);self.assertTrue(latest.regions[0].record()['reviewed_runs'])
        np.savez(self.seed,candidate_labels=np.zeros(self.scan.native_shape,int))
        with self.assertRaises(RuntimeError):ReviewStore(self.store.path.parent,self.scan,self.scan.maps['core'],str(self.seed))

    def test_category_never_promotes_untouched_pixels(self):
        self.window.category.setCurrentText('Full Lesion');self.window.save_all()
        rec=read(self.store.path)['regions'][0];self.assertFalse(rec['classification_complete']);self.assertEqual(rec['reviewed_runs'],[]);self.assertTrue(rec['unreviewed_runs'])
        self.assertEqual(rec['category'],'Unclassified')

    def test_manual_comparison_navigation_copy_and_hidden_auto(self):
        w=self.window;mask=np.zeros(self.scan.native_shape,bool);mask[2:6,2:8]=True
        self.scan.maps['manual_cnv']=mask;self.scan.metadata['reference_review']={'sources':[{'path':'original-manual-fixture','sha256':'a'*64}]}
        w.manual_components=[mask];w.manual_choice.clear();w.manual_choice.addItems(['Choose','Manual 1']);w.manual_choice.setCurrentIndex(1)
        before=w.store.signature();w.navigate_manual(1)
        self.assertEqual(w.store.signature(),before);self.assertEqual(w.selected,-1)
        w.auto_check.setChecked(False);w._enface_clicked(6,20)
        self.assertEqual(w.selected,-1);self.assertTrue(w.region_list.item(0).isHidden())
        w.copy_manual();r=w.selected_region()
        self.assertTrue(np.array_equal(r.mask,mask));self.assertFalse(r.core.any());self.assertEqual(r.seed_ids,[])
        self.assertEqual(r.decision,'unreviewed');self.assertFalse(r.record()['reviewed_runs'])
        self.assertEqual(r.events[0]['sources'][0]['path'],'original-manual-fixture')
        self.assertTrue(np.array_equal(self.scan.maps['manual_cnv'],mask))

    def test_new_manual_enters_reference_but_seeded_approval_is_assisted(self):
        import pilot
        w=self.window;w.outline_mode(False)
        w._outline_drawn([(2,2),(8,2),(8,8),(2,8)],'cnv_outline_add')
        manual=w.selected_region().mask.copy();w.approve()
        w.select_region(0);w.approve();self.assertTrue(w.save_all())
        with patch.object(pilot,'HERE',self.root):
            mask,normal,audit=pilot.manual_reference(self.scan.scan_id,str(self.scan.source_volume),self.scan.native_shape)
        self.assertTrue(np.array_equal(mask,manual));self.assertTrue(audit['reviewed_cnv'])
        self.assertEqual(len(audit['assisted_review_regions']),1)

    def test_complete_normal_review_and_recompute_is_assisted(self):
        import viewer,engine
        w=self.window;w.category.setCurrentText('Normal');w.complete_review()
        self.assertTrue(w.selected_region().complete)
        folder=self.root/'scans'/self.scan.scan_id;folder.mkdir(parents=True)
        np.savez(folder/'maps.npz',fixture=np.array(1))
        t=self.scan.maps['viewer_thickness_um']
        fresh=SimpleNamespace(maps=[(np.stack([t]*8),None)],metadata=lambda:dict(correction_fingerprints={},experimental=True))
        def compute(a,c,**kwargs):
            self.assertFalse(c['background_core'].any())
            self.assertTrue(np.array_equal(c['core'],a['core']))
            self.assertFalse(kwargs['extra_excluded'].any())
            m={key:a['default__'+key].copy() for key in ('deficit_percent','background_um','background_supported','background_regions','footprint')}
            m['core']=c['core'].copy()
            return m,dict(sufficient=True)
        with patch.object(viewer,'HERE',self.root),patch.object(engine,'Volume',return_value=fresh),patch.object(viewer,'quantify',side_effect=compute):
            w._recompute()
            out=self.root/'assisted_review'/self.scan.scan_id
            p=read(out/'provenance.json')
            self.assertIn('human-assisted',p['kind']);self.assertEqual(p['review_sha256'],sha(self.store.path))
            self.assertTrue(np.array_equal(npz(out/'maps.npz')['core'],self.scan.maps['core']))
        w.brush('paint');w._outline_drawn([(28,6)],'cnv_brush_add')
        self.assertIsNone(w.user_maps)

    def test_core_split_preserves_structural_footprint(self):
        w=self.window;before=w.selected_region().mask.copy()
        w.target.setCurrentIndex(1);w.diameter.setValue(2);w.brush('split')
        w._outline_drawn([(18,0),(18,11)],'cnv_brush_add')
        self.assertTrue(np.array_equal(before,w.selected_region().mask))
        self.assertEqual(len(w.store.regions),1)
        self.assertGreater(ndi.label(w.selected_region().core)[1],1)



class ShapeTests(unittest.TestCase):
    def rounded(self,centers=((256,256),),radius=22):
        a,r=fixture();y,x=np.indices(a['enface'].shape)
        for cy,cx in centers:
            focus=(y-cy)**2+(x-cx)**2<=radius**2
            a['enface'][focus]-=5;r[:,0,:][focus]=60
        a.update(geometry(r,0,300));return a

    def test_round_focus_and_no_background(self):
        a=self.rounded();a['automatic_thickness_um'][:]=np.nan
        c,rec=detect(a);self.assertEqual(len(rec),1);self.assertTrue(c['core'][256,256])
        for p in VARIANTS.values():
            m,d=quantify(a,c,p);self.assertTrue(np.array_equal(c['core'],m['core']));self.assertTrue(np.isnan(m['deficit_percent']).all())

    def test_vessel_trunk_and_elongated_failure_not_cnv(self):
        a,r=fixture();a['vessel'][50:460,250:260]=True;a['enface'][50:460,250:260]-=5;r[50:460,0,250:260]=60;a.update(geometry(r,0,300))
        c,rec=detect(a);self.assertEqual(len(rec),0);self.assertTrue(c['vessel_trunks'][200,255])
        self.assertTrue(a['geometry_any'][200,255])

    def test_count_guard_preserves_extra_evidence(self):
        a=self.rounded(((100,100),(100,250),(100,400),(330,130),(330,360)),18)
        c,rec=detect(a);self.assertEqual(len(rec),4);self.assertTrue(c['count_warning'])
        extras=json.loads(str(c['screened_records_json']));self.assertTrue(any('count sanity' in ' '.join(r['screen_reasons']) for r in extras))

    def test_geometry_alone_and_empty_scan_are_not_cnv(self):
        a,r=fixture();r[180:230,0,180:230]=60;a.update(geometry(r,0,300))
        c,rec=detect(a);self.assertFalse(c['core'].any());self.assertTrue(a['geometry_any'].any())
        clean,_=fixture();self.assertEqual(len(detect(clean)[1]),0)

    def test_edge_focus_remains_diagnostic(self):
        a=self.rounded(((14,256),));c,rec=detect(a)
        self.assertEqual(len(rec),0);self.assertTrue((c['screened_labels']>0).any())

if __name__=='__main__':
    destination(HERE/'verification/fixtures/.keep').parent.mkdir(parents=True,exist_ok=True)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(__import__('__main__')))
    write(HERE/'verification/tests.json',dict(tests=result.testsRun,failures=[str(v) for v in result.failures],errors=[str(v) for v in result.errors],passed=result.wasSuccessful()))
    raise SystemExit(0 if result.wasSuccessful() else 1)
