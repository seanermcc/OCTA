"""Synthetic contracts use in-memory human records, never written label files."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import numpy as np
from engine import Volume, LAYERS, SURFACE_NAMES, measure, pixel, approved_positions, P

class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        path=Path(self.temp.name)
        (path/'human_overrides_provenance.json').write_text('[]')
        (path/'measurements.npz').write_bytes(b'synthetic measurement fingerprint')
        self.v=Volume.__new__(Volume); v=self.v
        v.path=path; v.scan_id='SYNTHETIC'; v.config={'output':str(path)}
        v.shape=(3,4); v.offset=10; v.images=np.zeros((3,100,4)); v.scan=None
        endpoints=np.broadcast_to(np.arange(8)[None,:,None]*10+12,(3,8,4)).astype('float32').copy()
        v.d=dict(reported_positions=endpoints,uncertain_estimates=np.full_like(endpoints,np.nan),
            raw_position_branch=endpoints.copy(),state=np.ones_like(endpoints,dtype='uint8'),reason=np.ones_like(endpoints,dtype='uint8'))
        v.g={'shadow':np.zeros((3,4),bool)}
        v.index=SimpleNamespace(records={},refresh=lambda scan:None)
        v.limits={}; v.exported=[]

    def label(self):
        l=dict(surfaces=self.v.d['reported_positions'][1]-10,surface_names=SURFACE_NAMES,
            local_provenance_available=True,region_excluded=np.zeros(4,bool),verdict='corrected',
            surface_visible=np.ones(8,bool),surface_reliable=np.ones(8,bool),**P.empty_local(4))
        self.v.index.records={1:(self.v.path/'measurements.npz',l)}
        return l

    @unittest.skip('Historical strict-reporting policy; superseded by test_policy.py')
    def test_pairings_units_and_missing_internal(self):
        self.v.reload()
        np.testing.assert_allclose(self.v.maps[0][0][:,0,0],[78.4]+[11.2]*7)
        self.v.d['reported_positions'][:,3]=np.nan; self.v.reload()
        self.assertTrue(np.isfinite(self.v.maps[0][0][0]).all())
        self.assertTrue(np.isnan(self.v.maps[0][0][3:5]).all())

    @unittest.skip('Historical strict-reporting policy; superseded by test_policy.py')
    def test_raw_ilm_preview_only_and_other_raw_never_used(self):
        self.v.d['reported_positions'][:,0]=np.nan
        self.v.d['reported_positions'][:,2]=np.nan
        self.v.reload()
        self.assertTrue(np.isnan(self.v.maps[0][0][0]).all())
        self.assertTrue(self.v.maps[1][1][0].all())
        self.assertTrue(np.isnan(self.v.endpoints[1][:,2]).all())

    def test_shadow_exclusion_rejection_and_not_traceable(self):
        l=self.label(); l['region_excluded'][0]=True
        self.v.g['shadow'][0,0]=True; self.v.d['state'][2,0,0]=2
        self.v.reload()
        for maps,_ in self.v.maps:
            self.assertTrue(np.isnan(maps[:,0,0]).all()); self.assertTrue(np.isnan(maps[:,1,0]).all())
            self.assertTrue(np.isnan(maps[0,2,0]))
        l['verdict']='rejected'; self.v.reload()
        self.assertTrue(np.isnan(self.v.maps[1][0][:,1]).all())

    def test_crossing_and_outside_image(self):
        self.v.d['reported_positions'][0,1,0]=200
        self.v.d['reported_positions'][0,3,1]=self.v.d['reported_positions'][0,4,1]+1
        self.v.reload()
        self.assertTrue(np.isnan(self.v.maps[0][0][1,0,0]))
        self.assertTrue(np.isnan(self.v.maps[0][0][4,0,1]))

    @unittest.skip('Historical strict-reporting policy; superseded by test_policy.py')
    def test_pending_stroke_approval_denial_undo(self):
        l=self.label(); l['local_drawn'][0,1]=True; l['surfaces'][0,1]=4
        l['local_visibility'][0,1]=P.MARK_YES; l['local_reliability'][0,1]=P.MARK_NO
        self.v.reload()
        self.assertTrue(np.isnan(self.v.maps[0][0][0,1,1]))
        self.assertEqual(self.v.sources[1][1,0,1],5)
        l['local_reliability'][0,1]=P.MARK_YES; self.v.reload()
        self.assertEqual(self.v.sources[0][1,0,1],2)
        l['local_visibility'][0,1]=P.MARK_NO; self.v.reload()
        self.assertTrue(np.isnan(self.v.endpoints[1][1,0,1]))
        l['local_visibility'][0,1]=P.MARK_YES; l['local_drawn'][0,1]=False
        self.v.reload(); self.assertEqual(self.v.endpoints[0][1,0,1],2)

    def test_approval_matches_position_and_latest_event(self):
        l=self.label(); l['local_visibility'][:]=1; l['local_reliability'][:]=1
        e=dict(boundary='ILM',columns=[1],positions_crop_px=[2],action='approved_for_future_positions')
        self.assertTrue(approved_positions(l,[e])[0,1])
        self.assertFalse(approved_positions(l,[e,{**e,'action':'retained_uncertain'}]).any())
        l['surfaces'][0,1]=3; self.assertFalse(approved_positions(l,[e]).any())

    def test_legacy_generic_accept_displacement_and_taper(self):
        l=self.label(); l['surfaces'][0]=4; l['verdict']='accepted'
        l['local_provenance_available']=False; self.v.reload()
        np.testing.assert_equal(self.v.endpoints[0][1,0],2)
        l['local_provenance_available']=True; l['local_drawn'][0]=True
        l['local_visibility'][0]=1; l['local_reliability'][0]=1; l['local_displaced'][0]=True
        self.v.reload(); np.testing.assert_equal(self.v.endpoints[0][1,0],2)
        l['local_displaced'][0]=False; l['local_taper'][0]=True
        self.v.reload(); np.testing.assert_equal(self.v.endpoints[0][1,0],2)

    @unittest.skip('Historical strict-reporting policy; superseded by test_policy.py')
    def test_stale_context_and_fixed_limits(self):
        self.v.d['reported_positions'][:,2]=np.nan
        self.v.d['uncertain_estimates'][:,2]=32
        self.v.reload(); limits=dict(self.v.limits)
        self.assertTrue(np.isfinite(self.v.endpoints[1][:,2]).all())
        self.label(); self.v.reload()
        self.assertTrue(np.isnan(self.v.endpoints[1][:,2]).all())
        self.assertEqual(self.v.limits,limits)

    def test_exact_native_pixel(self):
        self.assertEqual(pixel(19.49,7.49,(512,512)),(7,19))
        self.assertEqual(pixel(19.5,7.5,(512,512)),(8,20))
        self.assertEqual(pixel(800,-1,(512,512)),(0,511))

    def test_map_point_agreement(self):
        self.v.reload()
        for mode in range(2):
            for k,rec in enumerate(self.v.point(1,2,mode)):
                self.assertAlmostEqual(rec['thickness_um'],self.v.maps[mode][0][k,1,2])
                self.assertAlmostEqual(rec['top_full_px'],rec['top_crop_px']+10)

if __name__=='__main__': unittest.main(verbosity=2)
