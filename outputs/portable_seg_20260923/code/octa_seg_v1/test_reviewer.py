"""GUI tests use synthetic study identities in temporary storage only."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from cnv_review_v1.test_review import fake_scan
from cnv_review_v1.label_gui import QtWidgets,QtCore,curve_path
from eight_surface import labels as L,provenance as P
from .reviewer import SegBoundaryEditor,display_masks,approved_position_mask,install_queue

class Reviewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.scan=fake_scan(self.root)
        self.path=self.root/"automatic.npz";shape=self.scan.surfaces.shape
        state=np.ones(shape,np.uint8);state[:,2,10:20]=3;state[:,3,10:20]=2
        estimates=np.full(shape,np.nan,np.float32);estimates[:,2,10:20]=self.scan.surfaces[:,2,10:20]
        np.savez(self.path,state=state,reason=np.ones(shape,np.uint8),probabilities=np.ones((12,8,2,40))*.8,
            uncertain_estimates=estimates,context_reason=np.zeros(shape,np.uint8))
        self.surfaces=self.scan.surfaces.copy();self.surfaces[state!=1]=np.nan
        self.editor=SegBoundaryEditor(self.root/"feedback")
        self.meta=dict(name="test octa-seg",path=str(self.path))
        self.open()
    def open(self,record=None):
        self.editor.set_line(self.scan,3,self.surfaces,self.scan.confidence,record,self.meta,np.zeros(40,bool),np.zeros(40,bool))
    def tearDown(self):
        self.editor.close();self.editor.deleteLater();self.app.processEvents();self.tmp.cleanup()
    def select(self):
        self.editor.surface_list.setCurrentRow(2);self.editor.s=2
        self.editor.span_lo.setValue(10);self.editor.span_hi.setValue(20)
    def test_browse_writes_no_labels(self):
        self.editor.commit_current()
        self.assertFalse(list((self.root/"feedback").rglob("*.npz")))
    def test_queue_navigation_does_not_capture_manual_volume_browsing(self):
        from types import SimpleNamespace
        class Window(QtWidgets.QMainWindow):
            ready=QtCore.Signal()
            def load_scan(self,index):
                self.loads.append(index)
                self.scan=SimpleNamespace(scan_id=self.paths[index].stem,surface_names=["ILM"])
                self.ready.emit()
            def navigate(self,row,col):self.locations.append((self.scan.scan_id,row,col))
        queue=self.root/"queue.json"
        queue.write_text(json.dumps({"examples":[dict(animal="TS999",scan_id=s,bscan=b,
            boundary="ILM",lo=10,hi=20,role="control") for s,b in (("A",3),("B",7))]}))
        win=Window();win.config={"review_queue":str(queue)};win.paths=[Path("A.npz"),Path("B.npz")]
        win.scan=None;win.loads=[];win.locations=[]
        surfaces=QtWidgets.QListWidget();surfaces.addItem("ILM")
        win.editor=SimpleNamespace(surface_list=surfaces,span_lo=QtWidgets.QSpinBox(),
            span_hi=QtWidgets.QSpinBox(),explain=lambda col:None)
        install_queue(win)
        win.load_scan(0)
        self.assertEqual(win.locations,[("A",3,15)])
        win.load_scan(1)  # Next scan must stay on B without following queue item A.
        self.assertEqual(win.scan.scan_id,"B");self.assertEqual(win.loads,[0,1])
        self.assertEqual(len(win.locations),1)
        win.queue_choice.setCurrentIndex(1)
        self.assertEqual(win.locations[-1],("B",7,15))
        win.queue_choice.setCurrentIndex(0)
        self.assertEqual(win.loads,[0,1,0]);self.assertEqual(win.locations[-1],("A",3,15))
        win.close();win.deleteLater()
    def test_nan_paths_move_after_gap(self):
        path=curve_path(np.array([1,2,np.nan,4,5]))
        self.assertTrue(path.elementAt(2).isMoveTo())
        st=self.editor.pack.states[0]
        measured,uncertain=display_masks(st,self.editor.seg_data["state"][3],self.editor.candidate_rows())
        self.assertFalse(measured[3,10:20].any());self.assertFalse(uncertain[3,10:20].any())
    def test_generic_accept_does_not_promote(self):
        self.select();self.editor.set_verdict("accepted");self.editor.commit_current()
        label=L.load_label(self.root/"feedback/surface_labels/TS999_TEST_b0003.npz")
        self.assertFalse(P.local_position_valid(label,"strict").any())
        self.assertFalse(list((self.root/"feedback/estimate_feedback").glob("*.json")))
    def test_estimate_approval_separate_from_drawing(self):
        self.select();self.editor.feedback_action("approved_for_future_positions")
        label=L.load_label(self.root/"feedback/surface_labels/TS999_TEST_b0003.npz")
        self.assertFalse(label["local_drawn"][2,10:20].any())
        self.assertFalse(P.local_position_valid(label,"strict").any())
        f=json.loads(next((self.root/"feedback/estimate_feedback").glob("*.json")).read_text())
        self.assertTrue(f["events"][-1]["approved_for_position_training"])
        self.assertEqual(approved_position_mask(label,f["events"]).sum(),10)
        self.editor.explain(15)
        self.assertIn("explicit human position approval",self.editor.state_text.text())
        label["local_reliability"][2,10:20]=P.MARK_NO
        self.assertFalse(approved_position_mask(label,f["events"]).any())
    def test_correction_requires_explicit_approval(self):
        self.select();self.editor.on_stroke([10,19],[33,33]);self.editor.set_verdict("accepted");self.editor.commit_current()
        path=self.root/"feedback/surface_labels/TS999_TEST_b0003.npz"
        label=L.load_label(path);self.assertFalse(P.local_position_valid(label,"strict").any())
        self.editor.feedback_action("approved_for_future_positions")
        label=L.load_label(path);self.assertEqual(P.local_position_valid(label,"strict").sum(),10)
        self.assertTrue(list((self.root/"feedback/surface_history").glob("*.npz")))
    def test_not_traceable_hides_candidate_and_preserves_original(self):
        self.select();original=self.path.read_bytes();self.editor.feedback_action("not_traceable")
        st=self.editor.pack.states[0];a,b=display_masks(st,self.editor.seg_data["state"][3],self.editor.candidate_rows())
        self.assertFalse(a[2,10:20].any());self.assertFalse(b[2,10:20].any());self.assertEqual(original,self.path.read_bytes())
    def test_explicit_states_survive_changed_auto_without_position_approval(self):
        st=self.editor.pack.states[0]
        st.local["local_reviewed"][2,5:8]=True
        st.local["local_visibility"][2,5:8]=P.MARK_YES
        st.local["local_reliability"][2,5:8]=P.MARK_YES
        st.verdict="accepted";self.editor.commit_current()
        path=self.root/"feedback/surface_labels/TS999_TEST_b0003.npz"
        rec=L.load_label(path);original=path.read_bytes()
        self.surfaces[:,2,5:8]+=3
        self.open((path,rec))
        st=self.editor.pack.states[0]
        self.assertTrue((st.local["local_reliability"][2,5:8]==P.MARK_YES).all())
        self.assertFalse(st.local["local_reviewed"][2,5:8].any())
        self.editor.commit_current();self.assertEqual(original,path.read_bytes())

if __name__=="__main__":unittest.main()
