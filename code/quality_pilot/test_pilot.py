import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
import numpy as np
from .metrics import roughness,diagnostic_thickness,onh_distance,select_strips
from .review_store import QualityStore,strip_rating
from .evaluate_reviews import auc

class Metrics(unittest.TestCase):
    def test_gaps_never_bridge(self):
        a=np.array([0,0,np.nan,100,100.]);j,s=roughness(a,1)
        np.testing.assert_equal(j,[np.nan,0,np.nan,np.nan,0]);np.testing.assert_equal(s,[0,0,np.nan,0,0])
        np.testing.assert_equal(a,[0,0,np.nan,100,100])

    def test_spike_step_and_broad_deformation(self):
        a=np.zeros(31);a[15]=30/1.12;j,s=roughness(a)
        self.assertAlmostEqual(float(s[15]),30,places=4);self.assertEqual(np.sum(j>20),2)
        broad=40*np.exp(-((np.arange(101)-50)/20)**2);_,s=roughness(broad,1)
        self.assertLess(float(np.max(s)),2)
        j,s=roughness(np.r_[np.zeros(12),np.ones(12)*30],1)
        self.assertEqual(np.sum(j>20),1);self.assertEqual(np.sum(s>20),0)

    def test_shadow_crossing_coverage(self):
        rows=np.broadcast_to(np.arange(8)[None,:,None]*10+50,(2,8,12)).astype(float).copy()
        rows[0,2,4]=rows[0,1,4]-1;shadow=np.zeros((2,12),bool);shadow[1,3]=True
        t,failed,invalid,cross=diagnostic_thickness(rows,shadow)
        self.assertTrue(np.isnan(t[1,:,3]).all());self.assertTrue(np.isnan(t[0,7,4]))
        self.assertTrue(cross[0,1,4]);self.assertTrue(invalid[0,1:3,4].all())

    def test_onh_mask_proxy_and_unknown(self):
        g={k:np.zeros((10,10),bool) for k in ('shadow','onh','onh_edge')};g['onh'][4,4]=True;g['onh_edge'][0,5]=True
        d,label=onh_distance('TS165_TEST',g);self.assertEqual(d[4,4],0);self.assertAlmostEqual(float(d[4,5]),1460/512,places=5)
        d,label=onh_distance('TS283_TEST',g);self.assertIn('partial-edge',label);self.assertEqual(d[0,5],0)
        d,label=onh_distance('TS336_TEST',g);self.assertTrue(np.isnan(d).all())

    def test_queue_sampling_and_separation(self):
        e=np.random.default_rng(1).random((80,8,256));s=e*30
        q=select_strips('test',e,s,7)
        self.assertEqual([p['role'] for p in q],['random','random','targeted','targeted'])
        self.assertEqual([p['driver'] for p in q[2:]],['entropy','spike'])
        for i,a in enumerate(q):
            for b in q[i+1:]:self.assertTrue(abs(a['bscan']-b['bscan'])>=24 or abs(a['lo']-b['lo'])>=128)

    def test_auroc_requires_both_classes(self):
        self.assertIsNone(auc([1,2],[False,False]));self.assertEqual(auc([1,2],[False,True]),1)

class Store(unittest.TestCase):
    def test_rating_comparison_separates_free_browsing(self):
        import json,csv
        from unittest.mock import patch
        from . import evaluate_reviews as ev
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'reports').mkdir();sid='TS999';model=['test']
            metrics=dict(scan_id=sid,bscan=0,lo=0,hi=10,entropy_median=.2,entropy_p95=.3,
                 jump_max_um=0,jump_p95_um=0,jump_gt20_fraction=0,spike_max_um=0,spike_p95_um=0,
                 spike_gt20_fraction=0,signal_cnr_median=10,solid_coverage=1,dashed_coverage=0)
            (root/'review_queue.json').write_text(json.dumps(dict(model_identity=model,examples=[dict(scan_id=sid,bscan=0,lo=0,hi=10,id='1',role='random',driver='random',metrics=metrics)])))
            (root/'reports/strips.csv').write_text('entropy_p95\n0.3\n')
            s=QualityStore(root/'reviewer/quality_reviews',sid,0,40,model);s.rate(0,10,'Good');s.rate(20,30,'Bad')
            base=root/'volumes'/sid;base.mkdir(parents=True);shape=(1,8,40)
            np.savez(base/'measurements.npz',entropy=np.ones(shape)*.3,reported_positions=np.ones(shape),uncertain_estimates=np.full(shape,np.nan))
            np.savez(base/'diagnostics.npz',solid_jump_um=np.zeros(shape),solid_spike_um=np.zeros(shape),dashed_jump_um=np.full(shape,np.nan),dashed_spike_um=np.full(shape,np.nan))
            np.savez(base/'geometry.npz',local_cnr=np.ones((1,40))*10)
            with patch.object(ev,'OUT',root):ev.run()
            with (root/'reports/rating_pairs.csv').open() as f:rows=list(csv.DictReader(f))
            self.assertEqual([(r['role'],r['rating']) for r in rows],[('random','Good'),('free_browse','Bad')])

    def test_undo_clear_reopen_no_training_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s=QualityStore(root,'TS999',3,40,['model'])
            self.assertFalse(s.path.exists());s.rate(5,15,'Bad','misplaced lines')
            self.assertEqual(strip_rating(s.data['records'],5,15),'Bad')
            s.rate(5,15,'Unsure');s.undo();self.assertEqual(strip_rating(s.data['records'],5,15),'Bad')
            s.clear();self.assertIsNone(strip_rating(s.data['records'],5,15));s.undo()
            saved=QualityStore(root,'TS999',3,40,['model']);self.assertEqual(saved.data['records'][0]['rating'],'Bad')
            self.assertFalse(list(root.rglob('*.npz')))
            for field in ('surfaces','local_drawn','region_excluded','surface_visible'):self.assertNotIn(field,saved.data)
            with self.assertRaises(ValueError):QualityStore(root,'TS999',3,40,['different model'])

class GUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_quality_drag_saves_without_mutating_labels(self):
        from cnv_review_v1.test_review import fake_scan
        from .gui import QualityEditor
        from PySide6 import QtCore,QtGui
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);scan=fake_scan(root);path=root/'auto.npz';shape=scan.surfaces.shape
            np.savez(path,state=np.ones(shape,np.uint8),reason=np.ones(shape,np.uint8),probabilities=np.ones((12,8,2,40))*.8,
                 uncertain_estimates=np.full(shape,np.nan),context_reason=np.zeros(shape,np.uint8))
            e=QualityEditor(root/'reviewer');e.quality_model=['test']
            e.set_line(scan,3,scan.surfaces,scan.confidence,None,dict(path=str(path)),np.zeros(40,bool),np.zeros(40,bool))
            before=e.signature();e.rate_range(5,15);e.commit_current()
            self.assertEqual(before,e.signature());self.assertFalse(list((root/'reviewer').rglob('*.npz')))
            self.assertEqual(e.quality_store.data['records'][0]['rating'],'Bad')
            # Exercise viewport dispatch, including right drag: no legacy stroke/exclusion signal.
            from PySide6.QtTest import QTest
            e.show();self.app.processEvents()
            left=e.canvas.mapFromScene(QtCore.QPointF(6,20));right=e.canvas.mapFromScene(QtCore.QPointF(12,20))
            QTest.mousePress(e.canvas.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=left)
            QTest.mouseMove(e.canvas.viewport(),right)
            QTest.mouseRelease(e.canvas.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=right)
            QTest.mousePress(e.canvas.viewport(),QtCore.Qt.MouseButton.RightButton,pos=left)
            QTest.mouseRelease(e.canvas.viewport(),QtCore.Qt.MouseButton.RightButton,pos=right)
            self.assertEqual(before,e.signature());self.assertEqual(len(e.quality_store.data['records']),2)
            self.assertFalse(e.pack.states[0].excluded.any())
            e.suggestion=dict(scan_id=scan.scan_id,bscan=3,lo=20,hi=30,id='1',role='targeted',driver='entropy',
                    metrics=dict(entropy_p95=.8,spike_max_um=30,jump_max_um=40))
            e.refresh_quality();self.assertIn('hidden',e.quality_status.text());self.assertNotIn('entropy',e.quality_status.text())
            e.rate_suggestion();self.assertIn('Entropy',e.quality_status.text());e.undo_quality();self.assertIn('hidden',e.quality_status.text())
            e.quality_mode.setChecked(False);e.on_stroke([5,14],[30,30]);self.assertNotEqual(before,e.signature())
            e.close();e.deleteLater();self.app.processEvents()

if __name__=='__main__':unittest.main()
