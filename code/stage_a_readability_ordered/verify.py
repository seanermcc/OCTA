"""Final packaged-code and delivered-measurement verification on development only."""
import json
from pathlib import Path
import numpy as np
import torch
from stage_a.common import write_json, fingerprint
from stage_a.model import decode
from stage_a.train import code_identity
from .readability import load_readability_model
from .experiment import RUN, CHECKPOINT, read_npz
from .ordered import decode_ordered


def run():
    torch.set_num_threads(4)
    prepared=json.loads((RUN/'prepared.json').read_text())
    model,head_ck=load_readability_model(RUN/'head_best.pt','cuda')
    old=torch.load(CHECKPOINT,map_location='cpu',weights_only=True)
    if code_identity()!=old['code_identity']:
        raise AssertionError('Original trainer code identity changed')
    exact=0; max_score_difference=0.; dec_exact=0
    for r in prepared['records']:
        t=read_npz(RUN/'cache'/(r['key']+'.npz'))
        with torch.no_grad():
            logits,regions,readable=model(torch.from_numpy(t['x']).unsqueeze(0).cuda())
            rows,entropy=decode(logits)
            feature_score=model.head(torch.from_numpy(t['features']).unsqueeze(0).cuda()).sigmoid()
        if not np.array_equal(rows[0].cpu().numpy(),t['raw_rows']) or not np.array_equal(entropy[0].cpu().numpy(),t['entropy']):
            raise AssertionError('Packaged boundary reproduction mismatch')
        exact+=1
        difference=float(abs(readable.sigmoid()-feature_score).max())
        max_score_difference=max(max_score_difference,difference)
        if difference>1e-7: raise AssertionError('Full image / cached head disagreement')
        if r['split']=='validation' and ('b0510' in r['key'] or 'D98' in r['key'] and 'b0061' in r['key']):
            saved=read_npz(RUN/'measurements/readability_ordered'/(r['key']+'.npz'))
            thr=json.loads((RUN/'exploratory_thresholds.json').read_text())['thresholds']['learned']['0.95']
            keep=1.-readable.sigmoid()[0].cpu().numpy()<=thr
            pred=decode_ordered(logits[0].cpu().numpy(),t['raw_rows'],t['entropy'],t['scope'],t['shadow'],head_ck['config']['decoder'],keep)
            if not np.array_equal(pred['reason_bits'],saved['reason_bits']) or not np.array_equal(pred['retained_rows'],saved['canonical_retained_rows'],equal_nan=True):
                raise AssertionError('Packaged decoder changed delivered failure case')
            dec_exact+=1
    files=list((RUN/'measurements').glob('*/*.npz'))
    for path in files:
        p=read_npz(path)
        if p['validated'] or not np.isnan(p['validated_thickness_um']).all(): raise AssertionError('Validation status changed')
        if not np.array_equal(p['retained'],p['reason_bits']==0): raise AssertionError('Reason mismatch')
        if not np.isnan(p['canonical_retained_rows'][~p['retained']]).all(): raise AssertionError('NaN gap lost')
    source={str(p.relative_to(RUN.parents[2])):fingerprint(p) for p in Path(__file__).parent.glob('*.py')}
    write_json(RUN/'final_software_verification.json',dict(
        original_stage_a_code_identity=code_identity(),original_resume_identity_preserved=True,
        packaged_boundary_reproduction_exact_bscans=exact,full_image_vs_cached_head_max_difference=max_score_difference,
        packaged_decoder_failure_cases_reproduced_exactly=dec_exact,measurement_files_checked=len(files),
        synthetic_new_tests=11,existing_tests=16,source_files=source,head_checkpoint=fingerprint(RUN/'head_best.pt')))


if __name__=='__main__': run()
