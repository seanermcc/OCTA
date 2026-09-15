"""Descriptive metrics and prespecified review roles, without accuracy claims."""
from .common import *
from quality_pilot.metrics import stats,roughness,diagnostic_thickness,select_strips,warnings
from eight_surface.config import SURFACE_NAMES
from scipy.ndimage import distance_transform_edt

def run(round_dir=ROUND):
    ROUND=Path(round_dir)
    learned=(ROUND/'model_manifest.json').exists()
    initialize();boundary=[];thick=[];queue=[];comparisons=[];signal=[];effects=[]
    for si,sid in enumerate(SCANS):
        out=ROUND/'volumes'/sid;d=npz(out/'measurements.npz');g=npz(out/'geometry.npz');p=read(out/'prepared.json');base=npz(out/'v1_matched_baseline.npz')
        diag,failed,invalid,cross=diagnostic_thickness(d['raw_position_branch'],g['shadow'])
        j,dev=roughness(np.where(invalid,np.nan,d['raw_position_branch']))
        dist=np.full((512,512),np.nan,np.float32);landmark='unknown'
        if g['onh'].any():dist=distance_transform_edt(~g['onh'],sampling=1460/512).astype(np.float32);landmark='distance to annotated mask'
        elif g['onh_edge'].any():dist=distance_transform_edt(~g['onh_edge'],sampling=1460/512).astype(np.float32);landmark='partial-edge proxy'
        save(out/'diagnostics.npz',jump_um=j,spike_um=dev,invalid=invalid,crossing=cross,
             diagnostic_thickness_um=diag,onh_distance_um=dist)
        from octa_seg_v1.decisions import decide
        cal=read(V1/'calibration/deployment_vessels.json')['thresholds']
        matched_auto=np.stack([decide(base['raw_position_branch'][b],base['probabilities'][b],cal,g['vessel'][b])[0] for b in range(512)])
        previous_v2=npz(OUT/'round_000/volumes'/sid/'measurements.npz') if learned else d
        pilot=PILOT/'volumes'/sid/'measurements.npz';historical=npz(pilot) if pilot.exists() else None
        for k,name in enumerate(SURFACE_NAMES):
            solid=np.isfinite(d['reported_positions'][:,k]);dash=np.isfinite(d['uncertain_estimates'][:,k])
            boundary.append(dict(scan_id=sid,boundary=name,solid_fraction=solid.mean(),dashed_fraction=dash.mean(),withheld_fraction=(~solid&~dash).mean(),
                invalid_fraction=invalid[:,k].mean(),entropy_mean=stats(d['entropy'][:,k])['mean'],entropy_p95=stats(d['entropy'][:,k])['p95'],
                adjacent_crossing_fraction=float(cross[:,max(0,k-1):min(7,k+1)].mean()),
                neural_candidate_fraction=(d['candidate_source'][:,k]==2).mean(),registered_candidate_fraction=(d['candidate_source'][:,k]==1).mean(),
                **warnings(j[:,k],dev[:,k])))
            comparisons.append(dict(scan_id=sid,boundary=name,matched_v1_solid_fraction=np.isfinite(base['reported_positions'][:,k]).mean(),
                v2_solid_fraction=solid.mean(),position_change_median_px=float(np.nanmedian(np.abs(d['raw_position_branch'][:,k]-base['raw_position_branch'][:,k]))),learned_change=learned,footprint_changed=p['footprint_changed_from_pilot']))
            matched=float(np.isfinite(matched_auto[:,k]).mean());guarded=float(np.isfinite(base['reported_positions'][:,k]).mean());old=float(np.isfinite(historical['reported_positions'][:,k]).mean()) if historical is not None else None
            effects.append(dict(scan_id=sid,boundary=name,historical_pilot_solid_fraction=old,matched_footprint_v1_automatic_fraction=matched,
                matched_footprint_v1_with_original_guards_fraction=guarded,v2_solid_fraction=float(solid.mean()),
                footprint_effect_percentage_points=100*(matched-old) if old is not None else None,
                original_guard_effect_percentage_points=100*(guarded-matched),policy_effect_percentage_points=100*(np.isfinite(previous_v2['reported_positions'][:,k]).mean()-guarded),
                learned_change_percentage_points=100*(float(solid.mean())-np.isfinite(previous_v2['reported_positions'][:,k]).mean())))
        for k,name in enumerate(d['thickness_names']):
            for kind,maps in [('reported',d['primary_thickness_um']),('raw_diagnostic',diag)]:
                tj,td=roughness(maps[:,k],scale=1)
                thick.append(dict(scan_id=sid,layer=str(name),kind=kind,finite_fraction=np.isfinite(maps[:,k]).mean(),
                    thickness_jump_p95_um=stats(tj)['p95'],thickness_local_deviation_p95_um=stats(td)['p95'],**stats(maps[:,k])))
        # Three tiles per scan: independent random assessment, targeted fitting, good-signal fitting.
        selected=select_strips(sid,d['entropy'],dev,20260910+si)
        chosen=[dict(selected[0],data_role='assessment'),dict(selected[2],data_role='training')]
        # Good-signal approval target, spatially separated from assessment row.
        good=[(float(np.nanmedian(g['local_cnr'][b,lo:lo+64])),b,lo) for b in range(16,512,32) for lo in range(0,512,64) if abs(b-chosen[0]['bscan'])>=24]
        _,b,lo=max(good);chosen.append(dict(scan_id=sid,bscan=b,lo=lo,hi=lo+64,role='good_signal',driver='signal',data_role='training'))
        for q in chosen:queue.append(dict(q,id=f'{sid}_b{q["bscan"]}_a{q["lo"]}',round_id=str(ROUND.relative_to(OUT))))
        signal.append(dict(p['acquisition'],onh_distance_definition=landmark,local_cnr_median=stats(g['local_cnr'])['median'],low_signal_fraction=g['low_signal'].mean(),
           vessel_fraction=g['vessel'].mean(),vessel_status=p['footprints']['status'],cnv_fraction=g['cnv'].mean()))
    table(ROUND/'reports/boundaries.csv',boundary);table(ROUND/'reports/thickness.csv',thick);table(ROUND/'reports/policy_comparison.csv',comparisons);table(ROUND/'reports/acquisition_context.csv',signal)
    table(ROUND/'reports/effect_decomposition.csv',effects)
    write(ROUND/'review_queue.json',dict(examples=queue,estimated_review_minutes='20–30; stop by 60',
        data_roles='random assessment B-scans are excluded wholesale from subsequent fitting/calibration; free browsing is training by default'))
    write(ROUND/'reports/human_assessment.json',dict(status='pending explicit v2 feedback',false_solid_reporting=None,good_retention=None,candidate_approval_rate=None,candidate_correction_rate=None,review_seconds=None,
        reason='No v2 user evidence yet; pilot Good/Bad and volume praise are not boundary labels'))
    print('Reports and 30-example queue complete',flush=True)

if __name__=='__main__':run()
