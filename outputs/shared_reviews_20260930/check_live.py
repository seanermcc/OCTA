"""Check live selection read-only, including an existing Mac local-copy scenario."""
from pathlib import Path
import json
import os
import sys
from unittest.mock import patch
HERE = Path(__file__).resolve().parent
mac = '--mac' in sys.argv
project = Path('F:/octa/Mac_Boundary_Reviewer/project' if mac else 'F:/octa/Full/_Project')
if mac: os.environ['OCTA_MAC_STATE'] = str(HERE/'mac_state')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path[:0] = [str(project/'outputs/octa-seg/octa-seg_v3/review/code'),
               str(project/'outputs/octa-seg/octa-seg_v2/code'), str(project/'code')]
from octa_seg_v3 import saved, portable
from octa_seg_v3.data import discover
from octa_seg_v3.gui import configure_v3_app
from PySide6 import QtWidgets
from types import SimpleNamespace
entries = discover()
rows = saved.shared_cases('lead', entries)
confirmed = {(r['scan_id'],r['bscan']) for r in saved.shared_index('lead') if r['status']=='Confirmed'}
print('Current confirmed count:', len(confirmed), flush=True)
# The lead may be actively editing; assert inclusion against this snapshot,
# rather than freezing the confirmation count from the initial audit.
assert confirmed
assert confirmed <= {(r['scan_id'],r['bscan']) for r in rows}
assert all(set(r)=={'scan_id','bscan','model_id','provider','data_role','starred'} for r in rows)
for r in rows:
    manifest = portable.manifest()['scans'][r['scan_id']]
    assert portable.local_path(r['provider']) == portable.inside(manifest['directory'])
    assert r['model_id'] == manifest['model_id']
    assert 0 <= r['bscan'] < manifest['image_shape'][0]
app = QtWidgets.QApplication([])
configure_v3_app(app)
# Dialog must use drive selections even when a Mac's local lead copy is absent.
window = QtWidgets.QWidget()
window.reviewer = 'shichu'
window.entries = entries
window.output = saved.OUT/'reviewers/shichu'
window.use_shared_cases = lambda *a: None
browser = saved.SharedBrowser(window)
browser.show(); app.processEvents()
assert len(browser.rows) == len(rows)
assert browser.grab().save(str(HERE/('mac_shared.png' if mac else 'windows_shared.png')))
result = dict(package=str(project), shared_bscans=len(rows), volumes=len({r['scan_id'] for r in rows}),
              confirmed_lead=len(confirmed), starred=sum(r['starred'] for r in rows),
              unstarred=sum(not r['starred'] for r in rows), native_macos_tested=False)
(HERE/('mac_live.json' if mac else 'windows_live.json')).write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
