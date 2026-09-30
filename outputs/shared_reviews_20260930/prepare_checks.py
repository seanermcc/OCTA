from pathlib import Path

HERE = Path(__file__).resolve().parent
project = Path('F:/octa/Full/_Project')
s = (project/'code/verify_shared_filter.py').read_text(encoding='utf-8')
s = s.replace("default=Path(__file__).resolve().parents[1]", "default=Path('F:/octa/Full/_Project')")
s = s.replace("'data_role'}", "'data_role','starred'}")
s = s.replace("patch.object(saved, 'OUT', folder)", "patch.object(saved, 'DATA_ROOT', saved.ROOT), patch.object(saved, 'OUT', folder)")
s = s.replace("lead.navigate(258); lead.ambiguous.setChecked(True)", """lead.navigate(258); lead.ambiguous.setChecked(True)
    lead.navigate(259)
    from octa_seg_v3.controls import confirm
    with patch.object(QtWidgets.QMessageBox, 'exec', return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        assert confirm(lead.editor)
    lead.save_all()
    lead.navigate(260)
    with patch.object(QtWidgets.QMessageBox, 'exec', return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        assert confirm(lead.editor)
    lead.editor.record_event('unreliable', 0, 20)  # Invalidates sharing by confirmation.
    lead.save_all()""")
s = s.replace('== [256,258]', '== [256,258,259]')
s = s.replace('len(browser.rows) == 2', 'len(browser.rows) == 3')
s = s.replace('== [258]', '== [258,259]')
s = s.replace("assert browser.grab().save", """assert browser.table.item(0, 2).text() == 'Shared'
    assert browser.table.item(1, 2).text() == '★ Starred'
    assert browser.table.item(2, 2).text() == 'Shared'
    assert browser.table.item(2, 3).text() == 'Not started'
    browser.kind.setCurrentIndex(1); assert [r['bscan'] for r in browser.rows] == [258]
    browser.kind.setCurrentIndex(2); assert [r['bscan'] for r in browser.rows] == [256,259]
    browser.kind.setCurrentIndex(0)
    assert browser.grab().save""")
s = s.replace("colleague.for_review.setChecked(True); colleague.save_all()", "colleague.for_review.setChecked(True); colleague.editor.record_event('unreliable', 0, 5); colleague.save_all()")
s = s.replace("    # Only the current user's status", "    assert browser.table.item(0, 3).text() == 'Started (draft)'\n    assert all('starred' not in q for q in colleague.queue)\n    # Only the current user's status")
s = s.replace('unflagged_and_unavailable_excluded=True', 'unconfirmed_unflagged_and_unavailable_excluded=True,confirmed_unstarred_included=True,sharing_filters=True,started_status=True')
(HERE/'verify_shared.py').write_text(s, encoding='utf-8')
