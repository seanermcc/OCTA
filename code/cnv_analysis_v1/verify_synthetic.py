"""End-to-end synthetic release in verification/synthetic; never creates human labels."""
from pathlib import Path
from unittest.mock import patch
import numpy as np
from .runner import Runner
from .common import default_config,write,read,save,fingerprint,digest,sha

def main():
    root=Path(default_config()['output'])/'verification/synthetic'
    batch=root/'fixture_batch'; batch.mkdir(parents=True,exist_ok=True)
    records=[]
    for i,(label,day) in enumerate([('D0',0),('D7',7),('6mo',None)]):
        sid=f'SYNTHETIC_OD_2026-0{i+1}-01_{label}_s01'
        records.append(dict(scan_id=sid,animal='SYNTHETIC',eye='OD',session_date=f'2026-0{i+1}-01',
            day_label=label,days_post_laser='' if day is None else str(day),timepoint_kind='day',
            native_shape=[40,40,100],source=str(batch/f'{sid}_processedVolumes.mat')))
        write(batch/'volumes'/sid/'qc_complete.json',dict(synthetic_fixture=True))
    write(batch/'manifest.json',dict(scans=records))
    write(batch/'FINAL_VERIFIED.json',dict(passed=True,scans=3,synthetic_fixture_only=True,tables=[]))
    c=default_config(); c.update(batch=str(batch),gate=str(batch/'FINAL_VERIFIED.json'),
        output=str(root/'cnv_analysis_v1'),field_um_yx=[80,80],absolute_edges_um=[0,4,8,12,16,20,24],
        bootstrap_samples=100,enface_labels=str(root/'nonexistent_annotations'),region_sources=[])
    y,x=np.indices((40,40)); mask=(x-20)**2+(y-20)**2<=9
    onh=(x-6)**2+(y-6)**2<9
    def annotation(config,record):
        return dict(lesions=[('lesion',mask,'synthetic_test')],onh=onh,onh_edge=np.zeros_like(mask),
                    vessel=np.zeros_like(mask),union=mask,denied=np.zeros_like(mask),spacing=np.array([2.,2.]),refs=[],reviewed=True)
    def thickness(self,sid,frozen):
        index=next(i for i,r in enumerate(records) if r['scan_id']==sid)
        thick=np.stack([100-k*10+index*3+x*.1+y*.05 for k in range(8)]).astype('float32')
        thick[5]=np.nan; thick[:,:,3]=np.nan
        path=self.out/'thickness'/f'{sid}.npz'; arrays=dict(exclude_unreliable_um=thick,shadow=x==3)
        save(path,**arrays); meta=dict(revision=f'synthetic-{index}',experimental=True,policy=c['policy'])
        write(path.with_suffix('.json'),meta); frozen['scans'][sid]=fingerprint(path); write(self.out/'frozen_inputs.json',frozen)
        return arrays,meta
    with patch('cnv_analysis_v1.runner.A.load',side_effect=annotation),patch.object(Runner,'thickness',thickness):
        runner=Runner(c); runner.inventory(); regs={}; identities=[]
        for r in records:
            sid=r['scan_id']
            regs[sid]=dict(scan_id=sid,reference_scan=records[1]['scan_id'],animal='SYNTHETIC',eye='OD',
                alignment=dict(state='verified',matrix=np.eye(3).tolist(),uncertainty_um=1),
                onh=dict(state='localized',center_um=[12.,12.],uncertainty_um=2,method='synthetic'))
            identities.append(dict(scan_id=sid,lesion_id='lesion',track_id='synthetic_track',state='tracked_match',identity_eligible=True,visit_id=r['session_date']))
        write(runner.out/'registration/registrations.json',regs); write(runner.out/'registration/identities.json',identities)
        runner.measure(); table=runner.out/'tables/lesion_visit_layer_band.csv'; before=sha(table)
        runner.measure(); assert sha(table)==before,'Resume changed numerical measurements'
        runner.figures()
        import pandas as pd
        d=pd.read_csv(table)
        assert len(d)==3*2*2*8*7
        assert d[d.layer=='OPL'].mean_thickness_um.isna().all()
        assert set(d[d.day_label=='6mo'].day_basis)=={'categorical'}
        assert d[d.day_label=='6mo'].day.isna().all()
        summary=read(runner.out/'ANALYSIS_COMPLETE.json')
        assert summary['passed'] and summary['figures']>10
        write(root.parent/'synthetic_checks.json',dict(passed=True,measurement_rows=len(d),
            resume_identical=True,missing_layer_preserved=True,unresolved_dates_preserved=True,
            figures=summary['figures'],synthetic_only=True,output=str(runner.out)))
        print(f'Synthetic pipeline passed: {len(d)} rows, {summary["figures"]} figures; identical resumed output.',flush=True)

if __name__=='__main__': main()
