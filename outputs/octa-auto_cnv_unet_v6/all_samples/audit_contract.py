from common import *
import ast

def run():
    original=HERE.parent;old=read(ROOT/'outputs/octa-seg_v1_batch/manifest.json')
    results=[]
    for fp in old['dependencies']:
        p=Path(fp['path']);actual=sha(p);results.append(dict(path=str(p),matches_frozen_batch=actual==fp['sha256'],actual_sha256=actual,expected_sha256=fp['sha256']))
    critical=('octa_seg_v1/predict.py','octa_seg_v1/model.py','octa_seg_v1/train.py','stage_a/geometry.py','eight_surface/segment.py','eight_surface/config.py','quality_pilot/prepare.py','scan_quality.py')
    for r in results:
        if any(r['path'].replace('\\','/').endswith(x) for x in critical):assert r['matches_frozen_batch'],r
    vessels=read(ROOT/'outputs/octa-vessel_seg_v1-batch/manifest.json')['code_hashes']
    for name,expected in vessels.items():assert sha(ROOT/'code'/name)==expected
    for name in ('dataset.py','model.py','metrics.py'):assert sha(HERE/name)==sha(original/name)
    # Validation-preserving copied numerical functions and every local module parse.
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    write(HERE/'verification/frozen_implementation_contract.json',dict(passed=True,dependencies=results,vessel_code_hashes=vessels,
        copied_v6_numerical_code_identical=True,normalization_refit=False,threshold_tuning=False,retraining=False,
        preprocessing='Frozen raw-neural available-position policy. Existing audited native exports reused; missing OCTA generated with the original mean-dB projection.'))
    print('Frozen numerical implementation contract passed',flush=True)

if __name__=='__main__':run()
