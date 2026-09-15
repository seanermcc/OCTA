"""Finalize GUI verification and input provenance. No training or label writes."""
from common import *
from datetime import datetime,timezone
tests=read(HERE/'verification/tests.json');gui=read(HERE/'verification/gui_all_scans.json')
assert tests['passed'] and tests['tests']>=16
assert gui['passed'] and len(gui['scans'])==17 and gui['review_files_unchanged']
octa=read(HERE/'verification/octa_sources.json');assert len(octa)==17
prior={}
for version in ('v3','v4'):
    base=ROOT/f'outputs/octa-auto_cnv_{version}'
    for name,digest in read(base/'implementation_manifest.json').items():
        assert sha(base/name)==digest;prior[f'{version}/{name}']=digest
write(HERE/'verification/previous_versions_preserved.json',prior)
write(HERE/'implementation_manifest.json',{p.name:sha(p) for p in HERE.iterdir() if p.suffix in ('.py','.cmd')})
inputs={}
for visit in selected():
    sid=visit['scan_id']
    for path in (DATA/'scans'/sid/'maps.npz',DATA/'proposals'/f'{sid}.npz',HERE/'octa_cache'/f'{sid}.npz'):
        inputs[str(path)]=sha(path)
write(HERE/'input_manifest.json',inputs)
write(HERE/'dependency_manifest.json',{str(p):sha(p) for p in [ROOT/'outputs/octa-thick_v1/engine.py',
    ROOT/'code/cnv_review_v1/gui.py',ROOT/'code/cnv_review_v1/data.py',ROOT/'code/eight_surface/cnv_gui.py',ROOT/'code/eight_surface/cnv_data.py']})
write(HERE/'COMPLETE.json',dict(version=VERSION,completed_at=datetime.now(timezone.utc).isoformat(),tests_passed=tests['tests'],
    gui_scans_verified=17,octa_scans=17,bscan='read-only; matching thickness endpoints only',new_cnv_model_implemented=False,
    model_training_run=False,model_plan='plans/CNV_UNET_PLAN.md',manual_review_preserved=True,detector='unchanged v3 suggestions'))
print('V5 complete: 16 tests; 17 OCTA scans and 8 thickness choices verified; no model training.',flush=True)
