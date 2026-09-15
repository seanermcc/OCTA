"""Switch only active entry points after successful verification; preserve original plans."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import shutil
import time

here=Path(__file__).resolve().parent
v3=here.parent
root=next(p for p in here.parents if (p/'PIPELINE.md').exists() and (p/'code/octa').exists())
verified=json.loads((here/'verification/latest.json').read_text())
assert verified['contract_tests'] >= 18 and not verified['protected_changes'] and not verified['qt']['callback_errors']
plan=here/'TRAINING_PLAN.md'
original=here/'TRAINING_PLAN_SPECIFICATION.md'
if not original.exists(): shutil.copy2(plan,original)
text=plan.read_text(encoding='utf8')
text=text.replace('This is the revised contract for the replacement GUI in `review`. It becomes operational when the accompanying implementation specification is implemented and verified. The existing GUI\'s completion checkbox does not implement this contract.',
    'This is the active collection and target-reader contract for the implemented replacement GUI in `review`, verified September 15, 2026. The historical GUI\'s completion checkbox does not implement this contract. See `IMPLEMENTATION.md` for verification and `PROVIDERS.md` for integration details.')
text=text.replace('Reviewers can pause at any time.', 'Reviewers can pause at any time. Changing a data-use role also requires reconfirmation; notes and sharing tags do not.')
plan.write_text(text,encoding='utf8')
for name in ('OPEN_OCTA_SEG_V3.cmd','OPEN_SHARED_REVIEW.cmd','VERIFY_V3.cmd'):
    (v3/name).write_text('@echo off\ncall "%~dp0review\\'+name+'" %*\n',encoding='utf8')
for name,heading in [('START_HERE.md','Current whole-B-scan review GUI'),('TRAINING_PLAN.md','Active training and annotation contract'),('IMPLEMENTATION.md','Current implementation and verification')]:
    (v3/name).write_text('# '+heading+'\n\nThe active document is **[review/'+name+'](review/'+name+')**. Use [OPEN_OCTA_SEG_V3.cmd](OPEN_OCTA_SEG_V3.cmd) to open the replacement.\n\nThe old GUI and documents are historical recovery materials: see [review/MIGRATION.md](review/MIGRATION.md). Existing reviewer originals remain at `reviewers/`; new work goes to `review/reviewers/`. Old completion flags do not approve positions under the new contract.\n',encoding='utf8')
for name in ('README.md','PIPELINE.md'):
    p=root/name
    content=p.read_text(encoding='utf8')
    note=('**Whole-B-scan review (2026-09-15):** the replacement [octa-seg_v3 review GUI](outputs/octa-seg/octa-seg_v3/review/START_HERE.md) explicitly approves inspected unchanged, drawn, joined and moved final positions when the entire B-scan is confirmed. Explicit exceptions remain masked. This new contract supersedes drawn-only rules only for valid new confirmations; historical labels and earlier model training retain their original meaning. No model was trained in this GUI task.\n\n')
    if note not in content:
        first,sep,rest=content.partition('\n')
        p.write_text(first+'\n\n'+note+rest.lstrip('\n'),encoding='utf8')
manifest=dict(created_at=time.time(),code_root=str(here/'code'),python_packages={p:importlib.metadata.version(p) for p in ('numpy','scipy','PySide6','h5py','matplotlib')},files={})
for p in sorted(here.rglob('*')):
    if p.is_file() and p.suffix in ('.py','.cmd','.md') and not any(x in p.relative_to(here).parts for x in ('verification','reviewers','runtime','__pycache__')):
        manifest['files'][str(p.relative_to(here))]=hashlib.sha256(p.read_bytes()).hexdigest()
(here/'implementation_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
print('Active v3 launchers and documents now point to review.')
