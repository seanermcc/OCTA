"""Persistence invariants using isolated synthetic records, never human reviews."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from .review_server import current, fingerprint, save, validate, analysis_inputs
from octa_reg_v2.reviewer_publish import visit


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.m = [[1,0,10],[0,1,20],[0,0,1]]
        self.data = dict(summary=dict(group='TS999_OS',canvas_origin=[100,100]), scans=[
            dict(scan_id='a',tier='supported',matrix_to_onh_pixels=self.m),
            dict(scan_id='b',tier='uncertain',matrix_to_onh_pixels=self.m),
            dict(scan_id='c',tier='excluded')])
        (self.folder/'montage.json').write_text(json.dumps(self.data))
        self.body = current(self.folder,self.data)

    def tearDown(self): self.tmp.cleanup()

    def test_roundtrip_preserves_baseline_and_history(self):
        baseline=(self.folder/'montage.json').read_bytes()
        self.body['fields']['b']=dict(matrix_to_onh_pixels=self.m,status='confirmed')
        saved=save(self.folder,self.data,self.body)
        self.assertEqual(current(self.folder,self.data)['fields']['b']['status'],'confirmed')
        saved['fields']['b']['status']='draft'; saved['fields']['b']['matrix_to_onh_pixels'][0][2]+=5
        save(self.folder,self.data,saved)
        self.assertEqual(json.loads((self.folder/'review_history/000001.json').read_text())['fields']['b']['status'],'confirmed')
        self.assertEqual((self.folder/'montage.json').read_bytes(),baseline)

    def test_stale_tab_cannot_overwrite(self):
        save(self.folder,self.data,self.body)
        with self.assertRaisesRegex(ValueError,'Another tab'): save(self.folder,self.data,self.body)

    def test_excluded_and_cross_group_fields_rejected(self):
        for sid in ('c','other_eye'):
            body=copy.deepcopy(self.body);body['fields'][sid]=dict(matrix_to_onh_pixels=self.m,status='confirmed')
            with self.assertRaises(ValueError):validate(self.data,body)

    def test_nonrigid_and_nonfinite_rejected(self):
        for m in ([[2,0,0],[0,1,0],[0,0,1]], [[-1,0,0],[0,1,0],[0,0,1]], [[1,0,float('nan')],[0,1,0],[0,0,1]]):
            self.body['fields']['b']=dict(matrix_to_onh_pixels=m,status='draft')
            with self.assertRaises(ValueError):validate(self.data,self.body)

    def test_changed_baseline_blocks_reuse(self):
        save(self.folder,self.data,self.body)
        self.data['scans'][0]['matrix_to_onh_pixels'][0][2]+=10
        with self.assertRaisesRegex(ValueError,'different automatic'):current(self.folder,self.data)

    def test_unlocalized_can_remain_flagged_on_montage_confirmation(self):
        self.data['scans'].append(dict(scan_id='d',tier='unlocalized'))
        self.body['base_fingerprint']=fingerprint(self.data);self.body['montage_confirmed']=True
        validate(self.data,self.body)
        self.body['decisions']['d']=dict(tier='supported',notes='')
        with self.assertRaisesRegex(ValueError,'Place'):validate(self.data,self.body)
        self.body['fields']['d']=dict(matrix_to_onh_pixels=self.m,status='draft')
        validate(self.data,self.body)

    def test_flagged_notes_survive_confirmation_and_analysis_omits_them(self):
        self.body['decisions']['a']=dict(tier='uncertain',notes='Vessels look enlarged <check scale>')
        self.body['decisions']['b']=dict(tier='supported',notes='Reviewed overlap')
        self.body['montage_confirmed']=True
        saved=save(self.folder,self.data,self.body)
        self.assertEqual(current(self.folder,self.data)['decisions'],self.body['decisions'])
        self.assertEqual([r['scan_id'] for r in analysis_inputs(self.folder)['records']],['b'])
        self.assertEqual(len(analysis_inputs(self.folder,include_flagged=True)['records']),2)
        self.assertEqual(saved['analysis_records'][0]['review_tier'],'uncertain')

    def test_manual_exclusion_removes_effective_transform_and_is_reversible(self):
        self.body['decisions']['a']=dict(tier='excluded',notes='Wrong scale')
        self.body['montage_confirmed']=True
        excluded=save(self.folder,self.data,self.body)
        self.assertNotIn('a',excluded['effective_matrices_to_onh_pixels'])
        self.assertNotIn('a',[r['scan_id'] for r in analysis_inputs(self.folder,include_flagged=True)['records']])
        excluded['decisions']['a']['tier']='supported'
        restored=save(self.folder,self.data,excluded)
        self.assertEqual(restored['effective_matrices_to_onh_pixels']['a'],self.m)

    def test_analysis_rejects_unconfirmed_and_preserves_categories_from_old_client(self):
        self.body['decisions']['a']=dict(tier='uncertain',notes='Check acquisition')
        saved=save(self.folder,self.data,self.body)
        with self.assertRaisesRegex(ValueError,'not confirmed'):analysis_inputs(self.folder)
        saved.pop('decisions')
        self.assertEqual(save(self.folder,self.data,saved)['decisions'],self.body['decisions'])

    def test_invalid_category_notes_and_source_exclusion_rejected(self):
        for decision in (dict(tier='good',notes=''),dict(tier='uncertain',notes=3),dict(tier='supported',notes='a'*8001)):
            self.body['decisions']={'a':decision}
            with self.assertRaises(ValueError):validate(self.data,self.body)
        self.body['decisions']={'c':dict(tier='supported',notes='')}
        with self.assertRaisesRegex(ValueError,'locked'):validate(self.data,self.body)

    def test_visit_uses_actual_day_and_short_special_labels(self):
        self.assertEqual(visit(dict(day_label='D14',days_post_laser='15'))['day_label'],'d15')
        self.assertEqual(visit(dict(day_label='before laser'))['day_label'],'pre')
        self.assertEqual(visit(dict(day_label='laser day'))['day_label'],'d0')
        self.assertEqual(visit(dict(day_label='6 mo'))['day_label'],'6mo')

    def test_manual_onh_rebases_coordinates_without_moving_fields(self):
        baseline=copy.deepcopy(self.data)
        self.body['fields']['b']=dict(matrix_to_onh_pixels=copy.deepcopy(self.m),status='confirmed')
        self.body['onh_override']=[30,-40]
        saved=save(self.folder,self.data,self.body)
        loaded=current(self.folder,self.data)
        self.assertEqual(loaded['onh_override'],[30,-40])
        self.assertEqual(loaded['fields']['b']['matrix_to_onh_pixels'],self.m)
        self.assertEqual(loaded['fields']['b']['status'],'confirmed')
        self.assertEqual(saved['effective_matrices_to_onh_pixels']['a'],[[1,0,-20],[0,1,60],[0,0,1]])
        self.assertNotIn('c',saved['effective_matrices_to_onh_pixels'])
        self.assertEqual(self.data,baseline)
        saved['onh_override']=None
        reset=save(self.folder,self.data,saved)
        self.assertEqual(reset['effective_matrices_to_onh_pixels']['a'],self.m)

    def test_legacy_review_and_client_do_not_erase_manual_origin(self):
        self.body.pop('onh_override')
        legacy=save(self.folder,self.data,self.body)
        self.assertIsNone(legacy['onh_override'])
        legacy['onh_override']=[12,34]
        manual=save(self.folder,self.data,legacy)
        manual.pop('onh_override')
        self.assertEqual(save(self.folder,self.data,manual)['onh_override'],[12,34])

    def test_invalid_onh_rejected(self):
        for point in ([1], [1,2,3], [float('nan'),0], ['2',0], [True,0], [100000,0]):
            self.body['onh_override']=point
            with self.assertRaises(ValueError):validate(self.data,self.body)


if __name__ == '__main__':unittest.main()
