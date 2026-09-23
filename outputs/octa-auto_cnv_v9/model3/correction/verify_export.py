"""Check the real export worker without loading or writing human annotations."""
from common import *
from viewer import Window,W,Q,configure_app
from PySide6.QtTest import QTest

app=W.QApplication([]);configure_app(app)
paths=list((HERE/'review').rglob('*.json'));before={str(p):sha(p) for p in paths}
window=Window(autoload=False)
ticks=[];timer=Q.QTimer();timer.timeout.connect(lambda:ticks.append(time.perf_counter()));timer.start(10)
window.export_sizes();assert window.export_process is not None
started=time.perf_counter()
while window.export_process is not None:
    app.processEvents();QTest.qWait(10)
    if time.perf_counter()-started>90:raise TimeoutError('Export worker stalled')
assert 'exported' in window.statusBar().currentMessage(),window.statusBar().currentMessage()
assert len(ticks)>2
summary=read(HERE/'reports/quantification/summary.json')
assert summary['confirmed_images']==34
window.close();app.processEvents()
assert before=={str(p):sha(p) for p in paths}
atomic(HERE/'verification/export_after.json',dict(passed=True,ui_timer_ticks=len(ticks),
    seconds=time.perf_counter()-started,confirmed_images=summary['confirmed_images'],reviews_unchanged=True))
print('PASS: background export, responsive event loop, 34 confirmed images, reviews unchanged',flush=True)
