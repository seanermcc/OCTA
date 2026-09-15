"""One-time mechanical migration edits, preserved for implementation provenance."""
from pathlib import Path
p = Path(__file__).parent / 'code/octa_seg_v3'
f = p / 'label_gui.py'
s = f.read_text(encoding='utf8')
start = s.index('    def _build_actions(self):')
end = s.index('    def update_drawing_mode', start)
s = s[:start] + s[end:]
s = s.replace('np.clip(xs, 0, 511)', 'np.clip(xs, 0, self.width - 1)')
s = s.replace('np.clip(round(x0), 0, 511)', 'np.clip(round(x0), 0, self.width - 1)').replace('np.clip(round(x1), 0, 511)', 'np.clip(round(x1), 0, self.width - 1)')
s = s.replace('np.clip(round(point.x()), 0, 511)', 'np.clip(round(point.x()), 0, self.width - 1)')
s = s.replace('range(8)', 'range(self.n_boundaries)').replace('np.arange(512)', 'np.arange(self.width)').replace('np.ones(512, bool)', 'np.ones(self.width, bool)')
s = s.replace(' % 8)', ' % self.n_boundaries)').replace("'clear_marks', 0, 512", "'clear_marks', 0, self.width").replace("'clear_exclusion', 0, 512", "'clear_exclusion', 0, self.width")
f.write_text(s, encoding='utf8')
