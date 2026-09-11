"""Launch the separate CNV classification and linked boundary editor."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cnv_review_v1.data import default_config, OUT, atomic_json
from cnv_review_v1.gui import MainWindow, QtWidgets, configure_app
from PySide6 import QtCore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=OUT / "settings.json")
    parser.add_argument("--scan", help="Scan ID (defaults to the recent TS247 manual review)")
    parser.add_argument("--capture-startup", action="store_true", help="Save one startup preview and status without editing labels")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config.exists() else default_config()
    app = QtWidgets.QApplication(sys.argv)
    configure_app(app)
    # Lock only this isolated output directory; leave older GUIs running.
    output = Path(config["output"])
    output.mkdir(parents=True, exist_ok=True)
    lock = QtCore.QLockFile(str(output / "review.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QtWidgets.QMessageBox.information(None, "CNV review is already open", "The separate CNV reviewer is already using this output folder. Switch to its window to continue.")
        return 0
    paths = sorted(Path(config["segmentations"]).glob("*.npz"))
    start = next((i for i, p in enumerate(paths) if p.stem == (args.scan or config.get("initial_scan", "TS247_OD_2024-11-06_D21_s03_104157"))), 0)
    if args.scan and all(p.stem != args.scan for p in paths):
        parser.error("Requested scan is not in the configured scan queue")
    window = MainWindow(config, paths, start)
    if args.capture_startup:
        def capture():
            window.grab().save(str(output / "startup.png"))
            atomic_json(output / "startup.json", dict(scan_id=window.scan.scan_id,
                        bscan=window.row, visible=window.isVisible(),
                        saved_bscan_reviews=len(window.index.records),
                        regions=len(window.store.regions), auto_source=window.auto_meta,
                        vessel_source=window.vessel_meta, font=app.font().family()))
            window.ready.disconnect(capture)
        window.ready.connect(capture)
    window.showMaximized()
    result = app.exec()
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
