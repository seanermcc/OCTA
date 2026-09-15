"""GUI save/reopen checks in temporary test output, never production labels."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile
import unittest
from pathlib import Path
import numpy as np
import app


class EditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=app.QtWidgets.QApplication.instance() or app.QtWidgets.QApplication([])
        app.configure_app(cls.qt)

    def test_draft_erase_undo_review_provenance_and_reopen(self):
        with tempfile.TemporaryDirectory(prefix='vessel-editor-test-') as tmp:
            dest=Path(tmp)
            w=app.Window(app.HERE/'review_queue.json',dest)
            original=w.state['vessel'].copy()
            self.assertTrue(original.any())
            before_onh=w.state['onh'].copy();before_cnv=w.state['cnv'].copy()
            w.size.setValue(150)
            # Erase all columns through real GUI brush handling.
            for y in range(0,513,60):
                w.stroke([(0,y),(512,y)],'vasculature_brush_erase')
            self.assertFalse(w.state['vessel'].any())
            self.assertFalse(w.state['reviewed'][1])
            w.undo();self.assertTrue(w.state['vessel'].any());w.redo()
            self.assertFalse(w.state['vessel'].any())
            path=w.save()
            reopened=app.load_scan(w.rows[w.index],dest)
            self.assertFalse(reopened['vessel'].any(),'Empty draft must override automatic seed')
            np.testing.assert_array_equal(reopened['onh'],before_onh)
            np.testing.assert_array_equal(reopened['cnv'],before_cnv)
            np.testing.assert_array_equal(reopened['initial_vessel'],original)
            self.assertTrue(reopened['vessel_touched'].any())
            w.set_tool('ONH outline');w.stroke([(80,80),(140,80),(140,140),(80,140)],'cnv_outline_add')
            self.assertTrue(w.state['onh'].any());self.assertFalse(w.state['reviewed'][2])
            w.visibility('Visible — outlined');w.review(2,True)
            w.set_tool('Vessel uncertain area');w.stroke([(250,250)],'vasculature_brush_add')
            self.assertTrue(w.state['vessel_excluded'].any())
            self.assertFalse(w.state['vessel'].any())
            w.review(1,True);w.save()
            reopened=app.load_scan(w.rows[w.index],dest)
            self.assertTrue(reopened['reviewed'][1]);self.assertTrue(reopened['reviewed'][2])
            self.assertTrue(reopened['onh_touched'].any());self.assertTrue(reopened['vessel_excluded'].any())
            with np.load(path,allow_pickle=False) as z:
                self.assertEqual(str(z['editor_version'][0]),'octo-vessel_onh_v1')
                self.assertEqual(str(z['queue_sha256'][0]),app.digest(app.HERE/'review_queue.json'))
            w.load(1);w.load(0)
            self.assertFalse(w.state['vessel'].any())
            w.close()

    def test_invalid_onh_approval_does_not_save(self):
        with tempfile.TemporaryDirectory(prefix='vessel-editor-test-') as tmp:
            w=app.Window(app.HERE/'review_queue.json',Path(tmp))
            w.review(2,True)
            with self.assertRaises(ValueError):w.save()
            self.assertEqual(list(Path(tmp).glob('*.npz')),[])
            w.dirty=False;w.close()

    def test_erase_toggle_and_onh_priority(self):
        with tempfile.TemporaryDirectory(prefix='vessel-editor-test-') as tmp:
            w=app.Window(app.HERE/'review_queue.json',Path(tmp))
            w.state['onh'][:]=False
            w.state['vessel'][:]=False
            w.state['vessel'][90:130,90:130]=True
            w.state['reviewed'][1]=True
            before=w.state['vessel'].copy()
            w.set_tool('ONH outline')
            w.stroke([(70,70),(150,70),(150,150),(70,150)],'cnv_outline_add')
            self.assertFalse((w.state['vessel'] & w.state['onh']).any())
            self.assertFalse(w.state['reviewed'][1])
            self.assertTrue(w.state['vessel_removed_by_onh'][100,100])
            w.undo();np.testing.assert_array_equal(w.state['vessel'],before)
            self.assertFalse(w.state['onh'].any())
            w.redo();self.assertFalse(w.state['vessel'].any())
            w.set_tool('Vessel brush');w.size.setValue(10)
            w.stroke([(100,100)],'vasculature_brush_add')
            self.assertFalse(w.state['vessel'][100,100])
            w.stroke([(200,200)],'vasculature_brush_add')
            self.assertTrue(w.state['vessel'][200,200])
            w.erase.setChecked(True)
            self.assertTrue(w.canvas.force_erase)
            w.stroke([(200,200)],'vasculature_brush_add')
            self.assertFalse(w.state['vessel'][200,200])
            w.set_tool('ONH outline')
            self.assertEqual(w.canvas.mode,'onh_brush')
            w.stroke([(100,100)],'onh_brush_add')
            self.assertFalse(w.state['onh'][100,100])
            self.assertFalse(w.state['vessel'][100,100])
            path=w.save()
            with np.load(path,allow_pickle=False) as z:
                self.assertFalse((z['onh_mask'] & z['vasculature_mask']).any())
                self.assertTrue(z['vessel_removed_by_onh'][100,100])
            w.close()


if __name__=='__main__':unittest.main()
