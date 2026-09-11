"""Offscreen real-volume rendering and native alignment; writes no human labels."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import numpy as np
from PySide6 import QtCore,QtWidgets
from cnv_review_v1.gui import MainWindow,configure_app
from .common import *

def run():
    config=read(OUT/'launch_config.json');app=QtWidgets.QApplication([]);configure_app(app)
    window=MainWindow(config,autoload=False);window.resize(1700,1150);window.show()
    window._quality_pending=False
    results=[]
    for sid in SCANS[4:]:
        loop=QtCore.QEventLoop();window.ready.connect(loop.quit)
        index=next(i for i,p in enumerate(window.paths) if p.stem==sid)
        window.load_scan(index);QtCore.QTimer.singleShot(60000,loop.quit);loop.exec();window.ready.disconnect(loop.quit)
        if window.scan is None or window.scan.scan_id!=sid:raise RuntimeError('GUI load failed or timed out')
        prep=read(OUT/'volumes'/sid/'prepared.json');images=np.load(prep['images'],mmap_mode='r')
        for row in (0,255,511):
            np.testing.assert_allclose(window.scan.structural_bscan(row),images[row],atol=1e-5,rtol=0)
        item=next(q for q in read(OUT/'review_queue.json')['examples'] if q['scan_id']==sid)
        window.editor.suggestion=item;window.navigate(item['bscan'],(item['lo']+item['hi'])//2);window.editor.refresh_quality()
        app.processEvents();folder=OUT/'reports/gui';folder.mkdir(parents=True,exist_ok=True)
        window.grab().save(str(folder/f'{sid}.png'))
        results.append(dict(scan_id=sid,native_source_matches_cached_crop=True,rows_checked=[0,255,511],
                   quality_mode=window.editor.quality_mode.isChecked(),metric_warnings_hidden='hidden' in window.editor.quality_status.text()))
    window.close();app.processEvents()
    assert not list((OUT/'reviewer/quality_reviews').glob('*.json'))
    assert not list((OUT/'reviewer/surface_labels').glob('*.npz'))
    atomic_json(OUT/'reports/gui/verification.json',dict(volumes=results,no_quality_or_boundary_labels_created=True,
        rendering='offscreen; not a claim that a desktop window is visible'))
    print(results,flush=True)

if __name__=='__main__':run()
