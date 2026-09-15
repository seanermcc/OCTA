"""Time actual GUI stroke handling; all records are synthetic and ineligible."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
from pathlib import Path
review = Path(__file__).resolve().parents[1]
root = review.parents[3]
sys.path[:0] = [str(review/'code'), str(review.parent.parent/'octa-seg_v2/code'), str(root/'code')]
import cProfile
import io
import json
import pstats
import time
import numpy as np
from octa_seg_v3.verify import fixture
from octa_seg_v3.gui import Window, configure_v3_app
from octa_seg_v3.data import VolumeCache
from octa_seg_v3.label_gui import QtWidgets, QtCore
from octa_seg_v3.controls import confirm

folder = review/'verification'/('drawing_' + sys.argv[1] + '_' + str(time.time_ns()))
folder.mkdir(parents=True)
app = QtWidgets.QApplication([])
QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(folder/'settings'))
configure_v3_app(app)
volume = fixture(folder)
window = Window('synthetic_performance', entries=[volume.entry], output=folder/'synthetic_performance', autoload=False,
    cache=VolumeCache([volume.entry], loader=lambda entry, image_budget: volume), queue_output=folder/'queues')
window.resize(1550, 950); window.show(); app.processEvents()
window.install_volume(volume, 0, 256, False); app.processEvents()
ed = window.editor
ed.surface_list.setCurrentRow(1)
times = []
prof = cProfile.Profile()
for i in range(30):
    if i == 5:
        assert confirm(ed)
    prof.enable()
    start = time.perf_counter()
    ed.on_stroke(np.arange(100., 240.), np.full(140, 46. + i%3))
    app.processEvents()
    times.append((time.perf_counter()-start)*1000)
    prof.disable()
stream = io.StringIO()
pstats.Stats(prof, stream=stream).sort_stats('cumulative').print_stats(35)
(folder/'profile.txt').write_text(stream.getvalue())
result = dict(median_ms=float(np.median(times)), last_ten_median_ms=float(np.median(times[-10:])), max_ms=max(times), samples_ms=times)
(folder/'timings.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result)); print(stream.getvalue()); print(folder)
window.close(); app.processEvents()
