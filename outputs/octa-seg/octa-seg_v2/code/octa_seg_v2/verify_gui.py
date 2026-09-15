"""Real Qt events on a synthetic fixture; read-only real-volume rendering."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from types import SimpleNamespace
from .common import *
from .label_gui import V2Editor,FeedbackJournal,Qt,QtCore,QtWidgets
from .test_contract import CAL
from cnv_review_v1.gui import configure_app
from PySide6.QtTest import QTest
from eight_surface.config import SURFACE_NAMES

def run():
    import faulthandler
    faulthandler.dump_traceback_later(30)
    app=QtWidgets.QApplication([]);configure_app(app)
    def fail(*args):raise RuntimeError(str(args[1:]))
    QtWidgets.QMessageBox.critical=fail
    import uuid
    folder=OUT/'tests/gui_runs'/uuid.uuid4().hex
    write(folder/'SYNTHETIC_FIXTURE.json',dict(training_eligible=False,purpose='automated Qt interaction checks'))
    print('Constructing synthetic editor',flush=True)
    editor=V2Editor(folder);editor.resize(1500,950);editor.show()
    rows=np.broadcast_to((np.arange(8)*25+10)[None,:,None],(1,8,512)).astype(np.float32).copy()
    from .policy import apply
    probabilities=np.full((1,8,2,512),.9);d=apply(rows[0],probabilities[0],CAL,np.zeros(512,bool),0,256)
    bundle={k:v[None] for k,v in d.items()};bundle.update(raw_position_branch=rows,probabilities=probabilities,entropy=np.zeros((1,8,512)),vessel=np.zeros((1,512),bool),label_offset=np.array(0))
    guards=dict(trace=np.full((1,8,512),-1),reliability=np.full((1,8,512),-1),excluded=np.zeros((1,8,512),bool),rejected=np.array([False]))
    image=np.broadcast_to(np.linspace(0,30,256)[:,None],(256,512)).copy()
    scan=SimpleNamespace(scan_id='SYNTHETIC_GUI_FIXTURE',surface_names=tuple(SURFACE_NAMES),source_volume=folder/'synthetic',retina_band=(0,256),shadow=np.zeros((1,512),bool),px_um=1.12,structural_bscan=lambda b:image)
    editor.set_bundle(bundle,guards,CAL,'round_000');source=dict(path=str(folder/'synthetic_provider.npz'))
    def reopen():editor.set_line(scan,0,rows,np.full_like(rows,np.nan),None,source,np.zeros(512,bool),np.zeros(512,bool));editor.fit_image();app.processEvents()
    reopen();print('Synthetic editor loaded',flush=True)
    # Affirmation records only finite visible solid segments, never a hidden boundary.
    editor.surface_list.item(7).setCheckState(Qt.CheckState.Unchecked)
    editor.action('approve_shown');assert (editor.resolved['reliability'][7]==-1).all()
    editor.undo_redo(-1);editor.surface_list.item(7).setCheckState(Qt.CheckState.Checked)
    a=editor.canvas.mapFromScene(QtCore.QPointF(50,80));b=editor.canvas.mapFromScene(QtCore.QPointF(100,180))
    # Derive expected native endpoints from the actual viewport event coordinates.
    lo,hi=sorted([round(editor.canvas.mapToScene(p).x()) for p in (a,b)])
    QTest.mousePress(editor.canvas.viewport(),Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(editor.canvas.viewport(),b);QTest.mouseRelease(editor.canvas.viewport(),Qt.MouseButton.LeftButton,pos=b);app.processEvents()
    assert np.all(editor.resolved['reliability'][:,lo:hi+1]==0)
    assert np.all(editor.resolved['trace']==-1)
    assert np.all(np.isfinite(editor.rendered['uncertain_estimates'][:,lo:hi+1]))
    assert not np.any(editor.pack.states[0].local['local_drawn'])
    cursor=editor.journal.data['cursor'];editor.surface_list.setCurrentRow(7);editor.surface_list.item(7).setCheckState(Qt.CheckState.Unchecked)
    editor.action('approve_position');assert editor.journal.data['cursor']==cursor
    editor.surface_list.item(7).setCheckState(Qt.CheckState.Checked);editor.surface_list.setCurrentRow(0)
    editor.undo_redo(-1);assert np.all(editor.resolved['reliability']==-1)
    editor.undo_redo(1);assert np.all(editor.resolved['reliability'][:,lo:hi+1]==0)
    reopen();assert np.all(editor.resolved['reliability'][:,lo:hi+1]==0)
    editor.span_lo.setValue(lo);editor.span_hi.setValue(hi+1);editor.surface_list.setCurrentRow(0)
    editor.action('affirm_measurable');assert np.all(np.isfinite(editor.rendered['reported_positions'][0,lo:hi+1]))
    assert not np.isfinite(editor.rendered['reported_positions'][1:,lo:hi+1]).any()
    editor.surface_list.setCurrentRow(1);editor.action('approve_position');assert editor.resolved['approved'][1,lo:hi+1].all()
    assert not np.isfinite(editor.rendered['reported_positions'][1,lo:hi+1]).any()
    editor.on_stroke(np.array([lo,hi]),np.array([36.,36.]));assert not editor.resolved['approved'][1,lo:hi+1].any()
    editor.action('not_traceable');assert not np.isfinite(editor.rendered['uncertain_estimates'][1,lo:hi+1]).any()
    # Conflict detection must preserve the unsaved older editor rather than overwrite.
    stale=FeedbackJournal(editor.journal.path,scan.scan_id,0,'round_000','training')
    editor.action('exclude_image')
    try:stale.change(direction=-1);raise AssertionError('Conflict accepted')
    except RuntimeError:pass
    editor.close()
    from .gui import Window
    window=Window(feedback_dir=OUT/'tests/read_only_real');window.show();app.processEvents();window.fit();app.processEvents()
    folder=OUT/'tests/screenshots';folder.mkdir(parents=True,exist_ok=True)
    window.grab().save(str(folder/'focused_reviewer.png'));window.close();app.processEvents()
    assert not list((OUT/'tests/read_only_real/surface_labels').glob('*.npz'))
    write(OUT/'tests/gui_verification.json',dict(real_qt_events=True,synthetic_only_mutations=True,regional_native_interval=[lo,hi+1],
       undo_redo=True,reopen=True,exception=True,candidate_approval_separate=True,changed_position_revokes_approval=True,conflict_protection=True,real_volume_read_only=True))
    print('Qt interaction and real-volume rendering checks passed',flush=True)

if __name__=='__main__':run()
