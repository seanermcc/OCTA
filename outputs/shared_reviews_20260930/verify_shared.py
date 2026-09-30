"""Exercise the shared selector with synthetic GUI-authored records only."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

p = argparse.ArgumentParser()
p.add_argument('--package', type=Path, default=Path('F:/octa/Full/_Project'))
p.add_argument('--real-index-only',action='store_true')
args = p.parse_args()
root = args.package.resolve()
review = root/'outputs/octa-seg/octa-seg_v3/review'
sys.path[:0] = [str(review/'code'), str(review.parent.parent/'octa-seg_v2/code'), str(root/'code')]
sys.dont_write_bytecode = True
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from octa_seg_v3.common import OUT, fingerprint
from octa_seg_v3.gui import Window, configure_v3_app
from octa_seg_v3.data import VolumeCache
from octa_seg_v3.verify import fixture
from octa_seg_v3 import saved
from PySide6 import QtCore, QtWidgets
from PySide6.QtTest import QTest

if args.real_index_only:
    from octa_seg_v3.data import discover
    from octa_seg_v3 import portable
    entries = discover()
    cases = saved.shared_cases('lead', entries)
    assert all(set(r) == {'scan_id','bscan','provider','model_id','data_role','starred'} for r in cases)
    if portable.enabled():
        for case in cases:
            record = portable.manifest()['scans'][case['scan_id']]
            assert portable.local_path(case['provider']) == portable.inside(record['directory'])
            assert case['model_id'] == record['model_id']
            assert 0 <= case['bscan'] < record['image_shape'][0]
    print(json.dumps(dict(available_volumes=len(entries),shared_bscans=len(cases),
        shared_volumes=len({r['scan_id'] for r in cases}),cases=cases),indent=2),flush=True)
    raise SystemExit(0)

folder = OUT/'verification'/('shared_filter_'+time.strftime('%Y%m%d_%H%M%S'))
folder.mkdir(parents=True)
app = QtWidgets.QApplication([]); configure_v3_app(app)
settings_type = QtCore.QSettings
errors = []
def record_error(typ, value, tb):
    import traceback
    traceback.print_exception(typ, value, tb)
    errors.append(str(value))
sys.excepthook = record_error

with patch('octa_seg_v3.portable.enabled', return_value=False), \
     patch.object(saved, 'DATA_ROOT', saved.ROOT), patch.object(saved, 'OUT', folder), patch.object(saved, 'V3', folder/'legacy'), \
     patch.object(QtCore, 'QSettings', side_effect=lambda *a, **kw: settings_type(str(folder/'settings.ini'), settings_type.Format.IniFormat)):
    volume = fixture(folder)
    missing = fixture(folder, 'SYNTHETIC_NOT_IN_PACKAGE')
    entries = [volume.entry, missing.entry]
    volumes = {v.entry['scan_id']: v for v in (volume, missing)}
    def window(owner, available):
        return Window(owner, entries=available, output=folder/'reviewers'/owner, autoload=False,
            cache=VolumeCache(available, loader=lambda entry, image_budget: volumes[entry['scan_id']]),
            queue_output=folder/'queues')
    lead = window('lead', entries)
    lead.show(); lead.install_volume(volume, 0, 256, False); app.processEvents()
    lead.for_review.setChecked(True)
    lead.editor.record_event('unreliable', 0, 20)
    lead.notes.setPlainText('Private lead note must not appear for coworker'); lead.save_all()
    lead.navigate(257); lead.for_review.setChecked(True); lead.for_review.setChecked(False)
    lead.navigate(258); lead.ambiguous.setChecked(True)
    lead.navigate(259)
    from octa_seg_v3.controls import confirm
    with patch.object(QtWidgets.QMessageBox, 'exec', return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        assert confirm(lead.editor)
    lead.save_all()
    lead.navigate(260)
    with patch.object(QtWidgets.QMessageBox, 'exec', return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        assert confirm(lead.editor)
    lead.editor.record_event('unreliable', 0, 20)  # Invalidates sharing by confirmation.
    lead.save_all()
    lead.install_volume(missing, 1, 256, False); lead.for_review.setChecked(True)
    lead.close(); app.processEvents()
    human = {str(f): fingerprint(f) for f in (folder/'reviewers/lead').rglob('*') if f.is_file()}
    colleague = window('colleague', [volume.entry])
    colleague.resize(1600,1000); colleague.show()
    colleague.install_volume(volume, 0, 255, False); app.processEvents()
    QTest.mouseClick(colleague.shared_button, QtCore.Qt.MouseButton.LeftButton); app.processEvents()
    browser = colleague.shared_browser
    assert browser.owner.currentText() == 'lead'
    assert [r['bscan'] for r in browser.rows] == [256,258,259], browser.rows
    assert all(set(r) == {'scan_id','bscan','provider','model_id','data_role','starred'} for r in browser.rows)
    browser.search.setText('not_found'); assert not browser.rows and not browser.open_button.isEnabled()
    browser.search.setText('SYNTHETIC_GUI'); assert len(browser.rows) == 3
    assert browser.table.item(0, 2).text() == 'Shared'
    assert browser.table.item(1, 2).text() == '★ Starred'
    assert browser.table.item(2, 2).text() == 'Shared'
    assert browser.table.item(2, 3).text() == 'Not started'
    browser.kind.setCurrentIndex(1); assert [r['bscan'] for r in browser.rows] == [258]
    browser.kind.setCurrentIndex(2); assert [r['bscan'] for r in browser.rows] == [256,259]
    browser.kind.setCurrentIndex(0)
    assert browser.grab().save(str(folder/'shared_list.png'))
    QTest.mouseClick(browser.open_button, QtCore.Qt.MouseButton.LeftButton)
    for _ in range(50):
        app.processEvents(); colleague.poll_cache()
        if colleague._pending is None: break
        QTest.qWait(20)
    assert colleague.row == 256 and colleague.reviewer == 'colleague'
    assert not colleague.editor.resolved['drawn'].any() and not colleague.editor.resolved['approved'].any()
    assert colleague.notes.toPlainText() == '' and not colleague.for_review.isChecked()
    assert not list((colleague.output/'journals').glob('*.json'))
    colleague.queue_step(1); assert colleague.row == 258
    colleague.queue_step(-1); assert colleague.row == 256
    # Saving must use only the coworker's identity; the lead files stay byte-for-byte intact.
    colleague.for_review.setChecked(True); colleague.editor.record_event('unreliable', 0, 5); colleague.save_all()
    assert colleague.editor.journal.data['reviewer_id'] == 'colleague'
    assert str(colleague.editor.journal.path).startswith(str(colleague.output))
    colleague.show_shared()
    assert browser.table.item(0, 3).text() == 'Started (draft)'
    assert all('starred' not in q for q in colleague.queue)
    # Only the current user's status is used by the unfinished filter.
    original_index = saved.index
    def with_confirmation(owner, output=None, include_tags=False):
        rows = original_index(owner, output, include_tags)
        if owner == 'colleague':
            rows.append(dict(scan_id=volume.scan.scan_id, bscan=256, status='Confirmed'))
        return rows
    with patch.object(saved, 'index', side_effect=with_confirmation):
        browser.unfinished.setChecked(True)
        assert [r['bscan'] for r in browser.rows] == [258,259]
    browser.unfinished.setChecked(False)
    browser.owner.setCurrentText('colleague'); assert [r['bscan'] for r in browser.rows] == [256]
    browser.owner.setCurrentText('lead'); assert len(browser.rows) == 3
    colleague.close(); app.processEvents()
    assert human == {str(f): fingerprint(f) for f in (folder/'reviewers/lead').rglob('*') if f.is_file()}
    assert not errors, errors

report = dict(status='passed',shared_and_ambiguous_flags=True,unconfirmed_unflagged_and_unavailable_excluded=True,confirmed_unstarred_included=True,sharing_filters=True,started_status=True,
    metadata_only_cases_included=True,search_and_empty_state=True,own_unfinished_filter=True,
    filtered_navigation=True,independent_reviewer_save=True,lead_records_unchanged=True,
    other_reviewer_answers_not_loaded=True,gui_errors=errors,screenshots=str(folder))
(folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
