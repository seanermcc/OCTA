"""Exercise inherited reviews and v3 persistence without changing source labels."""
import copy,json,tempfile,unittest
from pathlib import Path
from .review_server import current,save,analysis_inputs

class InheritedReviewTests(unittest.TestCase):
    def test_inheritance_retains_flags_notes_origin_and_not_whole_confirmed(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);m=[[1,0,-30],[0,1,42],[0,0,1]]
            rows=[dict(scan_id='field',review_tier='uncertain',placement_confirmed=True,notes='Scale concern',matrix_to_current_origin_pixels=m)]
            data=dict(summary=dict(group='TS999_OS',canvas_origin=[100,100],origin_kind='manual_onh'),
                      scans=[dict(scan_id='field',tier='uncertain',matrix_to_onh_pixels=m)],
                      inherited_review=dict(source='original/v2/human_review.json',revision=81,montage_confirmed=False,records=rows))
            (folder/'montage.json').write_text(json.dumps(data))
            review=current(folder,data)
            self.assertFalse((folder/'human_review.json').exists())
            self.assertEqual(review['fields']['field']['status'],'confirmed')
            self.assertIsNone(review['onh_override'])
            self.assertFalse(review['montage_confirmed'])
            with self.assertRaisesRegex(ValueError,'not confirmed'):analysis_inputs(folder)
            review['montage_confirmed']=True
            saved=save(folder,data,review)
            self.assertEqual(saved['inherited_from']['revision'],81)
            self.assertEqual(saved['onh_origin_kind'],'manual_onh')
            self.assertEqual(analysis_inputs(folder)['records'],[])
            included=analysis_inputs(folder,include_flagged=True)['records'][0]
            self.assertEqual(included['notes'],'Scale concern')
            self.assertEqual(included['matrix_to_current_origin_pixels'],m)

if __name__=='__main__':unittest.main()
