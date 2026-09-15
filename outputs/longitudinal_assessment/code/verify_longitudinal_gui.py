"""Read-only render checks for the actual longitudinal viewers."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
from longitudinal_assessment import OUT, bind, read


def main():
    version = sys.argv[1] if len(sys.argv)>1 else 'v1'
    assert version in ('v1', 'v2')
    sid = read(OUT/'manifest.json')['scans'][0]
    bind(sid)
    from PySide6 import QtWidgets, QtCore
    from octa_seg_v2.gui import Window, configure_app
    app = QtWidgets.QApplication([])
    configure_app(app)
    window = Window(feedback_dir=OUT/'verification/read_only_review')
    window.show(); app.processEvents(); window.fit(); app.processEvents()
    assert window.scan.scan_id == sid and len(window.images) == 512
    window.grab().save(str(OUT/'verification/v2_reviewer.png'))
    window.hide()
    from longitudinal_viewers import thickness_engine
    engine, cls = thickness_engine(version)
    import viewer
    viewer.HERE = OUT/f'verification/thick_{version}'; viewer.HERE.mkdir(parents=True, exist_ok=True)
    viewer.Volume = cls
    config = read(OUT/version/'launch_config.json'); config['_path'] = str(OUT/version/'launch_config.json')
    thick = viewer.Window([OUT/version/('volumes' if version=='v1' else 'round_000/volumes')/sid], config)
    thick.show()
    def ready():
        if thick.volume is None:
            QtCore.QTimer.singleShot(100, ready); return
        thick.navigate(); app.processEvents()
        assert thick.volume.shape == (512,512)
        thick.grab().save(str(OUT/f'verification/{version}_thick.png'))
        print(f'Longitudinal v2 reviewer and {version} octa-thick rendered successfully', flush=True)
        app.quit()
    QtCore.QTimer.singleShot(100, ready)
    QtCore.QTimer.singleShot(60000, app.quit)
    app.exec()
    assert (OUT/f'verification/{version}_thick.png').exists()
    thick.pool.shutdown(wait=True)


if __name__ == '__main__': main()
