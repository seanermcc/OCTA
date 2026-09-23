import unittest,uuid
from common import *
from review_store import ReviewStore,ReviewConflict

class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.root=HERE/'verification'/('test_'+uuid.uuid4().hex)
  asset=dest(self.root/'dummy.bin');asset.write_bytes(b'synthetic prediction only')
  status=[dict(model='v9_m'+str(n),prediction=fingerprint(asset),checkpoint=fingerprint(asset)) for n in (2,3)]
  write(self.root/'gallery/data.json',dict(selection_sha256='synthetic',cases=[dict(scan_id='synthetic',source_identity='fixture',status=status)]))
  write(self.root/'gallery/assets/synthetic/candidates.json',dict(m2=[dict(id=1,runs=[[1,2,4]],display_selected=True)],m3=[dict(id=2,runs=[[2,3,5]],display_selected=True)],manual=[]))
  self.store=ReviewStore(self.root/'gallery',self.root/'reviews')
 def payload(self,**changes):
  r=self.store.all()['records']['synthetic'];p=dict(expected_revision=r['revision'],token=r['token'],confirm_m2=False,confirm_m3=False,no_cnv_present=False,review_model3=False,notes='synthetic test');p.update(changes);return p
 def test_absence_survives_reload_and_uncheck(self):
  r=self.store.save('synthetic',self.payload(no_cnv_present=True));self.assertEqual(r['revision'],1)
  reloaded=ReviewStore(self.root/'gallery',self.root/'reviews');self.assertTrue(reloaded.all()['records']['synthetic']['no_cnv_present'])
  self.store.save('synthetic',self.payload(no_cnv_present=False));self.assertFalse(self.store.all()['records']['synthetic']['no_cnv_present'])
  self.assertTrue(read(self.root/'reviews/history/synthetic/000001.json')['no_cnv_present'])
 def test_conflicting_absence_or_correction_rejected(self):
  for values in [dict(no_cnv_present=True,confirm_m2=True),dict(no_cnv_present=True,confirm_m3=True),dict(confirm_m3=True,review_model3=True)]:
   with self.assertRaises(ValueError):self.store.save('synthetic',self.payload(**values))
  self.assertFalse((self.root/'reviews/decisions/synthetic.json').exists())
 def test_stale_revision_and_token_rejected(self):
  p=self.payload(confirm_m3=True);self.store.save('synthetic',p)
  with self.assertRaises(ReviewConflict):self.store.save('synthetic',p)
  with self.assertRaises(ReviewConflict):self.store.save('synthetic',self.payload(token='wrong'))
 def test_candidate_mutation_invalidates_decision(self):
  self.store.save('synthetic',self.payload(confirm_m3=True))
  p=self.root/'gallery/assets/synthetic/candidates.json';d=read(p);d['m3'][0]['runs']=[[3,4,6]];write(p,d)
  with self.assertRaises(ReviewConflict):self.store.all()
 def test_unconfirmed_is_not_negative(self):
  r=self.store.all()['records']['synthetic'];self.assertEqual(r['revision'],0);self.assertFalse(r['no_cnv_present'])
 def test_nonboolean_rejected(self):
  with self.assertRaises(ValueError):self.store.save('synthetic',self.payload(no_cnv_present=1))

class TrainingExportTests(unittest.TestCase):
 def test_exact_user_cohort_masks_and_preservation(self):
  m=read(HERE/'data/supervision.json');self.assertEqual(len(m['records']),101);self.assertEqual(m['eligible_counts'],dict(positive=73,negative=28))
  inventory=read(HERE/'data/inventory_snapshot.json');chosen={r['scan_id'] for r in inventory['selected_acquisitions'] if r['confirmed'] and r['kind'] in ('positive','negative')}
  self.assertEqual(chosen,{r['scan_id'] for r in m['records']})
  self.assertEqual(sum(len(r['regions']) for r in m['records']),156)
  for r in m['records']:
   verify(r['label']);verify(r['target_file']);z=npz(r['target_file']['path'])
   self.assertEqual(z['target'].shape,(512,512));self.assertTrue(np.array_equal(z['instances'].any(0),z['target']))
   self.assertFalse((z['target']&~z['known']).any());self.assertTrue(np.array_equal(z['ignored'],~z['known']))
   if r['kind']=='negative':self.assertTrue(z['known'].all());self.assertFalse(z['target'].any())

if __name__=='__main__':unittest.main(verbosity=2)
