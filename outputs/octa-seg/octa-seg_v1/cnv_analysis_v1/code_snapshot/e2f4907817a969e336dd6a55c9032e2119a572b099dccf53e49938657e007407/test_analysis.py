"""Synthetic scientific invariants; no annotation files are written."""
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter
from .geometry import Footprint,grid,bins,regions,rigid,transform,recover_outline,sample_mask
from .annotations import resolve_regions
from .common import day_info,default_config,gate
from .registration import propose,warp_image,fit_onh,branch_convergence,match_lesions
from .statistics import balanced,cohort
from .figures import cleaned

class GeometryTests(unittest.TestCase):
    def test_transferred_mask_uses_physical_pixel_extent(self):
        m=np.ones((3,3),bool); t=np.eye(3); t[0,2]=10
        p=np.array([[9.6,0],[9.4,0],[12.4,0],[12.6,0]])
        np.testing.assert_array_equal(sample_mask(m,[1,1],p,t),[True,False,True,False])

    def test_exact_rectangle_outline_anisotropic(self):
        m=np.zeros((15,20),bool); m[5:10,8:13]=True
        f=Footprint(m,[2.,3.]); self.assertEqual(f.area,150.)
        np.testing.assert_allclose(f.diameter,2*np.sqrt(150/np.pi))
        p=np.array([[7*3,6*2],[10*3,4*2],[7*3,4*2],[10*3,7*2]])
        np.testing.assert_allclose(f.distance(p),[1.5,1.,np.hypot(1.5,1),0])

    def test_circular_diameter_and_irregular_outline(self):
        y,x=np.indices((51,51)); m=(x-25)**2+(y-25)**2<=100
        f=Footprint(m,[1,1]); self.assertAlmostEqual(f.diameter,20,delta=.2)
        # Concavity is retained; distance is to the real L-shaped outline.
        m[:]=False; m[20:30,20:23]=True; m[27:30,20:30]=True
        f=Footprint(m,[1,1]); self.assertAlmostEqual(f.distance(np.array([[26.,24.]]))[0],2.5)

    def test_boundaries(self):
        d=np.array([0,.01,.5,1,1.5,2,2.5,3,3.001])
        np.testing.assert_array_equal(bins(d,d==0,[0,.5,1,1.5,2,2.5,3]),[0,1,2,3,4,5,6,6,-1])

    def test_overlaps_onh_and_area(self):
        a=np.zeros((30,40),bool); b=a.copy(); a[13:17,12:16]=True; b[13:17,22:26]=True
        onh=a.copy(); onh[:]=False; onh[10:12,12:16]=True
        fs=[Footprint(a,[2,2]),Footprint(b,[2,2])]
        result=regions(fs,a.shape,[2,2],onh,lambda f:np.arange(7)*5.)
        aa,bb=result[0][0],result[1][0]
        self.assertFalse(((aa>0)&(bb>0)).any())
        self.assertFalse((aa[b]>0).any()); self.assertTrue(np.all(aa[onh]==-1))
        self.assertGreater(sum(d['shared_area_um2'] for d in result[0][2]),0)
        for _,_,diag in result:
            for d in diag: self.assertLessEqual(d['fov_area_um2'],d['expected_area_um2']+1e-8)

    def test_clipped_and_recovery(self):
        a=np.zeros((20,20),bool); a[8:13,17:]=True
        b=np.zeros_like(a); b[8:13,:6]=True
        shift=np.eye(3); shift[0,2]=17
        f=Footprint(a,[1,1]); g=Footprint(b,[1,1],shift)
        self.assertFalse(f.complete); self.assertFalse(g.complete)
        recovered=recover_outline([f,g],[1,1]); self.assertTrue(recovered.complete)
        self.assertEqual(recovered.area,30)

    def test_rotation_and_scale_rejection(self):
        m=np.zeros((20,20),bool); m[7:12,8:13]=True
        t=np.array([[0,-1,40],[1,0,3],[0,0,1.]])
        f=Footprint(m,[2,3]); g=Footprint(m,[2,3],t)
        p=np.array([[2.,8.],[36.,19.],[30,20]])
        np.testing.assert_allclose(f.distance(p),g.distance(transform(p,t)))
        with self.assertRaises(ValueError): rigid(np.diag([1.1,1.1,1]))

class AnnotationTests(unittest.TestCase):
    def test_provisional_orientation_matches_declared_axes(self):
        from .common import provisional_sector
        self.assertEqual([provisional_sector(x,y) for x,y in [(0,-1),(0,1),(1,0),(-1,0)]],['D*','V*','N*','T*'])

    def test_negative_classification_overrides_inherited(self):
        m=np.zeros((12,12),bool); m[2:5,2:5]=True
        changed=np.zeros_like(m); changed[3,3]=True
        for category in ('Normal','Other'):
            result,denied=resolve_regions(m,[(dict(id='a',category=category),changed)])
            self.assertEqual(result,[]); self.assertTrue(np.all(denied[m]))

    def test_unreviewed_not_absence(self):
        m=np.eye(12,dtype=bool); result,_=resolve_regions(m,[])
        self.assertTrue(result)

    def test_6mo_and_d0(self):
        r=dict(session_date='2026-01-01',day_label='6mo',days_post_laser='',timepoint_kind='cnv')
        d=day_info(r); self.assertIsNone(d['day']); self.assertEqual(d['day_basis'],'categorical'); self.assertTrue(d['post_d0'])
        d=day_info(dict(r,day_label='D0')); self.assertFalse(d['prelaser']); self.assertFalse(d['post_d0'])
        d=day_info(dict(r,day_label='D119',days_post_laser='160')); self.assertEqual(d['day'],160)
        d=day_info(dict(r,day_label='D7',timepoint_kind='prelaser')); self.assertFalse(d['post_d0'])

    def test_gate_fails_closed(self):
        c=default_config(); c['gate']='nonexistent_final_audit.json'
        with self.assertRaisesRegex(RuntimeError,'gated'): gate(c)

    def test_user_override_skips_only_final_batch_marker(self):
        import tempfile
        from pathlib import Path
        from .common import write
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); c=default_config(); c.update(batch=str(root),gate=str(root/'absent.json'))
            c['batch_audit_override']=dict(authorized_by='user',instruction='Proceed without batch audit')
            write(root/'manifest.json',dict(scans=[dict(scan_id='fixture')]))
            with self.assertRaisesRegex(RuntimeError,'outputs are incomplete'): gate(c)
            for name in ('complete.json','neural_complete.json','geometry.npz','measurements.npz','images.npy','human_overrides_provenance.json','qc_complete.json'):
                p=root/'volumes/fixture'/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('synthetic fixture')
            proof=gate(c)
            self.assertFalse(proof['batch_audit_performed']); self.assertEqual(proof['scans'],1)
            self.assertFalse((root/'absent.json').exists())

class RegistrationTests(unittest.TestCase):
    def test_proposed_and_unmatched_identities_stay_ineligible(self):
        from pathlib import Path
        from .runner import Runner
        r=Runner.__new__(Runner); r.out=Path('nonexistent_test_identity_directory')
        ref=np.zeros((50,50),bool); ref[10:15,10:15]=True
        different=np.zeros_like(ref); different[35:40,35:40]=True
        masks={'reference':ref,'proposed':ref,'unmatched':different}
        r.annotation=lambda sid:dict(lesions=[('one',masks[sid],'test')],spacing=np.array([1.,1.]))
        inv=dict(scans=[dict(scan_id=sid,post_d0=True,session_date=f'2026-01-0{i+1}',visit_id=f'v{i}') for i,sid in enumerate(masks)])
        regs={sid:dict(scan_id=sid,reference_scan='reference',animal='A',eye='OD',
            alignment=dict(state='proposed' if sid=='proposed' else 'verified',matrix=np.eye(3).tolist())) for sid in masks}
        result={v['scan_id']:v for v in r.tracks(regs,inv)}
        self.assertTrue(result['reference']['identity_eligible'])
        self.assertFalse(result['proposed']['identity_eligible']); self.assertTrue(result['proposed']['proposed_track_id'])
        self.assertFalse(result['unmatched']['identity_eligible']); self.assertEqual(result['unmatched']['state'],'unmatched')

    def test_known_image_transform(self):
        rng=np.random.default_rng(42); image=gaussian_filter(rng.normal(size=(192,192)),1)
        theta=np.radians(7); matrix=np.array([[np.cos(theta),-np.sin(theta),12],[np.sin(theta),np.cos(theta),-9],[0,0,1]])
        fixed=warp_image(image,[2,2],image.shape,[2,2],matrix)
        exclusion=~np.isfinite(fixed); fixed=np.nan_to_num(fixed)
        settings=default_config()['registration']
        result=propose(image,fixed,[2,2],[2,2],np.zeros(image.shape,bool),exclusion,settings)
        self.assertEqual(result['state'],'proposed')
        np.testing.assert_allclose(result['matrix'],matrix,atol=2.)
        self.assertGreater(result['diagnostics']['correlation'],.85)

    def test_failed_image_match(self):
        a=np.zeros((64,64)); r=propose(a,a,[1,1],[1,1],a.astype(bool),a.astype(bool),default_config()['registration'])
        self.assertEqual(r['state'],'failed')

    def test_split_merger_ambiguous(self):
        a=np.zeros((40,40),bool); a[10:20,10:25]=True
        b=np.zeros_like(a); b[10:20,10:16]=True; c=np.zeros_like(a); c[10:20,18:25]=True
        res=match_lesions([Footprint(a,[1,1])],[Footprint(b,[1,1]),Footprint(c,[1,1])])
        self.assertEqual(res[0]['state'],'ambiguous_split_or_merge')

    def test_onh_and_convergence(self):
        y,x=np.indices((100,100)); m=(x-48)**2+(y-55)**2<20**2
        r=fit_onh(m,np.zeros_like(m),[2,2]); np.testing.assert_allclose(r['center_um'],[96,110],atol=1)
        r=branch_convergence([[[0,0],[10,10]],[[0,20],[10,10]],[[10,-10],[10,0]]])
        np.testing.assert_allclose(r['center_um'],[10,10],atol=1e-6)

class WeightingTests(unittest.TestCase):
    def rows(self):
        rows=[]
        for animal,eye,track,visit,scan,value in [('A','OD','a','v1','s1',10),('A','OD','a','v2','s2',20),
                                               ('A','OS','b','v1','s3',30),('B','OD','c','v1','s4',100)]:
            rows.append(dict(animal=animal,eye=eye,track_id=track,visit_id=visit,scan_id=scan,lesion_id=track,
                             mean_thickness_um=value,layer='GCL',band=1,distance_basis='normalized',region_definition='changing',
                             identity_eligible=True,normalized_eligible=True,post_d0=True))
        return pd.DataFrame(rows)

    def test_extra_repeats_do_not_reweight_animals(self):
        d=self.rows(); group=['layer','band']; a=balanced(d,group)
        self.assertEqual(a[a.animal=='A'].mean_thickness_um.iloc[0],22.5)
        b=cohort(a,group,100,1); self.assertEqual(b.mean_thickness_um.iloc[0],61.25)
        repeat=d.iloc[[0]].copy(); repeat['scan_id']='repeat'
        more=balanced(pd.concat([d,repeat,d]),group)
        pd.testing.assert_series_equal(a.mean_thickness_um,more.mean_thickness_um)

    def test_missing_layer_and_unmatched(self):
        d=self.rows(); d.loc[d.animal=='B','identity_eligible']=False
        missing=d.copy(); missing['layer']='RPE band'; missing['mean_thickness_um']=np.nan
        a=balanced(pd.concat([d,missing]),['layer','band']); self.assertEqual(set(a.layer),{'GCL'})
        self.assertEqual(len(a),1)

    def test_csv_boolean_strings(self):
        d=cleaned(pd.DataFrame(dict(identity_eligible=['False','True'],mean_thickness_um=['','2'])))
        self.assertFalse(d.identity_eligible.iloc[0]); self.assertTrue(np.isnan(d.mean_thickness_um.iloc[0]))

    def test_unmatched_visit_remains_visible_in_longitudinal_plot(self):
        import tempfile
        from pathlib import Path
        import matplotlib.pyplot as plt
        from .figures import longitudinal
        d=self.rows().iloc[:2].copy(); d['layer']='Full retina'; d['band']=0
        d['day']=[7,56]; d['day_label']=['D7','D56']; d['day_basis']='actual'
        d['session_date']=['2026-01-01','2026-02-19']; d['prelaser']=False
        d.loc[d.index[1],'identity_eligible']=False
        captured=[]
        class Collector:
            def add(self,fig,*args):
                for collection in fig.axes[0].collections:
                    captured.extend(collection.get_offsets().compressed().tolist())
                plt.close(fig)
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory); (out/'tables').mkdir()
            longitudinal(Collector(),d,out)
            means=pd.read_csv(out/'tables/longitudinal_A_changing.csv')
            self.assertIn('v2',means.visit_id.tolist())
            # An extra unmatched acquisition at the same visit removes local
            # uniqueness. It cannot silently increase a repeated lesion's weight.
            repeat=d.iloc[[-1]].copy(); repeat['scan_id']='uncertain_repeat'
            longitudinal(Collector(),pd.concat([d,repeat],ignore_index=True),out)
            means=pd.read_csv(out/'tables/longitudinal_A_changing.csv')
            self.assertNotIn('v2',means.visit_id.tolist())
        self.assertIn(56.,captured)

if __name__=='__main__': unittest.main()
