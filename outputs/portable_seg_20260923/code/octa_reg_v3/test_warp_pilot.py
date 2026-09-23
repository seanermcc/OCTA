"""Known-transform checks for experimental registration, independent of retinal data."""
import unittest
import numpy as np
from scipy import ndimage as ndi
from .warp_pilot import GRID,fit_fields,geometry,sample,match_point

class WarpTests(unittest.TestCase):
    def test_scale_and_inverse_sampling(self):
        yy,xx=np.mgrid[80:450:65,80:450:65];p=np.c_[xx.ravel(),yy.ravel()].astype(float)
        q=(p-255.5)*1.06+255.5+[4,-3]
        fields=fit_fields(p,q,np.ones((512,512),bool))
        expected=(GRID-255.5)*1.06+255.5+[4,-3]-GRID
        self.assertLess(np.max(np.abs(fields['similarity'].reshape(-1,2)-expected)),1e-4)
        g=geometry(fields['similarity'])
        self.assertAlmostEqual(g['jacobian_min'],1.06**2,places=4)
        # A source ramp must sample at p+displacement, not p-displacement.
        ramp=np.indices((512,512))[1].astype(float)
        loc=np.array([[200.,200.]])
        delta=np.c_[sample(fields['similarity'][:,:,0],loc),sample(fields['similarity'][:,:,1],loc)]
        self.assertAlmostEqual(sample(ramp,loc+delta)[0],(200-255.5)*1.06+255.5+4,places=4)
    def test_local_smooth_displacement_generalizes(self):
        yy,xx=np.mgrid[70:460:45,70:460:45];p=np.c_[xx.ravel(),yy.ravel()].astype(float)
        def delta(x):return np.c_[4*np.sin(x[:,0]/120)*np.sin(x[:,1]/130),3*np.cos(x[:,0]/150)*np.sin(x[:,1]/140)]
        field=fit_fields(p,p+delta(p),np.ones((512,512),bool))['tps_0.003']
        test=p[:-10]+13;pred=np.c_[sample(field[:,:,0],test),sample(field[:,:,1],test)]
        self.assertLess(np.median(np.linalg.norm(pred-delta(test),axis=1)),.3)
        self.assertEqual(geometry(field)['folding_pixels'],0)
    def test_patch_direction_and_unrelated_texture(self):
        rng=np.random.default_rng(8);a=ndi.gaussian_filter(rng.normal(size=(512,512)),2).astype('float32')*10
        b=ndi.shift(a,(7,-9),order=1)
        hit=match_point(a,b,np.array([220,230]))
        self.assertIsNotNone(hit)
        self.assertLess(np.linalg.norm(hit[0]-[211,237]),.1)
        unrelated=ndi.gaussian_filter(rng.normal(size=(512,512)),2).astype('float32')*10
        self.assertIsNone(match_point(a,unrelated,np.array([220,230])))
    def test_fold_detected(self):
        field=np.zeros((512,512,2));field[:,:,0]=-2*np.indices((512,512))[1]
        self.assertEqual(geometry(field)['folding_pixels'],512*512)

if __name__=='__main__':unittest.main()
