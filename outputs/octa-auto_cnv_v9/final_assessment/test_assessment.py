"""Selection policy and persistent review safety checks; isolated synthetic records."""
import tempfile
import unittest
from pathlib import Path
from build import choose
from server import AssessmentStore, Conflict, read

class PolicyTests(unittest.TestCase):
    def test_requested_rules(self):
        self.assertEqual(choose(None,dict(confirm_m2=True,review_model3=True)),('m2','confirmed_m2_review_m3'))
        self.assertEqual(choose(None,dict(confirm_m2=True,confirm_m3=True)),('m3','both_confirmed_prefer_m3'))
        self.assertEqual(choose(None,dict(review_model3=True)),('excluded','correction_review'))
        self.assertEqual(choose(None,dict(no_cnv_present=True)),('excluded','confirmed_no_cnv'))
        self.assertEqual(choose(None,{}),('excluded','unconfirmed'))
    def test_training_precedence(self):
        self.assertEqual(choose({'kind':'positive'},dict(confirm_m2=True,confirm_m3=True))[0],'manual')
        self.assertEqual(choose({'kind':'positive'},dict(review_model3=True))[0],'manual')
        self.assertEqual(choose({'kind':'negative'},dict(confirm_m3=True))[0],'excluded')

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.data={'cases':[dict(scan_id='synthetic',token='token',source='manual',mask_sha256='mask')]}
        self.store=AssessmentStore(self.data,self.root)
    def tearDown(self): self.tmp.cleanup()
    def payload(self,**kw):
        return dict(scan_id='synthetic',token='token',expected_revision=0,status='review',notes='Synthetic test',**kw)
    def test_persistence_and_history(self):
        first=self.store.save(self.payload()); self.assertEqual(first['revision'],1)
        fresh=AssessmentStore(self.data,self.root); self.assertEqual(fresh.head('synthetic'),first)
        p=self.payload();p.update(expected_revision=1,status='good',notes='')
        second=fresh.save(p); self.assertEqual(second['revision'],2)
        self.assertEqual(read(self.root/'history/synthetic/000001.json'),first)
        self.assertEqual(fresh.save({**p,'expected_revision':2}),second)
    def test_stale_tab_and_changed_mask(self):
        self.store.save(self.payload())
        with self.assertRaises(Conflict): self.store.save(self.payload())
        self.data['cases'][0]['token']='changed'
        with self.assertRaises(Conflict): AssessmentStore(self.data,self.root).head('synthetic')
    def test_unknown_and_invalid(self):
        for delta in [dict(scan_id='../escape'),dict(status='confirmed_training'),dict(notes='x'*4001),dict(expected_revision=True)]:
            with self.assertRaises(ValueError): self.store.save({**self.payload(),**delta})
        self.assertFalse((self.root/'decisions').exists())
    def test_bulk_preserves_flags_notes_and_secondary(self):
        self.data['cases'].append(dict(scan_id='second',token='t2',source='m3',mask_sha256='m2'))
        self.data['secondary_cases']=[dict(scan_id='poor',token='t3',source='deferred',mask_sha256='empty')]
        self.data['collection_token']='collection'
        store=AssessmentStore(self.data,self.root)
        self.assertEqual(store.head('second')['status'],'good')
        self.assertEqual(store.head('poor')['status'],'unassessed')
        flagged=store.save(self.payload())
        batch=store.confirm_all({'collection_token':'collection'})
        self.assertEqual((batch['confirmed'],batch['preserved_review']),(1,1))
        self.assertEqual(batch['records']['synthetic'],flagged)
        self.assertEqual(batch['records']['poor']['revision'],0)
        fresh=AssessmentStore(self.data,self.root)
        self.assertEqual(fresh.head('second')['status_origin'],'explicit_collection_confirmation')
        self.assertEqual(fresh.head('synthetic')['notes'],'Synthetic test')
        old=fresh.head('second')
        fresh.save(dict(scan_id='second',token='t2',expected_revision=old['revision'],status='review',notes='After bulk'))
        fresh.confirm_all({'collection_token':'collection'})
        self.assertEqual(AssessmentStore(self.data,self.root).head('second')['status'],'review')
        with self.assertRaises(Conflict): fresh.confirm_all({'collection_token':'stale'})

if __name__=='__main__': unittest.main(verbosity=2)
