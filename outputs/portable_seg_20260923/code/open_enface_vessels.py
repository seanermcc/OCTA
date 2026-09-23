"""Open the prepared en-face vessel queue at the first unfinished vessel review."""
import json
import sys
from pathlib import Path

from eight_surface import cnv_labels as CL
from eight_surface.cnv_gui import MainWindow, QtCore, QtWidgets, collect_segmentations
from eight_surface.vasculature_proposals import DEFAULT_PROPOSALS

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs/vasculature_baseline/20260909_queue32"


def main():
    paths = collect_segmentations(ROOT / "outputs/eight_surface/segmented")
    labels = ROOT / "outputs/cnv_labels"
    start = 0
    for i, path in enumerate(paths):
        saved = CL.label_path(labels, path.stem)
        if not saved.exists() or not CL.load_label(saved)["reviewed_targets"][1]:
            start = i
            break
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow(paths, labels, ROOT / "outputs/eight_surface/labels",
                        ROOT / "outputs/eight_surface/enface_line_review",
                        DEFAULT_PROPOSALS, start)
    if window.scan is None:
        raise RuntimeError("The first review scan could not be loaded")
    window.showMaximized()
    def ready():
        RUN.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(RUN / "gui_ready.png"))
        (RUN / "gui_ready.json").write_text(json.dumps(dict(
            scan_id=window.scan.scan_id, queue_length=len(paths),
            vessel_proposal_loaded=bool(window.vasculature_proposal_path),
            vessel_reviewed=bool(window.reviewed_targets[1]),
            vessel_pixels=int(window.vasculature_mask.sum()),
            visible=window.isVisible()), indent=2))
    QtCore.QTimer.singleShot(750, ready)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
