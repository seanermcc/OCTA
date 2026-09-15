"""Comparative tables, residual-error diagnostics and a proposal-only review queue."""
import json
import numpy as np
from stage_a.common import OUT, read_csv, write_csv, write_json, output_dir
from eight_surface.config import SURFACE_NAMES
from stage_a_readability_ordered.review import read_npz, intervals

RUN=OUT/'stage_a/20260908_v6_conservative_decoder'
OLD=OUT/'stage_a/20260908_v5_readability_ordered'


def run():
    plan=json.loads((RUN/'plan.json').read_text())
    stages=[s['name'] for s in plan['stages'] if (RUN/s['name']/'checkpoint.json').exists()]
    val=[r for r in plan['records'] if r['split']=='validation']
    old=read_csv(OLD/'comparison_summary.csv')
    wanted=['epoch124_existing','ordered_only','readability_only','readability_ordered','simple_rule','simple_ordered']
    summaries=[r for r in old if r['method'] in wanted]
    summaries += [dict(method=s,**json.loads((RUN/s/'summary.json').read_text())) for s in stages]
    fields=list(dict.fromkeys(k for row in summaries for k in row))
    write_csv(RUN/'comparison_summary.csv',[{k:r.get(k) for k in fields} for r in summaries])
    curves=read_csv(OLD/'coverage_error_curves.csv'); matches=[]
    for s in stages:
        summary=json.loads((RUN/s/'summary.json').read_text())
        for method in ['simple','learned']:
            for ordered in ['False','True']:
                closest=min([r for r in curves if r['method']==method and r['ordered']==ordered],key=lambda r:abs(float(r['supported_coverage'])-summary['supported_coverage']))
                matches.append(dict(conservative_stage=s,conservative_coverage=summary['supported_coverage'],
                    conservative_p95=summary['boundary_p95_um'],conservative_gross_n=summary['boundary_gross_n'],
                    conservative_leakage=summary['unreadable_leakage'],absolute_coverage_mismatch=abs(float(closest['supported_coverage'])-summary['supported_coverage']),
                    comparison='Descriptive closest point from previously evaluated fixed grid, not exact matching',**closest))
    write_csv(RUN/'approximate_matched_coverage.csv',matches)
    residual=[]; paired=[]; partial=[]; queue=[]
    final=stages[-1]
    for s in stages:
        pair=read_csv(RUN/s/'common_support_pairs.csv'); n=sum(int(r['n_common']) for r in pair)
        raw=sum(float(r['raw_error_sum']) for r in pair); dec=sum(float(r['decoded_error_sum']) for r in pair)
        paired.append(dict(stage=s,n_identical_supported_positions=n,raw_mae_um=raw/n,decoded_mae_um=dec/n,
            change_um=(dec-raw)/n,raw_gross_n=sum(int(r['raw_gross']) for r in pair),decoded_gross_n=sum(int(r['decoded_gross']) for r in pair),
            improved_gt1um=sum(int(r['improved_gt1um']) for r in pair),worsened_gt1um=sum(int(r['worsened_gt1um']) for r in pair)))
        for r in val:
            t=read_npz(OLD/'cache'/(r['key']+'.npz')); p=read_npz(RUN/s/'measurements'/(r['key']+'.npz'))
            v5=read_npz(OLD/'measurements/readability_ordered'/(r['key']+'.npz'))
            rawerr=abs(t['raw_rows']-t['truth'])*r['px_um']; err=abs(p['canonical_retained_rows']-t['truth'])*r['px_um']
            for k,name in enumerate(SURFACE_NAMES):
                gained=t['valid'][k]&p['retained'][k]&~v5['retained'][k]
                useful=gained&(err[k]<=5)
                partial.append(dict(stage=s,key=r['key'],surface=name,supported_added_vs_v5=int(gained.sum()),
                    added_within5um=int(useful.sum()),added_gross=int((gained&(err[k]>25)).sum()),
                    added_partial_column_within5um=int((useful&~p['retained'].all(0)).sum())))
                for a,b in intervals(t['valid'][k]&p['retained'][k]&(err[k]>25)):
                    residual.append(dict(stage=s,key=r['key'],animal=r['animal'],surface=name,start=int(a),end_exclusive=int(b),n=int(b-a),
                        max_error_um=float(err[k,a:b].max()),median_error_um=float(np.median(err[k,a:b])),
                        raw_median_error_um=float(np.median(rawerr[k,a:b])),
                        median_entropy=float(np.median(t['entropy'][k,a:b])),median_simple_score=float(np.median(p['simple_score'][a:b]))))
                if s==final and r['key'] in plan['focus']:
                    categories=[('retained_gross_error',t['valid'][k]&p['retained'][k]&(err[k]>25)),
                        ('accurate_raw_but_withheld',t['valid'][k]&~p['retained'][k]&(rawerr[k]<=5)),
                        ('partial_retention_needs_local_visibility',t['valid'][k]&p['retained'][k]&~p['retained'].all(0))]
                    for category,mask in categories:
                        runs=sorted(intervals(mask),key=lambda ab:ab[1]-ab[0],reverse=True)
                        for a,b in runs[:1]:
                            if b-a<(1 if category=='retained_gross_error' else 12): continue
                            queue.append(dict(key=r['key'],split=r['split'],animal=r['animal'],surface=name,
                                start=int(a),end_exclusive=int(b),reason=category,proposal_only=True,
                                instruction='Inspect image independently; draw visible boundary or explicitly mark locally unidentifiable; leave unreviewed columns unknown.'))
    write_csv(RUN/'paired_location_effect.csv',paired)
    write_csv(RUN/'residual_gross_error_runs.csv',sorted(residual,key=lambda r:(r['stage'],-r['max_error_um'])))
    write_csv(RUN/'partial_surface_recovery_vs_v5.csv',partial)
    # Keep the pilot short and balanced across the five prespecified focus images.
    selected=[]
    for key in plan['focus']:
        rows=[r for r in queue if r['key']==key]
        rows.sort(key=lambda r:({'retained_gross_error':0,'accurate_raw_but_withheld':1,'partial_retention_needs_local_visibility':2}[r['reason']],-(r['end_exclusive']-r['start'])))
        selected.extend(rows[:4])
    # Add two currently accuracy-unscorable development cases, selected by
    # residual model coverage only. A rejected verdict is not a visibility label.
    bscans=read_csv(RUN/final/'per_bscan.csv')
    unscorable=sorted([r for r in bscans if r['animal']=='TS336' and r['supported_surface_columns']=='0'],key=lambda r:int(r['retained_boundary_columns']),reverse=True)
    for r in unscorable[:2]:
        selected.append(dict(key=r['key'],split='validation',animal='TS336',surface='all eight separately',start=0,end_exclusive=512,
            reason='no_eligible_boundary_accuracy_targets',proposal_only=True,
            instruction='Inspect each boundary independently. Rejected B-scan status does not imply all columns are unreadable.'))
    # Training-side positive examples from two additional corrected animals.
    train=[r for r in plan['records'] if r['split']=='train' and r['eligible']]
    animals=sorted({r['animal'] for r in train})[:2]
    for animal in animals:
        r=max([r for r in train if r['animal']==animal],key=lambda r:sum(r['eligible_columns_by_surface']))
        selected.append(dict(key=r['key'],split='train',animal=animal,surface='all eight separately',start=0,end_exclusive=512,
            reason='training_positive_and_local_visibility_control',proposal_only=True,
            instruction='Sample clearly readable intervals and uncertain intervals for every boundary; record local review without inferring strokes from old surface-wide flags.'))
    for j,r in enumerate(selected): r['queue_id']=j+1
    write_csv(RUN/'annotation_queue_proposal.csv',selected)
    write_json(RUN/'analysis_complete.json',dict(stages=stages,annotation_proposal_rows=len(selected),
        annotation_images=len({r['key'] for r in selected}),annotation_animals=sorted({r['animal'] for r in selected}),
        annotation_labels_written=0,thresholds_promoted=0,source_model_retrained=False))


if __name__=='__main__': run()
