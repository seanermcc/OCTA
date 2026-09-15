"""Four-volume pilot smoke test; writes only verification artifacts here."""
import json
import os
from pathlib import Path
import time
import numpy as np
os.environ['QT_QPA_PLATFORM']='offscreen'
from engine import HERE, ROOT, Volume, sha, LAYERS
from viewer import Window, QtWidgets

def run():
    config_path=ROOT/'outputs/octa-seg/octa-seg_v1/launch_config.json'
    config=json.loads(config_path.read_text()); config['_path']=str(config_path)
    paths=[Path(x) for x in json.loads((HERE/'volumes.json').read_text())]
    out=HERE/'verification'; out.mkdir(exist_ok=True)
    protected=set()
    for path in paths:
        protected.update(path.glob('*.npz')); protected.update(path.glob('*.json')); protected.add(path/'images.npy')
    for root in [Path(config['output'])/'surface_labels',*[Path(x) for x in config['manual_sources']]]:
        for path in paths: protected.update(root.glob(f'{path.name}_b*.npz'))
    protected.update((Path(config['output'])/'estimate_feedback').glob('*.json'))
    before={str(p):sha(p) for p in protected}
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window=Window(paths,config); window.show()
    results=[]
    for i,path in enumerate(paths):
        if i: window.scan_choice.setCurrentIndex(i)
        deadline=time.monotonic()+90
        while window.future is not None and time.monotonic()<deadline:
            app.processEvents(); time.sleep(.02)
        if window.future is not None: raise RuntimeError('Loading timed out')
        v=window.volume
        assert v is not None,window.details.toPlainText()
        assert v.scan_id==path.name
        baseline=v.revision
        records=[]
        for mode in (0,1):
            window.preview.setChecked(bool(mode))
            for k in range(8):
                window.layer_choice.setCurrentIndex(k)
                window.row_spin.setValue(127); window.col_spin.setValue(203); app.processEvents()
                point=v.point(127,203,mode)[k]; value=v.maps[mode][0][k,127,203]
                assert (point['thickness_um'] is None and np.isnan(value)) or point['thickness_um']==value
                assert np.isnan(v.maps[mode][0][:,v.g['shadow']]).all()
            records.append([dict(layer=n,finite_percent=float(np.isfinite(v.maps[mode][0][k]).mean()*100),
                        estimated_percent=float(v.maps[mode][1][k].mean()*100)) for k,(n,_,_) in enumerate(LAYERS)])
        window.layer_choice.setCurrentIndex(0); app.processEvents()
        window.grab().save(str(out/f'{path.name}_preview.png'))
        window.preview.setChecked(False); app.processEvents()
        window.grab().save(str(out/f'{path.name}_reported.png'))
        export=out/f'{path.name}.npz'; v.export(export)
        with np.load(export) as d:
            np.testing.assert_equal(d['reported_um'],v.maps[0][0]); np.testing.assert_equal(d['preview_um'],v.maps[1][0])
            np.testing.assert_equal(np.isfinite(d['estimated_um']),v.maps[1][1])
        v.save_point(out/f'{path.name}_point.csv',127,203,1)
        limits=dict(v.limits); v.reload(); assert v.revision==baseline; assert v.limits==limits
        results.append(dict(scan_id=path.name,reported=records[0],preview=records[1],stale_context_rows=v.stale_context_rows))
    # Exercise actual PNG/NPZ/JSON export handler, then exact click and bracket position.
    window.preview.setChecked(True); window.export()
    from types import SimpleNamespace
    window.click(SimpleNamespace(xdata=13.2,ydata=17.2,inaxes=window.en_ax))
    assert (window.row,window.col)==(17,13)
    assert window.row_spin.value()==17 and window.col_spin.value()==13
    after={str(p):sha(p) for p in protected}
    assert before==after,'Protected source or label changed'
    (out/'report.json').write_text(json.dumps(dict(passed=True,protected_files_byte_identical=len(before),volumes=results),indent=2))
    window.close(); app.processEvents()
    print(json.dumps(dict(passed=True,protected_files_byte_identical=len(before),volumes=len(results))))

if __name__=='__main__': run()
