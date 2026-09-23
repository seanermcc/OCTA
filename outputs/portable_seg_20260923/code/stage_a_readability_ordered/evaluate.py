"""Dev comparison with explicit denominators, NaN measurements and raw controls."""
from collections import defaultdict
import json
import numpy as np
from stage_a.common import output_dir, write_json, write_csv, fingerprint
from .experiment import RUN, GRID, scores, read_npz
from .ordered import decode_ordered, gated_raw, crossing_flags, intervals, REASONS
from stage_a.inference import thickness
from stage_a.geometry import to_disk_rows
from stage_a.metrics import longest_run
from eight_surface.config import SURFACE_NAMES, LAYER_DEFS


def ratio(a,b):
    return float(a/b) if b else None


def summarize(items):
    """B-scan items; never connect runs across images/surfaces."""
    n_valid=sum(int(t['valid'].sum()) for _,t,p,keep in items)
    n_scored=sum(int((t['valid']&p['retained']&np.isfinite(p['rows'])).sum()) for _,t,p,keep in items)
    n_neg=sum(int(t['human_excluded'].sum()) for _,t,p,keep in items)
    n_pos=sum(int((t['readability_target']==1).sum()) for _,t,p,keep in items)
    errors=[]; longest=0; gross_n=0
    for r,t,p,keep in items:
        scored=t['valid']&p['retained']&np.isfinite(p['rows'])
        delta=abs(p['rows']-t['truth'])*r['px_um']
        errors.extend(delta[scored].tolist()); gross=scored&(delta>25)
        gross_n+=int(gross.sum()); longest=max(longest,max(longest_run(m) for m in gross))
    errors=np.asarray(errors)
    return dict(bscans=len(items), eligible_bscans=sum(int(t['valid'].any()) for _,t,_,_ in items),
        total_columns=sum(len(keep) for _,_,_,keep in items),
        readable_proxy_columns=n_pos,
        readable_gate_kept=sum(int(((t['readability_target']==1)&keep).sum()) for _,t,p,keep in items),
        readable_gate_coverage=ratio(sum(int(((t['readability_target']==1)&keep).sum()) for _,t,p,keep in items),n_pos),
        readable_all8_measured=sum(int(((t['readability_target']==1)&p['retained'].all(0)).sum()) for _,t,p,keep in items),
        readable_all8_coverage=ratio(sum(int(((t['readability_target']==1)&p['retained'].all(0)).sum()) for _,t,p,keep in items),n_pos),
        supported_surface_columns=n_valid, supported_measured=n_scored, supported_coverage=ratio(n_scored,n_valid),
        unreadable_columns=n_neg, unreadable_surface_denominator=8*n_neg,
        unreadable_surface_measured=sum(int(p['retained'][:,t['human_excluded']].sum()) for _,t,p,keep in items),
        unreadable_leakage=ratio(sum(int(p['retained'][:,t['human_excluded']].sum()) for _,t,p,keep in items),8*n_neg),
        unreadable_any_measured=sum(int((t['human_excluded']&p['retained'].any(0)).sum()) for _,t,p,keep in items),
        unreadable_all8_measured=sum(int((t['human_excluded']&p['retained'].all(0)).sum()) for _,t,p,keep in items),
        unknown_columns=sum(int((t['readability_target']<0).sum()) for _,t,p,keep in items),
        unknown_surface_measured=sum(int(p['retained'][:,t['readability_target']<0].sum()) for _,t,p,keep in items),
        boundary_median_um=float(np.median(errors)) if len(errors) else None,
        boundary_p95_um=float(np.quantile(errors,.95)) if len(errors) else None,
        boundary_gross_n=gross_n, boundary_gross_fraction=ratio(gross_n,n_scored),
        failure_or_withheld_fraction=ratio(n_valid-n_scored+gross_n,n_valid),
        worst_retained_gross_run=longest,
        raw_crossing_boundary_columns=sum(int(crossing_flags(t['raw_rows']).sum()) for _,t,p,keep in items),
        measured_crossing_boundary_columns=sum(int(crossing_flags(p['retained_rows']).sum()) for _,t,p,keep in items),
        total_boundary_columns=sum(t['raw_rows'].size for _,t,p,keep in items),
        retained_boundary_columns=sum(int(p['retained'].sum()) for _,t,p,keep in items))


def detailed(items, method):
    accum=defaultdict(list); per=[]
    for r,t,p,keep in items:
        pred_bands=thickness(p['retained_rows'],p['retained'],r['px_um'])
        truth_bands=thickness(t['truth'],t['valid'],r['px_um'])
        parts=[('boundary',name,(p['rows'][k]-t['truth'][k])*r['px_um'],t['valid'][k],p['retained'][k])
               for k,name in enumerate(SURFACE_NAMES)]
        for name,top,bottom in LAYER_DEFS:
            i,j=SURFACE_NAMES.index(top),SURFACE_NAMES.index(bottom)
            v=t['valid'][i]&t['valid'][j]&np.isfinite(truth_bands[name])
            parts.append(('thickness',name,pred_bands[name]-truth_bands[name],v,np.isfinite(pred_bands[name])))
        for kind,name,delta,valid,kept in parts:
            present=valid&kept&np.isfinite(delta); gross=present&(abs(delta)>25)
            runs=intervals(gross); worst=max(runs,key=lambda v:v[1]-v[0],default=(0,0))
            errors=np.asarray(delta[present],float)
            entry=dict(method=method,key=r['key'],animal=r['animal'],qc_group=r['qc_group'],kind=kind,name=name,
                n_eligible=int(valid.sum()),n_retained=int(present.sum()),n_gross=int(gross.sum()),
                median_abs_um=float(np.median(abs(errors))) if len(errors) else None,
                p95_abs_um=float(np.quantile(abs(errors),.95)) if len(errors) else None,
                worst_run=worst[1]-worst[0],run_start=worst[0],run_end_exclusive=worst[1])
            per.append(entry)
            for axis,group in [('pooled','all'),('animal',r['animal']),('qc',r['qc_group']),
                               ('biology',r['biological_group']),('scope',r['scope_status'])]:
                accum[axis,group,kind,name].append((errors,int(valid.sum()),int(present.sum()),int(gross.sum()),worst[1]-worst[0]))
    summary=[]
    for (axis,group,kind,name),parts in sorted(accum.items()):
        delta=np.concatenate([p[0] for p in parts]); n=sum(p[1] for p in parts); nr=sum(p[2] for p in parts); ng=sum(p[3] for p in parts)
        summary.append(dict(method=method,axis=axis,group=group,kind=kind,name=name,n_eligible=n,n_retained=nr,
            n_gross=ng,coverage=ratio(nr,n),median_abs_um=float(np.median(abs(delta))) if nr else None,
            p95_abs_um=float(np.quantile(abs(delta),.95)) if nr else None,
            mean_signed_um=float(np.mean(delta)) if nr else None,gross_fraction=ratio(ng,nr),
            gross_fraction_of_eligible=ratio(ng,n),failure_or_withheld_fraction=ratio(n-nr+ng,n),
            worst_run=max(p[4] for p in parts)))
    return summary,per


def check_measurement(r,t,p):
    if not np.array_equal(p['retained'],p['reason_bits']==0): raise AssertionError('Reason/retention mismatch')
    if not np.isnan(p['retained_rows'][~p['retained']]).all(): raise AssertionError('Missing NaN gap')
    if (p['retained'][:,~t['scope']|t['shadow']]).any(): raise AssertionError('Scope or shadow rescued')
    bands=thickness(p['retained_rows'],p['retained'],r['px_um'])
    for name,top,bottom in LAYER_DEFS:
        i,j=SURFACE_NAMES.index(top),SURFACE_NAMES.index(bottom)
        legal=p['retained'][i]&p['retained'][j]&np.isfinite(p['rows'][i])&np.isfinite(p['rows'][j])&(p['rows'][j]>=p['rows'][i])
        if not np.array_equal(np.isfinite(bands[name]),legal): raise AssertionError('Thickness support mismatch')
    disk=to_disk_rows(p['retained_rows'],t['x'].shape[1],bool(t['vitreous_high']))
    restored=to_disk_rows(disk,t['x'].shape[1],bool(t['vitreous_high']))
    if not np.allclose(restored,p['retained_rows'],atol=4e-5,equal_nan=True): raise AssertionError('Native geometry mismatch')
    return bands,disk


def run():
    if (RUN/'evaluation_complete.json').exists(): raise FileExistsError('Completed evaluation preserved')
    prepared=json.loads((RUN/'prepared.json').read_text()); plan=json.loads((RUN/'PRESPECIFIED_PLAN.json').read_text())
    values=scores(prepared,plan)
    train=[r for r in prepared['records'] if r['split']=='train']
    validation=[r for r in prepared['records'] if r['split']=='validation']
    thresholds={}
    for method in ('learned','simple'):
        positive=np.concatenate([values[r['key']][method][values[r['key']]['data']['readability_target']==1] for r in train])
        thresholds[method]={str(q):float(np.quantile(positive,q)) for q in GRID}
    write_json(RUN/'exploratory_thresholds.json',dict(thresholds=thresholds,
        note='Training proxy quantiles. Saved for reproducibility only, not an inference default.',experimental=True,validated=False))
    main=defaultdict(list); curve=defaultdict(list); changes=[]; partial=[]; reasons=[]
    for index,r in enumerate(validation):
        v=values[r['key']]; t=v['data']; raw=t['raw_rows']; scope=t['scope']; shadow=t['shadow']
        logits=np.load(RUN/'logits_validation'/(r['key']+'.npy'),allow_pickle=False)
        allkeep=np.ones(raw.shape[1],bool)
        baseline=gated_raw(raw,scope,shadow)
        main['epoch124_existing'].append((r,t,baseline,allkeep))
        rawdiag=dict(rows=raw,retained=np.isfinite(raw),retained_rows=raw,reason_bits=np.zeros_like(raw,dtype=np.uint16),decoder_displacement_px=np.zeros_like(raw))
        main['raw_diagnostic'].append((r,t,rawdiag,allkeep))
        ordered=decode_ordered(logits,raw,t['entropy'],scope,shadow,plan['decoder'])
        main['ordered_only'].append((r,t,ordered,allkeep))
        # Same final ordered support, old raw boundary locations: isolates the
        # decoder's selected columns from its boundary-location changes.
        support_raw={**baseline,'retained':baseline['retained']&ordered['retained']}
        support_raw['retained_rows']=np.where(support_raw['retained'],raw,np.nan)
        support_raw['reason_bits']=baseline['reason_bits']|ordered['reason_bits']
        main['decoder_support_raw'].append((r,t,support_raw,allkeep))
        saved={'epoch124_existing':baseline,'ordered_only':ordered,'decoder_support_raw':support_raw}
        for method in ('learned','simple'):
            for q in GRID:
                keep=v[method]<=thresholds[method][str(q)]
                gated=gated_raw(raw,scope,shadow,keep,'readability' if method=='learned' else 'simple_entropy_signal')
                dec=decode_ordered(logits,raw,t['entropy'],scope,shadow,plan['decoder'],keep)
                if method=='simple':
                    bits=dec['reason_bits']; flagged=(bits&REASONS['readability'])!=0
                    bits[flagged]=(bits[flagged]&np.uint16(65535-REASONS['readability']))|REASONS['simple_entropy_signal']
                curve[method,q,False].append((r,t,gated,keep))
                curve[method,q,True].append((r,t,dec,keep))
                if q==plan['display_coverage']:
                    name='readability_only' if method=='learned' else 'simple_rule'
                    both='readability_ordered' if method=='learned' else 'simple_ordered'
                    main[name].append((r,t,gated,keep)); main[both].append((r,t,dec,keep))
                    saved[name]=gated; saved[both]=dec
        keep=v['learned']<=thresholds['learned'][str(plan['display_coverage'])]
        combined=saved['readability_ordered']
        common=t['valid']&baseline['retained']&combined['retained']
        displacement=abs(combined['rows']-raw)
        raw_error=abs(raw-t['truth'])*r['px_um']; new_error=abs(combined['rows']-t['truth'])*r['px_um']
        for category,mask in [('outside_readability_rejection',np.broadcast_to(keep,raw.shape)),
                              ('inside_readability_rejection',np.broadcast_to(~keep,raw.shape))]:
            selected=mask&common
            changes.append(dict(key=r['key'],category=category,common_supported=int(selected.sum()),
                boundary_changes_gt1px=int((selected&(displacement>1)).sum()),
                boundary_improved_gt1um=int((selected&(new_error<raw_error-1)).sum()),
                boundary_worsened_gt1um=int((selected&(new_error>raw_error+1)).sum()),
                raw_absolute_error_sum=float(raw_error[selected].sum()),decoded_absolute_error_sum=float(new_error[selected].sum()),
                displacement_sum_px=float(displacement[selected].sum())))
        lost=t['valid']&baseline['retained']&~combined['retained']
        for k,name in enumerate(SURFACE_NAMES):
            # Proxy for useful loss, based solely on manually eligible positions.
            useful=lost[k]&(raw_error[k]<=5)
            partial.append(dict(key=r['key'],animal=r['animal'],surface=name,supported_lost=int(lost[k].sum()),
                useful_le5um_lost=int(useful.sum()),due_readability=int((useful&~keep).sum()),
                due_deeper_entropy_only=int((useful&keep&(t['entropy'][k]<=plan['decoder']['entropy_cap'][k])
                    &(t['entropy']>np.asarray(plan['decoder']['entropy_cap'])[:,None]).any(0)).sum()),
                manually_unreadable=int(t['human_excluded'].sum()),
                human_eligible_in_exclusion=int((t['valid'][k]&t['human_excluded']).sum())))
        for method,p in saved.items():
            bands,disk=check_measurement(r,t,p)
            output_dir(RUN/'measurements'/method)
            np.savez_compressed(RUN/'measurements'/method/(r['key']+'.npz'),raw_canonical_rows=raw,
                canonical_decoded_rows=p['rows'],canonical_retained_rows=p['retained_rows'],disk_retained_rows=disk,
                raw_entropy=t['entropy'],readability_score=1.-v['learned'],simple_score=v['simple'],
                human_excluded=t['human_excluded'],readability_target=t['readability_target'],
                scope=scope,shadow=shadow,reason_bits=p['reason_bits'],retained=p['retained'],
                decoder_displacement_px=p['decoder_displacement_px'],
                experimental_thickness_um=np.stack(list(bands.values())),thickness_names=np.array(list(bands)),
                validated_thickness_um=np.full((len(bands),raw.shape[1]),np.nan,np.float32),
                experimental=np.array(True),validated=np.array(False),surface_names=np.array(SURFACE_NAMES))
            reasons.append(dict(method=method,key=r['key'],**{name:int(((p['reason_bits']&bit)!=0).sum()) for name,bit in REASONS.items()}))
        print(f'evaluate {index+1}/{len(validation)} {r["key"]}',flush=True)
    summaries=[]; details=[]; per=[]; strata=[]; bscans=[]
    for method,items in main.items():
        summaries.append(dict(method=method,**summarize(items)))
        detail,scan_detail=detailed(items,method); details.extend(detail); per.extend(scan_detail)
        for item in items:
            bscans.append(dict(method=method,key=item[0]['key'],animal=item[0]['animal'],**summarize([item])))
        for axis,field in [('animal','animal'),('qc','qc_group'),('biology','biological_group'),('scope','scope_status')]:
            for group in sorted({r[field] for r,t,p,keep in items}):
                strata.append(dict(method=method,axis=axis,group=group,**summarize([i for i in items if i[0][field]==group])))
    curves=[dict(method=m,ordered=o,train_target_coverage=q,threshold=thresholds[m][str(q)],**summarize(items)) for (m,q,o),items in sorted(curve.items())]
    matched=[]
    for covaxis in ('readable_gate_coverage','supported_coverage','readable_all8_coverage'):
        for target in (.95,.90,.85,.80):
            for method in ('learned','simple'):
                for ordered_flag in (False,True):
                    best=min([c for c in curves if c['method']==method and c['ordered']==ordered_flag],key=lambda c:abs(c[covaxis]-target))
                    matched.append(dict(match_axis=covaxis,target_coverage=target,absolute_mismatch=abs(best[covaxis]-target),**best))
    write_csv(RUN/'comparison_summary.csv',summaries); write_csv(RUN/'boundary_thickness_by_stratum.csv',details)
    write_csv(RUN/'per_bscan_surface_and_thickness.csv',per); write_csv(RUN/'per_bscan_summary.csv',bscans)
    write_csv(RUN/'comparison_by_stratum.csv',strata); write_csv(RUN/'coverage_error_curves.csv',curves)
    write_csv(RUN/'matched_coverage.csv',matched); write_csv(RUN/'changes_outside_readability_mask.csv',changes)
    write_csv(RUN/'partial_visibility_loss.csv',partial); write_csv(RUN/'exclusion_reason_counts.csv',reasons)
    write_json(RUN/'evaluation_complete.json',dict(validation_decisions=len(validation),eligible_bscans=sum(r['eligible'] for r in validation),
        validation_animals=sorted({r['animal'] for r in validation}),corrected_validation_animals=sorted({r['animal'] for r in validation if r['eligible']}),
        main_methods=list(main),grid_points=len(curves),measurement_files=len(reasons),reason_definitions=REASONS,
        original_boundary_changes=0,experimental=True,validated=False,all_measurement_geometry_checks_pass=True,
        support_reference='frozen manual boundary eligibility; legacy surface-wide approximation',
        threshold_selection='training only; matched-coverage rows chosen descriptively on validation, not deployed',
        checkpoint=fingerprint(RUN/'head_best.pt')))


if __name__=='__main__': run()
