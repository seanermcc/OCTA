"""Seal the completed pilot and preserve the delivered v2 source snapshot."""
from common import *
from datetime import datetime,timezone

checks=read(HERE/'verification/tests.json');gui=read(HERE/'verification/gui_all_scans.json');audit=read(HERE/'AUDIT_COMPLETE.json')
assert checks['passed'] and checks['tests']>=16
assert gui['passed'] and len(gui['scans'])==17 and gui['review_files_unchanged']
assert audit['scans']==17 and audit['detector_hash']==sha(HERE/'algorithm.py')
manifest={p.name:sha(p) for p in HERE.iterdir() if p.suffix in ('.py','.cmd')}
for name,digest in manifest.items():
    snapshot=destination(HERE/'release_source'/name)
    snapshot.write_bytes((HERE/name).read_bytes())
write(HERE/'implementation_manifest.json',manifest)
upstream=[*list((ROOT/'code/cnv_review_v1').glob('*.py')),ROOT/'code/eight_surface/cnv_gui.py',ROOT/'code/eight_surface/cnv_labels.py',ROOT/'outputs/octa-thick_v1/engine.py']
write(HERE/'dependency_manifest.json',{str(p):sha(p) for p in upstream})
write(HERE/'COMPLETE.json',dict(completed_at=datetime.now(timezone.utc).isoformat(),implementation='octa-auto_cnv_v2',
    scans=17,tests_passed=checks['tests'],gui_acquisitions_verified=17,candidates=audit['candidates'],
    location_hits_75um=audit['location_hits'],manual_components=audit['manual_components'],
    default_background_unavailable=audit['insufficient_default_background'],
    human_review_complete=False,independent_validation=False,
    verification_hashes={name:sha(HERE/'verification'/name) for name in ('tests.json','native_checks.json','gui_all_scans.json','D14_regression.json','v1_preservation.json')},
    source_manifest_sha256=sha(HERE/'implementation_manifest.json')))
summary=f'''# Delivery check

Implemented and verified all 17 selected TS267 acquisitions. {checks['tests']} scientific and GUI tests passed; the actual integrated GUI opened and navigated all 17 scans without changing review files.

The D14 miss is exposed as candidate 7, with three identified boundary crossings and unavailable thickness retained. D7/D28 location agreement is 7/7 reviewed manual components versus 0/7 in v1. This is development evidence: the upstream model trained on TS267, and candidate coverage is broad.

Review burden increased to 220 candidates (v1: 13). Eight default fits have insufficient background. False-positive performance is unavailable because this reference set has no genuinely reviewed negatives. No longitudinal change is claimed.

Open **OPEN_OCTA_AUTO_CNV_V2.cmd**. Start with D14 candidate 7, then D7/D28 and D0 artifact challenges. Read **START_HERE.md** for tools, definitions and limitations; **REVIEW_ATLAS.html** shows examples. V1 source hashes match its existing manifest. Existing human labels, released models and source data were not edited.

The saved numerical audit reproduces all candidate masks and default measurements from the final detector. All six background variants retain the same first-stage candidate list. Human edits and assisted recomputation have isolated provenance and never silently alter numerical contours or approve untouched automatic pixels.
'''
destination(HERE/'DELIVERY.md').write_text(summary,encoding='utf-8')
plan=HERE/'PLAN.md';content=plan.read_text(encoding='utf-8')
content=content.replace('Status: implementation plan, 2026-09-11. V1 results and behavior are unchanged.','Status: implemented and pilot-verified, 2026-09-11. See START_HERE.md and DELIVERY.md. V1 results and behavior are unchanged.')
plan.write_text(content,encoding='utf-8')
print('Delivery sealed: 17 scans,',checks['tests'],'tests, 17 GUI opens; human review pending.')
