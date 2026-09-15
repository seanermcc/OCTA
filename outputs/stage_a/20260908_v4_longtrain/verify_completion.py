"""Final provenance and real no-op resume regression on the delivered run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from stage_a.train import code_identity,load_checkpoint
from stage_a.common import fingerprint
HERE=Path(__file__).resolve().parent
RUN=HERE/'dev_seed20260908'
summary=json.loads((RUN/'training_summary.json').read_text())
baseline=json.loads((HERE/'baseline_provenance.json').read_text())
expected=json.loads((HERE/'resume_regression_result.json').read_text())['code_identity_after']
assert summary['code_identity']==code_identity()==expected
assert summary['config']==baseline['config'] and summary['identity']==baseline['identity']
_,old=load_checkpoint(baseline['baseline_checkpoint']['path'])
assert old['code_identity']!=code_identity()
assert fingerprint(baseline['baseline_checkpoint']['path'])==baseline['baseline_checkpoint']
def training_files():
    return {p.name:dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mtime_ns=p.stat().st_mtime_ns)
            for p in RUN.iterdir() if p.suffix=='.pt' or p.name.startswith('run_step_')}
before=training_files()
command=[sys.executable,str(HERE/'run_task.py'),'module','stage_a.train','--data',str(HERE.parent/'20260908_v2'),
    '--out',str(RUN),'--epochs',str(summary['epochs']),'--steps-per-epoch','48','--base','8','--lr','0.0003',
    '--region-weight','0.1','--seed','20260908','--device','cuda','--resume',str(RUN/'last.pt')]
with (HERE/'logs/real_noop_resume.log').open('w') as f:
    subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True)
assert training_files()==before,'Completed real resume modified a checkpoint or history'
old_stats=json.loads((HERE/'frozen_file_stats_before.json').read_text())
new_stats={str(p):[p.stat().st_size,p.stat().st_mtime_ns] for d in ('20260908_v2','20260908_v3_readability')
    for p in (Path('outputs/stage_a')/d).rglob('*') if p.is_file()}
changed=[p for p in old_stats if old_stats[p]!=new_stats.get(p)]
added=sorted(set(new_stats)-set(old_stats))
assert not changed and not added,(changed,added)
for phase in ('before','after_fix','after'):
    test=json.loads((HERE/'checks'/phase/'test_results.json').read_text())
    assert test['success'] and test['tests']==16
report_before=json.loads((HERE/'checks/before/integrity_and_environment.json').read_text())
report_after=json.loads((HERE/'checks/after/integrity_and_environment.json').read_text())
assert report_before==report_after
result=dict(code_identity=code_identity(),config_and_data_identity_match_baseline=True,
    old_checkpoint_inference_loads=True,old_checkpoint_resume_identity_incompatible=True,
    baseline_checkpoint_fingerprint_unchanged=True,real_noop_resume_preserves_history_and_checkpoints=True,
    frozen_v2_v3_file_stats_unchanged=True,n_frozen_files=len(old_stats),
    prompt_correction_exception='Snapshot taken after user-authorized correction of NEXT_STEP_PROMPT_train_longer.md',
    report_before_after_identical=True,tests_before_after_fix_final=16,
    final_test_data_read=False,repeatability_data_read=False,
    best_checkpoint=fingerprint(RUN/'best.pt'),last_checkpoint=fingerprint(RUN/'last.pt'))
(RUN/'completion_verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
