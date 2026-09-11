"""Render the real queue in an offscreen GUI, save preview, never write labels."""
import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
import json
import sys
from pathlib import Path
from cnv_review_v1.gui import MainWindow,QtWidgets,QtCore,configure_app
from .common import *

def run():
    config=json.loads((OUT/"launch_config.json").read_text())
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv);configure_app(app)
    paths=sorted(Path(config["segmentations"]).glob("*.npz"))
    index=next(i for i,p in enumerate(paths) if p.stem==config["initial_scan"])
    win=MainWindow(config,paths,index)
    completed=[]
    before={str(p):fingerprint(p)["sha256"] for p in (OUT/"reviewer").rglob("*.npz")} if (OUT/"reviewer").exists() else {}
    def capture():
        if win.scan.scan_id!=config["initial_scan"]:return
        if completed:return
        def save():
            example=json.loads((OUT/"review_packs/queue.json").read_text())["examples"][win.queue_choice.currentIndex()]
            assert win.editor._column==(example["lo"]+example["hi"])//2,"Explanation must follow queued location"
            directory(OUT/"verification");win.grab().save(str(OUT/"verification/reviewer_preview.png"))
            completed.append(True)
            write_json(OUT/"verification/gui.json",dict(native_scan=win.scan.scan_id,bscan=win.row,
                selected_queue_index=win.queue_choice.currentIndex(),offscreen_render_only=True,user_desktop_visibility_confirmed=False,
                boundary_editor=type(win.editor).__name__,read_only_original_annotations=True))
            win.close();app.quit()
        QtCore.QTimer.singleShot(500,save)
    win.ready.connect(capture);win.showMaximized()
    QtCore.QTimer.singleShot(180000,app.quit)
    app.exec()
    after={str(p):fingerprint(p)["sha256"] for p in (OUT/"reviewer").rglob("*.npz")}
    assert before==after,"Browsing created or modified a human boundary label"
    if not completed:raise RuntimeError("GUI preview did not become ready")
    progress("real-data reviewer rendered offscreen; no labels written")

if __name__=="__main__":run()
