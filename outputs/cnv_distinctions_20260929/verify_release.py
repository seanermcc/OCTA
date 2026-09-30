"""Inspect actual migrated reviews using each installed package, without saving human work."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from unittest.mock import patch

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--mac', action='store_true')
    args = parser.parse_args()
    passport = Path('F:/octa')
    output = Path('D:/Projects/octa/outputs/cnv_distinctions_20260929')
    project = passport/('Mac_Boundary_Reviewer/project' if args.mac else 'Full/_Project')
    if args.mac:
        os.environ['OCTA_MAC_STATE'] = str(output/'mac_host_check')
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    sys.path[:0] = [str(project/'outputs/octa-seg/octa-seg_v3/review/code'),
                   str(project/'outputs/octa-seg/octa-seg_v2/code'), str(project/'code')]
    import numpy as np
    from octa_seg_v3 import lesions as L
    from octa_seg_v3.common import OUT, fingerprint
    from octa_seg_v3.data import discover, load_volume, VolumeCache
    from octa_seg_v3.gui import Window, configure_v3_app
    from octa_seg_v3.label_gui import QtWidgets
    from octa_seg_v3.saved import describe
    records = json.loads((passport/'CNV_DISTINCTIONS_MIGRATION.json').read_text())['records']
    live = passport/'For_Segmentation/Reviews/reviewers'
    inventories = {who: {p.name: p for p in (live/who/'journals').glob('*.json')} for who in ('lead','shichu')}
    common = set(inventories['lead']) & set(inventories['shichu'])
    positive = {(Path(r['path']).name, r['reviewer']) for r in records if r['columns'] > 0}
    name = next(n for n in sorted(common) if (n, 'lead') in positive and (n, 'shichu') in positive)
    sample = json.loads(inventories['lead'][name].read_text())
    entries = discover(); entry = next(e for e in entries if e['scan_id'] == sample['scan_id'])
    start = time.perf_counter()
    print('Loading real saved case:', name, 'package:', project, flush=True)
    volume = load_volume(entry, image_budget=0)
    app = QtWidgets.QApplication([]); configure_v3_app(app)
    errors = []
    def hook(kind, error, tb):
        errors.append(str(error)); sys.__excepthook__(kind, error, tb)
    sys.excepthook = hook
    checks = []
    for who, kind in L.LEGACY_MAPPING.items():
        source = inventories[who][name]
        before = fingerprint(source)
        destination = OUT/'reviewers'/who/'journals'/name
        if args.mac:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        # Simulate only the label-selection branch on Windows. This is not native Mac execution.
        with patch.object(sys, 'platform', 'darwin' if args.mac else sys.platform):
            w = Window(who, entries=[entry], output=destination.parent.parent, autoload=False, read_only=True,
                       cache=VolumeCache([entry], loader=lambda entry, image_budget: volume))
            w.resize(1700, 1050); w.show(); w.install_volume(volume, 0, sample['bscan'], False)
            app.processEvents(); w.fit(); w.update_map()
            ed = w.editor; state = ed.resolved['lesions']
            assert state[kind].any()
            assert not state['cnv_full' if kind == 'cnv_core' else 'cnv_core'].any()
            assert not state['cnv_region'].any()
            assert not ed.lesion_tools.region_items[kind].path().isEmpty()
            ed.lesion_tools.select(kind)
            if args.mac:
                assert 'Command+drag' in ed.mark_hint.text()
                assert 'Command+drag' in ed.lesion_tools.buttons[kind].toolTip()
            ed.cnv_info.setChecked(True); app.processEvents()
            screenshot = output/f'{"mac_host" if args.mac else "windows"}_{who}.png'
            w.grab().save(str(screenshot))
            ed.show_auto_cnv.setChecked(False); app.processEvents()
            assert not any(i.data(0) == 'cnv_context_outline' for i in ed._extras)
            assert ed.lesion_tools.region_items[kind].isVisible()
            assert fingerprint(source) == before
            assert fingerprint(destination) == before
            checks.append(dict(reviewer=who, scan_id=sample['scan_id'], bscan=sample['bscan'],
                               saved_kind=kind, columns=int(state[kind].sum()), status=ed.resolved['review_status'],
                               indexed_status=describe(destination)['status'], source_unchanged=True,
                               screenshot=str(screenshot), mac_command_labels=args.mac))
            w.close(); app.processEvents()
    assert not errors, errors
    result = dict(package=str(project), real_cases=checks, callback_errors=errors,
                  elapsed_seconds=time.perf_counter()-start, native_macos_execution_tested=False)
    (output/('mac_host_verification.json' if args.mac else 'windows_verification.json')).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
