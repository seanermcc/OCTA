"""Review artifacts for the completed experiment; figures use manual targets only."""
import json
import textwrap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import rankdata
from stage_a.common import OUT, output_dir, write_json, write_csv, read_csv
from eight_surface.config import SURFACE_NAMES

COLORS=plt.cm.turbo(np.linspace(.04,.96,8))
RUN=OUT/'stage_a/20260908_v5_readability_ordered'
REASONS=json.loads((RUN/'evaluation_complete.json').read_text())['reason_definitions']


def read_npz(path):
    with np.load(path,allow_pickle=False) as data:
        return {k:data[k] for k in data.files}


def intervals(mask):
    edges=np.flatnonzero(np.diff(np.r_[False,mask,False].astype(np.int8)))
    return zip(edges[::2],edges[1::2])
NAMES={'raw':'Raw epoch 124 (diagnostic)', 'epoch124_existing':'Epoch 124: existing withholding',
       'readability_only':'Learned readability + existing withholding', 'ordered_only':'Ordered + posterior support',
       'readability_ordered':'Learned readability + ordered decoding', 'simple_rule':'Entropy + signal rule',
       'simple_ordered':'Entropy + signal + ordered decoding'}


def spans(ax,mask,**kwargs):
    for a,b in intervals(mask): ax.axvspan(a-.5,b-.5,**kwargs)


def image_panel(ax,t,rows,title,legend=False):
    x=t['x'][0]
    selected=np.r_[t['raw_rows'].ravel(),t['truth'][t['valid']]]
    selected=selected[np.isfinite(selected)]
    lo=max(0,float(selected.min())-35); hi=min(x.shape[0]-1,float(selected.max())+35)
    ax.imshow(x,cmap='gray',aspect='auto',origin='upper',vmin=0,vmax=1)
    for k,name in enumerate(SURFACE_NAMES):
        ax.plot(rows[k],color=COLORS[k],lw=1.,label=name)
        ax.plot(np.where(t['valid'][k],t['truth'][k],np.nan),color=COLORS[k],lw=1.4,ls=':')
    spans(ax,t['human_excluded'],facecolor='red',alpha=.10)
    ax.set_xlim(-.5,x.shape[1]-.5); ax.set_ylim(hi,lo)
    ax.set_title(title,fontsize=9); ax.set_ylabel('Canonical depth (px)',fontsize=8)
    ax.tick_params(labelsize=8)
    if legend: ax.legend(ncol=8,loc='lower center',fontsize=6,framealpha=.8)


def measurement(r,t,p,path,threshold):
    fig,axes=plt.subplots(4,1,figsize=(14,13),gridspec_kw={'height_ratios':[5.2,1.1,1.55,1.6]},layout='constrained')
    image_panel(axes[0],t,p['canonical_retained_rows'],
        f'{r["key"]}\nCombined measurement: {p["retained"].sum():,}/{p["retained"].size:,} boundary-columns retained',True)
    a=axes[1]; a.plot(p['readability_score'],color='#126786',lw=1.6,label='Learned usable score (uncalibrated)')
    a.axhline(threshold,color='k',ls='--',lw=1,label='Training 95% proxy-coverage threshold')
    spans(a,t['human_excluded'],facecolor='red',alpha=.15)
    a.scatter(np.flatnonzero(t['readability_target']==1),np.full((t['readability_target']==1).sum(),1.03),s=3,color='green',label='Weak reviewed positive proxy')
    a.set_ylim(-.03,1.08); a.set_ylabel('Usable score'); a.legend(ncol=3,fontsize=8,loc='lower left')
    a=axes[2]; labels=[]; masks=[]
    for name,bit in REASONS.items():
        mask=((p['reason_bits']&bit)!=0).any(0)
        if mask.any(): labels.append(name.replace('_',' ')); masks.append(mask)
    labels.append('human exclusion (reference)'); masks.append(t['human_excluded'])
    a.imshow(np.stack(masks),cmap='Blues',vmin=0,vmax=1,aspect='auto',interpolation='nearest',extent=(-.5,511.5,len(masks)-.5,-.5))
    a.set_yticks(range(len(labels)),labels,fontsize=8)
    a.set_title('Exclusion reasons: overlaps retained; reference markings are not supplied at inference',fontsize=9)
    a=axes[3]
    for j,name in enumerate(p['thickness_names'].astype(str)):
        a.plot(p['experimental_thickness_um'][j],label=name,lw=1)
    a.set_ylabel('Thickness (um)'); a.set_xlabel('A-line; gaps are NaN, never interpolated')
    a.legend(ncol=4,fontsize=7,loc='upper left')
    for a in axes[1:]: a.set_xlim(-.5,511.5); a.tick_params(labelsize=8)
    fig.suptitle('EXPERIMENTAL | 2 corrected validation animals | solid = measured; dotted = eligible manual target\nCanonical coordinates: vitreous at depth 0. Red bands = explicit human unreadability.',fontsize=10)
    fig.savefig(path,dpi=135); plt.close(fig)


def panels(r,t,measurements,path):
    fig,axes=plt.subplots(2,3,figsize=(18,10.8),layout='constrained')
    methods=['raw','epoch124_existing','readability_only','ordered_only','readability_ordered','simple_rule']
    for ax,method in zip(axes.ravel(),methods):
        rows=t['raw_rows'] if method=='raw' else measurements[method]['canonical_retained_rows']
        count=np.isfinite(rows).sum()
        image_panel(ax,t,rows,f'{NAMES[method]}\n{count:,}/{rows.size:,} finite boundary-columns')
        ax.set_xlabel('A-line',fontsize=8)
    fig.suptitle(f'{r["key"]} | QC={r["qc_group"]} | {r["scope_status"]}\nEXPERIMENTAL. Red=human-excluded; dotted=manual eligible targets. Common image scaling and depth range in all panels.',fontsize=11)
    fig.savefig(path,dpi=135); plt.close(fig)


def run():
    print('review: loading metadata',flush=True)
    prepared=json.loads((RUN/'prepared.json').read_text()); plan=json.loads((RUN/'PRESPECIFIED_PLAN.json').read_text())
    thresholds=json.loads((RUN/'exploratory_thresholds.json').read_text())['thresholds']
    records=[r for r in prepared['records'] if r['split']=='validation' and r['eligible']]
    output_dir(RUN/'review/measurements'); output_dir(RUN/'review/comparisons')
    summary=read_csv(RUN/'per_bscan_summary.csv')
    for r in records:
        print('review: measurement '+r['key'],flush=True)
        t=read_npz(RUN/'cache'/(r['key']+'.npz'))
        p=read_npz(RUN/'measurements/readability_ordered'/(r['key']+'.npz'))
        measurement(r,t,p,RUN/'review/measurements'/(r['key']+'.png'),1.-thresholds['learned']['0.95'])
    # Motivating example, persistent catastrophe, readable controls, next worst,
    # and largest labelled-tissue coverage loss (failure, not cherry-picked success).
    picks=[r for r in records if ('D98' in r['key'] and 'b0061' in r['key']) or 'b0510' in r['key']
           or (r['animal']=='TS169' and 'b0164' in r['key']) or ('D42' in r['key'] and 'b0023' in r['key'])]
    a={r['key']:int(r['supported_measured']) for r in summary if r['method']=='epoch124_existing'}
    b={r['key']:int(r['supported_measured']) for r in summary if r['method']=='readability_ordered'}
    lost=sorted(a,key=lambda key:a[key]-b[key],reverse=True)
    for key in lost[:2]:
        rr=next((r for r in records if r['key']==key),None)
        if rr is not None and rr not in picks: picks.append(rr)
    for r in picks:
        print('review: comparison '+r['key'],flush=True)
        t=read_npz(RUN/'cache'/(r['key']+'.npz'))
        ms={m:read_npz(RUN/'measurements'/m/(r['key']+'.npz')) for m in NAMES if m!='raw'}
        panels(r,t,ms,RUN/'review/comparisons'/(r['key']+'.png'))
    curves=read_csv(RUN/'coverage_error_curves.csv')
    fig,axs=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for m,flag,color in [('learned',False,'#1167b1'),('simple',False,'#dd7925'),('learned',True,'#1b9e77'),('simple',True,'#a5479e')]:
        g=sorted([c for c in curves if c['method']==m and c['ordered']==str(flag)],key=lambda c:float(c['supported_coverage']))
        label=m+(' + ordered' if flag else ' gate')
        for ax,x,y in [(axs[0,0],'readable_gate_coverage','unreadable_leakage'),
                       (axs[0,1],'supported_coverage','unreadable_leakage'),
                       (axs[0,2],'supported_coverage','boundary_p95_um'),
                       (axs[1,0],'supported_coverage','boundary_gross_fraction'),
                       (axs[1,1],'supported_coverage','worst_retained_gross_run'),
                       (axs[1,2],'supported_coverage','boundary_median_um')]:
            ax.plot([float(c[x]) for c in g],[float(c[y]) for c in g],'o-',label=label,color=color,ms=4)
            ax.set_xlabel(x.replace('_',' '),fontsize=8); ax.set_ylabel(y.replace('_',' '),fontsize=8)
            ax.grid(alpha=.2); ax.legend(fontsize=7); ax.tick_params(labelsize=8)
    fig.suptitle('Exploratory validation accuracy and coverage | fixed training-quantile grid | 2 corrected animals',fontsize=11)
    fig.savefig(RUN/'accuracy_coverage.png',dpi=140); plt.close(fig)
    history=json.loads((RUN/'training_history.json').read_text())
    fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for key in ['train_macro_loss','validation_macro_loss']:
        axs[0].plot([r['epoch'] for r in history],[r[key] for r in history],label=key)
    axs[0].axvline(10,ls=':',color='k'); axs[0].legend(fontsize=8); axs[0].set_xlabel('Head epoch'); axs[0].set_ylabel('Weighted class-macro BCE')
    for animal in history[0]['validation_by_animal']:
        axs[1].plot([r['epoch'] for r in history],[r['validation_by_animal'][animal] for r in history],label=animal)
    axs[1].legend(); axs[1].set_xlabel('Head epoch'); axs[1].set_ylabel('Validation readability loss')
    fig.suptitle('Frozen epoch-124 features; only the added head is trained; epoch 10 selected')
    fig.savefig(RUN/'training_curve.png',dpi=140); plt.close(fig)
    # Distributions and tie-corrected rank AUROC are exploratory proxy diagnostics.
    print('review: scores',flush=True)
    auc=[]
    fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,split in zip(axs,['train','validation']):
        score_data=read_npz(RUN/f'readability_scores_{split}.npz')
        y,s=score_data['target'],score_data['score']
        for target,label,color in [(1,'weak positive proxy','green'),(0,'explicit human exclusion','red'),(-1,'unknown','gray')]:
            ax.hist(s[y==target],bins=np.linspace(0,1,26),density=True,histtype='step',label=f'{label} (n={(y==target).sum()})',color=color)
        known=y>=0; pos=y[known]==1; ranks=rankdata(s[known]); n1=pos.sum(); n0=(~pos).sum()
        area=float((ranks[pos].sum()-n1*(n1+1)/2)/(n1*n0))
        auc.append(dict(split=split,positive_proxy_n=int(n1),explicit_negative_n=int(n0),proxy_auroc=area))
        ax.set_title(f'{split}: proxy AUROC {area:.3f}'); ax.set_xlabel('Usable score (uncalibrated)'); ax.legend(fontsize=7)
    fig.savefig(RUN/'readability_scores.png',dpi=140); plt.close(fig)
    write_csv(RUN/'readability_proxy_auc.csv',auc)
    write_json(RUN/'review_complete.json',dict(measurement_overlays=len(records),comparison_overlays=len(picks),
        comparison_keys=[r['key'] for r in picks],same_color_limits=True,same_crop_within_comparison=True,
        coordinate_system='canonical native depth, vitreous at zero',ground_truth='eligible frozen manual annotations only'))


if __name__=='__main__': run()
