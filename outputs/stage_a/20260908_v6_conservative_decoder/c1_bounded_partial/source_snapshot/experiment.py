"""Checkpointed conservative iterations, evaluated only against development labels."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time
import numpy as np
from stage_a.common import OUT, write_json, write_csv, output_dir, fingerprint, verify, digest
from stage_a_readability_ordered.evaluate import summarize, detailed, check_measurement
from stage_a_readability_ordered.ordered import gated_raw
from .decoder import decode, REASONS

RUN=OUT/'stage_a/20260908_v6_conservative_decoder'
PREVIOUS=OUT/'stage_a/20260908_v5_readability_ordered'
DATA=OUT/'stage_a/20260908_v2'
FOCUS=['TS325_OD_2026-03-03_D98_s01_131308_b0061','TS325_OD_2026-05-26_6mo_s01_112940_b0510',
       'TS169_OS_2025-01-14_D35_s04_121533_b0164','TS325_OD_2026-01-05_D42_s05_131602_b0023',
       'TS325_OD_2026-01-05_D42_s05_131602_b0508']


def load(path):
    with np.load(path,allow_pickle=False) as d: return {k:d[k] for k in d.files}


def inventory():
    roots=[OUT/'stage_a'/name for name in ('20260908_v2','20260908_v3_readability','20260908_v4_longtrain','20260908_v5_readability_ordered')]
    return {str(p):[p.stat().st_size,p.stat().st_mtime_ns] for root in roots for p in root.rglob('*') if p.is_file()}


def prepare():
    output_dir(RUN)
    if (RUN/'plan.json').exists(): raise FileExistsError('Plan already frozen')
    old=json.loads((PREVIOUS/'prepared.json').read_text())
    # Only frozen derived train/validation arrays are read. Original labels are
    # verified, not reconstructed, rewritten, or treated as local visibility.
    protected=json.loads((PREVIOUS/'protected_fingerprints.json').read_text())
    for fp in protected: verify(fp)
    slopes=[[] for _ in range(8)]; ent=[[] for _ in range(8)]
    for r in old['records']:
        path=PREVIOUS/'cache'/(r['key']+'.npz')
        protected.append(fingerprint(path))
        if r['split']=='validation':
            protected.append(fingerprint(PREVIOUS/'logits_validation'/(r['key']+'.npy')))
            continue
        t=load(path)
        for k in range(8):
            v=t['valid'][k]
            slopes[k].extend(abs(np.diff(t['truth'][k]))[v[1:]&v[:-1]].tolist())
            ent[k].extend(t['entropy'][k,v].tolist())
    measured=[]
    for k in range(8):
        measured.append(dict(surface=k,
            n_adjacent=len(slopes[k]),manual_slope_p99=float(np.quantile(slopes[k],.99)),
            manual_slope_p999=float(np.quantile(slopes[k],.999)),manual_slope_max=float(np.max(slopes[k])),
            entropy_n=len(ent[k]),entropy_p995=float(np.quantile(ent[k],.995)),
            entropy_p99=float(np.quantile(ent[k],.99)),entropy_p985=float(np.quantile(ent[k],.985))))
    from eight_surface.config import SURFACE_NAMES
    for k,row in enumerate(measured): row['surface']=SURFACE_NAMES[k]
    steps=np.maximum(6.,2*np.array([m['manual_slope_p999'] for m in measured]))
    common=dict(max_log_drop=float(np.log(20)),continuity_weight=.15,jump_guard_radius=1,max_guard_iterations=8)
    stages=[dict(name='c1_bounded_partial',parent=None,gate_quantile=None,max_displacement_px=3.,
        min_interval_columns=6,entropy_cap=[m['entropy_p995'] for m in measured],max_step_px=steps.tolist(),**common),
        dict(name='c2_tighter_signal',parent='c1_bounded_partial',gate_quantile=.98,max_displacement_px=2.,
        min_interval_columns=8,entropy_cap=[m['entropy_p99'] for m in measured],max_step_px=np.maximum(4.,steps*.75).tolist(),**common),
        dict(name='c3_strict_signal',parent='c2_tighter_signal',gate_quantile=.95,max_displacement_px=1.5,
        min_interval_columns=16,entropy_cap=[m['entropy_p985'] for m in measured],max_step_px=np.maximum(3.,steps*.5).tolist(),**common)]
    plan=dict(created='2026-09-08',records=old['records'],identity=old['identity'],
        stages=stages,source_checkpoint=old['checkpoint'],training_updates=0,
        source_raw_predictions='unchanged epoch-124 model, v5 exact-reproduction cache',
        original_withholding='scope, shadow, missing, original crossing never rescued; parent masks only shrink',
        ground_truth='frozen eligible manual layer segmentations only; no published/classical layer truth',
        geometry='canonical native coordinates, ordered retained subset; no normal thickness bounds',
        exploration_note='Validation animals have been seen in prior work. Iterative development, not independent calibration.',
        iteration_rule='Checkpoint and inspect each stage. If criteria fail, run the next stricter version. '
            'After c3, continue only if a specific observable failure offers a defensible correction; '
            'do not keep rejecting tissue merely to improve conditional errors.',
        good_dev_criteria=dict(supported_coverage_min=.80,each_corrected_animal_coverage_min=.80,
            focus_readable_control_coverage_min=.90,unreadable_leakage_max=.05,boundary_gross_fraction_max=.005,
            worst_retained_gross_run_max=8,boundary_max_um_max=50.,crossings=0),
        focus=FOCUS,experimental=True,validated=False)
    write_csv(RUN/'manual_training_measurements.csv',measured)
    write_json(RUN/'plan.json',plan)
    write_json(RUN/'protected_fingerprints.json',protected)
    write_json(RUN/'old_inventory.json',inventory())
    write_json(RUN/'preparation_checkpoint.json',dict(plan=fingerprint(RUN/'plan.json'),protected_count=len(protected),
        original_checkpoint_unchanged=True,final_test_data_read=False,repeatability_data_read=False))


def extra(items):
    errors=[]; jumps=[]; retained=0; unavailable=[]
    for r,t,p,keep in items:
        valid=t['valid']&p['retained']
        errors.extend((abs(p['rows']-t['truth'])*r['px_um'])[valid].tolist())
        for k in range(8):
            both=p['retained'][k,1:]&p['retained'][k,:-1]
            jumps.extend(abs(np.diff(p['rows'][k]))[both].tolist())
        retained+=int(p['retained'].sum())
        if r['eligible'] and not valid.any(): unavailable.append(r['key'])
    return dict(boundary_max_um=float(max(errors)) if errors else None,
        retained_errors_gt50um=sum(e>50 for e in errors),retained_errors_gt100um=sum(e>100 for e in errors),
        maximum_retained_adjacent_jump_px=float(max(jumps)) if jumps else None,
        eligible_bscans_completely_withheld=unavailable)


def saved_prediction(path):
    d=load(path)
    return dict(rows=d['canonical_decoded_rows'],retained_rows=d['canonical_retained_rows'],
        retained=d['retained'],reason_bits=d['reason_bits'],decoder_displacement_px=d['decoder_displacement_px'])


def run_stage(name):
    plan=json.loads((RUN/'plan.json').read_text()); stage=next(s for s in plan['stages'] if s['name']==name)
    stage_dir=output_dir(RUN/name)
    if (stage_dir/'checkpoint.json').exists(): raise FileExistsError('Completed decoder checkpoint preserved')
    if stage['parent'] and not (RUN/stage['parent']/'checkpoint.json').exists(): raise FileNotFoundError('Run parent first')
    output_dir(stage_dir/'measurements'); output_dir(stage_dir/'source_snapshot')
    sources=[]
    for p in Path(__file__).parent.glob('*.py'):
        copied=stage_dir/'source_snapshot'/p.name
        copied.write_text(p.read_text(encoding='utf-8'),encoding='utf-8'); sources.append(fingerprint(copied))
    # Settings are written before evaluating this stage, including adaptive stages.
    write_json(stage_dir/'configuration.json',stage)
    simple_quantiles=json.loads((PREVIOUS/'exploratory_thresholds.json').read_text())['thresholds']['simple']
    mu=np.array(json.loads((PREVIOUS/'PRESPECIFIED_PLAN.json').read_text())['simple_mean'])
    sd=np.array(json.loads((PREVIOUS/'PRESPECIFIED_PLAN.json').read_text())['simple_sd'])
    items=[]; base_items=[]; bscans=[]; reasons=[]; loss_rows=[]; paired=[]
    start=time.monotonic()
    val=[r for r in plan['records'] if r['split']=='validation']
    for index,r in enumerate(val):
        t=load(PREVIOUS/'cache'/(r['key']+'.npz'))
        logits=np.load(PREVIOUS/'logits_validation'/(r['key']+'.npy'),allow_pickle=False)
        base=gated_raw(t['raw_rows'],t['scope'],t['shadow'])
        parent=saved_prediction(RUN/stage['parent']/'measurements'/(r['key']+'.npz')) if stage['parent'] else None
        z=(t['simple_features']-mu)/sd; simple=z[:,0]+z[:,1]-z[:,2]+z[:,3]
        gate=np.ones(logits.shape[-1],bool) if stage['gate_quantile'] is None else simple<=simple_quantiles[str(stage['gate_quantile'])]
        p=decode(logits,t['raw_rows'],t['entropy'],t['scope'],t['shadow'],stage,gate,parent)
        bands,disk=check_measurement(r,t,p)
        if (p['retained']&~base['retained']).any(): raise AssertionError('Original crossing rescue')
        if parent and (p['retained']&~parent['retained']).any(): raise AssertionError('Non-monotone masks')
        items.append((r,t,p,gate)); base_items.append((r,t,base,np.ones(len(gate),bool)))
        row=dict(key=r['key'],animal=r['animal'],qc_group=r['qc_group'],**summarize([items[-1]]),**extra([items[-1]]))
        bscans.append(row)
        np.savez_compressed(stage_dir/'measurements'/(r['key']+'.npz'),raw_canonical_rows=t['raw_rows'],
            canonical_decoded_rows=p['rows'],canonical_retained_rows=p['retained_rows'],disk_retained_rows=disk,
            retained=p['retained'],reason_bits=p['reason_bits'],raw_entropy=t['entropy'],simple_score=simple,
            human_excluded=t['human_excluded'],scope=t['scope'],shadow=t['shadow'],
            decoder_displacement_px=p['decoder_displacement_px'],experimental_thickness_um=np.stack(list(bands.values())),
            thickness_names=np.array(list(bands)),validated_thickness_um=np.full((len(bands),len(gate)),np.nan,np.float32),
            experimental=np.array(True),validated=np.array(False),configuration_id=np.array(digest(stage)))
        reasons.append(dict(key=r['key'],**{key:int(((p['reason_bits']&bit)!=0).sum()) for key,bit in REASONS.items()}))
        e0=abs(base['rows']-t['truth'])*r['px_um']; e1=abs(p['rows']-t['truth'])*r['px_um']
        common=t['valid']&base['retained']&p['retained']
        for k in range(8):
            lost=t['valid'][k]&base['retained'][k]&~p['retained'][k]
            loss_rows.append(dict(key=r['key'],surface=k,lost_supported=int(lost.sum()),
                lost_within5um=int((lost&(e0[k]<=5)).sum()),lost_gross=int((lost&(e0[k]>25)).sum())))
        paired.append(dict(key=r['key'],n_common=int(common.sum()),raw_error_sum=float(e0[common].sum()),
            decoded_error_sum=float(e1[common].sum()),raw_gross=int((e0[common]>25).sum()),decoded_gross=int((e1[common]>25).sum()),
            improved_gt1um=int((e1[common]<e0[common]-1).sum()),worsened_gt1um=int((e1[common]>e0[common]+1).sum())))
        print(f'{name} {index+1}/{len(val)} {r["key"]}',flush=True)
    overview={**summarize(items),**extra(items)}
    by=[]
    for axis,field in [('animal','animal'),('qc','qc_group'),('biology','biological_group'),('scope','scope_status')]:
        for group in sorted({r[field] for r in val}):
            subset=[i for i in items if i[0][field]==group]
            by.append(dict(axis=axis,group=group,**summarize(subset),**extra(subset)))
    detailed_summary,detail=detailed(items,name)
    criteria=plan['good_dev_criteria']
    tests=dict(supported_coverage=overview['supported_coverage']>=criteria['supported_coverage_min'],
        each_corrected_animal_coverage=all(s['supported_coverage']>=criteria['each_corrected_animal_coverage_min'] for s in by if s['axis']=='animal' and s['supported_surface_columns']),
        readable_controls=all(b['supported_coverage']>=criteria['focus_readable_control_coverage_min'] for b in bscans if b['key'] in FOCUS[2:4]),
        leakage=overview['unreadable_leakage']<=criteria['unreadable_leakage_max'],
        gross_fraction=overview['boundary_gross_fraction']<=criteria['boundary_gross_fraction_max'],
        worst_run=overview['worst_retained_gross_run']<=criteria['worst_retained_gross_run_max'],
        maximum_error=overview['boundary_max_um']<=criteria['boundary_max_um_max'],
        no_crossings=overview['measured_crossing_boundary_columns']==0)
    write_json(stage_dir/'summary.json',overview)
    write_csv(stage_dir/'per_bscan.csv',bscans); write_csv(stage_dir/'by_stratum.csv',by)
    write_csv(stage_dir/'boundary_thickness_metrics.csv',detailed_summary); write_csv(stage_dir/'per_surface_bscan.csv',detail)
    write_csv(stage_dir/'reasons.csv',reasons); write_csv(stage_dir/'useful_tissue_lost.csv',loss_rows)
    write_csv(stage_dir/'common_support_pairs.csv',paired)
    write_json(stage_dir/'decision.json',dict(criteria=criteria,checks=tests,all_pass=all(tests.values()),
        automatic_promotion=False,next='inspect overlays and checkpoint; continue next prespecified stricter version if useful'))
    write_json(stage_dir/'checkpoint.json',dict(configuration=fingerprint(stage_dir/'configuration.json'),
        source_snapshot=sources,source_model=plan['source_checkpoint'],training_updates=0,parent=stage['parent'],
        result=fingerprint(stage_dir/'summary.json'),seconds=time.monotonic()-start,
        measurement_files=len(val),experimental=True,validated=False))
    print(json.dumps(dict(stage=name,summary=overview,checks=tests)),flush=True)


def integrity():
    fps=json.loads((RUN/'protected_fingerprints.json').read_text())
    for fp in fps: verify(fp)
    before=json.loads((RUN/'old_inventory.json').read_text()); after=inventory()
    changed=[p for p,st in before.items() if after.get(p)!=st]
    if changed: raise AssertionError('Prior artifact changed: '+str(changed[:5]))
    checkpoints={}
    for d in RUN.glob('c*'):
        if not (d/'checkpoint.json').exists(): continue
        checkpoint=json.loads((d/'checkpoint.json').read_text())
        for fp in [checkpoint['configuration'],checkpoint['result'],*checkpoint['source_snapshot']]: verify(fp)
        checkpoints[d.name]=len(list((d/'measurements').glob('*.npz')))
    write_json(RUN/'integrity_complete.json',dict(development_fingerprints_verified=len(fps),
        prior_artifacts_metadata_unchanged=len(before),old_roots_added_files=len(set(after)-set(before)),
        checkpoints=checkpoints,human_labels_written=False,locked_contents_read=False,repeatability_data_read=False,
        frozen_dataset_definitions_modified=False,model_training_updates=0))


def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['prepare','run','integrity']); p.add_argument('--stage')
    args=p.parse_args()
    if args.action=='prepare': prepare()
    elif args.action=='run': run_stage(args.stage)
    else: integrity()


if __name__=='__main__': main()
