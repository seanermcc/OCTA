from pathlib import Path
import json
import shutil
import hashlib
from update_code import ROOT, ROOTS, REL

GUIDE = '''# CNV-Core and Full-CNV Lesion — September 29, 2026

Open `OPEN_BOUNDARY_REVIEWER.cmd` (or the spelling-compatible
`OPEN_BOUNDRY_REVIEWER.cmd`) on Windows. On Apple Silicon macOS open
`OPEN_BOUNDRY_REVIEWER_MAC.command`.

The same row now contains **CNV-Core**, **Full-CNV Lesion (RPE-Disrupt)**,
and a circled **i** that expands these definitions:

> CNV-Core is defined as the region where RPE is non-traceable with a loss of contrast (dark) blood-vessel invasion from the RPE

> Full-CNV Lesion is defined by regions where the RPE is clearly disrupted, and this should not depend on the hyper-reflective dots above the RPE

Select a category and left-drag across the B-scan to mark its lateral extent.
Each category is saved separately as full-depth columns. They may overlap.
Erase (E) removes only the selected category. Ctrl+drag also erases on Windows;
Command+drag erases on Mac. Mac shortcut labels use Command and Option.

**Colors:** CNV-Core is purple; Full-CNV is cyan; the separate octa-auto_CNV
context is pink. **Show auto-CNV (pink)** independently hides/shows the automatic
context in both the B-scan and en-face navigator, without changing any saved
mask, annotation, or reliability judgment. CNV edge and Hyper_Ref remain separate tools.

The requested migration maps lead's old CNV Region to CNV-Core and Shichu's
old CNV Region to Full-CNV. The opposite category is empty. Original events,
layer coordinates, exclusions, reliability judgments, review times, CNV edges,
and Hyper_Ref paint are preserved. No new human confirmation or negative label
is manufactured; use Confirm entire B-scan after reviewing both new categories.
Migration records form an undo floor. Older revisions remain in journal history
and the dated archive, and new strokes support normal undo/redo.

On My Passport (F:), the original reviewer sets stay under `octa/reviewers`.
The Windows app saves to `octa/For_Segmentation/Reviews/reviewers`.
Lead's more recent live work is preserved there. Shichu's migrated review set is
also available there, under her own reviewer ID.

Mac scan caches remain on the external drive. Existing Mac behavior saves new
reviews locally in `~/Documents/OCTA_Boundary_Reviews/portable-20260923/Reviews`.
The first launch seeds missing local review storage from the Passport. Existing
local lead/Shichu journals migrate through the GUI writer when opened; they are
never overwritten with the Windows copy. Native Mac execution was not tested
from Windows.

Previous GUI code and launchers: `archived/cnv_gui_before_20260929` on the
Passport, and `outputs/archived/cnv_gui_before_20260929` in the D: project.
The Passport archive includes exact original journal backups. Read
`CNV_DISTINCTIONS_MIGRATION.json` for the per-file audit. The source and data
used by octa-auto_CNV remain separate and unchanged.
'''

def archive_root(root):
    return ROOT/'outputs/archived/cnv_gui_before_20260929' if root == ROOT else Path('F:/octa/archived/cnv_gui_before_20260929')/('mac' if 'Mac_Boundary_Reviewer' in str(root) else 'windows')

def backup(path, root):
    target = archive_root(root)/path.relative_to(root)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

def main():
    for root in ROOTS:
        # Backfill the entire reviewer application; keep the already archived pre-edit versions.
        review = root/REL.parents[1]
        for path in review.rglob('*'):
            if (path.is_file() and path.suffix in ('.py', '.cmd', '.md') and
                    not any(p in ('verification', 'reviewers', 'runtime', '__pycache__') for p in path.relative_to(review).parts)
                    and path.name not in ('test_cnv_distinctions.py', 'CNV_DISTINCTIONS.md')):
                backup(path, root)
        path = root/REL/'saved.py'
        s = path.read_text(encoding='utf-8')
        s = s.replace("    for event in events:\n        if event['action'] == 'case_metadata':", "    for event in events:\n        if event['action'] == 'migrate_cnv_distinctions':\n            continue  # Layer confirmation is unchanged; new lesion definitions remain unconfirmed.\n        if event['action'] == 'case_metadata':")
        path.write_text(s, encoding='utf-8', newline='\n')
        path = root/REL/'verify_lesions.py'
        s = path.read_text(encoding='utf-8')
        a, b = s.split('def gui_checks(', 1)
        b = b.replace('cnv_region', 'cnv_core').replace('outside CNV region', 'outside CNV-Core / Full-CNV')
        b = b.replace("assert 'horizontal extent' in ed.cnv_hint.text() and 'lower depth boundary' in ed.cnv_hint.text()", "assert L.CORE_DEFINITION in ed.cnv_hint.text() and L.FULL_DEFINITION in ed.cnv_hint.text()")
        path.write_text(a+'def gui_checks('+b, encoding='utf-8', newline='\n')
        if root != ROOT:
            shutil.copy2(ROOT/REL/'test_cnv_distinctions.py', root/REL/'test_cnv_distinctions.py')
        (review/'CNV_DISTINCTIONS.md').write_text(GUIDE, encoding='utf-8')
        guide = review/'START_HERE.md'
        text = guide.read_text(encoding='utf-8') if guide.exists() else ''
        if not text.startswith('**Updated September 29, 2026:**'):
            guide.write_text('**Updated September 29, 2026:** CNV-Core and Full-CNV Lesion are independent manual categories. The pink auto-CNV overlay has its own toggle. See [definitions, migration, and saving](CNV_DISTINCTIONS.md).\n\n'+text, encoding='utf-8')
    # Keep both spellings so old shortcuts and the user's requested spelling work.
    passport = Path('F:/octa')
    for path in (passport/'OPEN_BOUNDARY_REVIEWER.cmd', passport/'OPEN_BOUNDRY_REVIEWER_MAC.command'):
        destination = passport/'archived/cnv_gui_before_20260929/launchers'/path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists(): shutil.copy2(path, destination)
    win = '@echo off\nrem CNV-Core / Full-CNV release 2026-09-29\ncall "%~dp0Full\\_Project\\OPEN_REVIEWER.cmd" %*\n'
    for name in ('OPEN_BOUNDARY_REVIEWER.cmd', 'OPEN_BOUNDRY_REVIEWER.cmd'):
        (passport/name).write_text(win, encoding='utf-8')
        # Main project uses this machine's tested portable runtime and Passport cache.
        (ROOT/name).write_text('@echo off\nsetlocal\nrem CNV-Core / Full-CNV release; save to the Passport reviewer store.\nif not exist "F:\\octa\\OPEN_BOUNDARY_REVIEWER.cmd" (\n  echo Connect My Passport as F: to open the cached boundary reviewer.\n  pause\n  exit /b 1\n)\ncall "F:\\octa\\OPEN_BOUNDARY_REVIEWER.cmd" %*\n', encoding='utf-8')
    mac = passport/'OPEN_BOUNDRY_REVIEWER_MAC.command'
    s = mac.read_text(encoding='utf-8').replace('# Apple Silicon launcher.', '# CNV-Core / Full-CNV release 2026-09-29. Apple Silicon launcher.')
    mac.write_text(s, encoding='utf-8', newline='\n')
    shutil.copy2(mac, ROOT/mac.name)
    shutil.copy2(mac, ROOT/'outputs/mac_boundary_20260923'/mac.name)
    import zipfile
    zip_path = passport/'Mac_Boundary_Reviewer/MAC_LAUNCHER.zip'
    zip_backup = passport/'archived/cnv_gui_before_20260929/launchers/MAC_LAUNCHER.zip'
    if not zip_backup.exists(): shutil.copy2(zip_path, zip_backup)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo(mac.name); info.create_system=3; info.external_attr=(0o100755 << 16)
        z.writestr(info, mac.read_bytes())
    for path in (passport/'CNV_DISTINCTIONS.md', ROOT/'outputs/cnv_distinctions_20260929/README.md'):
        path.write_text(GUIDE, encoding='utf-8')
    # Store exact installed code identities separately from the historical build manifests.
    for root in ROOTS:
        report = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/REL).glob('*.py')}
        (root/REL.parents[1]/'CNV_UPDATE_MANIFEST.json').write_text(json.dumps(report, indent=2))
    print('Archived complete reviewer sources; updated launchers, guides, tests, and save-list status.')

if __name__ == '__main__': main()
