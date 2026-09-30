"""Comparison checks use arrays in memory; never synthesize human label files."""
import unittest
import numpy as np
from build import paired, stats, safe, lesion_display, hyper_display, resolve, L


class DifferenceTests(unittest.TestCase):
    def record(self, z, mask):
        return dict(positions=np.array(z, float), approved=np.array(mask, bool))

    def test_signed_scale_and_intersection(self):
        a=self.record([[10,20,30,40]], [[True,True,False,True]])
        b=self.record([[12,18,90,42]], [[True,False,True,True]])
        delta=paired(a,b,'approved')
        np.testing.assert_allclose(delta, [[2.24,np.nan,np.nan,2.24]], equal_nan=True)
        self.assertAlmostEqual(stats(delta)['bias_um'],2.24)
        self.assertEqual(stats(delta)['n'],2)

    def test_missing_is_not_perfect_agreement(self):
        s=stats([np.nan])
        self.assertEqual(s['n'],0)
        self.assertIsNone(s['mae_um'])
        self.assertIsNone(s['within_5um_pct'])

    def test_bias_is_not_absolute_distance(self):
        s=stats([-10,10,0])
        self.assertEqual(s['bias_um'],0)
        self.assertAlmostEqual(s['mae_um'],20/3)
        self.assertAlmostEqual(s['within_5um_pct'],100/3)

    def test_no_resampling(self):
        with self.assertRaises(ValueError):
            paired(self.record([[1,2]],[[True,True]]),self.record([[1]],[[True]]),'approved')

    def test_json_nan_is_null(self):
        self.assertEqual(safe(np.array([[np.nan,2.]])),[[None,2.]])

    def test_swap_changes_bias_not_distance(self):
        a=self.record([[10,20]],[[True,True]])
        b=self.record([[12,25]],[[True,True]])
        ab,ba=stats(paired(a,b,'approved')),stats(paired(b,a,'approved'))
        self.assertEqual(ab['mae_um'],ba['mae_um'])
        self.assertEqual(ab['bias_um'],-ba['bias_um'])

    def test_cnv_replay_preserves_crop_coordinates_and_uncertainty(self):
        base=np.broadcast_to(np.arange(8)[:,None]*5+510,(8,8)).copy()
        def event(action,lo,hi,**kw):
            return dict(action=action,lo=lo,hi=hi,semantics=3,
                        lesion_definition=L.DEFINITION_VERSION,**kw)
        events=[event('cnv_region',1,6),
                event('cnv_edge',1,6,xs=[1,5],ys=[550,554]),
                event('cnv_edge_mark',2,3,mark='unreliable'),
                event('cnv_edge_mark',3,4,mark='not_traceable'),
                event('cnv_edge',4,5,erase=True)]
        r=resolve(events,base,500,80)
        c=lesion_display(r,events)
        np.testing.assert_array_equal(c['region'],[False,True,True,True,True,True,False,False])
        np.testing.assert_array_equal(c['edge_state'],[0,1,2,3,0,1,0,0])
        self.assertEqual(c['edge'][1],550)  # Full canonical depth: subtract offset once in UI.
        self.assertTrue(np.isnan(c['edge'][4]))
        self.assertFalse(c['confirmed'])
        self.assertIn('unconfirmed',c['status'])
        undone=lesion_display(resolve(events[:-1],base,500,80),events[:-1])
        self.assertEqual(undone['edge'][4],553)

    def test_no_cnv_work_is_not_confirmed_absence(self):
        r=dict(lesions=L.empty(8,80),lesion_confirmation=None,lesion_definition=None)
        c=lesion_display(r,[])
        self.assertFalse(c['confirmed'])
        self.assertEqual(c['status'],'No saved CNV annotations')

    def test_hyper_mask_crop_erase_and_undo(self):
        base=np.broadcast_to(np.arange(8)[:,None]*5+510,(8,8)).copy()
        paint=dict(action='hyper_ref',lo=0,hi=8,semantics=3,
                   lesion_definition=L.DEFINITION_VERSION,xs=[0,7],ys=[500,500],diameter=1)
        erase=dict(paint,xs=[3],ys=[500],erase=True)
        def exported(events):
            h=hyper_display(resolve(events,base,500,80),events)
            mask=np.zeros(80*8,bool)
            for lo,hi in h['runs']:mask[lo:hi]=True
            return h,mask.reshape(80,8)
        h,mask=exported([paint,erase])
        expected=np.zeros((80,8),bool);expected[0]=True;expected[0,3]=False
        np.testing.assert_array_equal(mask,expected)
        self.assertEqual(h['pixels'],7)
        self.assertEqual(h['bounds'],[0,0,8,1])
        self.assertIn('unconfirmed',h['status'])
        self.assertEqual(exported([paint])[0]['pixels'],8)
        self.assertEqual(exported([])[0]['status'],'No saved dot annotations')


if __name__=='__main__':
    unittest.main()
