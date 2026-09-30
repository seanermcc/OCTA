"""Windows host checks for the isolated Mac package; no claim of native Mac testing."""
import ast
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

PACKAGE = Path('E:/octa/Mac_Boundary_Reviewer')
TEST_ROOT = Path(__file__).resolve().parent / 'checks'
TEST_ROOT.mkdir(exist_ok=True)
os.environ['OCTA_MAC_STATE'] = str(TEST_ROOT / 'local-mac-state')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['MPLCONFIGDIR'] = str(TEST_ROOT / 'matplotlib')
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
sys.path.insert(0, str(PACKAGE))
import run_mac


class SetupTests(unittest.TestCase):
    def test_initial_copy_is_byte_identical_and_never_overwrites_local_work(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temp:
            root = Path(temp)
            original = root / 'source/reviewers/example/preservation-test.txt'
            original.parent.mkdir(parents=True)
            original.write_bytes(b'Synthetic byte-copy fixture\r\n\x00\xff')
            out = run_mac.seed_reviews(root / 'source', root / 'state')
            local = out / 'reviewers/example/preservation-test.txt'
            self.assertEqual(local.read_bytes(), original.read_bytes())
            local.write_bytes(b'Synthetic local changes must survive relaunch')
            run_mac.seed_reviews(root / 'source', root / 'state')
            self.assertEqual(local.read_bytes(), b'Synthetic local changes must survive relaunch')
            self.assertEqual(original.read_bytes(), b'Synthetic byte-copy fixture\r\n\x00\xff')

    def test_existing_unmarked_local_reviews_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temp:
            root = Path(temp)
            (root / 'state/Reviews').mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, 'preserved'):
                run_mac.seed_reviews(root / 'source', root / 'state')

    def test_mac_launcher_zip_retains_executable_mode_and_lf(self):
        with zipfile.ZipFile(PACKAGE / 'MAC_LAUNCHER.zip') as archive:
            info = archive.infolist()[0]
            self.assertEqual(info.external_attr >> 16 & 0o777, 0o755)
            self.assertNotIn(b'\r', archive.read(info))

    def test_all_copied_python_parses(self):
        for path in PACKAGE.rglob('*.py'):
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SetupTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    protected = [Path('E:/octa/For_Segmentation').resolve(),
                 Path('E:/octa/Full/_Project').resolve(), (PACKAGE / 'project').resolve()]
    denied = []
    def audit(event, args):
        candidates = []
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.suffix.lower() in ('.raw', '.mat'):
                raise RuntimeError('Cached review attempted to open a source volume: ' + str(path))
            if args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                candidates.append(path)
        elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime'):
            candidates.append(Path(args[0]).resolve())
        elif event in ('os.rename', 'os.link', 'os.symlink'):
            candidates.extend(Path(a).resolve() for a in args[:2])
        for path in candidates:
            if any(path.is_relative_to(root) for root in protected):
                denied.append((event, str(path)))
                raise RuntimeError('Mac package attempted a write to read-only source storage: ' + str(path))
    sys.addaudithook(audit)
    class NoTrainingDependencies(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in ('torch', 'tensorflow'):
                raise ImportError('Training dependencies are deliberately absent in the Mac reviewer')
    sys.meta_path.insert(0, NoTrainingDependencies())
    run_mac.configure_paths()
    from octa_seg_v3.common import OUT, ROOT, DATA_ROOT, RUNTIME
    assert OUT == TEST_ROOT / 'local-mac-state/Reviews'
    assert DATA_ROOT == Path('E:/octa/For_Segmentation')
    assert ROOT == PACKAGE / 'project'
    assert RUNTIME == TEST_ROOT / 'local-mac-state/runtime'
    from octa_seg_v3 import portable
    from pathlib import PurePosixPath
    directory_names = {}
    for relative in portable.manifest()['files']:
        base = ROOT if relative.startswith('@code/') else DATA_ROOT
        for part in PurePosixPath(relative.removeprefix('@code/')).parts:
            names = directory_names.setdefault(str(base), None)
            if names is None:
                names = directory_names[str(base)] = set(os.listdir(base))
            assert part in names, f'Case-sensitive Mac path mismatch: {base / part}'
            base /= part
    for alias, relative in portable.manifest()['aliases'].items():
        assert portable.inside(relative).exists(), relative
        # Source Windows paths must retain identity on a POSIX host.
        assert portable.key(str(PurePosixPath(alias))) == portable.key(alias)
    from verify_mac import verify
    report = verify(require_native=False)
    manifest = json.loads((PACKAGE / 'BUILD_MANIFEST.json').read_text())
    assert all(run_mac.sha256(Path(manifest['source']) / p) == h for p, h in manifest['copied_files'].items())
    report.update(setup_tests=result.testsRun, source_windows_files_unchanged=True,
                  package_python_syntax=True, mac_alias_paths_checked=True,
                  case_sensitive_cache_paths=True, training_dependencies_blocked=True,
                  source_write_attempts=denied,
                  limitation='Executed on Windows with offscreen Qt; native Mac setup/Cocoa/gestures require target verification.')
    (PACKAGE / 'VALIDATION.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Mac package host validation passed. Native Mac validation remains pending.', flush=True)
