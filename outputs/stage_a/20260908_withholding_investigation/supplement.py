"""Bounded signal-rule comparison and representative reviews."""
import argparse
import json
import numpy as np
from investigate import OUT,V2,V3,EVAL,metrics,match_score
import readability_helpers_snapshot as rd
from stage_a.common import write_csv,write_json

D=rd.load_npz(V3/'features/columns.npz')
A=rd.load_npz(OUT/'analysis_arrays.npz')
F=np.where(np.isfinite(D['features']),D['features'],0).astype(float)
fi={str(v):i for i,v in enumerate(D['feature_names'])}
tr=D['split']=='train'; va=D['split']=='validation'; base=D['existing_retained']
Z=(F-F[tr].mean(0))/(F[tr].std(0)+1e-9)
simple=A['simple_score']; simple_ret=A['retained_simple_q0.96']
scores={'cnr_deficit':-Z[:,fi['cnr']], 'low_signal':Z[:,fi['band_lowsig_frac']],
    'low_energy':-Z[:,fi['col_energy_z']], 'weak_gradient':-Z[:,fi['band_grad_p90']],
    'poor_neighbor_correlation':-Z[:,fi['neigh_corr']]}
hn=D['human_negative']; shadow=((A['reason']&2)!=0).any(1)
miss=hn&~shadow
summary=[]; complementary=[]
for name,score in scores.items():
    thr=float(np.quantile(score[tr&D['valid'].all(1)],.96))
    reject=score>thr
    for with_simple in (False,True):
        method=name+('_plus_simple_q0.96' if with_simple else '_q0.96')
        ret=(simple_ret if with_simple else base)&~reject[:,None]
        for split,m in [('train',tr),('validation',va)]:
            own=metrics(ret,D,m)
            matched,mt=match_score(simple,own['supported_retained'],D,m)
            comp=metrics(matched,D,m)
            summary.append(dict(method=method,split=split,threshold=thr,**own,
                matched_simple_count_mismatch=comp['supported_retained']-own['supported_retained'],
                matched_simple_leakage=comp['unreadable_leakage'],
                matched_simple_p95=comp['retained_p95_um'],matched_simple_run=comp['longest_gross_run']))
    for split,m in [('train',tr),('validation',va)]:
        remaining=miss&m&simple_ret.any(1)
        complementary.append(dict(feature=name,split=split,threshold=thr,
            remaining_shadow_misses=int(remaining.sum()),
            caught_additionally=int((remaining&reject).sum()),
            additional_supported_lost=int((D['human_positive']&simple_ret&reject[:,None]&m[:,None]).sum())))
write_csv(OUT/'signal_candidates.csv',summary)
write_csv(OUT/'signal_complementarity.csv',complementary)

# Test whether crossing evidence adds value to the already-promising score.
combined=[]
for name in ('whole_crossing','inversion_span','whole_crossing_count_ge4','whole_crossing_count_ge6'):
    ret=A['retained_'+name]&simple_ret
    for split,m in [('train',tr),('validation',va)]:
        own=metrics(ret,D,m)
        cmpret,thr=match_score(simple,own['supported_retained'],D,m)
        cmp=metrics(cmpret,D,m)
        combined.append(dict(method=name+'_plus_simple_q0.96',split=split,**own,
            matched_simple_count_mismatch=cmp['supported_retained']-own['supported_retained'],
            matched_simple_leakage=cmp['unreadable_leakage'],matched_simple_p95=cmp['retained_p95_um'],
            matched_simple_run=cmp['longest_gross_run']))
write_csv(OUT/'crossing_complementarity.csv',combined)

# Four distinct cases selected by explicit reproducible criteria, not aesthetic choice.
keyidx=D['key_idx']; keys=D['keys'].astype(str)
def pick(mask):
    counts=np.bincount(keyidx,weights=mask,minlength=len(keys))
    return keys[int(counts.argmax())]
cases=[('shadow_miss_caught',pick(va&miss&~simple_ret.any(1)),'simple_q0.96'),
       ('whole_column_supported_loss',pick((D['animal']=='TS169')&(D['human_positive']&base&~A['retained_whole_crossing']).any(1)),'whole_crossing'),
       ('remaining_unreadable',pick(miss&simple_ret.any(1)),'simple_q0.96'),
       ('catastrophic_scan',next(k for k in keys if 'TS325_OD_2026-05-26_6mo_s01_112940_b0510' in k),'whole_crossing_count_ge4')]
rd.V3=OUT  # display output root in this process only; source remains untouched.
splits={}; index=[]
for label,key,method in cases:
    i=int(np.flatnonzero(keys==key)[0]); ix=keyidx==i; sp=str(D['split'][ix][0])
    if sp not in splits: splits[sp]=rd.FrozenSplit(V2,sp)
    so=splits[sp]; rec=next(r for r in so.records if r['key']==key)
    rd.cmd_display(argparse.Namespace(data=V2,split=sp,eval=EVAL[sp],keys=[key],out=OUT,
        raw=False,include_ineligible=True))
    pred,tgt,image,vhi,offset=rd._prepare_overlay_inputs(rec,so,EVAL[sp])
    alt={k:v.copy() for k,v in pred.items()}
    alt['retained']=A['retained_'+method][ix].T
    added=pred['retained']&~alt['retained']
    # This is a hypothetical policy in a review image, not a saved production mask.
    bit=16 if method.startswith('simple') else 8
    alt['reason_bits'][added] |= bit
    path=OUT/'review'/sp/f'{key}__{method}.png'
    rd._draw_overlay(path,image,vhi,offset,alt,tgt,
        f'{key} | {label} | SIMULATED {method}, not adopted', 'measurement',rec['px_um'])
    index.append(dict(case=label,key=key,split=sp,candidate=method,
        baseline_image=str((OUT/'review'/sp/f'{key}__measurement.png').relative_to(OUT)),
        candidate_image=str(path.relative_to(OUT)),
        manual_shadow_misses=int((miss&ix).sum()),
        additional_supported_lost=int((D['human_positive'][ix]&base[ix]&~A['retained_'+method][ix]).sum())))
write_json(OUT/'review/cases.json',index)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
rows=json.loads((OUT/'candidate_metrics.json').read_text())
fig,axs=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
for ax,split in zip(axs,['train','validation']):
    for row in rows:
        if row['group']!='split' or row['value']!=split or row['method'].endswith('ge8'): continue
        x=row['supported_coverage']*100;y=row['unreadable_leakage']*100
        ax.scatter(x,y,s=35)
        label=row['method'].replace('whole_crossing_count_ge','cross >= ').replace('_',' ')
        ax.annotate(label,(x,y),xytext=(3,4),textcoords='offset points',fontsize=7)
    ax.set(xlabel='Human-supported boundary measurements retained (%)',
           ylabel='Manually unreadable measurements retained (%)',title=split.title())
    ax.grid(alpha=.2)
fig.suptitle('Frozen model: coverage cost versus unreadable leakage\nExperimental; two corrected validation animals',fontsize=11)
fig.savefig(OUT/'coverage_tradeoff.png',dpi=150)
plt.close(fig)
print(json.dumps(index,indent=2))
