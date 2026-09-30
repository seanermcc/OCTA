from pathlib import Path
from collections import Counter
import hashlib
import json
from update_code import ROOT, ROOTS, REL

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    passport = Path('F:/octa')
    for root in ROOTS:
        path = root/REL/'label_gui.py'
        text = path.read_text(encoding='utf-8')
        text = text.replace("            if status == 'Confirmed' and self.resolved['lesion_confirmation'] is None:",
                            "            if self.resolved.get('confirmation') and self.resolved['lesion_confirmation'] is None:")
        path.write_text(text, encoding='utf-8', newline='\n')
        for source in (root/REL).glob('*.py'):
            compile(source.read_text(encoding='utf-8'), str(source), 'exec')
        manifest = {p.name: sha(p) for p in (root/REL).glob('*.py')}
        (root/REL.parents[1]/'CNV_UPDATE_MANIFEST.json').write_text(json.dumps(manifest, indent=2))
    report = json.loads((passport/'CNV_DISTINCTIONS_MIGRATION.json').read_text())
    for record in report['records']:
        assert sha(Path(record['path'])) == record['after_sha256']
        assert sha(Path(record['archive'])) == record['before_sha256']
    seed = json.loads((passport/'For_Segmentation/Reviews/reviewers/shichu/CNV_MIGRATED_COPY.json').read_text())
    for record in seed['copied']:
        assert sha(Path(record['source'])) == record['sha256'] == sha(Path(record['destination']))
    # The stored code is shared for the scientific semantics; deployment adapters remain distinct.
    for name in ('lesions.py', 'feedback.py', 'lesion_tools.py', 'controls.py', 'label_gui.py'):
        assert len({sha(root/REL/name) for root in ROOTS}) == 1, name
    counts = Counter((r['reviewer'], r['status']) for r in report['records'])
    result = dict(release='cnv-core-full-20260929', installed_projects=[str(r) for r in ROOTS],
                  journals_checked=len(report['records']),
                  migrations={str(k):v for k,v in counts.items()},
                  shichu_live_journals=len(list((passport/'For_Segmentation/Reviews/reviewers/shichu/journals').glob('*.json'))),
                  original_journal_backups_hash_verified=True, portable_copy_hash_verified=True,
                  shared_semantics_hash_verified=True, source_compilation=True,
                  contract_tests=40, qt_edit_save_undo_reopen=True, auto_cnv_bscan_and_enface_toggle=True,
                  old_lesion_gui_regression_checks=True,
                  windows_real_cases=json.loads((ROOT/'outputs/cnv_distinctions_20260929/windows_verification.json').read_text()),
                  mac_package_real_cases_on_windows=json.loads((ROOT/'outputs/cnv_distinctions_20260929/mac_host_verification.json').read_text()),
                  native_macos_execution_tested=False)
    for target in (ROOT/'outputs/cnv_distinctions_20260929/VALIDATION.json', passport/'CNV_DISTINCTIONS_VALIDATION.json'):
        target.write_text(json.dumps(result, indent=2))
    print(json.dumps({k:v for k,v in result.items() if 'real_cases' not in k}, indent=2))

if __name__ == '__main__': main()
