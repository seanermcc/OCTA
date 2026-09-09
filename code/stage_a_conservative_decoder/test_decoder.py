"""Conservative decoding contracts; synthetic geometry, never synthetic labels."""
import unittest
import numpy as np
from stage_a.inference import thickness
from stage_a.geometry import to_disk_rows
from .decoder import decode, ordered_flags, jump_flags, REASONS


def fixture(width=24):
    raw=np.broadcast_to(np.arange(10,90,10,dtype=np.float32)[:,None],(8,width)).copy()
    logits=-.5*((np.arange(120)[None,:,None]-raw[:,None,:])/1.5)**2
    return logits.astype(np.float32),raw,np.full_like(raw,.1),np.ones(width,bool),np.zeros(width,bool)


def settings(**kw):
    return dict(max_displacement_px=3.,entropy_cap=[.8]*8,max_step_px=[6.]*8,
        max_log_drop=float(np.log(20)),continuity_weight=.15,jump_guard_radius=1,
        min_interval_columns=4,max_guard_iterations=8,**kw)


class ConservativeTests(unittest.TestCase):
    def test_normal_retains_all_and_native_geometry(self):
        args=fixture(); p=decode(*args,settings())
        self.assertTrue(p['retained'].all())
        np.testing.assert_equal(p['rows'],args[1])
        disk=to_disk_rows(p['retained_rows'],120,True)
        np.testing.assert_equal(to_disk_rows(disk,120,True),args[1])

    def test_original_crossing_cannot_be_repaired_into_measurement(self):
        args=list(fixture()); args[1][1,8:16]=35
        p=decode(*args,settings())
        self.assertFalse(p['retained'][1:3,8:16].any())
        self.assertTrue(((p['reason_bits'][1:3,8:16]&REASONS['crossing'])!=0).all())
        self.assertTrue(p['retained'][0].all())

    def test_partial_entropy_retains_ilm_and_other_thickness(self):
        args=list(fixture()); args[2][7,8:16]=.9
        p=decode(*args,settings())
        self.assertTrue(p['retained'][:7].all())
        self.assertFalse(p['retained'][7,8:16].any())
        bands=thickness(p['retained_rows'],p['retained'],1.12)
        self.assertTrue(np.isnan(bands['TOTAL'][8:16]).all())
        self.assertTrue(np.isfinite(bands['RNFL']).all())

    def test_scope_shadow_and_gate_stay_nan(self):
        args=list(fixture()); args[3][0:4]=False; args[4][8:12]=True
        gate=np.ones((8,24),bool); gate[0,16:20]=False
        p=decode(*args,settings(),gate)
        self.assertTrue(np.isnan(p['retained_rows'][:,:4]).all())
        self.assertTrue(np.isnan(p['retained_rows'][:,8:12]).all())
        self.assertTrue(np.isnan(p['retained_rows'][0,16:20]).all())
        self.assertTrue(p['retained'][1:,16:20].all())

    def test_parent_mask_is_monotone_even_if_gate_relaxes(self):
        args=fixture(); gate=np.ones(24,bool); gate[8:16]=False
        parent=decode(*args,settings(),gate)
        child=decode(*args,settings(),parent=parent)
        self.assertFalse((child['retained']&~parent['retained']).any())
        self.assertTrue(((child['reason_bits'][:,8:16]&4096)!=0).all())

    def test_multimodal_far_peak_is_withheld_instead_of_relocated(self):
        args=list(fixture()); args[0][0]=-100; args[0][0,45]=0
        p=decode(*args,settings())
        self.assertFalse(p['retained'][0].any())
        self.assertTrue(((p['reason_bits'][0]&512)!=0).all())
        self.assertTrue(p['retained'][1:].all())

    def test_retained_pairs_ordered_across_missing_named_surface(self):
        args=list(fixture()); args[1][1]=np.nan; args[1][0]=35
        args[0][0]=-100; args[0][0,35]=0
        p=decode(*args,settings())
        self.assertFalse(ordered_flags(p['retained_rows']).any())
        self.assertFalse(p['retained'][0].any())
        self.assertFalse(p['retained'][2].any())

    def test_disconnected_intervals_have_no_lateral_influence(self):
        args=fixture(); gate=np.ones(24,bool); gate[10:14]=False
        first=decode(*args,settings(),gate)
        modified=list(fixture()); modified[0][:,:,14:]=np.roll(modified[0][:,:,14:],2,axis=1)
        second=decode(*modified,settings(),gate)
        np.testing.assert_equal(first['retained_rows'][:,:10],second['retained_rows'][:,:10])
        self.assertTrue(np.isnan(second['retained_rows'][:,10:14]).all())

    def test_abrupt_jump_breaks_without_bridging_or_flattening(self):
        args=list(fixture()); args[1][:,12:]+=15
        args[0]=(-.5*((np.arange(120)[None,:,None]-args[1][:,None,:])/1.5)**2).astype(np.float32)
        p=decode(*args,settings())
        self.assertTrue(np.isnan(p['retained_rows'][:,10:14]).all())
        np.testing.assert_equal(p['retained_rows'][:,:10],args[1][:,:10])
        np.testing.assert_equal(p['retained_rows'][:,14:],args[1][:,14:])
        self.assertFalse(jump_flags(p['retained_rows'],p['retained'],[6]*8,0).any())

    def test_short_islands_are_nan_but_long_intervals_remain(self):
        args=fixture(); gate=np.zeros(24,bool); gate[:3]=True; gate[12:]=True
        p=decode(*args,settings(),gate)
        self.assertFalse(p['retained'][:,:12].any())
        self.assertTrue(((p['reason_bits'][:,:3]&2048)!=0).all())
        self.assertTrue(p['retained'][:,12:].all())

    def test_curved_tissue_under_measured_limit_is_not_flattened(self):
        args=list(fixture()); args[1]+=np.round(4*np.sin(np.arange(24)/4)).astype(np.float32)
        args[0]=(-.5*((np.arange(120)[None,:,None]-args[1][:,None,:])/1.5)**2).astype(np.float32)
        p=decode(*args,settings())
        self.assertTrue(p['retained'].all())
        np.testing.assert_equal(p['rows'],args[1])

    def test_all_missing_fail_closed(self):
        args=list(fixture()); args[1][:]=np.nan; args[0][:]=np.nan
        p=decode(*args,settings())
        self.assertFalse(p['retained'].any())
        self.assertTrue(np.isnan(p['retained_rows']).all())

    def test_relocation_cap_is_enforced(self):
        args=list(fixture()); args[1]+=.4
        args[0]=np.roll(args[0],3,axis=1)
        p=decode(*args,settings())
        self.assertTrue(p['retained'].all())
        self.assertLessEqual(float(abs(p['retained_rows']-args[1]).max()),3.)

    def test_nonfinite_single_posterior_does_not_remove_other_surfaces(self):
        args=list(fixture()); args[0][4,50,8:16]=np.nan
        p=decode(*args,settings())
        self.assertFalse(p['retained'][4,8:16].any())
        self.assertTrue(p['retained'][[0,1,2,3,5,6,7]].all())


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ConservativeTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
