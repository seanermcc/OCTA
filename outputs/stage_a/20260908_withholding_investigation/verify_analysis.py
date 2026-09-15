"""Run existing synthetic suite without its writes into the frozen v2 folder."""
import json
import shutil
import unittest
from pathlib import Path
import numpy as np
import torch
import stage_a.test_stage_a as tests
from stage_a.common import write_json
from investigate import OUT,V2,V3,package_hash,fstat
import readability_helpers_snapshot as rd

fixture=OUT/'test_fixture'
fixture.mkdir(exist_ok=True)
for name in ('manifest.json','partitions.json','historical_cohort.json'):
    shutil.copyfile(V2/name,fixture/name)
tests.DEFAULT=fixture
torch.set_num_threads(2)
suite=unittest.defaultTestLoader.loadTestsFromTestCase(tests.StageATests)
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
D=rd.load_npz(V3/'features/columns.npz')
A=rd.load_npz(OUT/'analysis_arrays.npz')
reason=A['reason']; ret=D['existing_retained']; hp=D['human_positive']; hn=D['human_negative']
assert np.array_equal(ret,reason==0)
assert int((hp&~ret).sum())==18870
assert int(ret[hn].sum())==17590
assert int(hn.sum())==9723
assert int((((reason&8)!=0).any(1)&hn).sum())==7447
for name,r in A.items():
    if name.startswith('retained_'):
        assert not np.any(r&~ret),name
assert np.array_equal(A['retained_whole_crossing_count_ge8'],ret)
matched=json.loads((OUT/'matched_supported_coverage.json').read_text())
assert all(abs(r['count_mismatch'])<=3 for r in matched)
before=json.loads((OUT/'integrity_before.json').read_text())
assert before['files']==fstat()
assert before['package_hashes']==package_hash()
write_json(OUT/'test_results.json',dict(existing_suite_tests=result.testsRun,
    success=result.wasSuccessful(),frozen_audit_counts_reproduced=True,
    masks_only_remove_measurements=True,all8_rule_correctly_noop=True,
    matched_count_max_difference=max(abs(r['count_mismatch']) for r in matched),
    test_fixture='Metadata copies only; no final-test arrays read',
    package_and_frozen_artifacts_unchanged=True))
print('Existing 16 tests and independent frozen-array checks passed.')
