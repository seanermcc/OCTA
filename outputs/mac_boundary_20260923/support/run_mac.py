"""Mac-only runtime and writable-review setup; copied annotations remain byte-identical."""
from pathlib import Path
import hashlib
import importlib
import json
import os
import platform
import runpy
import shutil
import sys
import tempfile
import time

PACKAGE = Path(__file__).resolve().parent
PROJECT = PACKAGE / 'project'
REVIEW = PROJECT / 'outputs/octa-seg/octa-seg_v3/review'
RELEASE = 'portable-20260923'


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def check_dependencies(require_native=True):
    if require_native:
        if sys.platform != 'darwin' or platform.machine() != 'arm64':
            raise RuntimeError('The Mac reviewer requires native Apple Silicon Python, not Rosetta.')
        if sys.version_info[:2] != (3, 11):
            raise RuntimeError('The Mac reviewer requires its private Python 3.11 environment.')
        if Path(sys.prefix).resolve() != Path(os.environ.get('CONDA_PREFIX', '')).resolve():
            raise RuntimeError('Activate the Mac environment using OPEN_BOUNDRY_REVIEWER_MAC.command.')
    versions = {}
    for name in ('numpy', 'scipy', 'h5py', 'matplotlib', 'pandas', 'skimage', 'PySide6'):
        module = importlib.import_module(name)
        versions[name] = module.__version__
        if require_native and not Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
            raise RuntimeError(f'{name} loaded outside the private Mac environment.')
    import numpy as np
    from scipy.linalg import solve
    import h5py
    np.testing.assert_allclose(np.dot(np.eye(8), np.ones(8)), np.ones(8))
    np.testing.assert_allclose(solve(np.eye(3), np.ones(3)), np.ones(3))
    with h5py.File('mac-memory-check', 'w', driver='core', backing_store=False) as handle:
        handle['synthetic'] = np.arange(8)
        np.testing.assert_array_equal(handle['synthetic'][:], np.arange(8))
    return dict(versions=versions, platform=sys.platform, architecture=platform.machine(),
                python=sys.version, native_macos_test=sys.platform == 'darwin')


def seed_reviews(source, state):
    """One-time byte-for-byte copy. Never merge over or rewrite a human record."""
    source, state = Path(source).resolve(), Path(state).resolve()
    destination = state / 'Reviews'
    marker = destination / 'MAC_INITIAL_COPY.json'
    if marker.is_file():
        if json.loads(marker.read_text())['release'] != RELEASE:
            raise RuntimeError('The local review folder belongs to a different package.')
        return destination
    if destination.exists():
        raise RuntimeError(f'Existing reviews lack an initial-copy marker: {destination}. '
                           'They were preserved. Inspect this folder before continuing; do not overwrite it.')
    if not (source / 'reviewers').is_dir():
        raise RuntimeError(f'Missing original review folder: {source / "reviewers"}')
    state.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='initial-review-copy-', dir=state))
    records = {}
    print('Copying existing reviews to local Mac storage once (scan arrays stay on the drive)...', flush=True)
    sources = []
    for group in ('reviewers', 'review_queues'):
        root = source / group
        if not root.exists():
            continue
        for src in sorted(root.rglob('*')):
            if src.is_symlink():
                raise RuntimeError(f'Review copy cannot follow a symbolic link: {src}')
            if not src.is_file():
                continue
            sources.append(src)
    print(f'  {len(sources)} review and history files to preserve.', flush=True)
    for src in sources:
        relative = src.relative_to(source)
        dst = staging / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        before = sha256(src)
        shutil.copyfile(src, dst)
        if before != sha256(dst) or before != sha256(src):
            raise RuntimeError(f'A review changed during copying: {src}. Retry after closing other reviewers.')
        records[relative.as_posix()] = before
        if len(records) % 50 == 0 or len(records) == len(sources):
            print(f'  Copied {len(records)}/{len(sources)} review files...', flush=True)
    ledger = dict(release=RELEASE, source=str(source), copied_at=time.strftime('%Y-%m-%d %H:%M:%S'),
                  files=records, note='Byte copies only; future Mac saves use the original GUI writer.')
    (staging / marker.name).write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    # Atomic publication, with no overwrite of a competing completed copy.
    try:
        staging.rename(destination)
    except OSError:
        if not marker.is_file():
            raise
    print(f'Reviews are saved locally at: {destination}', flush=True)
    return destination


def configure_paths(seed=True):
    state_text = os.environ.get('OCTA_MAC_STATE')
    if not state_text:
        raise RuntimeError('OCTA_MAC_STATE is missing. Use the Mac command launcher.')
    state = Path(state_text).expanduser().resolve()
    layout = json.loads((PROJECT / 'portable_layout.json').read_text())
    data = (PROJECT / layout['data_root']).resolve()
    if state.is_relative_to(data) or state.is_relative_to(PACKAGE):
        raise RuntimeError('Mac reviews must be outside the external package and source data.')
    (state / 'runtime').mkdir(parents=True, exist_ok=True)
    # Fail before opening the GUI if the local save directory is not writable.
    with tempfile.TemporaryFile(dir=state / 'runtime') as probe:
        probe.write(b'writable')
    if seed:
        seed_reviews(data / 'Reviews', state)
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(REVIEW / 'code'), str(PROJECT / 'outputs/octa-seg/octa-seg_v2/code'), str(PROJECT / 'code')]
    return state, data


def main():
    if '--check-dependencies' in sys.argv:
        report = check_dependencies()
        from PySide6.QtWidgets import QApplication
        app = QApplication([])
        if app.platformName() != 'cocoa':
            raise RuntimeError('The native macOS Qt platform did not load.')
        print(json.dumps(dict(report, qt_platform=app.platformName()), indent=2), flush=True)
        return
    check_dependencies()
    state, data = configure_paths()
    print(f'Cached scans: {data}', flush=True)
    print(f'Saved reviews: {state / "Reviews"}', flush=True)
    if '--verify-mac' in sys.argv:
        from verify_mac import verify
        verify(require_native=True)
        return
    # Original entry point and annotation writer, using only the duplicated code.
    sys.argv[0] = str(REVIEW / 'launch.py')
    runpy.run_path(str(REVIEW / 'launch.py'), run_name='__main__')


if __name__ == '__main__':
    main()
