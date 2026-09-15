"""Native map inspection with linked B-scans and established region editing."""
import argparse
import subprocess
from types import SimpleNamespace
from common import *
from algorithm import VARIANTS, run, grow
from PySide6 import QtCore, QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.widgets import LassoSelector
from matplotlib.path import Path as MplPath
from cnv_review_v1.gui import configure_app


class Window(QtWidgets.QMainWindow):
    def __init__(self, sid=None):
        super().__init__()
        self.setWindowTitle('octa-auto_cnv_v1 · Experimental CNV and thinning')
        self.resize(1560, 1000)
        self.row, self.col = 256, 256
        self.data = None
        self.lasso = None
        self.user_maps = None
        root = QtWidgets.QWidget(); self.setCentralWidget(root)
        layout = QtWidgets.QVBoxLayout(root)
        bar = QtWidgets.QHBoxLayout(); layout.addLayout(bar)
        self.scan = QtWidgets.QComboBox()
        for visit in selected():
            if (HERE/'scans'/visit['scan_id']/'maps.npz').exists():
                self.scan.addItem(visit['scan_id'])
        bar.addWidget(self.scan, 2)
        self.branch = QtWidgets.QComboBox(); self.branch.addItems(['Automatic inputs', 'Assisted viewer inputs'])
        bar.addWidget(self.branch)
        self.variant = QtWidgets.QComboBox(); self.variant.addItems(list(VARIANTS))
        bar.addWidget(self.variant)
        self.map_choice = QtWidgets.QComboBox(); self.map_choice.addItems(['Signed deficit (%)', 'Expected background (µm)', 'Full retina (µm)', 'Reference sensitivity (pp)', 'Missing / exclusions'])
        bar.addWidget(self.map_choice)
        opts = QtWidgets.QHBoxLayout(); layout.addLayout(opts)
        self.checks = {}
        for name in ('Cores', 'Footprints', 'Manual', 'Background regions', 'Unsupported', 'Uncertain margins', '10%', '20%', '30%'):
            check = QtWidgets.QCheckBox(name); check.setChecked(name in ('Cores', 'Manual', 'Unsupported', '10%', '20%', '30%'))
            opts.addWidget(check); self.checks[name] = check
            check.toggled.connect(self.draw)
        self.bscan = QtWidgets.QSpinBox(); self.bscan.setRange(0, 511); self.bscan.setValue(self.row)
        opts.addWidget(QtWidgets.QLabel('B-scan')); opts.addWidget(self.bscan)
        self.notice = QtWidgets.QLabel(); self.notice.setWordWrap(True); layout.addWidget(self.notice)
        self.figure = Figure(figsize=(14, 8), layout='constrained')
        self.canvas = FigureCanvasQTAgg(self.figure); layout.addWidget(self.canvas, 1)
        actions = QtWidgets.QHBoxLayout(); layout.addLayout(actions)
        for text, fn in [('Edit proposals', self.edit_proposals), ('Exclude background area', self.exclude),
                         ('Reset background selection', self.reset_background), ('Export displayed image', self.export),
                         ('Open report', self.open_report)]:
            b = QtWidgets.QPushButton(text); b.clicked.connect(fn); actions.addWidget(b)
        self.scan.currentIndexChanged.connect(self.load)
        self.branch.currentIndexChanged.connect(self.draw)
        self.variant.currentIndexChanged.connect(self.draw)
        self.map_choice.currentIndexChanged.connect(self.draw)
        self.bscan.valueChanged.connect(self.navigate)
        self.canvas.mpl_connect('button_press_event', self.click)
        if sid:
            self.scan.setCurrentText(sid)
        self.load()

    def load(self, *_):
        sid = self.scan.currentText()
        if not sid:
            self.notice.setText('Run RUN_PILOT.cmd to create maps first.'); return
        self.notice.setText('Loading saved native maps…'); QtWidgets.QApplication.processEvents()
        self.data = npz(HERE/'scans'/sid/'maps.npz')
        self.meta = json.loads(str(self.data['metadata_json']))
        self.images = np.load(volume_path(sid)/'images.npy', mmap_mode='r')
        self.user_excluded = np.zeros((512, 512), bool)
        self.user_maps = None
        saved = HERE/'background_review'/sid/'selection.npz'
        if saved.exists():
            d = npz(saved)
            if str(d['source_sha256']) == sha(HERE/'scans'/sid/'maps.npz'):
                self.user_excluded = d['excluded']
                if (saved.parent/'maps.npz').exists():
                    self.user_maps = npz(saved.parent/'maps.npz')
        self.draw()

    def current(self):
        a = self.data
        if self.branch.currentIndex():
            result = {k: a['assisted__'+k] for k in ('background_um', 'background_supported', 'deficit_percent', 'core', 'footprint')}
            result['background_regions'] = a.get('assisted__background_regions', np.zeros((512, 512), bool))
            return result
        if self.user_maps is not None and self.variant.currentText() == 'default':
            return self.user_maps
        variant = self.variant.currentText()
        result = {k: a[variant+'__'+k] for k in ('background_regions', 'background_supported', 'deficit_percent', 'core', 'footprint')}
        # Variant reference is recoverable only where measurement and deficit exist;
        # save full surfaces on disk for unsupported-reference inspection.
        result['background_um'] = a.get(variant+'__background_um', a['background_um'])
        return result

    @staticmethod
    def contour(ax, mask, color, width=1):
        if mask.any() and not mask.all():
            ax.contour(mask, [.5], colors=[color], linewidths=width)

    def draw(self, *_):
        if self.data is None:
            return
        if self.lasso is not None:
            self.lasso.disconnect_events(); self.lasso = None
        a, m = self.data, self.current()
        self.variant.setEnabled(not self.branch.currentIndex())
        self.figure.clear()
        grid = self.figure.add_gridspec(2, 2, height_ratios=[1, .7])
        self.struct_ax = self.figure.add_subplot(grid[0, 0])
        self.map_ax = self.figure.add_subplot(grid[0, 1])
        self.b_ax = self.figure.add_subplot(grid[1, :])
        lo, hi = np.percentile(a['enface'], [2, 98])
        for ax in (self.struct_ax, self.map_ax):
            ax.imshow(a['enface'], cmap='gray', vmin=lo, vmax=hi, interpolation='nearest')
        choice = self.map_choice.currentIndex()
        thickness = a['viewer_thickness_um' if self.branch.currentIndex() else 'automatic_thickness_um']
        if choice < 4:
            values, label, cmap, lim = [
                (m['deficit_percent'], 'Signed deficit (%)', 'coolwarm', (-30, 40)),
                (m['background_um'], 'Estimated reference (µm)', 'viridis', (180, 360)),
                (thickness, 'Full retina (µm)', 'viridis', (180, 360)),
                (a['deficit_sensitivity_span'], 'Automatic reference span (pp)', 'magma', (0, 15)),
            ][choice]
            heat = self.map_ax.imshow(values, cmap=cmap, vmin=lim[0], vmax=lim[1], interpolation='nearest')
            self.figure.colorbar(heat, ax=self.map_ax, label=label, fraction=.035)
        else:
            rgba = np.zeros((512, 512, 4))
            rgba[~np.isfinite(thickness)] = (1, .2, .5, .7)
            rgba[a['shadow'] | a['vessel']] = (.2, .6, 1, .8)
            rgba[a['low_signal']] = (.9, .6, .1, .6)
            self.map_ax.imshow(rgba)
        for ax in (self.struct_ax, self.map_ax):
            for name, key, color in [('Cores', 'core', '#ff6048'), ('Footprints', 'footprint', '#ffdb55')]:
                if self.checks[name].isChecked(): self.contour(ax, m[key], color)
            if self.checks['Manual'].isChecked(): self.contour(ax, a['manual_cnv'], '#57e4ff')
            if self.checks['Background regions'].isChecked():
                self.contour(ax, m.get('background_regions', a['background_regions']), '#b7ff72', .6)
                self.contour(ax, self.user_excluded, '#d874ff', 1)
            if self.checks['Unsupported'].isChecked():
                self.contour(ax, m['background_supported'], '#eeeeee', .7)
            if self.checks['Uncertain margins'].isChecked():
                margin = grow(m['core'] | m['footprint'], 15) & (~m['background_supported'] | a['vessel'] | a['shadow'])
                self.contour(ax, margin, '#ea84ff', 1)
            ax.axhline(self.row, color='coral', lw=.6); ax.axvline(self.col, color='coral', lw=.6)
            ax.set_xlabel('Native A-line'); ax.set_ylabel('Native B-scan')
        for t, c in ((10, 'gold'), (20, 'orange'), (30, 'red')):
            if self.checks[f'{t}%'].isChecked(): self.contour(self.map_ax, m['deficit_percent'] >= t, c, .6)
        self.struct_ax.set_title('Structural context · red core · cyan manual · yellow footprint')
        self.map_ax.set_title(self.map_choice.currentText()+' · '+('assisted default' if self.branch.currentIndex() else self.variant.currentText()))
        image = self.images[self.row]
        lo, hi = np.percentile(image, [2, 99])
        self.b_ax.imshow(image, cmap='gray', vmin=lo, vmax=hi, aspect='auto')
        for k, c in ((0, '#55dfff'), (1, '#ffb65c')):
            self.b_ax.plot(a['automatic_endpoints_crop_px'][self.row, k], color=c, lw=.8)
        self.b_ax.axvline(self.col, color='coral', lw=.7)
        self.b_ax.set_ylim(image.shape[0]-.5, -.5)
        self.b_ax.set_title('Saved neural ILM / outer RPE · canonical cropped depth (px)')
        self.b_ax.set_xlabel('Native A-line')
        y, x = self.row, self.col
        value = float(m['deficit_percent'][y, x])
        thickness_text = f'{thickness[y,x]:.1f} µm' if np.isfinite(thickness[y,x]) else 'unavailable'
        deficit_text = f'{value:.1f}%' if np.isfinite(value) else 'unavailable'
        audit = self.meta['audit']
        causes = [label for bit, label in audit['cause_bits'].items() if a['unavailable_cause_bits'][y, x] & int(bit)]
        self.notice.setText(f"{self.scan.currentText()} · pixel ({y}, {x}) · thickness {thickness_text} · deficit {deficit_text} · "
                           f"{'reference supported' if m['background_supported'][y,x] else 'UNSUPPORTED reference'} · "
                           f"{'; '.join(causes) or 'no exclusion flags'}\n"
                           'Experimental; training overlap. White boundary encloses supported reference. Missing values are not zero. '
                           + ('User-adjusted reference active; automatic proposals remain unchanged on disk.' if self.user_maps is not None else ''))
        self.canvas.draw_idle()

    def navigate(self, value):
        self.row = value; self.draw()

    def click(self, event):
        if self.lasso is not None or event.xdata is None or event.ydata is None:
            return
        if event.inaxes in (self.struct_ax, self.map_ax):
            self.row = int(np.clip(np.floor(event.ydata+.5), 0, 511))
            self.col = int(np.clip(np.floor(event.xdata+.5), 0, 511))
        elif event.inaxes == self.b_ax:
            self.col = int(np.clip(np.floor(event.xdata+.5), 0, 511))
        else:
            return
        self.bscan.blockSignals(True); self.bscan.setValue(self.row); self.bscan.blockSignals(False)
        self.draw()

    def exclude(self):
        self.branch.setCurrentIndex(0); self.variant.setCurrentText('default')
        self.notice.setText('Drag a closed outline on the structural panel to exclude that area from background fitting. This saves a separate assisted reference selection.')
        self.lasso = LassoSelector(self.struct_ax, self.excluded)

    def excluded(self, vertices):
        yy, xx = np.indices(self.user_excluded.shape)
        self.user_excluded |= MplPath(vertices).contains_points(np.c_[xx.ravel(), yy.ravel()]).reshape(yy.shape)
        self.recompute()

    def recompute(self):
        a = self.data
        self.notice.setText('Refitting the separately saved user-adjusted background…'); QtWidgets.QApplication.processEvents()
        maps, diag = run(a['automatic_thickness_um'], a['vessel'], a['shadow'], a['automatic_measurement_loss'], a['low_signal'], a['enface'], user_excluded=self.user_excluded)
        directory = HERE/'background_review'/self.scan.currentText()
        save_npz(directory/'selection.npz', excluded=self.user_excluded, source_sha256=np.array(sha(HERE/'scans'/self.scan.currentText()/'maps.npz')))
        save_npz(directory/'maps.npz', **maps)
        write(directory/'provenance.json', dict(kind='GUI background exclusion; assisted estimate, not tissue labels', diagnostics=diag))
        self.user_maps = maps; self.draw()

    def reset_background(self):
        self.user_excluded[:] = False
        self.recompute()

    def edit_proposals(self):
        subprocess.Popen([sys.executable, str(HERE/'review_proposals.py'), '--scan', self.scan.currentText()], cwd=HERE,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def export(self):
        self.figure.savefig(destination(HERE/'screenshots'/(self.scan.currentText()+'_display.png')), dpi=150)
        self.notice.setText('Displayed image saved in the screenshots folder.')

    def open_report(self):
        if os.name == 'nt': os.startfile(HERE/'START_HERE.md')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--scan'); parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    app = QtWidgets.QApplication([]); configure_app(app)
    window = Window(args.scan); window.show()
    if args.capture:
        def capture():
            window.grab().save(str(destination(HERE/'verification/viewer.png')))
            app.quit()
        QtCore.QTimer.singleShot(1500, capture)
    return app.exec()

if __name__ == '__main__':
    raise SystemExit(main())
