"""Delivered-array audit and exact reruns of the two prespecified failure cases."""
import json
import unittest
import numpy as np
import torch
from stage_a.common import fingerprint, verify as check_fingerprint, write_json
from stage_a.train import code_identity
from stage_a_readability_ordered.evaluate import check_measurement
from .experiment import RUN, PREVIOUS, load, saved_prediction
from .decoder import decode, ordered_flags, jump_flags


def run():
    torch.set_num_threads(2)
    plan=json.loads((RUN/'plan.json').read_text())
    prepared=json.loads((RUN/'preparation_checkpoint.json').read_text())
    check_fingerprint(prepared['plan'])
    check_fingerprint(plan['source_checkpoint'])
    old=torch.load(plan['source_checkpoint']['path'],map_location='cpu',weights_only=True)
    if code_identity()!=old['code_identity']: raise AssertionError('Original trainer identity changed')
    from stage_a.test_stage_a import StageATests
    from stage_a_readability_ordered.test_readability_ordered import ReadabilityTests
    from .test_decoder import ConservativeTests
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (StageATests,ReadabilityTests,ConservativeTests))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise AssertionError('Software checks failed')
    stages=[s for s in plan['stages'] if (RUN/s['name']/'checkpoint.json').exists()]
    thresholds=json.loads((PREVIOUS/'exploratory_thresholds.json').read_text())['thresholds']['simple']
    exact=0; count=0; all_pairs=0; fingerprints=[]
    for stage in stages:
        for r in [r for r in plan['records'] if r['split']=='validation']:
            path=RUN/stage['name']/'measurements'/(r['key']+'.npz')
            d=load(path); t=load(PREVIOUS/'cache'/(r['key']+'.npz')); p=saved_prediction(path)
            bands,disk=check_measurement(r,t,p)
            np.testing.assert_equal(disk,d['disk_retained_rows'])
            np.testing.assert_equal(np.stack(list(bands.values())),d['experimental_thickness_um'])
            if d['validated'] or not d['experimental'] or not np.isnan(d['validated_thickness_um']).all(): raise AssertionError('Experimental contract')
            if ordered_flags(p['retained_rows']).any(): raise AssertionError('Nonadjacent retained crossing')
            if jump_flags(p['retained_rows'],p['retained'],stage['max_step_px'],0).any(): raise AssertionError('Unbroken jump')
            if np.any(abs(p['retained_rows']-t['raw_rows'])[p['retained']]>stage['max_displacement_px']+1e-5): raise AssertionError('Excess relocation')
            parent=saved_prediction(RUN/stage['parent']/'measurements'/(r['key']+'.npz')) if stage['parent'] else None
            if parent and (p['retained']&~parent['retained']).any(): raise AssertionError('Parent mask rescued')
            for k in range(8):
                for j in range(k+1,8): all_pairs+=int((p['retained'][k]&p['retained'][j]).sum())
            if r['key'] in plan['focus'][:2]:
                logits=np.load(PREVIOUS/'logits_validation'/(r['key']+'.npy'),allow_pickle=False)
                gate=np.ones(512,bool) if stage['gate_quantile'] is None else d['simple_score']<=thresholds[str(stage['gate_quantile'])]
                q=decode(logits,t['raw_rows'],t['entropy'],t['scope'],t['shadow'],stage,gate,parent)
                np.testing.assert_equal(q['reason_bits'],p['reason_bits'])
                np.testing.assert_equal(q['retained_rows'],p['retained_rows'])
                exact+=1
            fingerprints.append(fingerprint(path)); count+=1
    write_json(RUN/'measurement_fingerprints.json',fingerprints)
    write_json(RUN/'software_verification.json',dict(tests=result.testsRun,failures=0,measurement_files_checked=count,
        retained_surface_pairs_order_checked=all_pairs,exact_failure_case_reruns=exact,model_code_identity=code_identity(),
        epoch124_checkpoint_unchanged=True,training_updates=0,NaN_geometry_thickness_scope_parent_checks=True,
        final_test_accessed=False,repeatability_accessed=False))


if __name__=='__main__': run()
