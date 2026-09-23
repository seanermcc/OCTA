"""Contract tests and real Qt verification; all synthetic records remain isolated."""
from common import *
import unittest, tempfile, copy
from unittest.mock import patch
from review_store import Store, targets, progress, valid_confirmation
from prepare_queue import day_value, ordered_queue

class Contracts(unittest.TestCase):
    def setUp(self):
        self.directory=HERE/'verification/tests'/uuid.uuid4().hex/'regions'
        self.a=dict(scan_id='SYNTHETIC_A',animal='TS267',source_identity='synthetic_a',native_shape=[12,14])
        self.s=Store(self.a,self.directory,synthetic=True)
        self.mask=np.zeros((12,14),bool);self.mask[2:5,1:4]=True

    def kept(self,s=None):
        s=s or self.s;i=s.add(mask=self.mask);s.set_region(i,state='kept');return i

    def test_browse_never_creates_annotation(self):
        self.assertFalse(self.s.save());self.assertFalse(self.s.path.exists())
        self.assertEqual(progress([self.a],self.directory)['positive'],0)

    def test_draft_background_and_confirmation(self):
        self.kept();self.s.save();self.assertFalse(targets(self.s.state,self.s.shape)[1].any())
        self.s.confirm();self.s.save();p,b,i,_,_=targets(self.s.state,self.s.shape)
        self.assertTrue(np.array_equal(b,~p));self.assertEqual(p.sum(),9)
        reopened=Store(self.a,self.directory,synthetic=True)
        self.assertTrue(valid_confirmation(reopened.state));self.assertEqual(reopened.state,self.s.state)

    def test_absence_requires_confirmation(self):
        self.s.absence(True);self.s.save();self.assertFalse(targets(self.s.state,self.s.shape)[1].any())
        self.s.confirm();self.s.save();self.assertTrue(targets(self.s.state,self.s.shape)[1].all())
        self.assertEqual(progress([self.a],self.directory,verify_synthetic=True)['negative'],1)

    def test_absence_conflicts_and_add_undo(self):
        self.s.absence(True);self.s.confirm();self.s.add(mask=self.mask)
        self.assertFalse(self.s.state['absence']);self.assertFalse(valid_confirmation(self.s.state))
        self.s.undo();self.assertTrue(valid_confirmation(self.s.state));self.assertTrue(self.s.state['absence'])
        self.s.redo();self.assertFalse(self.s.state['absence'])
        with self.assertRaises(ValueError):self.s.absence(True)

    def test_absence_cannot_restore_removed_region(self):
        self.kept();self.s.set_region(0,state='removed');self.s.absence(True);self.s.confirm()
        for state in ('draft','kept','unsure','excluded'):
            with self.assertRaises(ValueError):self.s.set_region(0,state=state)
        self.assertTrue(valid_confirmation(self.s.state))
        self.s.absence(False);self.s.set_region(0,state='kept');self.s.confirm()

    def test_keep_unsure_excluded_removed(self):
        self.kept();self.s.set_region(0,state='unsure')
        with self.assertRaises(ValueError):self.s.confirm()
        self.s.set_region(0,state='excluded')
        with self.assertRaises(ValueError):self.s.absence(True)
        self.s.set_region(0,state='removed');self.s.absence(True);self.s.confirm()

    def test_edits_invalidate_and_undo_restore(self):
        self.kept();self.s.confirm();self.s.save()
        m=self.mask.copy();m[0,0]=True;self.s.set_region(0,mask=m)
        self.assertFalse(valid_confirmation(self.s.state));self.assertFalse(targets(self.s.state,self.s.shape)[1].any())
        self.s.undo();self.assertTrue(valid_confirmation(self.s.state));self.s.redo();self.assertFalse(valid_confirmation(self.s.state))
        self.s.confirm();self.s.save();self.assertTrue(valid_confirmation(Store(self.a,self.directory,synthetic=True).state))

    def test_empty_and_invalid_geometry(self):
        self.s.add();self.s.set_region(0,state='kept')
        with self.assertRaises(ValueError):self.s.confirm()
        for runs in ([[0,0,15]],[[12,0,1]],[[0,-1,1]],[[0,1.0,2]],[[0,0,2],[0,1,2]]):
            with self.assertRaises(ValueError):decode(runs,(12,14))

    def test_explicit_overlap_ignore(self):
        self.kept();u=self.mask.copy();u[2:4]=False
        i=self.s.add(mask=u);self.s.set_region(i,state='unsure')
        with self.assertRaises(ValueError):self.s.confirm()
        self.s.confirm(True);p,b,ignored,_,n=targets(self.s.state,self.s.shape)
        self.assertEqual(n,3);self.assertFalse((p&ignored).any());self.assertFalse((b&ignored).any())
        self.assertEqual(self.s.state['confirmation']['ignored_conflict_pixels'],3)

    def test_counts_acquisitions_not_lesions_or_revisions(self):
        self.kept();self.kept();self.s.confirm();self.s.save();self.s.confirm();self.s.save()
        p=progress([self.a,self.a],self.directory,verify_synthetic=True);self.assertEqual(p['positive'],1)
        self.assertEqual(progress([self.a],self.directory)['positive'],0)
        self.s.set_region(0,state='removed');self.s.save()
        self.assertEqual(progress([self.a],self.directory,verify_synthetic=True)['positive'],0)
        self.s.confirm();self.s.save();self.assertEqual(progress([self.a],self.directory,verify_synthetic=True)['positive'],1)
        self.s.set_region(1,state='removed');self.s.absence(True);self.s.confirm();self.s.save()
        self.assertEqual(progress([self.a],self.directory,verify_synthetic=True)['negative'],1)

    def test_target_and_beyond_30(self):
        acquisitions=[]
        for k in range(32):
            a=dict(self.a,scan_id=f'SYNTHETIC_{k}',source_identity=f'synthetic_{k}');acquisitions.append(a)
            s=Store(a,self.directory,synthetic=True);self.kept(s);s.confirm();s.save()
        self.assertTrue(progress(acquisitions,self.directory,verify_synthetic=True)['target_reached'])
        self.assertEqual(progress(acquisitions,self.directory,verify_synthetic=True)['positive'],32)

    def test_stale_writer(self):
        second=Store(self.a,self.directory,synthetic=True);self.kept();self.s.save();self.kept(second)
        before=sha(self.s.path)
        with self.assertRaises(RuntimeError):second.save()
        self.assertEqual(before,sha(self.s.path));self.assertTrue(second.dirty)

    def test_atomic_save_failure_and_recovery(self):
        self.kept();self.s.confirm();self.s.save();before=sha(self.s.path)
        self.s.set_region(0,state='unsure')
        original=os.replace
        def fail(src,dst):
            if Path(dst)==self.s.path:raise OSError('simulated disk full')
            return original(src,dst)
        with patch('common.os.replace',side_effect=fail):
            with self.assertRaises(OSError):self.s.save()
        self.assertEqual(before,sha(self.s.path));self.assertTrue(self.s.dirty);self.assertFalse(self.s.path.with_suffix('.lock').exists())
        self.s.save();self.assertFalse(self.s.dirty);self.assertGreaterEqual(len(list((self.directory/'history'/self.a['scan_id']).glob('*.json'))),2)

    def test_storage_boundary(self):
        with self.assertRaises(ValueError):atomic(V6/'DO_NOT_WRITE.json',{})
        with self.assertRaises(ValueError):Store(self.a,HERE/'review/regions',synthetic=True)

    def test_day_rules(self):
        base=dict(animal='TS267',day='',days_post_laser='')
        self.assertEqual(day_value(dict(base,day_label='D92'))[0],92)
        self.assertEqual(day_value(dict(base,day_label='6 mo'))[0],180)
        self.assertEqual(day_value(dict(base,day_label='D7'))[0],7)
        self.assertEqual(day_value(dict(base,day_label='D14',days_post_laser='6'))[0],6)
        self.assertIsNone(day_value(dict(base,day_label='before laser'))[0])
        self.assertIsNone(day_value(dict(base,day_label='unknown'))[0])
        self.assertIsNone(day_value(dict(base,animal='TS165',day_label='D35'))[0])

    def test_frozen_queue_order_and_visit_cycles(self):
        q=read(HERE/'queue/queue.json');a=q['acquisitions'];again,_=ordered_queue(a,q['config']['seed'])
        self.assertEqual([x['scan_id'] for x in a],[x['scan_id'] for x in again])
        self.assertEqual([x['animal'] for x in a[:10]],q['config']['animals'])
        self.assertEqual(len({x['source_identity'] for x in a}),len(a));self.assertGreater(len(a),30)
        self.assertTrue(all(x['eligibility_day']>7 and x['animal']!='TS165' for x in a))
        for animal,n in q['config']['visit_counts'].items():
            rows=[x for x in a if x['animal']==animal]
            self.assertEqual(len({x['session_date'] for x in rows[:n]}),n)
        self.assertEqual(len(q['config']['exhaustion']),10)
        self.assertTrue(any(x.get('metadata_note') for x in a if x['animal']=='TS336'))

    def test_closed_loop_and_deliberate_erasure(self):
        from viewer import paint_filled,brush_segment
        old=np.zeros((40,40),bool);stroke=old.copy()
        for a,b in [((5,5),(5,30)),((5,30),(30,30)),((30,30),(30,5)),((30,5),(5,5))]:brush_segment(stroke,a,b,2)
        filled=paint_filled(old,stroke);self.assertTrue(filled[15,15])
        filled[15,15]=False;stroke[:]=False;stroke[0,0]=True
        self.assertFalse(paint_filled(filled,stroke)[15,15])

    def test_intervals_native_edges_and_empty_rows(self):
        mask=np.zeros((512,512),bool);mask[0,[0,1,6,511]]=True;mask[-1,20:25]=True
        self.assertEqual(intervals(mask[0]),[(0,2),(6,7),(511,512)])
        self.assertEqual(intervals(mask[511]),[(20,25)]);self.assertEqual(intervals(mask[256]),[])
        self.assertTrue(np.array_equal(decode(encode(mask)),mask))

    def test_gui_filters_and_restart_navigation(self):
        from viewer import Window,W
        from types import SimpleNamespace
        app=W.QApplication.instance() or W.QApplication([])
        window=Window(review_directory=self.directory,synthetic=True,autoload=False)
        original=[a['scan_id'] for a in window.queue]
        window.animal.setCurrentText('TS267')
        self.assertTrue(all(window.queue[i]['animal']=='TS267' for i in window.filtered))
        self.assertEqual(original,[a['scan_id'] for a in window.queue])
        window.index=5;window.queue_cursor=2;window.row=37;window.scan=SimpleNamespace()
        window.save_session()
        reopened=Window(review_directory=self.directory,synthetic=True,autoload=False)
        self.assertEqual(reopened.resume_row,37);self.assertEqual(reopened.queue_cursor,2)
        self.assertEqual(read(reopened.session_path)['scan_id'],window.queue[5]['scan_id'])
        with patch.object(reopened,'load') as load:
            reopened.return_queue();load.assert_called_once_with(2)
        window.scan=None;window.close();reopened.close()

    def test_gui_target_message_requires_saved_confirmation(self):
        from viewer import Window,W
        app=W.QApplication.instance() or W.QApplication([])
        window=Window(review_directory=self.directory,synthetic=True,autoload=False)
        self.kept();window.store=self.s
        summary=progress([]);summary.update(positive=30,target_reached=True)
        with patch('viewer.progress',return_value=summary),patch.object(W.QMessageBox,'information') as message:
            window.confirm();self.assertTrue(self.s.path.exists());self.assertTrue(valid_confirmation(read(self.s.path)['state']))
            self.assertTrue(window.milestone_shown);message.assert_called_once()
            window.confirm();message.assert_called_once() # No repeated interruption at the milestone.
        window.close()

def run_tests():
    import io
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    text=stream.getvalue();destination(HERE/'verification/contract_tests.txt').write_text(text,encoding='utf-8');print(text)
    atomic(HERE/'verification/contract_tests.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),at=now()))
    if not result.wasSuccessful():raise SystemExit(1)

if __name__=='__main__':run_tests()
