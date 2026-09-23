import unittest
from common import *
from candidates import *
class CandidateTests(unittest.TestCase):
 def setup_case(self):
  score=np.zeros((512,512),np.float32);score[10:20,10:20]=.9;score[30,30]=.8
  context=np.zeros((11,512,512),np.float32);context[2]=1
  return score,context
 def test_small_and_irregular_preserved(self):
  p,c=self.setup_case();p[15,20:40]=.9
  labels,rr=extract(p,c);self.assertEqual(len(rr),2);self.assertEqual(sum(r['area_pixels'] for r in rr),int((p>=.7).sum()));self.assertEqual(rr[1]['area_pixels'],1)
  self.assertAlmostEqual(rr[1]['area_um2'],(1460/512)**2)
 def test_candidate_matching_unknown_split_merge(self):
  p,c=self.setup_case();labels,rr=extract(p,c);truth=p>=.85;known=np.ones_like(truth);known[29:32,29:32]=False
  z=dict(target=truth,known=known,instances=truth[None]);correspondence(labels,rr,z)
  self.assertEqual(rr[0]['match']['label'],1);self.assertIsNone(rr[1]['match']['label'])
  # One prediction touching two human footprints must be ambiguous to scorer.
  a=truth.copy();a[:,15:]=False;b=truth.copy();b[:,:15]=False;z['instances']=np.stack([a,b]);correspondence(labels,rr,z);self.assertTrue(rr[0]['match']['merge']);self.assertIsNone(rr[0]['match']['label'])
  # Two predictions touching one human footprint are split and not fitted as true.
  p[10:20,14:16]=0;labels,rr=extract(p,c);z['instances']=truth[None];correspondence(labels,rr,z);self.assertTrue(rr[0]['match']['split']);self.assertIsNone(rr[0]['match']['label'])
 def test_background_false_and_negative_metrics(self):
  p,c=self.setup_case();labels,rr=extract(p,c);zero=np.zeros_like(p,bool);z=dict(target=zero,known=~zero,instances=np.zeros((0,512,512),bool));correspondence(labels,rr,z)
  self.assertTrue(all(r['match']['label']==0 for r in rr));m=metrics(labels,rr,z);self.assertEqual(m['false_positive_candidates'],2);self.assertEqual(m['dice'],0)
 def test_score_geometry_and_missing_flags(self):
  p,c=self.setup_case();labels,rr=extract(p,c);examples=[]
  for i in range(20):
   r=dict(rr[i%2]);r.update(animal='a'+str(i%3),match=dict(label=int(i%2==0)));examples.append(r)
  scorer=fit_scorer(examples,dict(synthetic=True));adj=adjust(rr,scorer)
  self.assertTrue(scorer['fitted']);self.assertEqual([r['runs'] for r in rr],[r['runs'] for r in adj]);self.assertTrue(all(r['missing_context'] for r in adj))
  self.assertTrue(all(0<=r['adjusted_score']<=1 for r in adj))
  rr[0]['area_pixels']=999999;self.assertTrue(adjust(rr,scorer)[0]['size_extrapolation'])
if __name__=='__main__':unittest.main()
