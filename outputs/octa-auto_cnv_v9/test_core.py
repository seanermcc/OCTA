import unittest,copy
from common import *
from audit import validate_target
from context import build_context
from training import windows
class CoreTests(unittest.TestCase):
 def test_round_trip_edges(self):
  x=np.zeros((512,512),bool);x[0,:]=True;x[511,511]=True
  np.testing.assert_array_equal(decode(encode(x)),x)
  with self.assertRaises(ValueError):decode([[0,0,3],[0,2,4]])
 def test_target_contract(self):
  a=dict(scan_id='synthetic',source_identity='synthetic')
  s=dict(regions=[dict(id='kept',state='kept',runs=[[0,0,4]]),dict(id='removed',state='removed',runs=[[0,2,6]]),dict(id='ignored',state='unsure',runs=[[0,3,5]])],absence=False,confirmation=None,defer_reason='')
  s['confirmation']=dict(whole_field_checked=True,annotation_sha256=digest({k:s[k] for k in ('regions','absence')}),completion_revision=1,ignored_conflict_pixels=1)
  p=decode([[0,0,3]]);ig=decode([[0,3,5]])
  d=dict(schema='cnv-model1-correction-v8.1',synthetic=False,**a,native_shape=[512,512],axis_order='B-scan,A-line',state=s,revision=1,kind='positive',masks=dict(positive=encode(p),reviewed_background=encode(~(p|ig)),ignored=encode(ig)))
  z,kind=validate_target(d,a);self.assertTrue(z['target'][0,2]);self.assertFalse(z['known'][0,3]);self.assertTrue(z['known'][0,5]);self.assertFalse(z['target'][0,5])
  bad=copy.deepcopy(d);bad['state']['regions'][0]['runs']=[[0,0,2]]
  with self.assertRaises(ValueError):validate_target(bad,a)
 def test_unknown_not_absence(self):
  zero=np.zeros((512,512),bool);z=dict(vessel_mask=zero,onh_mask=zero)
  r=dict(excluded_from_analysis=False,vessel_reviewed=False,onh_reviewed=False,selection='frozen_v1',onh_visibility='Not assessed',notes='',masks_sha256='x',source_sha256='y',revision=None)
  x,p=build_context(z,r);self.assertTrue(x[2].all());self.assertFalse(x[3].any())
  r['onh_reviewed']=True;x,p=build_context(z,r);self.assertTrue(x[3].all());self.assertFalse(x[1].any())
  r['excluded_from_analysis']=True
  with self.assertRaises(ValueError):build_context(z,r)
 def test_pool_windows(self):
  x=np.zeros((512,512),bool);x[511,511]=True;c=windows(x);self.assertEqual(c.shape,(257,257));self.assertEqual(c[-1,-1],1);self.assertEqual(c[0,0],0)
 def test_fold_separation(self):
  p=read(HERE/'data/protocol.json');seen=[]
  for f in p['folds']:
   self.assertFalse(set(f['train_animals'])&set(f['evaluation_animals']));seen+=f['evaluation_animals']
   for i in f['inner']:
    self.assertFalse(set(i['train_animals'])&set(i['candidate_animals']));self.assertFalse((set(i['train_animals'])|set(i['candidate_animals']))&set(f['evaluation_animals']))
  self.assertEqual(len(seen),len(set(seen)))
if __name__=='__main__':unittest.main()
