"""Synthetic semantics and measurement safeguards; no human-label writes."""
import itertools
import unittest
import numpy as np
import torch
from eight_surface.config import CASCADE_VERSION
from .readability import readability_targets, masked_readability_loss, ReadabilityUNet
from stage_a.model import BoundaryUNet
from .ordered import ordered_column, decode_ordered, gated_raw, REASONS, intervals
from stage_a.inference import thickness
from stage_a.geometry import to_disk_rows


def human(width=12):
    return dict(verdict='corrected',cascade_version=CASCADE_VERSION,
        region_excluded=np.zeros(width,bool),surface_edited=np.ones(8,bool),
        surface_visible=np.ones(8,bool),surface_reliable=np.ones(8,bool),
        surface_displaced=np.zeros(8,bool),seconds_active=80,n_strokes=16)


def example(width=9, height=96):
    truth=np.repeat((np.arange(8)*10+10)[:,None],width,axis=1).astype(np.float32)
    depth=np.arange(height)[None,:,None]
    logits=(-.5*((depth-truth[:,None,:])/2)**2).astype(np.float32)
    config=dict(entropy_cap=[.9]*8,continuity_scale_px=[3.]*8,
        continuity_weight=.15,continuity_truncation=4.,max_log_drop=3.)
    return truth,logits,config


class ReadabilityTests(unittest.TestCase):
    def test_local_visibility_unknown_is_not_positive_or_whole_column_negative(self):
        r=human(); r['local_provenance_available']=True
        r['local_visibility']=np.ones((8,12),np.uint8)
        r['local_reliability']=np.ones((8,12),np.uint8)
        r['local_visibility'][3,0]=0
        r['local_visibility'][3,1]=2
        y,w,s=readability_targets(r,np.ones((8,12),bool))
        np.testing.assert_equal(y[:2],[-1,-1])
        self.assertTrue((y[2:]==1).all())
        self.assertTrue((w[2:]==1).all()); self.assertTrue((s[2:]==2).all())

    def test_explicit_exclusions_only_negatives(self):
        r=human(); r['verdict']='rejected'; r['region_excluded'][3:5]=True
        y,w,s=readability_targets(r,np.zeros((8,12),bool))
        np.testing.assert_array_equal(np.flatnonzero(y==0),[3,4])
        self.assertTrue((y[np.r_[0:3,5:12]]==-1).all())
        self.assertEqual(w.sum(),2)

    def test_unedited_invisible_shadow_scope_missing_stay_unknown(self):
        for field in ['surface_edited','surface_visible','surface_reliable']:
            r=human(); r[field][4]=False
            y,_,_=readability_targets(r,np.ones((8,12),bool))
            self.assertTrue((y==-1).all())
        for verdict in ['accepted','rejected']:
            r=human(); r['verdict']=verdict
            self.assertTrue((readability_targets(r,np.ones((8,12),bool))[0]==-1).all())
        r=human(); valid=np.ones((8,12),bool); valid[0,:4]=False
        self.assertTrue((readability_targets(r,valid)[0][:4]==-1).all())

    def test_weak_and_strict_are_explicit_and_exclusion_wins(self):
        r=human(); r['region_excluded'][4]=True
        y,w,s=readability_targets(r,np.ones((8,12),bool))
        self.assertEqual(y[4],0); self.assertEqual(s[4],1)
        self.assertTrue((w[y==1]==.25).all())
        self.assertTrue((s[y==1]==3).all())
        self.assertEqual((readability_targets(r,np.ones((8,12),bool),'strict')[0]==1).sum(),0)
        r['seconds_active']=0
        self.assertEqual((readability_targets(r,np.ones((8,12),bool))[0]==1).sum(),0)

    def test_unknown_mask_zero_gradient_and_horizontal_alignment(self):
        p=torch.tensor([[.5,-.3,8.,-6.]],requires_grad=True)
        y=torch.tensor([[1,0,-1,-1]]); w=torch.tensor([[.25,1.,0.,0.]])
        a=masked_readability_loss(p,y,w)
        b=masked_readability_loss(p.flip(-1),y.flip(-1),w.flip(-1))
        self.assertTrue(torch.equal(a,b)); a.backward()
        self.assertTrue(torch.equal(p.grad[0,2:],torch.zeros(2)))
        self.assertGreater(float(p.grad[0,:2].abs().sum()),0)
        z=torch.randn(1,4,requires_grad=True)
        masked_readability_loss(z,y*0-1,w*0).backward()
        self.assertTrue(torch.equal(z.grad,torch.zeros_like(z)))

    def test_frozen_backbone_predictions_exact_and_head_trainable(self):
        torch.manual_seed(1)
        backbone=BoundaryUNet().eval(); m=ReadabilityUNet(backbone).eval()
        x=torch.randn(1,1,97,35)
        with torch.no_grad(): old=backbone(x)
        a,b,r=m(x)
        self.assertTrue(torch.equal(a,old[0])); self.assertTrue(torch.equal(b,old[1]))
        r.square().mean().backward()
        self.assertTrue(all(p.grad is None for p in backbone.parameters()))
        self.assertTrue(any(p.grad is not None for p in m.head.parameters()))
        self.assertEqual(r.shape,(1,35))

    def test_column_dp_matches_exhaustive_global_optimum(self):
        rng=np.random.default_rng(4)
        for _ in range(12):
            c=rng.normal(size=(3,9)); c[rng.random(c.shape)<.1]=np.inf
            options=list(itertools.combinations(range(9),3))
            costs=[sum(c[k,x] for k,x in enumerate(v)) for v in options]
            result=ordered_column(c)
            self.assertAlmostEqual(sum(c[k,x] for k,x in enumerate(result)),min(costs))
        self.assertIsNone(ordered_column(np.full((8,5),np.inf)))

    def test_crossing_modes_ordered_or_withheld_without_displacement(self):
        raw,logits,cfg=example()
        logits[[2,3]]=logits[[3,2]]; raw[[2,3]]=raw[[3,2]]
        p=decode_ordered(logits,raw,np.zeros_like(raw),np.ones(9,bool),np.zeros(9,bool),cfg)
        self.assertFalse(p['retained'].any())
        self.assertTrue(((p['reason_bits']&REASONS['order_infeasible'])!=0).all())
        self.assertTrue(np.isnan(p['retained_rows']).all())

    def test_disconnected_intervals_have_no_influence_across_gap(self):
        raw,logits,cfg=example(); keep=np.ones(9,bool); keep[4]=False
        a=decode_ordered(logits,raw,np.zeros_like(raw),np.ones(9,bool),np.zeros(9,bool),cfg,keep)
        changed=logits.copy(); changed[:,:,5:]=np.roll(changed[:,:,5:],5,axis=1)
        b=decode_ordered(changed,raw,np.zeros_like(raw),np.ones(9,bool),np.zeros(9,bool),cfg,keep)
        np.testing.assert_equal(a['rows'][:,:4],b['rows'][:,:4])
        self.assertTrue(np.isnan(a['rows'][:,4]).all())
        self.assertEqual(intervals(keep),[(0,4),(5,9)])

    def test_partial_support_withheld_and_no_scope_shadow_rescue(self):
        raw,logits,cfg=example(); ent=np.zeros_like(raw); ent[7,3]=.99
        scope=np.ones(9,bool); scope[0]=False
        shadow=np.zeros(9,bool); shadow[1]=True
        p=decode_ordered(logits,raw,ent,scope,shadow,cfg)
        self.assertTrue(np.isnan(p['retained_rows'][:,[0,1,3]]).all())
        self.assertTrue(p['retained'][:,[2,4,5,6,7,8]].all())
        self.assertTrue((np.diff(p['rows'][:,2])>0).all())

    def test_canonical_disk_nan_geometry_and_thickness(self):
        raw,_,_=example(); keep=np.ones(9,bool); keep[4]=False
        p=gated_raw(raw,np.ones(9,bool),np.zeros(9,bool),keep)
        disk=to_disk_rows(p['retained_rows'],96,True)
        np.testing.assert_equal(to_disk_rows(disk,96,True),p['retained_rows'])
        bands=thickness(p['retained_rows'],p['retained'],1.12)
        self.assertTrue(all(np.isnan(v[4]) for v in bands.values()))
        np.testing.assert_allclose(bands['TOTAL'][[0,1]],78.4)
        raw[1,2]=raw[0,2]-10
        self.assertTrue(np.isnan(thickness(raw,np.ones_like(raw,bool),1.12)['RNFL'][2]))
        raw[0,3]=np.nan
        self.assertTrue(np.isnan(thickness(raw,np.ones_like(raw,bool),1.12)['TOTAL'][3]))


if __name__=='__main__':
    torch.set_num_threads(2)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReadabilityTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
