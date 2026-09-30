"""Finish the local release after verification and the audited GUI-writer migration."""
from pathlib import Path
import hashlib
import json
import shutil
from update_code import ROOT, ROOTS, REL

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    passport = Path('F:/octa')
    report = json.loads((passport/'CNV_DISTINCTIONS_MIGRATION.json').read_text())
    assert len(report['records']) == 85
    for rec in report['records']:
        assert sha(Path(rec['path'])) == rec['after_sha256']
        assert sha(Path(rec['archive'])) == rec['before_sha256']
    # Make Shichu's requested existing work available to the portable app, which
    # previously had no shichu save store. Never overwrite a live reviewer folder.
    src = passport/'reviewers/shichu'
    dst = passport/'For_Segmentation/Reviews/reviewers/shichu'
    if dst.exists():
        raise RuntimeError('A live Shichu folder already exists; inspect before merging.')
    copies = []
    for folder in ('journals', 'surface_labels', 'surface_context', 'context_exposure'):
        for path in (src/folder).rglob('*'):
            if path.is_file() and 'history' not in path.relative_to(src).parts and path.suffix != '.lock':
                dest = dst/path.relative_to(src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                assert sha(path) == sha(dest)
                copies.append(dict(source=str(path), destination=str(dest), sha256=sha(dest)))
    if (src/'session.json').exists():
        shutil.copy2(src/'session.json', dst/'session.json')
    (dst/'CNV_MIGRATED_COPY.json').write_text(json.dumps(dict(copied=copies,
        original_history=str(src/'journals/history'), reason='User-requested CNV distinction migration; first live portable copy.'), indent=2))
    # Refresh tracked code hashes only; the portable scan/cache manifest stays frozen.
    for root in ROOTS:
        for name in ('lesion_tools.py', 'label_gui.py'):
            path = root/REL/name
            text = path.read_text(encoding='utf-8')
            if name == 'lesion_tools.py':
                old = "                self.editor.mark_hint.setText('Left-drag: ' + ('mark CNV columns; Ctrl+drag clears' if mode in L.REGION_KEYS else 'paint Hyper_Ref; E toggles erase'))"
                new = "                modifier = 'Command' if __import__('sys').platform == 'darwin' else 'Ctrl'\n                self.editor.mark_hint.setText('Left-drag: ' + (f'mark CNV columns; {modifier}+drag clears' if mode in L.REGION_KEYS else 'paint Hyper_Ref; E toggles erase'))"
                assert old in text
                text = text.replace(old, new)
            else:
                text = text.replace("        kind = L.LEGACY_MAPPING.get(self.data['reviewer_id'])", "        if self.read_only:\n            return False\n        kind = L.LEGACY_MAPPING.get(self.data['reviewer_id'])")
                text = text.replace("                self.status.setText('Select a retinal boundary to use that boundary action. Ctrl+drag erases the selected lesion tool.')", "                modifier = 'Command' if os.sys.platform == 'darwin' else 'Ctrl'\n                self.status.setText(f'Select a retinal boundary to use that boundary action. {modifier}+drag erases the selected lesion tool.')")
            compile(text, str(path), 'exec')
            path.write_text(text, encoding='utf-8', newline='\n')
        manifest = {p.name: sha(p) for p in (root/REL).glob('*.py')}
        (root/REL.parents[1]/'CNV_UPDATE_MANIFEST.json').write_text(json.dumps(manifest, indent=2))
    doc = ROOT/'README.md'
    text = doc.read_text(encoding='utf-8')
    headline, rest = text.split('\n', 1)
    note = '**CNV distinctions (2026-09-29):** [Open the boundary reviewer](OPEN_BOUNDARY_REVIEWER.cmd). Manual CNV-Core (purple) and Full-CNV Lesion / RPE-Disrupt (cyan) now save independently; the circled i shows their definitions. The separate pink auto-CNV overlay has its own display toggle. Lead and Shichu\'s Passport journals were migrated with original backups. Windows and Mac packages are updated; see the [release guide](outputs/cnv_distinctions_20260929/README.md).\n\n'
    doc.write_text(headline+'\n\n'+note+rest.lstrip('\n'), encoding='utf-8')
    (passport/'Mac_Boundary_Reviewer/CNV_DISTINCTIONS.md').write_text((ROOT/'outputs/cnv_distinctions_20260929/README.md').read_text(encoding='utf-8'), encoding='utf-8')
    print(json.dumps(dict(verified_journals=85, live_shichu_journals=len(list((dst/'journals').glob('*.json'))), copied_files=len(copies))))

if __name__ == '__main__': main()
