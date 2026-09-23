"""Synthetic review records only; never approves a real acquisition."""
from common import *
from review_store import ReviewStore,ReviewConflict
import tempfile,unittest

class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='review-test-',dir=HERE/'verification')
  self.store=ReviewStore(HERE/'verification/ui_fixture',self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def payload(self,sid='SYNTHETIC_0',**updates):
  r=self.store.all()['records'][sid]
  p=dict(expected_revision=r['revision'],token=r['token'],confirm_m1=False,confirm_m2_adjusted=False,review_model2=False,notes='')
  p.update(updates);return p
 def test_persistence_history_conflicts_and_queue(self):
  p=self.payload(confirm_m1=True,confirm_m2_adjusted=True)
  r=self.store.save('SYNTHETIC_0',p)
  self.assertFalse(r['needs_target_resolution'])
  self.assertTrue(r['accepted_outline_variation'])
  self.assertEqual(r['preferred_shared_target_model'],'m2_adjusted')
  self.assertEqual(r['model_specific_target_models'],{'m1':'m1','m2':'m2_adjusted'})
  self.assertFalse(r['training_exported'])
  self.assertEqual(r['prediction_contract']['models']['m2_adjusted']['candidate_ids'],[1])
  old=sha(Path(self.tmp.name)/'history/SYNTHETIC_0/000001.json')
  with self.assertRaises(ReviewConflict):self.store.save('SYNTHETIC_0',p)
  reopened=ReviewStore(self.store.gallery,self.tmp.name)
  self.assertTrue(reopened.all()['records']['SYNTHETIC_0']['confirm_m1'])
  r=self.store.save('SYNTHETIC_0',self.payload(confirm_m1=True,review_model2=True,notes='Correct edge'))
  self.assertFalse(r['confirm_m2_adjusted'])
  self.assertEqual(r['preferred_shared_target_model'],'m1')
  self.assertIsNone(r['model_specific_target_models']['m2'])
  self.assertEqual(len(self.store.queue()['acquisitions']),1)
  self.assertEqual(sha(Path(self.tmp.name)/'history/SYNTHETIC_0/000001.json'),old)
  self.store.save('SYNTHETIC_0',self.payload())
  self.assertEqual(self.store.queue()['acquisitions'],[])
  self.assertIsNone(self.store.all()['records']['SYNTHETIC_0']['preferred_shared_target_model'])
 def test_no_cnv_requires_explicit_confirmation(self):
  initial=self.store.all()['records']['SYNTHETIC_1'];self.assertFalse(initial['confirm_m1'])
  r=self.store.save('SYNTHETIC_1',self.payload('SYNTHETIC_1',confirm_m1=True))
  self.assertEqual(r['prediction_contract']['models']['m1']['area_pixels'],0)
  self.assertTrue(r['confirm_m1']);self.assertFalse(r['confirm_m2_adjusted'])
 def test_invalid_or_stale_decisions_rejected(self):
  for changes in [dict(token='stale'),dict(confirm_m2_adjusted=True,review_model2=True),dict(confirm_m1=1),dict(notes='x'*4001),dict(expected_revision=-1)]:
   with self.assertRaises(ValueError):self.store.save('SYNTHETIC_0',self.payload(**changes))
  with self.assertRaises(ValueError):self.store.save('../outside',self.payload())
  self.assertEqual(self.store.all()['records']['SYNTHETIC_0']['revision'],0)
 def test_prediction_changes_reject_saved_decisions(self):
  self.store.save('SYNTHETIC_0',self.payload(confirm_m1=True))
  self.store.data['selection_sha256']='different-selection'
  with self.assertRaises(ReviewConflict):self.store.all()
 def test_legacy_both_good_preserves_original_record(self):
  r=self.store.save('SYNTHETIC_0',self.payload(confirm_m1=True,confirm_m2_adjusted=True,notes='Both are good; boundary uncertain'))
  path=Path(self.tmp.name)/'decisions/SYNTHETIC_0.json'
  r['needs_target_resolution']=True
  write(path,r);before=sha(path)
  view=self.store.all()['records']['SYNTHETIC_0']
  self.assertFalse(view['needs_target_resolution'])
  self.assertTrue(view['historical_target_resolution_requirement_superseded'])
  self.assertEqual(view['preferred_shared_target_model'],'m2_adjusted')
  self.assertEqual(view['notes'],'Both are good; boundary uncertain')
  self.assertEqual(sha(path),before)

if __name__=='__main__':unittest.main()
