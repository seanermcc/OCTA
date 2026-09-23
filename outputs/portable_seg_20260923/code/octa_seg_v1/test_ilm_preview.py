"""View-only raw ILM must never change labels, candidates or measurements."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from pathlib import Path
import numpy as np
from cnv_review_v1.test_review import fake_scan
from cnv_review_v1.label_gui import QtWidgets
from eight_surface import provenance as P, labels as L
from .reviewer import SegBoundaryEditor
from .ilm_preview import load_ilm_preview, ilm_preview_mask


class ILMPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.scan=fake_scan(self.root);shape=self.scan.surfaces.shape
        self.provider=self.root/"review_packs/automatic"/f"{self.scan.scan_id}.npz"
        self.provider.parent.mkdir(parents=True)
        self.measurements=self.root/"volumes"/self.scan.scan_id/"measurements.npz"
        self.measurements.parent.mkdir(parents=True)
        self.raw=self.scan.surfaces+17
        self.surfaces=self.scan.surfaces.copy();self.surfaces[:,0]=np.nan
        self.state=np.ones(shape,np.uint8);self.state[:,0]=3
        np.savez(self.provider,state=self.state,reason=np.full(shape,9,np.uint8),
            probabilities=np.ones((12,8,2,40))*.8,uncertain_estimates=np.full(shape,np.nan),
            context_reason=np.ones(shape,np.uint8),label_offset=17,
            surface_names=np.array(self.scan.surface_names),scan_id=np.array([self.scan.scan_id]))
        self.write_measurements(17)
        self.original=self.measurements.read_bytes()
        self.editor=SegBoundaryEditor(self.root/"reviewer")
        self.editor.set_line(self.scan,3,self.surfaces,self.scan.confidence,None,
            dict(path=str(self.provider)),np.zeros(40,bool),np.zeros(40,bool))
        self.editor.surface_list.setCurrentRow(0);self.editor.s=0

    def write_measurements(self,offset):
        np.savez(self.measurements,raw_position_branch=self.raw,label_offset=offset,
            surface_names=np.array(self.scan.surface_names),reported_positions=self.surfaces+17)

    def tearDown(self):
        self.editor.close();self.editor.deleteLater();self.app.processEvents();self.temp.cleanup()

    def test_native_crop_coordinates_and_display_only_toggle(self):
        np.testing.assert_allclose(self.editor._raw_ilm,self.scan.surfaces[:,0])
        before=self.editor.signature();self.editor.redraw_surfaces()
        self.assertGreater(self.editor._ilm_preview_item.path().elementCount(),0)
        self.editor.show_ilm.setChecked(False);self.assertIsNone(self.editor._ilm_preview_item)
        self.editor.show_ilm.setChecked(True);self.editor.commit_current()
        self.assertEqual(before,self.editor.signature())
        self.assertTrue(np.isnan(self.editor.pack.states[0].current[0]).all())
        self.assertTrue(np.isnan(self.editor.candidate_rows()[0]).all())
        self.assertEqual(self.original,self.measurements.read_bytes())
        self.assertFalse(list((self.root/"reviewer").rglob("*.npz")))

    def test_denial_gap_exclusion_rejection_and_invalid_rows(self):
        st=self.editor.pack.states[0];st.local["local_visibility"][0,10:20]=P.MARK_NO
        st.excluded[25:28]=True;self.editor.seg_data["state"][3,0,30:33]=2
        self.editor._raw_ilm[3,35]=-1;self.editor._raw_ilm[3,36]=100
        mask=ilm_preview_mask(self.editor._raw_ilm[3],st,self.editor.seg_data["state"][3],0,100)
        self.assertTrue(mask[:10].all())
        self.assertFalse(mask[10:20].any());self.assertFalse(mask[25:28].any())
        self.assertFalse(mask[30:33].any());self.assertFalse(mask[35:37].any())
        self.editor.redraw_surfaces();path=self.editor._ilm_preview_item.path()
        self.assertTrue(path.elementAt(10).isMoveTo())
        st.verdict="rejected"
        self.assertFalse(ilm_preview_mask(self.editor._raw_ilm[3],st,self.state[3],0,100).any())

    def test_acceptance_cannot_promote_raw_preview(self):
        self.editor.span_lo.setValue(0);self.editor.span_hi.setValue(40)
        self.editor.feedback_action("approved_for_future_positions")
        self.assertFalse(self.editor._feedback)
        self.editor.set_verdict("accepted");self.editor.commit_current()
        label=L.load_label(self.root/"reviewer/surface_labels/TS999_TEST_b0003.npz")
        self.assertTrue(np.isnan(label["surfaces"][0]).all())
        self.assertFalse(P.local_position_valid(label,"strict").any())
        self.assertEqual(self.original,self.measurements.read_bytes())

    def test_mismatched_coordinate_frame_is_rejected(self):
        self.write_measurements(18)
        with self.assertRaisesRegex(ValueError,"coordinate frame"):
            load_ilm_preview(self.provider,self.scan.scan_id,self.scan.surface_names,self.state.shape)


if __name__=="__main__":unittest.main()
