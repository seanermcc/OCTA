"""octa-thick_v1: separate read-only pilot viewer."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import traceback
from engine import HERE, ROOT, Volume, LAYERS, SURFACE_NAMES, pixel
import numpy as np
from PySide6 import QtCore, QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from cnv_review_v1.gui import configure_app

class Window(QtWidgets.QMainWindow):
    def __init__(self, paths, config, capture=False):
        configure_app(QtWidgets.QApplication.instance())
        super().__init__(); self.setWindowTitle('octa-thick_v1 · Thickness pilot · Read only')
        self.resize(1480, 980); self.paths = paths; self.config = config; self.capture = capture
        self.pool = ThreadPoolExecutor(max_workers=1); self.cache = {}; self.volume = None
        self.row = 0; self.col = 0; self.mode = 0; self.layer = 0; self.future = None
        self.out = HERE/'exports'; self.out.mkdir(exist_ok=True)
        central = QtWidgets.QWidget(); self.setCentralWidget(central); layout = QtWidgets.QVBoxLayout(central)
        self.controls = QtWidgets.QWidget(); bar = QtWidgets.QHBoxLayout(self.controls); bar.setContentsMargins(0,0,0,0)
        self.scan_choice = QtWidgets.QComboBox()
        for p in paths: self.scan_choice.addItem(p.name)
        bar.addWidget(self.scan_choice, 2)
        self.layer_choice = QtWidgets.QComboBox(); self.layer_choice.addItems([x[0] for x in LAYERS]); bar.addWidget(self.layer_choice)
        self.preview = QtWidgets.QCheckBox('Include unreliable measurements'); bar.addWidget(self.preview)
        layout.addWidget(self.controls)
        self.options = QtWidgets.QWidget(); opts = QtWidgets.QHBoxLayout(self.options); opts.setContentsMargins(0,0,0,0)
        self.overlay = QtWidgets.QCheckBox('Structural background'); self.overlay.setChecked(True); opts.addWidget(self.overlay)
        self.opacity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal); self.opacity.setRange(10,100); self.opacity.setValue(80); self.opacity.setMaximumWidth(100)
        opts.addWidget(QtWidgets.QLabel('Opacity')); opts.addWidget(self.opacity)
        self.low = QtWidgets.QDoubleSpinBox(); self.high = QtWidgets.QDoubleSpinBox()
        for spin in (self.low, self.high): spin.setRange(-10000,10000); spin.setDecimals(1); spin.setSuffix(' µm')
        opts.addWidget(QtWidgets.QLabel('Color limits')); opts.addWidget(self.low); opts.addWidget(self.high)
        self.row_spin = QtWidgets.QSpinBox(); self.col_spin = QtWidgets.QSpinBox()
        opts.addWidget(QtWidgets.QLabel('B-scan (0-based)')); opts.addWidget(self.row_spin)
        opts.addWidget(QtWidgets.QLabel('A-line')); opts.addWidget(self.col_spin)
        layout.addWidget(self.options)
        self.notice = QtWidgets.QLabel('Loading completed volume…'); self.notice.setWordWrap(True); layout.addWidget(self.notice)
        split = QtWidgets.QSplitter(); layout.addWidget(split, 1)
        self.figure = Figure(figsize=(11,8), layout='constrained'); self.canvas = FigureCanvasQTAgg(self.figure); split.addWidget(self.canvas)
        self.details = QtWidgets.QTextBrowser(); self.details.setMinimumWidth(300); split.addWidget(self.details); split.setSizes([1100,340])
        self.actions = QtWidgets.QWidget(); buttons = QtWidgets.QHBoxLayout(self.actions)
        for title, action in [('Open correction GUI', self.correction), ('Reload corrections', self.reload),
                              ('Export maps + displayed PNG', self.export), ('Save this point to CSV', self.save_point)]:
            button = QtWidgets.QPushButton(title); button.clicked.connect(action); buttons.addWidget(button)
        layout.addWidget(self.actions)
        self.scan_choice.currentIndexChanged.connect(self.load)
        self.layer_choice.currentIndexChanged.connect(self.change_layer)
        self.preview.toggled.connect(self.change_mode)
        self.overlay.toggled.connect(self.draw); self.opacity.valueChanged.connect(self.draw)
        self.low.editingFinished.connect(self.limits); self.high.editingFinished.connect(self.limits)
        self.row_spin.valueChanged.connect(self.navigate); self.col_spin.valueChanged.connect(self.navigate)
        self.canvas.mpl_connect('button_press_event', self.click)
        self.timer = QtCore.QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(100)
        self.load(0)

    def busy(self, text):
        self.notice.setText(text)
        for w in (self.controls, self.options, self.actions): w.setEnabled(False)

    def load(self, index):
        self.busy('Loading cached structural images and measurements…')
        path = self.paths[index]
        self.future = self.pool.submit(lambda: self.cache.get(path) or Volume(path, self.config))

    def reload(self):
        if self.volume is None: return
        self.busy('Reloading saved geometry and judgments together…')
        def work():
            self.volume.reload(); return self.volume
        self.future = self.pool.submit(work)

    def poll(self):
        if self.future is None or not self.future.done(): return
        future = self.future; self.future = None
        try:
            self.volume = future.result(); self.cache[self.volume.path] = self.volume
            for spin, maximum, value in ((self.row_spin,self.volume.shape[0]-1,self.row), (self.col_spin,self.volume.shape[1]-1,self.col)):
                spin.blockSignals(True); spin.setMaximum(maximum); spin.setValue(min(value,maximum)); spin.blockSignals(False)
            self.row = self.row_spin.value(); self.col = self.col_spin.value()
            self.change_layer(self.layer)
            if self.capture:
                self.capture = False
                QtCore.QTimer.singleShot(500, lambda: self.grab().save(str(HERE/'startup.png')))
        except Exception as exc:
            self.volume = None; self.notice.setText(f'Cannot display this volume: {exc}')
            self.details.setPlainText(traceback.format_exc())
        finally:
            for w in (self.controls,self.options,self.actions): w.setEnabled(True)

    def change_layer(self, layer):
        self.layer = layer
        if not self.volume: return
        lo, hi = self.volume.limits[layer]; self.low.setValue(lo); self.high.setValue(hi); self.draw()

    def change_mode(self, checked):
        self.mode = int(checked); self.draw()

    def limits(self):
        if not self.volume: return
        if self.high.value() <= self.low.value():
            self.notice.setText('Upper color limit must exceed lower limit.'); return
        self.volume.limits[self.layer] = [self.low.value(), self.high.value()]; self.draw()

    def navigate(self):
        self.row = self.row_spin.value(); self.col = self.col_spin.value(); self.draw()

    def click(self, event):
        if not self.volume or self.future or event.xdata is None or event.ydata is None: return
        if event.inaxes in (self.en_ax, self.map_ax):
            self.row, self.col = pixel(event.xdata, event.ydata, self.volume.shape)
        elif event.inaxes == self.b_ax:
            _, self.col = pixel(event.xdata, 0, self.volume.shape)
        else: return
        for spin, value in ((self.row_spin,self.row),(self.col_spin,self.col)):
            spin.blockSignals(True); spin.setValue(value); spin.blockSignals(False)
        self.draw()

    def draw(self, *_):
        v = self.volume
        if v is None: return
        self.figure.clear(); grid = self.figure.add_gridspec(2,2, height_ratios=[1,1.05])
        self.en_ax = self.figure.add_subplot(grid[0,0]); self.map_ax = self.figure.add_subplot(grid[0,1]); self.b_ax = self.figure.add_subplot(grid[1,:])
        data = v.maps[self.mode][0][self.layer]; estimated = v.maps[self.mode][1][self.layer]
        kwargs = dict(origin='upper', interpolation='nearest')
        enlo, enhi = np.percentile(v.enface,[2,98])
        self.en_ax.imshow(v.enface,cmap='gray',vmin=enlo,vmax=enhi,**kwargs); self.en_ax.set_title('Structural OCT en face')
        if self.overlay.isChecked(): self.map_ax.imshow(v.enface,cmap='gray',vmin=enlo,vmax=enhi,**kwargs)
        lo, hi = v.limits[self.layer]
        heat = self.map_ax.imshow(data,cmap='viridis',vmin=lo,vmax=hi,alpha=self.opacity.value()/100 if self.overlay.isChecked() else 1,**kwargs)
        self.figure.colorbar(heat,ax=self.map_ax,label='Thickness (µm)',fraction=.045)
        # Stipple is a separate, unsmoothed native-pixel mask; measurements are unchanged.
        yy, xx = np.indices(v.shape); dots = estimated & (yy%5 == 0) & (xx%5 == 0)
        self.map_ax.scatter(xx[dots],yy[dots],s=1,c='white',alpha=.85,linewidths=0)
        self.map_ax.set_title(f'{LAYERS[self.layer][0]} · '+('Including unreliable · white stipple' if self.mode else 'Unreliable excluded'))
        for ax in (self.en_ax,self.map_ax):
            ax.axhline(self.row,color='#ff725e',lw=.8); ax.axvline(self.col,color='#ff725e',lw=.8)
            ax.set_xlabel('Native A-line'); ax.set_ylabel('Native B-scan')
        image = v.images[self.row]; blo,bhi = np.percentile(image,[2,99])
        self.b_ax.imshow(image,cmap='gray',vmin=blo,vmax=bhi,aspect='auto',**kwargs)
        _, a, b = LAYERS[self.layer]
        for k in range(8):
            curve = v.endpoints[self.mode][self.row,k]; codes = v.sources[self.mode][self.row,k]
            color = '#66deff' if k == a else '#ffb65a' if k == b else '#b4c5cc'
            lw = 1.8 if k in (a,b) else .65
            self.b_ax.plot(np.where(~v.unreliable[self.row,k],curve,np.nan),color=color,lw=lw)
            self.b_ax.plot(np.where(v.unreliable[self.row,k],curve,np.nan),color=color,lw=lw,ls=':')
        self.b_ax.axvline(self.col,color='#ff725e',lw=.7)
        ends = v.endpoints[self.mode][self.row,[a,b],self.col]
        if np.isfinite(data[self.row,self.col]):
            self.b_ax.plot([self.col,self.col],ends,color='#ffec67',lw=2)
            for z in ends: self.b_ax.plot([self.col-4,self.col+4],[z,z],color='#ffec67',lw=2)
        self.b_ax.set(xlabel='Native A-line',ylabel='Canonical crop depth (px; vitreous above)',
            title=f'B-scan {self.row} · A-line {self.col} · {SURFACE_NAMES[a]} → {SURFACE_NAMES[b]}')
        finite = np.isfinite(data).mean()*100; est = estimated.mean()*100
        reported = np.isfinite(v.maps[0][0][self.layer]).mean()*100
        text = f'Coverage {finite:.1f}% · excluding unreliable {reported:.1f}% · unreliable included {est:.1f}% of native grid. '
        if not np.isfinite(data).any(): text += 'No eligible measurements here. Try including unreliable measurements; shadows, exclusions and invalid positions remain blank. '
        if any(revision != v.revision for _,revision in v.exported): text += 'PREVIOUS EXPORTS ARE STALE — export again. '
        self.notice.setText(text)
        records = v.point(self.row,self.col,self.mode)
        lines = [v.scan_id, f'B-scan {self.row} / A-line {self.col} (0-based)', 'Available segmentation treated as usable for this pilot.', '']
        for record in records:
            value = 'blank' if record['thickness_um'] is None else f"{record['thickness_um']:.2f} µm" + (' · unreliable' if record['estimated'] else '')
            top = 'missing' if record['top_crop_px'] is None else f"{record['top_crop_px']:.2f}"
            bottom = 'missing' if record['bottom_crop_px'] is None else f"{record['bottom_crop_px']:.2f}"
            lines += [f"{record['layer']}: {value}",
                f"{record['top_boundary']}: {top} px · {record['top_source']}",
                f"{record['bottom_boundary']}: {bottom} px · {record['bottom_source']}"]
            if record['missing_reason']: lines.append(record['missing_reason'])
            lines.append('')
        lines += [f'Full canonical depth = crop depth + {v.offset} px.', 'Photoreceptor composite includes ONL; isolated ONL unavailable.',
                  'Dotted boundaries and white map stipple indicate explicitly unreliable measurements. No smoothing or missing-value filling.']
        self.details.setPlainText('\n'.join(lines)); self.canvas.draw_idle()

    def correction(self):
        if self.volume is None: return
        subprocess.Popen([sys.executable,str(ROOT/'code/cnv_review_v1/main.py'),'--config',self.config['_path'],'--scan',self.volume.scan_id],cwd=ROOT)
        self.notice.setText(f'Correction GUI opened for {self.volume.scan_id}. Use its navigation controls for B-scan {self.row}, A-line {self.col}; save there, then Reload corrections here.')

    def export(self):
        if self.volume is None: return
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f'); stem = self.out/f'{self.volume.scan_id}_{stamp}'
        try:
            self.volume.export(stem.with_suffix('.npz'))
            # Export only the displayed map, including its color bar and exact display settings.
            fig = Figure(figsize=(7,6),layout='constrained'); ax = fig.subplots()
            v=self.volume; data=v.maps[self.mode][0][self.layer]
            if self.overlay.isChecked():
                lo,hi=np.percentile(v.enface,[2,98]); ax.imshow(v.enface,cmap='gray',vmin=lo,vmax=hi,interpolation='nearest')
            lo,hi=v.limits[self.layer]
            im=ax.imshow(data,cmap='viridis',vmin=lo,vmax=hi,interpolation='nearest',alpha=self.opacity.value()/100 if self.overlay.isChecked() else 1)
            yy,xx=np.indices(v.shape); mask=v.maps[self.mode][1][self.layer] & (yy%5==0) & (xx%5==0)
            ax.scatter(xx[mask],yy[mask],s=1,c='white',linewidths=0)
            ax.axhline(self.row,color='#ff725e',lw=.8); ax.axvline(self.col,color='#ff725e',lw=.8)
            ax.set(title=f"{v.scan_id}\n{LAYERS[self.layer][0]} · {'Including unreliable (stipple)' if self.mode else 'Unreliable excluded'} · Pilot",xlabel='Native A-line',ylabel='Native B-scan')
            fig.colorbar(im,ax=ax,label='Thickness (µm)'); fig.savefig(stem.with_suffix('.png'),dpi=150)
            metadata=v.metadata(); metadata['display']=dict(layer=self.layer,mode=self.mode,opacity=self.opacity.value()/100,overlay=self.overlay.isChecked(),bscan=self.row,aline=self.col)
            stem.with_suffix('.json').write_text(json.dumps(metadata,indent=2))
            v.exported.extend([(stem.with_suffix('.png'),v.revision),(stem.with_suffix('.json'),v.revision)])
            self.notice.setText(f'Exported maps, provenance, and displayed PNG to {stem}')
        except Exception as exc: self.notice.setText(f'Export failed: {exc}')

    def save_point(self):
        if self.volume:
            path=self.out/f'{self.volume.scan_id}_pilot_v2_points.csv'; self.volume.save_point(path,self.row,self.col,self.mode)
            self.notice.setText(f'Saved all eight measurements at B{self.row} / A{self.col} to {path}')

    def closeEvent(self,event):
        settings=dict(volumes=[str(p) for p in self.paths],last_scan=self.scan_choice.currentIndex())
        (HERE/'settings.json').write_text(json.dumps(settings,indent=2))
        self.pool.shutdown(wait=False); event.accept()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('volumes',nargs='*',type=Path,help='Explicit completed volume directories')
    p.add_argument('--list',type=Path,help='JSON list of completed volume directories')
    p.add_argument('--correction-config',type=Path,default=ROOT/'outputs/octa-seg/octa-seg_v1/launch_config.json')
    p.add_argument('--capture-startup',action='store_true')
    args=p.parse_args()
    paths=args.volumes or [Path(x) for x in json.loads((args.list or HERE/'volumes.json').read_text())]
    if not paths: p.error('Select at least one completed volume')
    config=json.loads(args.correction_config.read_text()); config['_path']=str(args.correction_config.resolve())
    app=QtWidgets.QApplication(sys.argv); app.setStyle('Fusion')
    window=Window([x.resolve() for x in paths],config,args.capture_startup); window.show()
    return app.exec()

if __name__ == '__main__': raise SystemExit(main())
