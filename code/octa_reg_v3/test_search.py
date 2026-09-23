import unittest
import numpy as np
from scipy import ndimage as ndi
from octa_reg_v2.run import matrix
from .search import distance,lesion_metrics,evaluate

def field():
    sk=np.zeros((512,512),bool)
    for y in range(65,480,75):sk[y,30:480]=True
    for x in range(60,490,80):sk[30:480,x]=True
    vessel=ndi.binary_dilation(sk,iterations=2);pts=np.argwhere(sk)[:,::-1].astype(float)
    image=ndi.gaussian_filter(vessel.astype(float),1)
    return dict(info=dict(session_date='2025-01-01',spacing=[1460/512]*2),points=pts,dt=ndi.distance_transform_edt(~sk),
        image=image,detail=image,vessel=vessel,valid=np.ones_like(sk),thin_pts=pts,thin_dt=ndi.distance_transform_edt(~sk),
        lesions=np.array([[180.,210.]]),cnv_meta=dict(weight=1.))

class SearchTests(unittest.TestCase):
    def test_cnv_only_cannot_accept(self):
        a=field();b=field();b['dt'][:]=100;b['thin_dt'][:]=100;b['vessel'][:]=False
        r=evaluate(a,b,np.eye(3))
        self.assertEqual(r['cnv_support'],1.)
        self.assertFalse(r['vessel_gate']);self.assertFalse(r['small_gate'])
    def test_time_and_confidence_weights(self):
        a=field();b=field();same=lesion_metrics(a,b,np.eye(3))
        b['info']['session_date']='2025-02-01';later=lesion_metrics(a,b,np.eye(3))
        self.assertLess(later['cnv_weight'],same['cnv_weight'])
        b['cnv_meta']['weight']=.2;auto=lesion_metrics(a,b,np.eye(3))
        self.assertLess(auto['cnv_weight'],later['cnv_weight'])
    def test_absence_not_positive_match(self):
        a=field();b=field();a['lesions']=np.empty((0,2))
        self.assertIsNone(lesion_metrics(a,b,np.eye(3))['cnv_support'])
    def test_fine_detail_prefers_correct_pose(self):
        a=field();b=field();good=evaluate(a,b,np.eye(3));bad=evaluate(a,b,matrix([.1,23,-17]))
        self.assertGreater(good['detail_corr'],bad['detail_corr'])
        self.assertGreater(good['score'],bad['score'])
        self.assertTrue(good['vessel_gate'])
    def test_rigid_distance(self):
        self.assertEqual(distance(np.eye(3),np.eye(3)),0.)
        self.assertGreater(distance(np.eye(3),matrix([.2,0,0])),20)

if __name__=='__main__':unittest.main()
