"""Open the original paired OCT/OCTA GUI using the external image dataset."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path('G:/OCT_TreeShrew/octa')
sys.path.insert(0, str(HERE.parents[1] / 'code'))
from eight_surface.cnv_gui import MainWindow, QtWidgets, QtCore, collect_segmentations

app = QtWidgets.QApplication(sys.argv)
app.setStyle('Fusion')
paths = collect_segmentations(ROOT / 'outputs/eight_surface/segmented')
if not paths:
    raise FileNotFoundError('The external drive has no original segmentation inputs.')
window = MainWindow(paths, ROOT / 'outputs/cnv_labels',
                    ROOT / 'outputs/eight_surface/labels',
                    ROOT / 'outputs/eight_surface/enface_line_review', None, 0)
window.showMaximized()

def report_startup():
    if window.scan is not None:
        window.grab().save(str(HERE / 'original_oct_octa.png'))
        (HERE / 'original_oct_octa_status.json').write_text(json.dumps({
            'scan': window.scan.scan_id, 'visible': window.isVisible(),
            'oct_shape': list(window.scan.structural_enface.shape),
            'octa_shape': list(window.scan.octa_enface.shape),
        }), encoding='utf-8')

QtCore.QTimer.singleShot(1500, report_startup)
sys.exit(app.exec())
