"""Verify the UI extension without altering the completed scientific release."""
import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
import json
from pathlib import Path
import sys
import tempfile
import numpy as np
from cnv_review_v1.gui import MainWindow,QtWidgets,QtCore,configure_app
from .common import OUT,directory,write_json
from .ilm_preview import load_ilm_preview


def run():
    dest=directory(OUT/"reviewer/diagnostics/ilm_preview")
    config=json.loads((OUT/"launch_config.json").read_text())
    volumes=[]
    for provider in sorted((OUT/"review_packs/automatic").glob("*.npz")):
        with np.load(provider,allow_pickle=False) as data:
            shape=data["state"].shape;names=list(data["surface_names"])
            reported=data["surfaces"][:,names.index("ILM")]
        raw,path=load_ilm_preview(provider,provider.stem,names,shape)
        assert raw is not None and np.isfinite(raw).all()
        assert not np.isfinite(reported).any()
        volumes.append(dict(scan_id=provider.stem,bscans=len(raw),raw_positions=int(raw.size),
            reported_positions=int(np.isfinite(reported).sum()),source=str(path)))
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv);configure_app(app)
    completed=[];errors=[]
    with tempfile.TemporaryDirectory() as temp:
        # Read current user feedback but isolate this offscreen window's writer.
        config["manual_sources"].insert(0,str(Path(config["output"])/"surface_labels"))
        config["region_sources"].insert(0,str(Path(config["output"])/"regions"))
        config["output"]=temp
        paths=sorted(Path(config["segmentations"]).glob("*.npz"))
        index=next(i for i,p in enumerate(paths) if p.stem==config["initial_scan"])
        win=MainWindow(config,paths,index)
        def capture():
            if completed or errors:return
            def save():
                try:
                    editor=win.editor;before=editor.signature()
                    editor.surface_list.setCurrentRow(editor.pack.names.index("ILM"))
                    editor.show_ilm.setChecked(False);editor.show_ilm.setChecked(True)
                    assert editor._ilm_preview_item is not None
                    assert editor._ilm_preview_item.path().elementCount()>0
                    assert before==editor.signature(),"Overlay changed annotation state"
                    assert "excluded from measurements" in editor.state_text.text()
                    app.processEvents()  # Settle the longer ILM explanation before capture.
                    assert win.grab().save(str(dest/"reviewer_preview.png"))
                    completed.append(True)
                except Exception as exc:errors.append(str(exc))
                finally:win.close();app.quit()
            QtCore.QTimer.singleShot(500,save)
        win.ready.connect(capture);win.showMaximized()
        QtCore.QTimer.singleShot(180000,app.quit);app.exec()
        assert not list(Path(temp).rglob("*.npz")),"Browsing wrote labels"
        assert completed and not errors,errors or "GUI did not become ready"
    write_json(dest/"verification.json",dict(volumes=volumes,offscreen_only=True,
        user_desktop_visibility_confirmed=False,no_labels_written=True,
        overlay="white dots; read-only ILM position branch; omitted from measurements and approval targets"))
    print("ILM overlay verified in four volume sources; real-data GUI rendered without label writes.",flush=True)


if __name__=="__main__":run()
