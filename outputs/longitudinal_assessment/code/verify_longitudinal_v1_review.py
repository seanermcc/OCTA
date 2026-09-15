"""Read-only startup check of the v1 longitudinal correction provider."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import numpy as np
from pathlib import Path
from longitudinal_assessment import OUT, read
from cnv_review_v1.gui import MainWindow, QtWidgets, configure_app
from PySide6 import QtCore


def main():
    app = QtWidgets.QApplication([]); configure_app(app)
    config = read(OUT/'v1/launch_config.json')
    config['output'] = str(OUT/'verification/read_only_v1_review')
    paths = sorted(Path(config['segmentations']).glob('*.npz'))
    window = MainWindow(config, paths[:1], 0)
    def ready():
        assert window.editor._raw_ilm is not None
        assert window.scan.native_shape == (512,512)
        with np.load(OUT/'v1/volumes'/window.scan.scan_id/'geometry.npz') as g:
            np.testing.assert_equal(window.vessels, g['vessel'])
        window.navigate(256,256); app.processEvents(); window.fit_all(); app.processEvents()
        window.grab().save(str(OUT/'verification/v1_reviewer.png'))
        print('V1 longitudinal reviewer loaded, including native raw-ILM preview', flush=True)
        app.quit()
    window.ready.connect(ready)
    window.show(); QtCore.QTimer.singleShot(60000, app.quit); app.exec()
    if window.loader and window.loader.isRunning(): window.loader.wait()
    assert (OUT/'verification/v1_reviewer.png').exists()


if __name__ == '__main__': main()
