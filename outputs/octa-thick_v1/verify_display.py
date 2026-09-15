"""Visual smoke check with the explicit Windows font and existing GUI startup."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import time
import json
import numpy as np
from pathlib import Path
from engine import HERE, ROOT, sha
from viewer import Window, QtWidgets

def wait(app, predicate, seconds=90):
    until=time.monotonic()+seconds
    while not predicate() and time.monotonic()<until:
        app.processEvents(); time.sleep(.02)
    if not predicate(): raise RuntimeError('GUI did not become ready')
    app.processEvents()

if __name__=='__main__':
    config_path=ROOT/'outputs/octa-seg/octa-seg_v1/launch_config.json'
    config=json.loads(config_path.read_text()); config['_path']=str(config_path)
    paths=[Path(x) for x in json.loads((HERE/'volumes.json').read_text())]
    app=QtWidgets.QApplication([]); window=Window(paths,config); window.show()
    for i,path in enumerate(paths):
        if i: window.scan_choice.setCurrentIndex(i)
        wait(app,lambda: window.future is None)
        assert window.volume is not None,window.notice.text()
        valid=np.argwhere(np.isfinite(window.volume.maps[1][0][0]))
        row,col=valid[np.argmin(np.sum((valid-256)**2,axis=1))]
        window.row_spin.setValue(int(row)); window.col_spin.setValue(int(col))
        window.preview.setChecked(True); app.processEvents()
        bracket=window.volume.endpoints[1][row,[0,7],col]
        assert any(np.array_equal(line.get_ydata(),bracket) and np.array_equal(line.get_xdata(),[col,col]) for line in window.b_ax.lines)
        window.grab().save(str(HERE/'verification'/f'{path.name}_preview.png'))
        if i==0: window.grab().save(str(HERE/'startup.png'))
        window.preview.setChecked(False); app.processEvents()
        window.grab().save(str(HERE/'verification'/f'{path.name}_reported.png'))
    window.close(); app.processEvents()
    from cnv_review_v1.gui import MainWindow
    labels=[p for root in [Path(config['output']),*[Path(x) for x in config['manual_sources']]] for p in root.rglob('*.npz')]
    before={str(p):sha(p) for p in labels}
    queue=sorted(Path(config['segmentations']).glob('*.npz')); ready=[]
    old=MainWindow(config,queue,0); old.ready.connect(lambda: ready.append(True)); old.show()
    wait(app,lambda: bool(ready),180)
    old.grab().save(str(HERE/'verification/existing_reviewer_startup.png'))
    old.close(); app.processEvents()
    assert before=={str(p):sha(p) for p in labels}
    (HERE/'verification/display.json').write_text(json.dumps(dict(passed=True,font=app.font().family(),all_four_rendered=True,brackets_match=True,existing_gui_startup=True,labels_unchanged=True),indent=2))
    print('All four displays, brackets, and existing reviewer startup passed.')
