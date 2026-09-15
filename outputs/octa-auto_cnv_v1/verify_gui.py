"""Read-only native viewer interaction checks; no annotation saving."""
from common import *
from viewer_auto import Window, QtWidgets, configure_app
from types import SimpleNamespace

app = QtWidgets.QApplication([]); configure_app(app)
w = Window('TS267_OD_2025-04-16_D56_s01_100746')
w.show(); app.processEvents()
checks = []
for name in ('default', 'narrow_halo', 'wide_halo', 'lower_reference', 'upper_reference', 'plane_reference'):
    w.variant.setCurrentText(name)
    current = w.current()
    np.testing.assert_array_equal(current['deficit_percent'], w.data[name+'__deficit_percent'])
    checks.append('variant '+name)
w.branch.setCurrentIndex(1)
np.testing.assert_array_equal(w.current()['deficit_percent'], w.data['assisted__deficit_percent'])
assert not w.variant.isEnabled()
checks.append('assisted branch distinct')
w.branch.setCurrentIndex(0); w.variant.setCurrentText('default')
for i in range(w.map_choice.count()):
    w.map_choice.setCurrentIndex(i); app.processEvents()
    checks.append('display '+str(i))
w.map_choice.setCurrentIndex(0)
w.click(SimpleNamespace(inaxes=w.map_ax, xdata=117.1, ydata=381.1))
assert (w.row, w.col) == (381, 117)
assert np.array_equal(w.b_ax.images[0].get_array(), w.images[381])
checks.append('click/native B-scan mapping')
for check in w.checks.values():
    check.setChecked(True)
app.processEvents()
w.grab().save(str(destination(HERE/'verification/all_overlays.png')))
write(HERE/'verification/gui_checks.json', dict(checks=checks, annotation_writes=False))
w.close()
