import unittest
import numpy as np
from test_pilot import Contracts
from engine import P
class PilotPolicy(Contracts):
    def test_available_raw_positions_used_by_default(self):
        self.v.d['reported_positions'][:]=np.nan
        self.v.d['state'][:]=3; self.v.d['reason'][:]=9
        self.v.reload()
        self.assertTrue(np.isfinite(self.v.maps[0][0]).all())
        self.assertFalse(self.v.maps[0][1].any())
    def test_explicit_unreliable_toggle(self):
        l=self.label(); l['local_reliability'][0,2]=P.MARK_NO
        self.v.reload()
        self.assertTrue(np.isnan(self.v.maps[0][0][0,1,2]))
        self.assertTrue(np.isfinite(self.v.maps[1][0][0,1,2]))
        self.assertTrue(self.v.maps[1][1][0,1,2])
        l['local_visibility'][0,2]=P.MARK_NO; self.v.reload()
        self.assertTrue(np.isnan(self.v.maps[1][0][0,1,2]))
    def test_pending_stroke_used_unless_unreliable(self):
        l=self.label(); l['local_drawn'][0,2]=True; l['surfaces'][0,2]=4
        self.v.reload(); self.assertEqual(self.v.endpoints[0][1,0,2],4)
if __name__=='__main__':
    names=['test_available_raw_positions_used_by_default','test_explicit_unreliable_toggle','test_pending_stroke_used_unless_unreliable','test_shadow_exclusion_rejection_and_not_traceable','test_crossing_and_outside_image','test_exact_native_pixel','test_map_point_agreement']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(PilotPolicy(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
