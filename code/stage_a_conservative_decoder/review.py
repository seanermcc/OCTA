"""Static scientific review figures, isolated from the torch evaluation process."""
import argparse
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from stage_a.common import OUT, output_dir, write_json, read_csv
from eight_surface.config import SURFACE_NAMES
from stage_a_readability_ordered.review import image_panel, spans, read_npz

RUN=OUT/'stage_a/20260908_v6_conservative_decoder'
OLD=OUT/'stage_a/20260908_v5_readability_ordered'
LABELS={'c1_bounded_partial':'C1: bounded movement, partial surfaces',
        'c2_tighter_signal':'C2: tighter movement + signal gate',
        'c3_strict_signal':'C3: strict signal + longer intervals'}


def title(name,t,p):
    valid=t['valid']&p['retained']
    den=int(t['valid'].sum()); n=int(valid.sum())
    err=(abs(p['canonical_retained_rows']-t['truth'])*1.12)[valid]
    tail=f'p95 {np.quantile(err,.95):.1f} um; gross (>25 um) {int((err>25).sum())}' if len(err) else 'Accuracy unavailable: no eligible targets retained'
    return f'{name}\nSupported: {n:,}/{den:,} ({100*n/den:.1f}%) | {tail}' if den else f'{name}\nNo eligible manual boundary targets'


def comparisons(r,t,stage,path):
    plan=json.loads((RUN/'plan.json').read_text())
    names=[s['name'] for s in plan['stages']]
    done=names[:names.index(stage)+1]
    cells=[('Raw epoch 124 (diagnostic)',None),('Epoch 124: existing withholding',OLD/'measurements/epoch124_existing'),
           ('Previous learned + ordered decoder',OLD/'measurements/readability_ordered')]
    cells += [(LABELS[n],RUN/n/'measurements') for n in done]
    fig,axes=plt.subplots(2,3,figsize=(18,11.4),layout='constrained')
    for ax,(label,folder) in zip(axes.ravel(),cells):
        if folder is None:
            rows=t['raw_rows']; name=label+'\nDotted lines are eligible manual targets'
        else:
            p=read_npz(folder/(r['key']+'.npz')); rows=p['canonical_retained_rows']; name=title(label,t,p)
        image_panel(ax,t,rows,name)
        ax.set_xlabel('A-line',fontsize=8)
    for ax in axes.ravel()[len(cells):]: ax.set_axis_off()
    fig.suptitle(f'{r["key"]}\nEXPERIMENTAL | solid = measured, dotted = manual | red = human-excluded | common native image scale',fontsize=11)
    fig.savefig(path,dpi=135); plt.close(fig)


def measurement(r,t,p,stage,path):
    fig,axes=plt.subplots(5,1,figsize=(14,15),gridspec_kw={'height_ratios':[5,1.2,1.2,2,1.6]},layout='constrained')
    image_panel(axes[0],t,p['canonical_retained_rows'],title(LABELS[stage],t,p),True)
    a=axes[1]; a.plot(p['simple_score'],lw=1,color='#116789',label='Entropy + signal score (larger = more rejection)')
    cfg=json.loads((RUN/stage/'configuration.json').read_text())
    if cfg['gate_quantile'] is not None:
        q=cfg['gate_quantile']; threshold=json.loads((OLD/'exploratory_thresholds.json').read_text())['thresholds']['simple'][str(q)]
        a.axhline(threshold,color='k',ls='--',lw=1,label=f'Exploratory training quantile {q}')
    spans(a,t['human_excluded'],facecolor='red',alpha=.12); a.legend(fontsize=8,loc='upper right'); a.set_ylabel('Score')
    a=axes[2]; a.imshow(p['retained'],aspect='auto',cmap='Blues',interpolation='nearest',vmin=0,vmax=1)
    a.set_yticks(range(8),SURFACE_NAMES,fontsize=7); a.set_title('Per-boundary retained support: blue = measured, white = NaN',fontsize=9)
    a=axes[3]; masks=[]; labels=[]
    reason_map={'scope':1,'shadow':2,'missing':4,'original crossing':8,'posterior uncertainty':64,
        'order infeasible':128,'signal gate':256,'no nearby supported row':512,'abrupt jump':1024,
        'short interval':2048,'previous version withheld':4096}
    for name,bit in reason_map.items():
        flag=((p['reason_bits']&bit)!=0).any(0)
        if flag.any(): labels.append(name); masks.append(flag)
    labels.append('human exclusion (reference)'); masks.append(t['human_excluded'])
    a.imshow(np.stack(masks),aspect='auto',cmap='Blues',interpolation='nearest',vmin=0,vmax=1)
    a.set_yticks(range(len(labels)),labels,fontsize=7); a.set_title('Withholding reasons: overlapping flags, any affected surface; reference is not an inference input',fontsize=9)
    a=axes[4]
    for j,name in enumerate(p['thickness_names'].astype(str)): a.plot(p['experimental_thickness_um'][j],lw=1,label=name)
    a.set_ylabel('Thickness (um)'); a.set_xlabel('A-line; missing endpoints give NaN thickness'); a.legend(ncol=4,fontsize=7)
    for a in axes[1:]: a.set_xlim(-.5,511.5); a.tick_params(labelsize=8)
    fig.suptitle(f'{r["key"]}\nEXPERIMENTAL | canonical depth 0 = vitreous | solid = measured; dotted = manual; red = human-excluded',fontsize=11)
    fig.savefig(path,dpi=130); plt.close(fig)


def run(stage,all_eligible=False):
    plan=json.loads((RUN/'plan.json').read_text())
    target=output_dir(RUN/stage/'review'); output_dir(target/'comparisons'); output_dir(target/'measurements')
    records=[r for r in plan['records'] if r['split']=='validation' and (r['key'] in plan['focus'] or (all_eligible and r['eligible']))]
    for r in records:
        t=read_npz(OLD/'cache'/(r['key']+'.npz')); p=read_npz(RUN/stage/'measurements'/(r['key']+'.npz'))
        measurement(r,t,p,stage,target/'measurements'/(r['key']+'.png'))
        if r['key'] in plan['focus']: comparisons(r,t,stage,target/'comparisons'/(r['key']+'.png'))
        print('review '+stage+' '+r['key'],flush=True)
    write_json(target/'complete.json',dict(keys=[r['key'] for r in records],comparisons=plan['focus'],
        display='Canonical native coordinates, common image scale, no interpolation',reference='Frozen eligible manual surfaces only'))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--stage',required=True); p.add_argument('--all-eligible',action='store_true')
    args=p.parse_args(); run(args.stage,args.all_eligible)
