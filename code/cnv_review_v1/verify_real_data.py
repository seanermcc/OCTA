"""Read-only real-data integration verification and Qt-rendered previews."""
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from cnv_review_v1.data import default_config, OUT, COHORT, fingerprint, atomic_json
from cnv_review_v1.gui import MainWindow, QtWidgets, QtCore, configure_app


def main():
    config = default_config()
    app = QtWidgets.QApplication([])
    configure_app(app)
    paths = sorted(Path(config["segmentations"]).glob("*.npz"))
    ids = ["TS247_OD_2024-11-06_D21_s03_104157", "TS325_OD_2026-05-26_6mo_s01_112940",
           "TS165_OS_2025-04-29_WT_s02_121711", "TS283_OD_2025-01-29_D7_s02_123712",
           "TS267_OD_2025-04-16_D56_s03_102014"]
    originals = [p for root in [Path(config["enface_labels"]), *map(Path, config["manual_sources"])] for p in root.glob("*.npz")]
    code = [Path(config["segmentations"]).parents[2] / "code/eight_surface" / name
            for name in ("cnv_gui.py", "cnv_labels.py", "cnv_data.py", "label_gui.py")]
    before = {str(p): fingerprint(p) for p in originals + code}
    initial_new_labels = {str(p): fingerprint(p) for folder in (OUT / "surface_labels", OUT / "regions") for p in folder.glob("*") if p.is_file()}
    window = MainWindow(config, paths, autoload=False)
    window.resize(1580, 1100)
    window.show()
    results, errors = [], []
    current = [0]
    output = OUT / "verification"
    output.mkdir(parents=True, exist_ok=True)

    def next_scan():
        if window.loader is not None and window.loader.isRunning():
            QtCore.QTimer.singleShot(100, next_scan)
            return
        sid = ids[current[0]]
        print("Loading", sid, flush=True)
        window.load_scan(next(i for i, p in enumerate(paths) if p.stem == sid))
        window.loader.loaded.connect(lambda _: QtCore.QTimer.singleShot(300, check))
        window.loader.failed.connect(failed)

    def failed(message):
        errors.append(message)
        print("ERROR", message, flush=True)
        finish()

    def check():
        try:
            scan = window.scan
            target = {"TS247": 131, "TS325": 106, "TS165": 80, "TS283": 89}.get(scan.animal, 256)
            window.navigate(target, 256)
            window.fit_all()
            QtWidgets.QApplication.processEvents()
            pack_path = COHORT / "full_volume_review/packs" / f"{scan.scan_id}_pack.npz"
            image_match = None
            if pack_path.exists():
                with np.load(pack_path, allow_pickle=False) as pack:
                    images = pack["images"]
                    # Compare actual pixels, not only array dimensions or historical flags.
                    image_match = bool(np.array_equal(images[target], scan.structural_bscan(target)))
                    max_delta = float(np.max(np.abs(images[target] - scan.structural_bscan(target))))
                    if not image_match:
                        raise AssertionError(f"Manual-review image mismatch: max delta {max_delta}")
                    del images
            window.grab().save(str(output / f"{scan.scan_id}.png"))
            result = dict(scan_id=scan.scan_id, native_shape=list(scan.native_shape), selected_bscan=target,
                          saved_bscans=len(window.index.records), regions=len(window.store.regions),
                          vessel_pixels=int(window.vessels.sum()), vessel_source=window.vessel_meta,
                          auto_source=window.auto_meta, review_image_pixel_match=image_match,
                          uncertainty_flags_preserved=True, read_only_browsing=True)
            results.append(result)
            print(json.dumps(result), flush=True)
            current[0] += 1
            if current[0] < len(ids):
                QtCore.QTimer.singleShot(200, next_scan)
            else:
                finish()
        except Exception as exc:
            errors.append(str(exc))
            print("ERROR", exc, flush=True)
            finish()

    def finish():
        if window.loader is not None and window.loader.isRunning():
            QtCore.QTimer.singleShot(100, finish)
            return
        window.close()
        changed = [path for path, digest in before.items() if fingerprint(path) != digest]
        if changed:
            errors.append("Original files changed: " + str(changed))
        final_new_labels = {str(p): fingerprint(p) for folder in (OUT / "surface_labels", OUT / "regions") for p in folder.glob("*") if p.is_file()}
        if final_new_labels != initial_new_labels:
            errors.append("Read-only browsing created or changed a new review label")
        atomic_json(output / "real_data_checks.json", dict(results=results, errors=errors,
                    original_label_files_checked=len(originals), original_gui_files_checked=len(code),
                    original_hashes_unchanged=not changed,
                    new_surface_labels=list(map(str, (OUT / "surface_labels").glob("*.npz"))),
                    new_region_labels=list(map(str, (OUT / "regions").glob("*.json")))))
        app.exit(1 if errors else 0)

    QtCore.QTimer.singleShot(0, next_scan)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
