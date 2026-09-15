import unittest
import numpy as np
from .feedback import resolve,training_targets
from .policy import apply,geometry_valid

CAL=[dict(not_traceable_cutoff=.1,trace_cutoff=.5,reliability_cutoff=.5,supported=True) for _ in range(8)]

def event(action,lo=10,hi=30,**kw):return dict(action=action,lo=lo,hi=hi,model_id='round_000',**kw)

class Contract(unittest.TestCase):
    def setUp(self):
        self.rows=np.broadcast_to(np.arange(8)[:,None]*25+10,(8,512)).astype(np.float32).copy()
        self.p=np.full((8,2,512),.9);self.v=np.zeros(512,bool)
    def policy(self,events=(),**kw):return apply(self.rows,self.p,CAL,self.v,0,256,feedback=resolve(events),**kw)
    def test_regional_only_negative_reliability(self):
        t=training_targets([event('unreliable_region')]);self.assertTrue((t['reliability_target'][:,10:30]==0).all())
        self.assertTrue((t['trace_target']==-1).all());self.assertFalse(t['manual_valid'].any());self.assertFalse(t['approved_valid'].any())
        self.assertTrue((t['reliability_event_provenance'][:,10:30]==0).all())
    def test_full_width_fallback_without_anchors(self):
        d=self.policy([event('unreliable_region',0,512)]);self.assertFalse(np.isfinite(d['reported_positions']).any());self.assertTrue(np.isfinite(d['uncertain_estimates']).all());self.assertTrue((d['candidate_source']==2).all())
    def test_exception_and_clear_restore(self):
        es=[event('affirm_measurable',boundaries=[0]),event('unreliable_region')]
        self.assertTrue((resolve(es)['reliability'][:,10:30]==0).all())
        es.append(event('affirm_measurable',15,20,boundaries=[0]));d=resolve(es)
        self.assertTrue((d['reliability'][0,15:20]==1).all());self.assertTrue((d['reliability'][1:,15:20]==0).all())
        es.append(event('clear_region'));d=resolve(es);self.assertTrue((d['reliability'][0,10:30]==1).all());self.assertTrue((d['reliability'][1:,10:30]==-1).all())
    def test_denial_and_exclusion_forbid_candidates(self):
        d=self.policy([event('unreliable_region',0,512),event('not_traceable',boundaries=[2]),event('exclude_image',40,60)])
        self.assertFalse(np.isfinite(d['uncertain_estimates'][2,10:30]).any());self.assertFalse(np.isfinite(d['uncertain_estimates'][:,40:60]).any())
    def test_ilm_policy_is_not_training_evidence(self):
        cal=[dict(c) for c in CAL];cal[0]['supported']=False
        d=apply(self.rows,self.p,cal,self.v,0,256);self.assertTrue((d['state'][0]==1).all());self.assertTrue((d['reason'][0]==12).all())
        self.assertTrue((training_targets([])['reliability_target']==-1).all())
    def test_invalid_geometry_never_filled(self):
        self.rows[0,15]=-1;self.rows[3,19]=self.rows[4,19]+1;self.rows[2,20]=np.nan;self.rows[3,20]=self.rows[1,20]-1
        d=self.policy([event('unreliable_region',0,512)]);self.assertFalse(np.isfinite(d['uncertain_estimates'][0,15]));self.assertFalse(np.isfinite(d['uncertain_estimates'][3,19]));self.assertFalse(np.isfinite(d['uncertain_estimates'][3,20]))
    def test_candidate_approval_not_measurability(self):
        es=[event('unreliable_region'),event('approve_position',10,12,boundaries=[1],positions={'1':[35,35]})]
        d=resolve(es);self.assertTrue(d['approved'][1,10:12].all());self.assertTrue((d['reliability'][1,10:12]==0).all())
        es.append(event('not_traceable',10,11,boundaries=[1]));self.assertFalse(resolve(es)['approved'][1,10])
        self.assertFalse(resolve(es,model_id='round_001')['approved'].any())
    def test_changed_position_revokes_approval(self):
        es=[event('approve_position',10,11,boundaries=[1],positions={'1':[35]}),event('correct',10,11,boundaries=[1],positions={'1':[36]})]
        d=resolve(es);self.assertFalse(d['approved'].any());self.assertTrue(d['manual'][1,10])
    def test_hidden_good_ratings_cannot_import(self):
        with self.assertRaises(ValueError):resolve([event('Good')])
    def test_automatic_denial_keeps_gap(self):
        self.p[3,0,10:30]=.01;d=self.policy([event('unreliable_region')]);self.assertFalse(np.isfinite(d['uncertain_estimates'][3,10:30]).any())
    def test_old_unreliable_guard_cannot_override_auto_trace_denial(self):
        self.p[3,0,10:30]=.01;rel=np.full((8,512),-1);rel[:,10:30]=0
        d=self.policy(guard=dict(reliability=rel));self.assertTrue((d['state'][3,10:30]==2).all());self.assertFalse(np.isfinite(d['uncertain_estimates'][3,10:30]).any())
    def test_context_preferred_with_provenance(self):
        c=np.full_like(self.rows,np.nan);c[3,12:15]=self.rows[3,12:15]+1
        d=self.policy([event('unreliable_region')],context=c);self.assertTrue((d['candidate_source'][3,12:15]==1).all());self.assertTrue((d['candidate_source'][3,15:30]==2).all())

if __name__=='__main__':unittest.main()
