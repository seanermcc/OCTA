"""Verify one complete longitudinal v1 input through this isolated batch."""
from batch import *
from supervise import process

sid='TS267_OD_2025-02-19_D0_s02_112013'
failure=process(record(sid))
if failure:raise RuntimeError(failure)
old=ROOT/'outputs/longitudinal_assessment/v1/volumes'/sid
fresh=npz(directory(sid)/'measurements.npz');reference=npz(old/'measurements.npz')
checks={}
for key in ['raw_position_branch','probabilities','entropy','reported_positions','state','reason','uncertain_estimates','context_reason','primary_thickness_um','shadow','vessel','cnv','label_offset','surface_names']:
    same=np.array_equal(fresh[key],reference[key],equal_nan=True) if fresh[key].dtype.kind in 'fc' else np.array_equal(fresh[key],reference[key])
    checks[key]=same
    assert same,(key,'differs from unchanged longitudinal v1')
write(OUT/'verification/longitudinal_v1_exact_match.json',dict(scan_id=sid,all_arrays_equal=True,checks=checks,reference=fingerprint(old/'measurements.npz'),batch=fingerprint(directory(sid)/'measurements.npz'),reuse=read(directory(sid)/'neural_complete.json').get('reused',False)))
print('Exact longitudinal v1 match passed',sid,flush=True)
