"""Copy-only, recoverable migration. Never writes historical annotations."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import time
import zipfile
import importlib.metadata

HERE = Path(__file__).resolve().parent
V3 = HERE.parent
ROOT = V3.parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    archive = V3 / 'old_review' / time.strftime('%Y%m%d_%H%M%S')
    archive.mkdir(parents=True, exist_ok=False)
    manifest = dict(created_at=time.time(), mode='copy only; old GUI may remain running',
        originals=str(V3), historical_records=str(V3 / 'reviewers'),
        historical_queues=str(V3 / 'review_queues'), python=sys.executable,
        dependencies={p: importlib.metadata.version(p) for p in ['numpy', 'scipy', 'PySide6', 'h5py', 'matplotlib']},
        files=[], external_references=[])
    candidates = [p for p in V3.rglob('*') if p.is_file() and
        p.relative_to(V3).parts[0] not in ('review', 'old_review') and
        '__pycache__' not in p.parts and p.suffix not in ('.lock', '.tmp')]
    # Preserve the small imported runtime, with its original project-relative locations.
    for folder in ('eight_surface', 'cnv_review_v1', 'octa', 'octa_seg_v1'):
        candidates.extend((ROOT / 'code' / folder).glob('*.py'))
    candidates += [ROOT / 'code/label_gui.py']
    candidates.extend((V3.parent / 'octa-seg_v2/code/octa_seg_v2').glob('*.py'))
    with zipfile.ZipFile(archive / 'snapshot.zip', 'w', zipfile.ZIP_DEFLATED) as output:
        for path in sorted(set(candidates)):
            entry = dict(original_path=str(path), bytes=path.stat().st_size)
            if path.stat().st_size > 20 * 1024**2:
                manifest['external_references'].append(entry)
                continue
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            name = str(path.relative_to(ROOT)).replace('\\', '/')
            output.writestr(name, content)
            entry.update(sha256=digest, archive_path=name, stable_during_copy=sha(path) == digest)
            manifest['files'].append(entry)
    manifest['large_frozen_sources'] = [str(ROOT / 'outputs/octa-seg_v1_batch'),
        str(V3.parent / 'octa-seg_v2/round_000'), str(V3.parent / 'octa-seg_v1/models')]
    with zipfile.ZipFile(archive / 'snapshot.zip') as check:
        assert check.testzip() is None
        assert all(hashlib.sha256(check.read(e['archive_path'])).hexdigest() == e['sha256'] for e in manifest['files'])
    manifest['restore_verified'] = 'Every archived byte read back and SHA-256 matched; no originals overwritten.'
    (archive / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    (archive / 'RESTORE.md').write_text('# Restore old reviewer\n\nClose any old GUI/writer first. Extract snapshot.zip into a separate empty project root: paths are project-relative. Compare every entry with manifest.json SHA-256 before use. Restore the listed code and top-level launchers only after backing up the current files. Point large frozen providers at the original paths listed in the manifest; do not copy acquisitions or checkpoints. Never overwrite live reviewer records with this point-in-time copy. Historical reviewer originals and shared queues remain in the original v3 folder. The old GUI is permitted to remain running during this copy-only migration; stable_during_copy reports each copy check.\n', encoding='utf8')
    shutil.copytree(V3 / 'code', HERE / 'code', dirs_exist_ok=False, ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('catalog.json', 'dependencies.json'):
        shutil.copy2(V3 / name, HERE / name)
    (HERE / 'migration.json').write_text(json.dumps(dict(archive=str(archive), historical_reviewers=str(V3 / 'reviewers'), historical_queues=str(V3 / 'review_queues')), indent=2), encoding='utf8')
    print(json.dumps(dict(archive=str(archive), files=len(manifest['files']), unstable=[e['original_path'] for e in manifest['files'] if not e['stable_during_copy']])))

if __name__ == '__main__':
    main()
