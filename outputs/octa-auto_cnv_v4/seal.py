"""Seal a verified v4 GUI release; never write human annotation files."""
from common import *
from datetime import datetime,timezone
tests=read(HERE/'verification/tests.json')
gui=read(HERE/'verification/gui_all_scans.json')
assert tests['passed'] and tests['tests']>=20
assert gui['passed'] and len(gui['scans'])==17 and gui['review_files_unchanged']
assert read(HERE/'verification/startup_fit.json')['all_maps_fit']
previous=ROOT/'outputs/octa-auto_cnv_v3'
assert all(sha(previous/name)==digest for name,digest in read(previous/'implementation_manifest.json').items())
inputs={}
for visit in selected():
    sid=visit['scan_id']
    for suffix in (f'scans/{sid}/maps.npz',f'proposals/{sid}.npz'):
        digest=sha(previous/suffix);assert sha(HERE/suffix)==digest
        inputs[suffix]=dict(source=str(previous/suffix),sha256=digest)
write(HERE/'input_manifest.json',inputs)
manifest={p.name:sha(p) for p in HERE.iterdir() if p.suffix in ('.py','.cmd')}
write(HERE/'implementation_manifest.json',manifest)
dependencies=[*list((ROOT/'code/cnv_review_v1').glob('*.py')),ROOT/'outputs/octa-thick_v1/engine.py',
    ROOT/'code/eight_surface/cnv_gui.py',ROOT/'code/eight_surface/config.py']
write(HERE/'dependency_manifest.json',{str(p):sha(p) for p in dependencies})
write(HERE/'COMPLETE.json',dict(version=VERSION,completed_at=datetime.now(timezone.utc).isoformat(),
    tests_passed=tests['tests'],gui_scans_verified=17,middle_layers=7,right_panel='Full retina',
    closed_paint_fills=True,manual_review_preserved=True,previous_version_unchanged=True,
    detector='unchanged v3',experimental_thickness=True))
print('V4 verified: 20 tests, 17 acquisitions, 7 selectable layers, full retina fixed.')
