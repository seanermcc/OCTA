import unittest
import numpy as np
from .cohort_graph import assemble,center,components
from .run import matrix

def scan(center_um=None,excluded=False):
    info=dict(spacing=[1,1],branches=[],onh_assessable=True)
    if center_um is not None:info['visible_onh']=dict(resolved=True,center_um=center_um,arc_deg=360)
    return dict(info=info,excluded=excluded)

def edge(a,b,translation=(0,0),accepted=True):
    return dict(a=a,b=b,matrix=matrix([0,*translation]).tolist(),accepted=accepted,score=.9,
                inliers=20,support=.9,dice=.85,span_px=80,overlap=.7,corr=.8)

class CohortTests(unittest.TestCase):
    def test_tentative_bridge_cannot_move_supported_backbone(self):
        scans=[scan([30,40]),scan(),scan()];good=[edge(0,1,(20,-10))]
        before=assemble(scans,good,good);weak=edge(1,2,(140,180),False)
        after=assemble(scans,good,good+[weak])
        for i in ['0','1']:np.testing.assert_array_equal(before['poses'][i],after['poses'][i])
        self.assertEqual(after['tiers']['2'],'uncertain');self.assertIn('2',after['poses'])

    def test_exclusion_is_never_an_anchor_or_proposal(self):
        scans=[scan([30,40],True),scan(),scan()]
        r=assemble(scans,[edge(1,2)],[edge(0,1,accepted=False),edge(1,2)])
        self.assertNotIn('0',r['poses']);self.assertEqual(r['tiers']['0'],'excluded');self.assertEqual(r['reference'],1)

    def test_parallel_vessels_do_not_invent_onh(self):
        info=dict(spacing=[1,1],branches=[dict(point=[100,y],direction=[1,0],accepted=True,length_um=300) for y in [50,100,200]])
        c,kind=center(info);self.assertIsNone(c);self.assertEqual(kind,'unresolved')

    def test_anatomy_only_attachment_is_uncertain(self):
        scans=[scan([20,30]),scan([-80,-90])]
        r=assemble(scans,[],[])
        self.assertEqual(r['tiers']['1'],'uncertain')
        np.testing.assert_allclose(np.array(r['poses']['1'])[:2,2],[80,90])

    def test_no_defensible_connection_keeps_field_unlocalized(self):
        r=assemble([scan(),scan()],[],[])
        self.assertEqual(r['tiers']['1'],'unlocalized');self.assertNotIn('1',r['poses']);self.assertEqual(r['origin_kind'],'unresolved')

    def test_component_partition_keeps_all_singletons(self):
        self.assertEqual(components([0,1,2,3],[edge(1,2)]),[(1,2),(0,),(3,)])

    def test_reviewed_onh_constrains_large_rotation(self):
        from PIL import Image,ImageDraw
        from scipy import ndimage as ndi
        from .test_registration import scan as mask_scan
        from .cohort_anatomy import anchored_match
        from .run import apply
        image=Image.new('L',(512,512));d=ImageDraw.Draw(image)
        for line in [[(240,220),(285,350),(420,480)],[(240,220),(365,170),(480,115)],[(240,220),(170,260),(40,340)],[(285,350),(160,370),(80,450)]]:
            d.line(line,fill=255,width=7)
        a=mask_scan(np.asarray(image)>0);c=np.array([240.,220.]);theta=np.deg2rad(155)
        true=matrix([theta,0,0]);true[:2,2]=c-true[:2,:2]@c;inv=np.linalg.inv(true)
        warped=ndi.affine_transform(a['vessel'].astype(np.uint8),inv[:2,:2][::-1,::-1],inv[:2,2][::-1],order=0)>0
        b=mask_scan(warped)
        for s in [a,b]:s['info']=scan(c.tolist())['info']
        r=anchored_match(a,b);self.assertTrue(r['accepted'])
        points=np.array([[100,100],[300,300],[400,100]])
        self.assertLess(np.linalg.norm(apply(points,np.array(r['matrix']))-apply(points,true),axis=1).max(),3)
        from .cohort import curve_pair
        r=curve_pair(a,b);self.assertTrue(r['accepted'])
        self.assertLess(np.linalg.norm(apply(points,np.array(r['matrix']))-apply(points,true),axis=1).max(),3)

if __name__=='__main__':unittest.main()
