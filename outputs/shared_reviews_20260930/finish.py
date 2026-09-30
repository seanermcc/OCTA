from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PASSPORT = Path('F:/octa')
guide = HERE/'START_HERE.md'
for destination in (PASSPORT/'SHICHU_REVIEW_START_HERE.md',
                    PASSPORT/'Mac_Boundary_Reviewer/SHARED_REVIEWS.md'):
    shutil.copy2(guide, destination)

mac_guide = PASSPORT/'Mac_Boundary_Reviewer/START_HERE_MAC.md'
s = mac_guide.read_text(encoding='utf-8')
note = ('**September 30 update:** CNV-Core and Full-CNV are separate tools. All '
        'confirmed lead B-scans now appear in Shared / starred samples, with '
        'Shared versus Starred and your own review progress shown separately. '
        'The shared selection reads the current lead records from the drive on '
        'every refresh, even after the first launch; your local annotations are '
        'preserved. See [Shichu setup and saving](SHARED_REVIEWS.md).\n\n')
if note not in s:
    title, body = s.split('\n', 1)
    mac_guide.write_text(title+'\n\n'+note+body.lstrip('\n'), encoding='utf-8')

readme = ROOT/'README.md'
s = readme.read_text(encoding='utf-8')
note = ('**Shared boundary reviews (2026-09-30):** Mac and Windows now include '
        'all confirmed lead B-scans in Shared / starred samples. Shared cases '
        'without stars, ambiguous starred cases, and the current reviewer\'s '
        'progress have separate indicators. The initial audit found 20 '
        'confirmed B-scans; see [counts and Shichu setup](outputs/shared_reviews_20260930/START_HERE.md).\n\n')
if note not in s:
    title, body = s.split('\n',1)
    readme.write_text(title+'\n\n'+note+body.lstrip('\n'), encoding='utf-8')

rel = Path('outputs/octa-seg/octa-seg_v3/review')
for root in (ROOT, PASSPORT/'Full/_Project', PASSPORT/'Mac_Boundary_Reviewer/project'):
    report = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/rel/'code/octa_seg_v3').glob('*.py')}
    (root/rel/'SHARED_UPDATE_MANIFEST.json').write_text(json.dumps(report, indent=2))

before = json.loads((HERE/'human_files_before.json').read_text())
changes = [p for p, sha in before.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=sha]
(HERE/'verification_summary.json').write_text(json.dumps(dict(
    cnv_contract_tests=40, cnv_qt_checks='passed', shared_windows_qt='passed', shared_mac_package_qt='passed',
    native_macos_execution_tested=False,
    live_human_files_changed_during_active_lead_review=changes,
    annotation_policy='Update scripts never call a human annotation writer; synthetic GUI fixtures use isolated verification folders.'), indent=2))
print('Published guide and code manifests. Concurrent live-review changes:', len(changes))
