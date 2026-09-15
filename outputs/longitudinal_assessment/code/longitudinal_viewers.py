"""Launch existing viewers with longitudinal-only paths and version scope."""
import sys
import subprocess
from pathlib import Path
from longitudinal_assessment import ROOT, OUT, bind, read


def thickness_engine(version):
    sys.path.insert(0, str(ROOT/'outputs/octa-thick_v1'))
    import engine
    engine.HERE = OUT/version/'thick'
    if version == 'v2':
        bind()
        from octa_seg_v2.policy import POLICY_REASONS
        engine.WHY = {**engine.WHY, **POLICY_REASONS}
    base = engine.Volume

    class LongitudinalVolume(base):
        def metadata(self):
            data = super().metadata()
            data.update(model_version=f'octa-seg_{version}', group='longitudinal_assessment',
                        visit=next(r for r in read(OUT/'manifest.json')['visits'] if r['scan_id'] == self.scan_id))
            return data

    return engine, LongitudinalVolume


def launch(action, version, scan=None):
    home = OUT/version
    if action == 'review' and version == 'v2':
        bind()
        from octa_seg_v2.gui import Window, QtWidgets, configure_app, SCANS
        app = QtWidgets.QApplication([]); configure_app(app)
        window = Window(home/'round_000')
        if scan: window.load_scan(SCANS.index(scan))
        window.setWindowTitle('Longitudinal assessment · octa-seg v2')
        window.show(); return app.exec()
    if action == 'review':
        from cnv_review_v1.main import main
        sys.argv = [sys.argv[0], '--config', str(home/'launch_config.json')]
        if scan: sys.argv += ['--scan', scan]
        return main()
    engine, volume_class = thickness_engine(version)
    import viewer
    viewer.Volume = volume_class
    viewer.HERE = home/'thick'
    original = viewer.Window.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.setWindowTitle(f'octa-thick_long_{version} · Longitudinal assessment')

    def correction(self):
        subprocess.Popen([sys.executable, str(Path(__file__).with_name('longitudinal_assessment.py')),
                          'review', '--version', version, '--scan', self.volume.scan_id], cwd=ROOT)

    viewer.Window.__init__ = initialize
    viewer.Window.correction = correction
    sys.argv = [sys.argv[0], '--list', str(home/'thick/volumes.json'),
                '--correction-config', str(home/'launch_config.json')]
    return viewer.main()
