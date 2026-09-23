"""Read-only regression check using the affected lead reviews; never writes labels."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
import time
from pathlib import Path
from unittest.mock import patch

review = Path(__file__).resolve().parents[1]
root = next(p for p in review.parents if (p / 'PIPELINE.md').is_file())
sys.dont_write_bytecode = True
sys.path[:0] = [str(review / 'code'), str(review.parent.parent / 'octa-seg_v2/code'), str(root / 'code')]
from octa_seg_v3.common import fingerprint, read
from octa_seg_v3.data import local_path, load_volume
from octa_seg_v3.gui import Window, configure_v3_app
from octa_seg_v3.label_gui import QtCore, QtWidgets
from octa_seg_v3.saved import index

sid = 'TS241_OD_2024-09-25_D42_s03_111600'
records = {r['bscan']: r for r in index('lead') if r['scan_id'] == sid}
protected = {p: fingerprint(p) for p in (review / 'reviewers').rglob('*')
             if p.is_file() and p.suffix in ('.json', '.npz')}
old = records[210]['source']['provider']
assert not (Path(old) / 'prepared.json').exists(), 'Expected the reported stale path'
current = local_path(old)
assert (current / 'prepared.json').is_file()
# A missing provider must still fail rather than silently selecting another scan.
try:
    load_volume(dict(scan_id=sid, directory=str(current / '__missing_provider__')))
except FileNotFoundError:
    pass
else:
    raise AssertionError('Missing provider was accepted')

QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope,
                        str(review / 'verification/saved_path_preferences'))
app = QtWidgets.QApplication([])
configure_v3_app(app)
entry = dict(scan_id=sid, directory=str(current))
window = Window('lead', entries=[entry], autoload=False, read_only=True)
errors = []
sys.excepthook = lambda typ, exc, tb: errors.append(str(exc))
window.show()
try:
    with patch.object(QtWidgets.QMessageBox, 'critical', side_effect=lambda *args: errors.append(str(args[2]))):
        for row in (210, 244, 189):
            window.open_saved(records[row])
            deadline = time.monotonic() + 60
            while window._pending is not None and time.monotonic() < deadline and not errors:
                app.processEvents()
                time.sleep(.01)
            assert not errors, errors
            assert window._pending is None, 'Load timed out'
            assert window.row == row
            assert window.volume.model_id == records[row]['model_id']
            assert window.volume.provenance['provider_sha256'] == records[row]['source']['provider_sha256']
            assert window.editor.journal.data == read(records[row]['path'])
            assert window.editor.resolved['review_status'] == 'Confirmed'
            print(f'B{row}: opened saved review; exact provider hash; confirmed; original journal replayed', flush=True)
finally:
    window.close()
    app.processEvents()
changed = [str(p) for p, digest in protected.items() if fingerprint(p) != digest]
assert not changed, changed
print(f'PASS: {len(protected)} protected journal/label/session files unchanged; missing provider rejected')
