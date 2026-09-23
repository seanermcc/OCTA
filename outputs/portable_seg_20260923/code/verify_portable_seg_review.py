"""Exercise the portable GUI with all home-project reads and MAT/RAW opens denied."""
import argparse
import gc
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

parser=argparse.ArgumentParser()
parser.add_argument('package', type=Path)
args=parser.parse_args()
root=args.package.resolve()
review=root/'outputs/octa-seg/octa-seg_v3/review'
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.dont_write_bytecode=True
sys.path[:0]=[str(review/'code'),str(review.parent.parent/'octa-seg_v2/code'),str(root/'code')]
from octa_seg_v3.common import ROOT, OUT, read, fingerprint
assert ROOT==root, (ROOT,root)
from octa_seg_v3 import portable
from octa_seg_v3.data import discover, load_volume, local_path
from octa_seg_v3.gui import Window, configure_v3_app
from octa_seg_v3.label_gui import QtCore, QtWidgets
from octa_seg_v3.feedback import resolve, training_targets
from octa_seg_v3.verify_review import qt_checks
import numpy as np

denied=[]
def audit(event, arguments):
    if event!='open' or not arguments or not isinstance(arguments[0],(str,bytes,os.PathLike)):
        return
    path=Path(os.fsdecode(arguments[0])).resolve()
    forbidden=path.suffix.lower() in ('.raw','.mat')
    for source_root in (Path('G:/OCT_TreeShrew'),Path('F:/OCT_TreeShrew')):
        forbidden |= path.is_relative_to(source_root) and not path.is_relative_to(root)
    if forbidden:
        denied.append(str(path))
        raise RuntimeError('Test blocked external source access: '+str(path))
sys.addaudithook(audit)

manifest=portable.manifest()
assert not list(root.rglob('*.mat')) and not list(root.rglob('*.RAW'))
folder=OUT/'verification'/('portable_'+time.strftime('%Y%m%d_%H%M%S'))
folder.mkdir(parents=True)
QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat,QtCore.QSettings.Scope.UserScope,str(folder/'preferences'))
app=QtWidgets.QApplication([])
configure_v3_app(app)
errors=[]
sys.excepthook=lambda typ,exc,tb:errors.append(str(exc))
results=[]
entries=discover()
assert len(entries)==len(manifest['scans'])
for number,entry in enumerate(entries):
    sid=entry['scan_id']; rec=manifest['scans'][sid]
    print('Verify',sid,flush=True)
    volume=load_volume(entry,image_budget=0)
    assert volume.model_id==rec['model_id']
    assert list(volume.images.shape)==rec['image_shape']
    # Verify all home/stale drive aliases resolve inside this exact package.
    for old,relative in manifest['aliases'].items():
        assert local_path(old)==portable.inside(relative)
        assert local_path('Z:/moved/renamed-package/'+relative)==portable.inside(relative)
    window=Window('lead',entries=[entry],autoload=False,read_only=True)
    window.resize(1600,1000); window.show(); app.processEvents()
    with patch.object(QtWidgets.QMessageBox,'critical',side_effect=lambda *a: errors.append(str(a[2]))):
        window.install_volume(volume,0,rec['confirmed_bscans'][0],False)
        for case in [c for c in manifest['confirmed_cases'] if c['scan_id']==sid]:
            window.navigate(case['bscan']); app.processEvents()
            original=read(root/case['path'])
            assert window.editor.journal.data==original
            assert window.editor.resolved['review_status']=='Confirmed'
            row=case['bscan']
            state=resolve(original['events'][:original['cursor']],volume.data['raw_position_branch'][row],
                          int(volume.data['label_offset']),volume.images.shape[1])
            np.testing.assert_array_equal(window.editor.resolved['positions'],state['positions'])
            training_targets(original,volume.data['raw_position_branch'][row],int(volume.data['label_offset']),
                             volume.images.shape[1],volume.data['shadow'][row],vessel=volume.overlays[1][row])
            results.append(dict(scan_id=sid,bscan=row,status='Confirmed',journal_unchanged=True))
        # Adjacent browsing and complete native range must still work.
        window.navigate(0); app.processEvents()
        window.navigate(volume.images.shape[0]-1); app.processEvents()
        window.navigate(rec['confirmed_bscans'][0]); window.fit(); app.processEvents()
        if number in (0,len(entries)-1):
            assert window.grab().save(str(folder/f'{sid}.png'))
        assert not errors,errors
        window.close(); app.processEvents()
    del window,volume
    gc.collect()

# Existing synthetic Qt checks exercise actual GUI gestures, save, undo, confirm,
# reopen, independent reviewer IDs and queue behavior. They never label a real scan.
# Context fixtures bypass portable overlays because their scan is intentionally synthetic.
with patch('octa_seg_v3.portable.enabled',return_value=False):
    synthetic=qt_checks(app,folder/'synthetic')

for relative,digest in manifest['copied_human_files'].items():
    assert fingerprint(root/relative)==digest, 'Copied human record changed: '+relative
assert not denied,denied
assert not errors,errors
probe=next(iter(manifest['scans'].values()))['context']
portable._verify.cache_clear()
with patch('octa_seg_v3.portable.fingerprint',return_value='simulated-corruption'):
    try: portable.verify(probe)
    except ValueError: pass
    else: raise AssertionError('Changed cache was accepted')
portable._verify.cache_clear()
portable.verify(probe)
# A nonexistent alias is rejected even if some external source were available.
try: local_path('G:/OCT_TreeShrew/octa/__not_in_package__')
except FileNotFoundError: pass
else: raise AssertionError('Portable resolver permitted an external fallback')

report=dict(status='passed',package=str(root),volumes=len(entries),confirmed_cases=results,
    external_source_access_attempts=denied,original_mat_raw_files_required=False,
    human_files_unchanged=len(manifest['copied_human_files']),synthetic_gui=synthetic,
    gui_errors=errors,screenshots=str(folder),python_environment=sys.prefix,
    corrupted_cache_rejected=True,relocated_drive_aliases_checked=True,
    note='Real scans read-only; synthetic save/confirm tests only. Offscreen Qt rendering.')
(root/'PORTABLE_VALIDATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
