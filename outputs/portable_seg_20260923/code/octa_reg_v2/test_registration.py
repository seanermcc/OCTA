import unittest
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from .run import matrix,apply,score
from .curves import match
from .assemble import solve,CORNERS,ROOT_INDEX

def scan(mask):
    sk=skeletonize(mask);points=np.argwhere(sk)[:,::-1].astype(float)
    return dict(vessel=mask,skel=sk,points=points,dt=ndi.distance_transform_edt(~sk),
                valid=np.ones_like(mask),image=1-ndi.gaussian_filter(mask.astype(float),1))

class RegistrationTests(unittest.TestCase):
    def test_known_curve_transform_with_partial_overlap(self):
        im=Image.new('L',(512,512));d=ImageDraw.Draw(im)
        for line in [[(110,90),(145,210),(235,320),(365,485)],[(110,90),(235,135),(490,190)],
                     [(110,90),(78,230),(35,410)],[(145,210),(260,190),(390,250)],[(235,320),(315,310),(480,340)]]:
            d.line(line,fill=255,width=7)
        a=scan(np.asarray(im)>0);m=matrix([np.deg2rad(18),63,-43]);inv=np.linalg.inv(m)
        mask=ndi.affine_transform(a['vessel'].astype(np.uint8),inv[:2,:2][::-1,::-1],inv[:2,2][::-1],order=0)>0
        b=scan(mask);result=match(a,b)
        self.assertTrue(result['accepted'],result)
        error=np.linalg.norm(apply(CORNERS,np.array(result['matrix']))-apply(CORNERS,m),axis=1)
        self.assertLess(error.max(),3.)

    def test_single_straight_trunk_is_not_spatially_informative(self):
        mask=np.zeros((512,512),bool);mask[:,250:257]=True;s=scan(mask)
        result=score(s,s,np.eye(3));self.assertGreater(result['dice'],.99);self.assertLess(result['span_px'],3)

    def test_no_overlap_not_accepted(self):
        mask=np.zeros((512,512),bool);mask[80:420,180:185]=True;s=scan(mask)
        self.assertEqual(score(s,s,matrix([0,800,800]))['support'],0)

    def test_onh_direction_and_inverse(self):
        onh_native=np.array([-150.,-90.]);m=matrix([0,*-onh_native])
        self.assertTrue(np.all(apply([256,256],m)>0))
        np.testing.assert_allclose(apply(onh_native,m),[0,0])
        np.testing.assert_allclose(apply(apply(CORNERS,m),np.linalg.inv(m)),CORNERS)

    def test_neighbor_consensus_overrules_wrong_high_score_bridge(self):
        scans=[dict(excluded=True,info={}) for _ in range(7)]
        for i in [0,1,2,3,6]:scans[i]=dict(excluded=False,info={})
        scans[6]['info']=dict(visible_onh=dict(center_um=[0,0]),spacing=[1,1])
        ee=[]
        for i in [1,2,3]:ee.append(dict(a=6,b=i,matrix=np.eye(3).tolist(),score=.99))
        ee.append(dict(a=0,b=1,matrix=matrix([1.1,230,-100]).tolist(),score=.97))
        for i in [2,3,6]:ee.append(dict(a=0,b=i,matrix=np.eye(3).tolist(),score=.85))
        ps,good,bad=solve(scans,ee)
        np.testing.assert_allclose(ps[0],np.eye(3),atol=1e-5)
        self.assertEqual(len(bad),1);self.assertEqual((bad[0]['a'],bad[0]['b']),(0,1))
        self.assertNotIn(4,ps)

if __name__=='__main__':unittest.main()
