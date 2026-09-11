import unittest
import numpy as np
from eight_surface import provenance as P
from .audit import targets
from .decisions import *

def label(w=32):
    out=dict(surfaces=np.tile(np.arange(8)[:,None]*10+10,(1,w)),
        surface_visible=np.ones(8,bool),surface_reliable=np.ones(8,bool),
        surface_edited=np.zeros(8,bool),surface_displaced=np.zeros(8,bool),
        region_excluded=np.zeros(w,bool),verdict="corrected",local_provenance_available=True)
    out.update(P.empty_local(w));out["provenance_code"]=np.zeros((8,w),np.uint8)
    return out

def cal():return [dict(not_traceable_cutoff=.2,trace_cutoff=.6,reliability_cutoff=.6,supported=True) for _ in range(8)]

class Contract(unittest.TestCase):
    def test_unknown_not_positive(self):
        d=targets(label(),np.zeros(32,bool),100,0)
        self.assertFalse(d["valid"].any());self.assertTrue((d["trace_target"]==-1).all())
    def test_saved_manual_empty_vessel_mask_beats_proposal(self):
        from eight_surface.vasculature_proposals import has_saved_vessel_work
        record=dict(reviewed_targets=[False]*4,vasculature_mask=np.zeros((4,4),bool),vasculature_brush_touched=np.eye(4,dtype=bool))
        self.assertTrue(has_saved_vessel_work(record))
    def test_rejected_negative_survives(self):
        l=label();l["verdict"]="rejected";l["local_visibility"][3,5:9]=2;l["local_reliability"][4,2:6]=2
        d=targets(l,np.zeros(32,bool),100,0)
        self.assertEqual((d["trace_target"]==0).sum(),4);self.assertEqual((d["reliability_target"]==0).sum(),4)
        self.assertFalse(d["valid"].any())
    def test_no_taper_displaced_automatic_targets(self):
        l=label();l["provenance_code"][0,:6]=[0,1,2,3,4,5]
        d=targets(l,np.zeros(32,bool),100,0)
        self.assertEqual(d["valid"].sum(),1);self.assertTrue(d["valid"][0,1])
        self.assertEqual(d["reliability_target"][0,1],-1)
        self.assertEqual(d["trace_target"][0,1],-1)
    def test_last_pixel_and_shadow(self):
        l=label();l["surfaces"]=l["surfaces"].astype(float);l["provenance_code"][0,:3]=1
        l["surfaces"][0,0]=99.5;s=np.zeros(32,bool);s[1]=True
        self.assertEqual(targets(l,s,100,0)["valid"].sum(),1)
    def test_vessel_precedence_per_boundary(self):
        rows=label()["surfaces"];p=np.ones((8,2,32))*.9;v=np.ones(32,bool)
        rel=np.full((8,32),-1);rel[2]=1
        rep,state,_=decide(rows,p,cal(),v,reliability=rel)
        self.assertTrue(np.isfinite(rep[0]).all());self.assertTrue(np.isfinite(rep[2]).all())
        self.assertTrue(np.isnan(rep[1]).all());self.assertFalse((state==NOT_TRACEABLE).any())
    def test_denial_and_nan(self):
        rows=label()["surfaces"];p=np.ones((8,2,32))*.9;t=np.full((8,32),-1);t[2,8:15]=0
        rep,state,_=decide(rows,p,cal(),np.zeros(32,bool),trace=t)
        self.assertTrue(np.isnan(rep[2,8:15]).all());self.assertTrue(np.isfinite(rep[0]).all())
        thick=thickness(rep,np.zeros(32,bool));self.assertTrue(np.isnan(thick[1:3,8:15]).all())
        self.assertTrue(np.isfinite(thick[0]).all())
        self.assertTrue(np.isnan(thickness(rep,np.ones(32,bool))).all())
    def test_human_unreliable_overrides_model_not_traceable(self):
        p=np.ones((8,2,32))*.1;rel=np.full((8,32),-1);rel[3,5:10]=0
        _,s,_=decide(label()["surfaces"],p,cal(),np.zeros(32,bool),reliability=rel)
        self.assertTrue((s[3,5:10]==UNCERTAIN).all())
        trace=np.full((8,32),-1);trace[3,5:10]=0
        _,s,_=decide(label()["surfaces"],p,cal(),np.zeros(32,bool),reliability=rel,trace=trace)
        self.assertTrue((s[3,5:10]==NOT_TRACEABLE).all())
    def test_registration_native_translation(self):
        image=np.random.default_rng(8).normal(size=(96,80))
        moved=np.roll(np.roll(image,2,0),3,1)
        shifts,scores=alignment(np.stack([image,moved]))
        np.testing.assert_array_equal(shifts[0],[-2,-3]);self.assertGreater(scores[0],.99)
    def test_context_no_bridge_or_propagation(self):
        w=80;rows=np.tile(label(w)["surfaces"],(3,1,1)).astype(float)
        rep=rows.copy();states=np.ones_like(rows,np.uint8);reasons=np.ones_like(states)
        states[1,2,20:40]=NOT_TRACEABLE;rep[1,2,20:40]=np.nan
        im=np.random.default_rng(4).normal(size=(100,w));images=np.stack([im]*3)
        e,_,_=estimate_context(rows,rep,states,reasons,images,np.zeros((2,2)),np.ones(2))
        self.assertFalse(np.isfinite(e).any())
        states[1,2,20:40]=UNCERTAIN
        e,_,_=estimate_context(rows,rep,states,reasons,images,np.zeros((2,2)),np.ones(2))
        self.assertEqual(np.isfinite(e).sum(),20)
        e,_,_=estimate_context(rows,rep,states,reasons,images,np.zeros((2,2)),np.zeros(2))
        self.assertFalse(np.isfinite(e).any())
    def test_context_preserves_deformation(self):
        rows=np.tile(label(80)["surfaces"],(3,1,1)).astype(float);rows[:,2,25:35]+=3
        rep=rows.copy();state=np.ones_like(rows,np.uint8);state[1,2,20:40]=3;rep[1,2,20:40]=np.nan
        im=np.random.default_rng(5).normal(size=(100,80))
        e,_,_=estimate_context(rows,rep,state,np.ones_like(state),np.stack([im]*3),np.zeros((2,2)),np.ones(2))
        np.testing.assert_array_equal(e[1,2,20:40],rows[1,2,20:40])
    def test_uncertain_neighbor_shape_is_context_not_measurement(self):
        rows=np.tile(label(80)["surfaces"],(3,1,1)).astype(float)
        rep=rows.copy();state=np.ones_like(rows,np.uint8);state[:,2,20:40]=3;rep[:,2,20:40]=np.nan
        reasons=np.ones_like(state);im=np.random.default_rng(11).normal(size=(100,80))
        e,_,_=estimate_context(rows,rep,state,reasons,np.stack([im]*3),np.zeros((2,2)),np.ones(2))
        self.assertEqual(np.isfinite(e).sum(),20);self.assertTrue(np.isnan(rep[:,2,20:40]).all())
        state[0,2,25]=NOT_TRACEABLE
        e,_,_=estimate_context(rows,rep,state,reasons,np.stack([im]*3),np.zeros((2,2)),np.ones(2))
        self.assertFalse(np.isfinite(e).any())
if __name__=="__main__":unittest.main()
