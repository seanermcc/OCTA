"""Final cohort reconciliation and output integrity checks."""
from batch import *

def audit():
    from check_metrics import run_checks
    from qc import aggregate
    check_dependencies();run_checks();m=manifest();expected={r['scan_id'] for r in m['scans']}
    match=read(OUT/'verification/longitudinal_v1_exact_match.json');assert match['all_arrays_equal']
    verify(match['reference']);verify(match['batch'])
    records=[]
    for i,r in enumerate(m['scans'],1):
        sid=r['scan_id'];o=directory(sid);proof=read(o/'qc_complete.json');assert proof['schema_version']==2
        verify(r['source_fingerprint'])
        for fp in proof['inputs']+proof['artifacts']:verify(fp)
        assert read(o/'prepared.json')['source']==r['source_fingerprint']
        records.append(dict(scan_id=sid,checks_passed=True,reused=proof['reused']))
        print(f'Integrity verified {i}/{len(expected)}: {sid}',flush=True)
    aggregate()
    scans=csvread(OUT/'scan_qc.csv');boundaries=csvread(OUT/'boundary_qc.csv');layers=csvread(OUT/'layer_qc.csv')
    assert len(scans)==len(expected) and {r['scan_id'] for r in scans}==expected
    assert len(boundaries)==8*len(expected) and len({(r['scan_id'],r['boundary']) for r in boundaries})==len(boundaries)
    from eight_surface.config import LAYER_DEFS
    expected_layers={name for name,_,_ in LAYER_DEFS}|{'INNER_RETINA','ONL','ELM','IS','OS','BM','IPL_S1','IPL_S2','IPL_S3'}
    assert len(layers)==len(expected_layers)*len(expected)
    assert {(r['scan_id'],r['layer']) for r in layers}=={(sid,name) for sid in expected for name in expected_layers}
    assert {Path(p).name for p in read(OUT/'thick/volumes.json')}==expected
    for r in scans:
        if r['repeat_comparable']!='True':assert not r['repeat_disagreement']
    for r in boundaries:
        assert np.isclose(sum(float(r['native_'+word+'_pct']) for word in ['reported','uncertain','not_traceable']),100)
        assert sum(int(r['human_visibility_'+word+'_n']) for word in ['yes','no','unknown'])==262144
    for r in layers:
        for policy in ['segmentation_','preliminary_','preliminary_include_unreliable_']:
            if r.get(policy+'n'):
                assert int(r[policy+'n'])==int(r[policy+'finite_eligible_n'])<=int(r[policy+'eligible_n'])
    from ratings import compare
    compare()
    csvwrite(OUT/'verification/final_scan_audit.csv',records)
    write(OUT/'FINAL_VERIFIED.json',dict(passed=True,scans=len(scans),boundary_rows=len(boundaries),layer_rows=len(layers),all_native_grid_checks=True,all_input_artifact_hashes_verified=True,checkpoint_provenance_verified=True,tables=[fingerprint(OUT/p) for p in ['scan_qc.csv','boundary_qc.csv','layer_qc.csv','region_layer_qc.csv','region_qc.csv']],completed=time.strftime('%Y-%m-%dT%H:%M:%S')))
    report=OUT/'REPORT.md';report.write_text(report.read_text(encoding='utf-8')+'\nFinal cohort audit passed. See FINAL_VERIFIED.json and verification/final_scan_audit.csv.\n\nExact longitudinal v1 array matching passed. Read [material limitations](LIMITATIONS.md), including the frozen ILM withholding behavior and why strict segmentation RNFL/total differ from preliminary viewer measurements.\n',encoding='utf-8')
    print('FINAL AUDIT PASSED',len(scans),'acquisitions',flush=True)

if __name__=='__main__':audit()
