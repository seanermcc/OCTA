"""Existing labeling GUI with full-volume selection and direct B-scan navigation."""
import argparse
import hashlib
import pickle
import sys
from pathlib import Path

from eight_surface.label_gui import MainWindow, QtWidgets, Qt, collect_packs
from eight_surface import labels as L


class FullVolumeWindow(MainWindow):
    @staticmethod
    def _edit_signature(state):
        # Viewing time alone must not rewrite an existing manual annotation.
        return hashlib.sha256(pickle.dumps((state._snapshot(), state.verdict,
            state.notes, state.n_strokes), protocol=5)).digest()

    def _prepare_browsing(self):
        if self.pack is None or getattr(self.pack, "_browsing_prepared", False):
            return
        for i, state in enumerate(self.pack.states):
            if state.verdict is not None:
                record = L.load_label(L.label_path(self.label_dir, self.pack.scan_id,
                                                  int(self.pack.bscan_index[i])))
                # Keep the original automatic baseline of a resumed annotation.
                state.auto = record["auto_surfaces"].astype(float)
            state._saved_edit_signature = self._edit_signature(state)
        self.pack._browsing_prepared = True

    def commit_current(self):
        if not self._has_current_bscan():
            return
        self._prepare_browsing()
        state = self.pack.states[self.i]
        if self._edit_signature(state) == state._saved_edit_signature:
            self._bank_time()
            return
        super().commit_current()
        state._saved_edit_signature = self._edit_signature(state)

    def _build_side_panel(self):
        super()._build_side_panel()
        dock = self.findChildren(QtWidgets.QDockWidget)[0]
        box = QtWidgets.QGroupBox("Full-volume navigation")
        layout = QtWidgets.QFormLayout(box)
        self.volume_choice = QtWidgets.QComboBox()
        for path in self.pack_paths:
            self.volume_choice.addItem(path.name.removesuffix("_pack.npz"))
        self.volume_choice.activated.connect(self.load_pack)
        layout.addRow("Volume", self.volume_choice)
        self.bscan_choice = QtWidgets.QSpinBox()
        self.bscan_choice.setKeyboardTracking(False)
        self.bscan_choice.setToolTip("Native B-scan index, starting at 0. Includes previously rejected images.")
        self.bscan_choice.valueChanged.connect(self._jump)
        layout.addRow("B-scan", self.bscan_choice)
        self.bscan_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.bscan_slider.setTracking(False)
        self.bscan_slider.valueChanged.connect(self._jump)
        layout.addRow(self.bscan_slider)
        dock.widget().layout().insertWidget(0, box)

    @staticmethod
    def _displayable_index(pack, start, direction):
        return start if 0 <= start < pack.n else None

    def _jump(self, bscan):
        if self.pack is not None:
            matches = (self.pack.bscan_index == bscan).nonzero()[0]
            if len(matches):
                self.show_bscan(int(matches[0]))

    def show_bscan(self, i, fit=False):
        self._prepare_browsing()
        super().show_bscan(i, fit=fit)
        if self.pack is None:
            return
        self.volume_choice.blockSignals(True)
        self.volume_choice.setCurrentIndex(self.pi)
        self.volume_choice.blockSignals(False)
        for widget in (self.bscan_choice, self.bscan_slider):
            widget.blockSignals(True)
            widget.setRange(int(self.pack.bscan_index.min()), int(self.pack.bscan_index.max()))
            widget.setValue(int(self.pack.bscan_index[self.i]))
            widget.blockSignals(False)

    def next_bscan(self, step):
        if self.pack is None or step not in (-1, 1):
            return
        j = self.i + step
        if 0 <= j < self.pack.n:
            self.show_bscan(j)
        else:
            self.load_pack(self.pi + step, direction=step)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--labels", type=Path, default=Path(__file__).resolve().parents[1] / "outputs/eight_surface/labels")
    args = parser.parse_args()
    packs = collect_packs(args.target)
    if not packs:
        parser.error("No full-volume packs found")
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = FullVolumeWindow(packs, args.labels)
    window.setWindowTitle("Full processed volumes - manual labeling")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
