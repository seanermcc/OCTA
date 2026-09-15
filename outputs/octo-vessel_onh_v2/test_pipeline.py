"""Safety and scientific-contract tests using synthetic arrays, never labels."""
import unittest
import numpy as np
import torch
from torch.nn import functional as F
from audit import supervision
from network import masked_loss,resolved_masks,confusion,native_prob,Model

class Contracts(unittest.TestCase):
    def fixture(self):
        shape=(8,8)
        z={k:np.zeros(shape,bool) for k in ['vasculature_mask','onh_mask','onh_edge_mask','vasculature_brush_touched','vessel_removed_by_onh','vessel_region_excluded','onh_region_excluded']}
        z['reviewed_targets']=np.array([False,True,True]);z['onh_visibility']=np.array(['Outside image'])
        z['vasculature_mask'][2:4,2:4]=True;z['vasculature_brush_touched'][2,2]=True;z['vasculature_brush_touched'][5,5]=True
        return z
    def test_automatic_pixels_ignored(self):
        p,n=supervision(self.fixture());self.assertEqual(p[0].sum(),1);self.assertEqual(n[0].sum(),1)
        self.assertFalse(p[0,3,3] or n[0,3,3])
    def test_scan_exclusion_overrides_brush_and_review(self):
        p,n=supervision(self.fixture(),True);self.assertFalse(p.any() or n.any())
    def test_target_completion_separate(self):
        z=self.fixture();z['reviewed_targets'][1]=False;p,n=supervision(z)
        self.assertFalse(p[0].any() or n[0].any());self.assertTrue(n[1].all())
    def test_unknown_is_not_absent(self):
        for state in ['Not assessed','Cannot judge']:
            z=self.fixture();z['onh_visibility']=np.array([state]);p,n=supervision(z)
            self.assertFalse(p[1].any() or n[1].any())
        z=self.fixture();z['reviewed_targets'][2]=False;p,n=supervision(z);self.assertFalse(n[1].any())
    def test_uncertain_pixels_and_derived_removals(self):
        z=self.fixture();z['vessel_region_excluded'][2,2]=True;z['vessel_removed_by_onh'][5,5]=True;z['onh_region_excluded'][1,1]=True
        p,n=supervision(z);self.assertFalse(p[0].any() or n[0].any());self.assertFalse(n[1,1,1])
    def test_partial_visible_only(self):
        z=self.fixture();z['onh_visibility']=np.array(['Partially visible — outlined']);z['onh_mask'][:,0:2]=True
        p,n=supervision(z);self.assertEqual(p[1].sum(),16);self.assertFalse((p&n).any())
    def test_contradictory_absence_fails(self):
        z=self.fixture();z['onh_mask'][0,0]=True
        with self.assertRaises(ValueError):supervision(z)
    def test_unknown_has_zero_loss_gradient(self):
        x=torch.zeros((1,2,8,8),requires_grad=True);p=torch.zeros_like(x);n=torch.zeros_like(x)
        p[0,0,2,2]=1;n[0,0,4,4]=1
        masked_loss(x,p,n).backward();self.assertEqual(int(torch.count_nonzero(x.grad)),2)
        self.assertLess(x.grad[0,0,2,2],0);self.assertGreater(x.grad[0,0,4,4],0)
    def test_pooling_preserves_supervised_pixel_mass(self):
        p=torch.zeros((1,2,8,8));p[0,0,1,1]=1
        q=F.avg_pool2d(p,2);self.assertEqual(float(q.sum()*4),1);self.assertEqual(float(q.max()),.25)
    def test_overlap_resolves_to_onh(self):
        p=np.ones((2,8,8),np.float32);m=resolved_masks(p,[.5,.5],0)
        self.assertTrue(m[1].all());self.assertFalse(m[0].any())
    def test_native_grid_and_threshold_reproducible(self):
        raw=np.zeros((2,4,4),np.float16);raw[0,:,2:]=1;p=native_prob(raw,(8,8))
        self.assertEqual(p.shape,(2,8,8));self.assertTrue((p[0,:,:2]==0).all());self.assertTrue((p[0,:,-2:]==1).all())
    def test_scoring_ignores_unreviewed_prediction(self):
        pos=np.zeros((8,8),bool);neg=pos.copy();pos[0,0]=True;neg[1,1]=True
        c=confusion(np.ones((8,8),bool),pos,neg);self.assertEqual(c,dict(tp=1,fn=0,fp=1,tn=0))

if __name__=='__main__':unittest.main()
