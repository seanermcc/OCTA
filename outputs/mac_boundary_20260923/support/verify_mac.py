"""Read-only real scan check plus synthetic GUI save/reopen; usable on the target Mac."""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch


def verify(require_native=True):
    from run_mac import check_dependencies, configure_paths, sha256
    report = check_dependencies(require_native=require_native)
    state, data = configure_paths()
    folder = state / 'runtime/checks' / (time.strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid()))
    folder.mkdir(parents=True)
    from PySide6 import QtCore, QtWidgets
    import numpy as np
    from octa_seg_v3.common import OUT, RUNTIME, read
    from octa_seg_v3 import portable
    from octa_seg_v3.data import discover, load_volume
    from octa_seg_v3.gui import Window, configure_v3_app
    from octa_seg_v3.feedback import resolve
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if require_native and app.platformName() != 'cocoa':
        raise RuntimeError('Native Cocoa Qt platform is required for the Mac GUI check.')
    configure_v3_app(app)
    from octa_seg_v3.verify_review import qt_checks
    constructor = QtCore.QSettings
    errors = []
    old_hook = sys.excepthook
    sys.excepthook = lambda typ, exc, tb: errors.append(str(exc))
    try:
        with patch.object(QtCore, 'QSettings', side_effect=lambda *a, **kw:
                          constructor(str(folder / 'preferences.ini'), constructor.Format.IniFormat)):
            entries = discover()
            manifest = portable.manifest()
            sid = manifest['confirmed_cases'][0]['scan_id']
            cases = [c for c in manifest['confirmed_cases'] if c['scan_id'] == sid]
            entry = next(e for e in entries if e['scan_id'] == sid)
            # Other people may still be reviewing on Windows. Check our local
            # copy and the source journals actually opened, not unrelated live
            # reviewers' changing timers/history files.
            journals = list((OUT / 'reviewers').rglob('*')) + [portable.inside(c['path']) for c in cases]
            before = {str(p): sha256(p) for p in journals if p.is_file()}
            print('Loading and verifying one real cached scan: ' + sid, flush=True)
            volume = load_volume(entry, image_budget=0)
            assert list(volume.images.shape) == manifest['scans'][sid]['image_shape']
            window = Window('lead', entries=[entry], autoload=False, read_only=True)
            window.resize(1400, 900)
            window.show()
            app.processEvents()
            with patch.object(QtWidgets.QMessageBox, 'critical', side_effect=lambda *a: errors.append(str(a[2]))):
                window.install_volume(volume, 0, cases[0]['bscan'], False)
                for case in cases:
                    window.navigate(case['bscan'])
                    app.processEvents()
                    relative = Path(case['path']).relative_to('Reviews')
                    saved = read(OUT / relative)
                    expected = resolve(saved['events'][:saved['cursor']], volume.data['raw_position_branch'][case['bscan']],
                                       int(volume.data['label_offset']), volume.images.shape[1])
                    np.testing.assert_array_equal(window.editor.resolved['positions'], expected['positions'])
                    assert window.editor.journal.data == saved
                window.navigate(0)
                window.navigate(volume.images.shape[0] - 1)
                window.navigate(cases[0]['bscan'])
                window.fit()
                app.processEvents()
                assert window.grab().save(str(folder / 'reviewer.png'))
                window.close()
                app.processEvents()
            changed = [p for p, value in before.items() if sha256(p) != value]
            assert not changed, 'Examined human records changed during verification: ' + str(changed)
            print('Testing synthetic editing, undo, confirmation and save/reopen...', flush=True)
            with patch('octa_seg_v3.portable.enabled', return_value=False):
                synthetic = qt_checks(app, RUNTIME / 'verification' / folder.name / 'synthetic')
            assert not errors, errors
            report.update(status='passed', cached_scans=len(entries), checked_scan=sid,
                          saved_bscans=[c['bscan'] for c in cases], human_records_unchanged=True,
                          synthetic_gui=synthetic, qt_platform=app.platformName(),
                          review_folder=str(OUT), screenshot=str(folder / 'reviewer.png'))
    finally:
        sys.excepthook = old_hook
    (folder / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='passed', native_macos_test=report['native_macos_test'], report=str(folder / 'result.json'))), flush=True)
    return report
