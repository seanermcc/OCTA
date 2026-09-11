"""Bounded real-data interface and numerical validation, separate from release output."""
from pathlib import Path
import importlib.util
import numpy as np
from .runner import Runner
from .common import ROOT,default_config,read,write,sha,fingerprint,save
from .geometry import Footprint,grid,bins

def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    r=Runner(default_config()); inv=r.inventory_data(); out=r.out/'verification'
    candidates=[row for row in inv['scans'] if row['lesion_count'] and row['volume_ready'] and row['post_d0']]
    checks=[]; protected={fp['path']:sha(fp['path']) for fp in inv['annotations']}
    selected=[]
    for row in candidates:
        if row['animal'] not in {v['animal'] for v in selected}: selected.append(row)
        if len(selected)==3: break
    for row in selected:
        sid=row['scan_id']; vol=r.batch/'volumes'/sid
        for name in ['measurements.npz','geometry.npz','human_overrides_provenance.json']:
            protected[str(vol/name)]=sha(vol/name)
        spec=importlib.util.spec_from_file_location('cnv_verify_engine',ROOT/'outputs/octa-thick_v1/engine.py')
        engine=importlib.util.module_from_spec(spec); spec.loader.exec_module(engine); engine.HERE=out/'viewer_cache'
        v=engine.Volume(vol,read(r.batch/'launch_config.json')); a=r.annotation(sid)
        independent=[]
        for _,top,bottom in engine.LAYERS:
            delta=(v.endpoints[0][:,bottom]-v.endpoints[0][:,top])*1.12
            independent.append(np.where((delta>0)&~v.g['shadow'],delta,np.nan))
        np.testing.assert_equal(np.stack(independent),v.maps[0][0])
        if np.isfinite(v.maps[0][0][:,v.g['shadow']]).any(): raise AssertionError('Shadow measurement')
        lid,mask,source=a['lesions'][0]; f=Footprint(mask,a['spacing']); points=grid(mask.shape,a['spacing'])
        distance=f.distance(points); band=bins(distance,f.inside(points),np.arange(7)*.5*f.diameter)
        stats=[]
        for k,layer in enumerate(engine.LAYERS):
            selected_pixels=(band==0)&np.isfinite(v.maps[0][0][k]); values=v.maps[0][0][k][selected_pixels]
            stats.append(dict(layer=layer[0],valid_pixels=len(values),mean_um=float(values.mean()) if len(values) else None))
        fig,axes=plt.subplots(1,3,figsize=(15,5))
        axes[0].imshow(v.enface,cmap='gray'); axes[0].contour(mask,levels=[.5],colors=['red']); axes[0].set_title('Manual CNV outline')
        im=axes[1].imshow(np.ma.masked_where(band<0,band),cmap='tab10',vmin=0,vmax=6); axes[1].set_title('Interior + six outward bands'); fig.colorbar(im,ax=axes[1])
        im=axes[2].imshow(v.maps[0][0][0],cmap='viridis'); axes[2].contour(mask,levels=[.5],colors=['red']); axes[2].set_title('octa-thick exclude_unreliable_um'); fig.colorbar(im,ax=axes[2],label='µm')
        fig.suptitle(f'Validation only — {sid}\nD = {f.diameter:.1f} µm; complete outline = {f.complete}',fontsize=11)
        fig.tight_layout(); out.mkdir(exist_ok=True); fig.savefig(out/f'{sid}_ring_check.png',dpi=110); plt.close(fig)
        checks.append(dict(scan_id=sid,exact_octathick_match=True,shadow_nans_preserved=True,
            diameter_um=f.diameter,diameter_complete=f.complete,layers=stats,measurement_revision=v.revision,
            metadata=v.metadata()))
        del v
        print('Verified real thickness and outline: '+sid,flush=True)
    # One real same-eye registration attempt is retained whether it passes or
    # fails diagnostics; a failed match is not relabeled as correspondence.
    from .registration import propose
    same_eye=[row for row in candidates if row['animal']=='TS247' and row['eye']=='OD']
    registration=None
    if len(same_eye)>=2:
        fixed_row,moving_row=same_eye[:2]; ref=fixed_row['scan_id']; sid=moving_row['scan_id']
        fixed,bad_f=r.image(ref); moving,bad_m=r.image(sid)
        a=r.annotation(sid); b=r.annotation(ref)
        registration=propose(moving,fixed,a['spacing'],b['spacing'],bad_m|a['union']|a['onh'],
            bad_f|b['union']|b['onh'],r.c['registration'])
        write(out/'real_registration_check.json',dict(source_scan=sid,target_scan=ref,validation_only=True,**registration))
        r.registration_overlay(sid,ref,moving,fixed,a['spacing'],b['spacing'],registration)
        print('Real registration diagnostics: '+registration['state'],flush=True)
    for path,expected in protected.items():
        if sha(path)!=expected: raise AssertionError('Source changed during validation: '+path)
    write(out/'real_data_checks.json',dict(passed=True,scans=checks,protected_source_hashes=protected,
        all_source_hashes_unchanged=True,registration_state=registration['state'] if registration else 'unavailable',
        note='Bounded interface validation only; final cohort measurements remain gated.'))

if __name__=='__main__': main()
