import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from scipy.ndimage import gaussian_filter
from skimage.transform import EuclideanTransform
from . import CONFIG
from .io import save,sha,select_masks,assessable_onh,write,read,load_scan
from .geometry import register,features,apply,pixel_to_physical,build_components,onh_fit
from .pipeline import pair_signature,match_pair
from control_map_v1.geometry import register as inherited_register,features as inherited_features

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.row=dict(scan_id='TS1_OD_2020-01-01_s01',animal='TS1',eye='OD',session_date='2020-01-01',source='C:/OCTA_RawData/a.mat')
        self.shape=(12,16);self.empty=np.zeros(self.shape,bool);self.side={'geometry':{'path':str(self.root/self.row['scan_id']/'geometry.npz')}}
        save(self.side['geometry']['path'],vessel=~self.empty,native_shape=np.array([12,16,100]))
        self.side['geometry']['sha256']=sha(self.side['geometry']['path'])
        self.path=self.root/'mask.npz'
        self.arrays=dict(vessel_mask=self.empty,onh_mask=self.empty,scan_id=np.array(self.row['scan_id']),source_volume=np.array(self.row['source']),
            axis_order=np.array('B-scan,A-line'),native_shape=np.array(self.shape),excluded_from_analysis=np.array(False))
        save(self.path,**self.arrays)
        self.rec=dict(self.row,source_volume=self.row['source'],masks='mask.npz',masks_sha256=sha(self.path),excluded_from_analysis=False,
                      onh_reviewed=False,onh_visibility='Not assessed',vessel_reviewed=False,selection='saved_manual')
    def load(self,records=None):return select_masks(self.row,self.side,self.shape,{self.row['scan_id']:self.rec} if records is None else records,self.root)
    def test_selected_empty_draft_never_falls_back(self):
        a,p=self.load();self.assertFalse(a['vessel_mask'].any());self.assertEqual(p['mask_source'],'primary_export');self.assertFalse(p['onh_assessable'])
    def test_fallback_only_when_absent(self):
        a,p=self.load({});self.assertTrue(a['vessel_mask'].all());self.assertFalse(p['onh_available']);self.assertNotIn('onh_mask',a)
    def test_hash_mismatch_blocks_does_not_fallback(self):
        self.rec['masks_sha256']='bad'
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.load()
    def test_grid_mismatch_blocks(self):
        self.arrays['vessel_mask']=self.empty.T;save(self.path,**self.arrays);self.rec['masks_sha256']=sha(self.path)
        with self.assertRaisesRegex(ValueError,'grid mismatch'):self.load()
    def test_identity_mismatch_blocks(self):
        self.rec['source_volume']='different.mat'
        with self.assertRaisesRegex(ValueError,'identity mismatch'):self.load()
    def test_fallback_hash_mismatch_blocks(self):
        self.side['geometry']['sha256']='bad'
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.load({})
    def test_exclusion_preserved(self):
        self.arrays['excluded_from_analysis']=np.array(True);save(self.path,**self.arrays);self.rec.update(excluded_from_analysis=True,masks_sha256=sha(self.path),exclusion_reason='artifact')
        _,p=self.load();self.assertTrue(p['excluded_from_analysis']);self.assertEqual(p['exclusion_reason'],'artifact')
    def test_onh_review_is_independent(self):
        self.rec['vessel_reviewed']=True;self.assertFalse(assessable_onh(self.rec))
        self.rec.update(onh_reviewed=True,onh_visibility='Cannot judge');self.assertFalse(assessable_onh(self.rec))
        self.rec['onh_visibility']='Partially visible — outlined';self.assertTrue(assessable_onh(self.rec))
    def test_optional_inventory_dimensions_use_verified_sidecar(self):
        inputs=self.root/'inputs';inputs.mkdir();p=inputs/(self.row['scan_id']+'.npz')
        save(p,optical=np.ones((2,*self.shape),dtype='float32'))
        side=dict(self.side,scan_id=self.row['scan_id'],source={'path':self.row['source']},axis_order='B-scan,A-line',
                  orientation_fresh_detected=True,native_shape=[*self.shape,100],optical_cache={'sha256':sha(p)})
        write(p.with_suffix('.json'),side)
        arrays,info=load_scan(self.row,self.root/'inventory.json',{self.row['scan_id']:self.rec},self.root)
        self.assertEqual(info['shape'],list(self.shape));self.assertIn('absent',info['grid_provenance'])
        row=dict(self.row,n_slow=99,n_fast=16)
        with self.assertRaisesRegex(ValueError,'Inventory grid mismatch'):load_scan(row,self.root/'inventory.json',{self.row['scan_id']:self.rec},self.root)
    def test_uncertain_onh_does_not_manufacture_boundary(self):
        y,x=np.indices((101,101));mask=(x-50)**2+(y-50)**2<20**2
        arrays=dict(selected_onh_mask=mask,selected_onh_region_excluded=np.ones_like(mask),spacing=[2,2])
        r=onh_fit(arrays,dict(onh_available=True,onh_assessable=True),CONFIG)
        self.assertFalse(r['resolved'])

class TransformTests(unittest.TestCase):
    def info(self,s):return dict(scan_id=s,animal='TS1',eye='OD',session_date='2020-01-01',shape=[120,160],spacing=[3.,2.],status='prepared',signature=s,branches=[],onh_assessable=False)
    def pair(self,a,b,mat,residual=1):return dict(pair_id=a+'__'+b,scan_a=a,scan_b=b,matrix=np.asarray(mat).tolist(),status='automatic_proposal',residual_um=residual)
    def test_pixel_spacing_inverse_and_composition(self):
        t=EuclideanTransform(rotation=.17,translation=[25,-19]).params;p=pixel_to_physical([3,2]);xy=np.array([[5,10],[7,9]])
        np.testing.assert_allclose(apply(xy,t@p),apply(apply(xy,p),t));np.testing.assert_allclose(apply(apply(xy,t@p),np.linalg.inv(t@p)),xy)
    def test_singletons_and_disconnected(self):
        infos={s:self.info(s) for s in 'abc'};cs,ts=build_components(infos,[self.pair('a','b',np.eye(3))],CONFIG)
        self.assertEqual(sorted(len(c['members']) for c in cs),[1,2]);np.testing.assert_equal(ts['c']['matrix_to_component'],np.eye(3))
    def test_loop_inconsistent(self):
        infos={s:self.info(s) for s in 'abc'};bad=np.eye(3);bad[0,2]=100
        ps=[self.pair('a','b',np.eye(3)),self.pair('b','c',np.eye(3)),self.pair('a','c',bad,3)]
        cs,ts=build_components(infos,ps,CONFIG);self.assertEqual(cs[0]['status'],'withheld_loop_inconsistent')
    def test_onh_disagreement_does_not_invalidate_registration(self):
        infos={s:self.info(s) for s in 'ab'}
        for s,x in [('a',0),('b',500)]:infos[s].update(onh_assessable=True,visible_onh=dict(resolved=True,center_um=[x,0],uncertainty_um=2,diameter_um=200))
        cs,_=build_components(infos,[self.pair('a','b',np.eye(3))],CONFIG)
        self.assertEqual(cs[0]['status'],'automatic_proposal');self.assertTrue(cs[0]['onh_disagreements'])
    def test_cross_eye_forbidden(self):
        infos={s:self.info(s) for s in 'ab'};infos['b']['eye']='OS'
        with self.assertRaises(ValueError):build_components(infos,[self.pair('a','b',np.eye(3))],CONFIG)
    def test_matcher_is_inherited_and_deterministic(self):
        self.assertIs(register,inherited_register);self.assertIs(features,inherited_features)
        rng=np.random.default_rng(20);image=gaussian_filter(rng.normal(size=(120,160)),1);v=rng.random(image.shape)>.65
        a=dict(enface=image,vessel=v,registration_blocked=np.zeros_like(v),spacing=np.array([3.,2.]))
        b=dict(a,enface=np.roll(image,5,axis=1),vessel=np.roll(v,5,axis=1))
        pts=rng.uniform(40,220,(25,2));desc=rng.random((25,256))>.5
        fa=dict(points=pts,descriptors=desc,branches=pts[:6]);fb=dict(fa,points=pts+[10,0],branches=pts[:6]+[10,0])
        result=register(a,b,fa,fb,CONFIG);self.assertEqual(result,inherited_register(a,b,fa,fb,CONFIG));self.assertTrue(result['verified'])
        np.testing.assert_allclose(np.asarray(result['matrix'])[:2,2],[10,0],atol=1e-8)
        self.assertEqual(result,register(a,b,fa,fb,CONFIG))
        no=dict(fb,points=pts+[10000,0],branches=pts[:6]+[10000,0]);self.assertFalse(register(a,b,fa,no,CONFIG)['verified'])
    def test_empty_masks_and_features_reject(self):
        rng=np.random.default_rng(0);image=rng.normal(size=(128,128));z=np.zeros_like(image,bool)
        f=features(image,z,z,[2,3]);a=dict(enface=image,vessel=z,registration_blocked=z,spacing=[2,3])
        self.assertFalse(register(a,a,f,f,CONFIG)['verified'])
    def test_input_signature_invalidates_resume(self):
        a,b=self.info('a'),self.info('b');pin={'signature':'code-config-source'}
        sig=pair_signature(a,b,pin);self.assertEqual(sig,pair_signature(a,b,pin));a['signature']='changed-input-hash';self.assertNotEqual(sig,pair_signature(a,b,pin))
    def test_excluded_pair_is_blocked(self):
        a,b=self.info('a'),self.info('b');a['status']='excluded';a['exclusion_reason']='artifact'
        r=match_pair(a,b,{},CONFIG,{'signature':'x'});self.assertEqual(r['status'],'blocked');self.assertIn('artifact',r['reason'])
    def test_pair_exceptions_do_not_abort_next_eye(self):
        a,b=self.info('a'),self.info('b');arr={s:{'feature_'+k:np.empty((0,2)) for k in ('points','descriptors','branches')} for s in 'ab'}
        with patch('octa_reg_v1.pipeline.register',side_effect=RuntimeError('synthetic software failure')):
            r=match_pair(a,b,arr,CONFIG,{'signature':'x'});self.assertEqual(r['status'],'implementation_failure')
        a['status']='excluded';self.assertEqual(match_pair(a,b,{},CONFIG,{'signature':'x'})['status'],'blocked')
    def test_failed_estimation_sentinel_is_an_algorithm_rejection(self):
        class Failed:
            def __bool__(self):return False
            def __getattr__(self,key):raise RuntimeError('Failed estimation has no '+key)
        a,b=self.info('a'),self.info('b');pts=np.arange(20).reshape(10,2)
        arr={s:dict(feature_points=pts,feature_descriptors=np.eye(10,dtype=bool),feature_branches=pts[:4]) for s in 'ab'}
        with patch('octa_reg_v1.pipeline.register',return_value=dict(verified=False,reason='insufficient vessel-anchored structural matches')),patch('skimage.measure.ransac',return_value=(Failed(),np.zeros(10,bool))):
            r=match_pair(a,b,arr,CONFIG,{'signature':'x'})
        self.assertEqual(r['status'],'rejected');self.assertIsNone(r['matrix']);self.assertNotIn('failed_consensus_matrix',r)

if __name__=='__main__':unittest.main()
