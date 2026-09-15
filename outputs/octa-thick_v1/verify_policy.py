import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json,time
from pathlib import Path
from engine import HERE,ROOT,Volume,sha
import numpy as np
from viewer import Window,QtWidgets
config=json.loads((ROOT/'outputs/octa-seg/octa-seg_v1/launch_config.json').read_text())
paths=[Path(p) for p in json.loads((HERE/'volumes.json').read_text())]
report=[]
for p in paths:
 before=sha(p/'measurements.npz')
 v=Volume(p,config)
 assert np.isfinite(v.maps[0][0][0]).any()
 assert not v.maps[0][1].any()
 out=HERE/'verification'/f'{p.name}_policy_v2.npz'; v.export(out)
 with np.load(out) as d: np.testing.assert_equal(d['exclude_unreliable_um'],v.maps[0][0])
 assert before==sha(p/'measurements.npz')
 report.append({'scan':p.name,'default_coverage':float(np.isfinite(v.maps[0][0][0]).mean()),'include_unreliable_coverage':float(np.isfinite(v.maps[1][0][0]).mean())})
 print(report[-1],flush=True)
app=QtWidgets.QApplication([]); win=Window(paths,config); win.show()
while win.future is not None: app.processEvents(); time.sleep(.02)
assert win.volume is not None
win.row_spin.setValue(256);win.col_spin.setValue(256);app.processEvents()
win.grab().save(str(HERE/'verification/policy_v2.png'))
limits=dict(win.volume.limits); win.preview.setChecked(True);app.processEvents();assert win.volume.limits==limits
win.close();app.processEvents()
(HERE/'verification/policy_v2.json').write_text(json.dumps(report,indent=2))
