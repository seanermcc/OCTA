"""Build a separate Mac application snapshot; never change Windows code or reviews."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
SOURCE = Path('E:/octa/Full/_Project')
DEST = Path('E:/octa/Mac_Boundary_Reviewer')
PROJECT = DEST / 'project'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    DEST.mkdir(exist_ok=True)
    copied = {}
    def copy(relative):
        src = SOURCE / relative
        dst = PROJECT / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        copied[relative] = digest(src)

    for name in ('README.md', 'PIPELINE.md', 'AGENTS.md', 'PORTABLE_CACHE.json',
                 'portable_layout.json', 'requirements-reviewer.txt'):
        copy(name)
    for folder in ('code', 'outputs/octa-seg/octa-seg_v2/code',
                   'outputs/octa-seg/octa-seg_v3/review'):
        for path in sorted((SOURCE / folder).rglob('*.py')):
            if '__pycache__' not in path.parts:
                copy(path.relative_to(SOURCE).as_posix())
    manifest = json.loads((SOURCE / 'PORTABLE_CACHE.json').read_text())
    for name in manifest['files']:
        if name.startswith('@code/'):
            copy(name.removeprefix('@code/'))

    common = PROJECT / 'outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3/common.py'
    content = common.read_text(encoding='utf-8')
    anchor = "RUNTIME = ROOT / 'runtime' if DATA_ROOT != ROOT else OUT / 'runtime'"
    assert content.count(anchor) == 1
    content = content.replace(anchor, anchor + '''
# Mac package only: caches can stay on a read-only NTFS drive. All new
# journals and transient writes go to the user's local Mac storage.
if os.environ.get('OCTA_MAC_STATE'):
    MAC_STATE = Path(os.environ['OCTA_MAC_STATE']).expanduser().resolve()
    OUT = MAC_STATE / 'Reviews'
    RUNTIME = MAC_STATE / 'runtime'
''')
    common.write_text(content, encoding='utf-8', newline='\n')

    gui = PROJECT / 'outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3/gui.py'
    content = gui.read_text(encoding='utf-8')
    anchor = 'def configure_v3_app(app):'
    assert content.count(anchor) == 1
    content = content.replace(anchor, '''# Qt maps ControlModifier to Command on macOS. Keep editing semantics intact.
import sys
if sys.platform == 'darwin':
    GESTURES = GESTURES.replace('Ctrl', 'Command').replace('Alt', 'Option')

''' + anchor)
    gui.write_text(content, encoding='utf-8', newline='\n')

    for src in (HERE / 'support').iterdir():
        if src.is_file():
            shutil.copyfile(src, DEST / src.name)
    launcher = HERE / 'OPEN_BOUNDRY_REVIEWER_MAC.command'
    shutil.copyfile(launcher, DEST.parent / launcher.name)
    # Archive preserves the executable bit when Finder cannot execute a file
    # directly from a Windows-formatted drive. Extract beside Mac_Boundary_Reviewer.
    with zipfile.ZipFile(DEST / 'MAC_LAUNCHER.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo(launcher.name)
        info.create_system = 3
        info.external_attr = (0o100755 << 16)
        archive.writestr(info, launcher.read_bytes())
    changed = {rel: {'windows_sha256': sha, 'mac_sha256': digest(PROJECT / rel)}
               for rel, sha in copied.items() if digest(PROJECT / rel) != sha}
    report = dict(format='octa-mac-package-1', target='Apple Silicon; requested macOS Tahoe 26.6.1',
                  source=str(SOURCE), copied_files=copied, modified_copies=changed,
                  source_files_unchanged=all(digest(SOURCE / p) == h for p, h in copied.items()),
                  cached_scans=len(manifest['scans']), native_macos_execution_tested=False)
    (DEST / 'BUILD_MANIFEST.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'destination': str(DEST), 'copied_files': len(copied),
                      'modified_copies': list(changed), 'cached_scans': len(manifest['scans'])}))


if __name__ == '__main__':
    main()
