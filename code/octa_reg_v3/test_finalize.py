import json,tempfile,unittest
from pathlib import Path
from .finalize import finalize

class BackboneTests(unittest.TestCase):
    def test_flagged_bridge_cannot_leave_child_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'TS999_OD';folder.mkdir()
            m=[[1,0,0],[0,1,0],[0,0,1]]
            graph=dict(reference=0,poses={str(i):m for i in range(3)},tiers={'0':'supported','1':'uncertain','2':'supported'},
                reasons={'0':[],'1':['Large displacement'],'2':[]},edges=[dict(a=0,b=1,matrix=m,score=.8),dict(a=1,b=2,matrix=m,score=.9)])
            (root/'run_plan.json').write_text(json.dumps(dict(groups=['TS999_OD'])))
            (folder/'registration.json').write_text(json.dumps(dict(graph=graph,inherited_review=None)))
            finalize(root)
            after=json.loads((folder/'review_registration.json').read_text())['graph']
            self.assertEqual(after['tiers']['2'],'uncertain')
            self.assertEqual(after['poses']['0'],m)

    def test_final_onh_conflict_demotes_dependent_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'TS999_OD';folder.mkdir();m=[[1,0,0],[0,1,0],[0,0,1]]
            scans=[dict(spacing=[1,1],onh_assessable=True,visible_onh=dict(resolved=True,center_um=c)) for c in ([0,0],[200,0])]
            scans.append(dict(spacing=[1,1]))
            graph=dict(reference=0,origin_kind='reviewed_onh',poses={str(i):m for i in range(3)},
                tiers={str(i):'supported' for i in range(3)},reasons={str(i):[] for i in range(3)},
                edges=[dict(a=0,b=1,matrix=m,score=.8),dict(a=1,b=2,matrix=m,score=.9)])
            (root/'run_plan.json').write_text(json.dumps(dict(groups=['TS999_OD'])))
            (folder/'registration.json').write_text(json.dumps(dict(graph=graph,scans=scans,inherited_review=None)))
            finalize(root);result=json.loads((folder/'review_registration.json').read_text())
            self.assertEqual(result['graph']['tiers'],{'0':'supported','1':'uncertain','2':'uncertain'})
            self.assertFalse(result['anatomy_audit']['centers'][1]['consistent'])

if __name__=='__main__':unittest.main()
