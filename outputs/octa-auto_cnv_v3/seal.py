"""Record the verified v3 delivery without changing source data or labels."""
from common import *
from datetime import datetime, timezone
import csv

tests = read(HERE/'verification/tests.json')
gui = read(HERE/'verification/gui_all_scans.json')
numeric = read(HERE/'verification/numerical_checks.json')
prior = read(HERE/'verification/prior_versions_preserved.json')
results = read(HERE/'RESULTS.json')
assert tests['passed'] and tests['tests'] >= 14
assert gui['passed'] and len(gui['scans']) == 17 and gui['review_files_unchanged']
assert len(numeric) == 17
assert all(all(r[k] for k in ('core_reproduced', 'default_deficit_reproduced',
    'background_independent', 'units_and_missingness')) for r in numeric)
assert prior and all(prior.values())
with (HERE/'manual_inventory.csv').open(newline='', encoding='utf-8') as handle:
    manuals = list(csv.DictReader(handle))
assert all(sha(r['path']) == r['sha256'] for r in manuals)
manifest = {p.name:sha(p) for p in HERE.iterdir() if p.suffix in ('.py', '.cmd')}
for name in manifest:
    destination(HERE/'release_source'/name).write_bytes((HERE/name).read_bytes())
write(HERE/'implementation_manifest.json', manifest)
upstream = [*list((ROOT/'code/cnv_review_v1').glob('*.py')),
    ROOT/'code/eight_surface/cnv_gui.py', ROOT/'code/eight_surface/cnv_labels.py',
    ROOT/'outputs/octa-thick_v1/engine.py']
write(HERE/'dependency_manifest.json', {str(p):sha(p) for p in upstream})
write(HERE/'COMPLETE.json', dict(completed_at=datetime.now(timezone.utc).isoformat(),
    implementation=VERSION, **results, tests_passed=tests['tests'],
    gui_acquisitions_verified=17, original_manual_files_preserved=len(manuals),
    detector_hash=sha(HERE/'algorithm.py'), independent_validation_complete=False))
delivery = f'''# CNV v3 is ready for review

V3 proposes {results['proposals']} compact foci across 17 scans, compared with 220 in v2. Each scan has 0–4 proposals. Shape, vessel-trunk and structural-evidence rules remove diffuse and elongated detections; no scan needed the four-proposal cap in this pilot.

Open **OPEN_OCTA_AUTO_CNV_V3.cmd**. Your original manual files remain in `G:/OCT_TreeShrew/octa/outputs/cnv_labels/`; see **MANUAL_ANNOTATIONS.md** for all six TS267 files. D7 and D28 matching acquisitions appear as cyan outlines in the viewer, with a dropdown for navigation.

Yes, draw a few now: **OPEN_MANUAL_REVIEW.cmd** starts D14 with automatic proposals hidden. Review 3–5 acquisitions including the lower D7 miss and confirmed vessel/edge negatives. New drawings save separately inside v3. Use the explicit classification, complete-review and Save all controls.

The pilot retains {results['location_hits']}/{results['manual_components']} existing D7/D28 manual component locations within 75 µm; the lower D7 component is missed. This is development agreement, not independent accuracy validation. Fourteen tests, numerical reproduction on all 17 scans, and all 17 GUI opens passed. Previous versions and original manual files are preserved.
'''
destination(HERE/'DELIVERY.md').write_text(delivery, encoding='utf-8')
print(f"V3 sealed: {results['proposals']} proposals, {tests['tests']} tests, 17 verified GUI scans.")
