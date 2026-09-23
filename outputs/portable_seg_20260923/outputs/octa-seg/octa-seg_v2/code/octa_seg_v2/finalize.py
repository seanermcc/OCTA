"""Seal round_000 after verification; keep reviewer feedback and later rounds mutable."""
import io
import unittest
from .common import *
from .policy import POLICY_REVISION

def run():
    complete=ROUND/'COMPLETE.json'
    if complete.exists():
        for fp in read(complete)['artifacts']:verify(fp)
        print('Frozen round_000 verified',flush=True);return
    suite=unittest.defaultTestLoader.loadTestsFromName('octa_seg_v2.test_contract');stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    path=writable(OUT/'tests/contract_tests.txt');path.write_text(stream.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():raise RuntimeError(stream.getvalue())
    assert read(OUT/'tests/gui_verification.json')['real_qt_events']
    assert read(OUT/'tests/volume_verification.json')['total_native_bscans']==5120
    assert read(OUT/'tests/neural_verification.json')['unknown_trace_has_zero_gradient']
    for sid in SCANS:
        assert read(ROUND/'volumes'/sid/'exported.json')['policy_revision']==POLICY_REVISION
    assert len(list((ROUND/'figures').glob('*/*.png')))==90
    from .verify import protect
    protect()
    outputs=sorted(p for p in ROUND.rglob('*') if p.is_file() and p.name!='COMPLETE.json')
    summary=[]
    for sid in SCANS:
        d=read(ROUND/'volumes'/sid/'exported.json');summary.append(dict(scan_id=sid,n_bscans=512,solid_pct=100*d['v2_reported_fraction'],candidate_pct=100*d['v2_candidate_fraction'],v1_matched_solid_pct=100*d['matched_baseline_reported_fraction']))
    table(OUT/'TEN_VOLUME_SUMMARY.csv',summary)
    write(complete,dict(version='octa-seg_v2',round='round_000',policy_revision=POLICY_REVISION,scans=SCANS,
        total_bscans=5120,model_trained=False,tests_run=result.testsRun,experimental=True,
        artifacts=[fingerprint(p) for p in outputs]))
    source_files=list((OUT/'code/octa_seg_v2').glob('*.py'))
    write(OUT/'RELEASE.json',dict(status='round_000 complete; user feedback/training rounds remain separate',round=fingerprint(complete),
        implementation=[fingerprint(p) for p in source_files],
        tests=[fingerprint(p) for p in (OUT/'tests').glob('*') if p.is_file()],
        new_work_confined_to=str(OUT),existing_gui_files_unchanged=True,new_model_learning=False))
    print('Sealed octa-seg_v2 round_000: ten volumes, 5120 B-scans, 90 figures.',flush=True)

if __name__=='__main__':run()
