"""Scientific comparison figures and image-first annotation proposal cards."""
import json
import textwrap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from stage_a.common import OUT, output_dir, read_csv, write_json
from stage_a_readability_ordered.review import image_panel, read_npz
from .review import title

RUN=OUT/'stage_a/20260908_v6_conservative_decoder'; OLD=OUT/'stage_a/20260908_v5_readability_ordered'


def compact(key,cells,path):
    t=read_npz(OLD/'cache'/(key+'.npz'))
    fig,axes=plt.subplots(1,len(cells),figsize=(6*len(cells),6.2),layout='constrained')
    for ax,(name,folder) in zip(np.atleast_1d(axes),cells):
        p=read_npz(folder/(key+'.npz'))
        image_panel(ax,t,p['canonical_retained_rows'],title(name,t,p))
        ax.set_xlabel('A-line')
    fig.suptitle(f'{key}\nEXPERIMENTAL | solid: measured; dotted: manual reference; red: human-excluded',fontsize=12)
    fig.savefig(path,dpi=140); plt.close(fig)


def run():
    plan=json.loads((RUN/'plan.json').read_text()); stage_names=[s['name'] for s in plan['stages']]
    output_dir(RUN/'figures'); output_dir(RUN/'annotation_cards')
    compact(plan['focus'][0],[('Previous learned + ordered',OLD/'measurements/readability_ordered'),
        ('C2: conservative decoder',RUN/stage_names[1]/'measurements'),
        ('C3: stricter decoder',RUN/stage_names[2]/'measurements')],RUN/'figures/D98_comparison.png')
    compact(plan['focus'][1],[('Epoch 124: existing withholding',OLD/'measurements/epoch124_existing'),
        ('C1: conservative decoder',RUN/stage_names[0]/'measurements'),
        ('C2: all measurements withheld',RUN/stage_names[1]/'measurements')],RUN/'figures/b0510_comparison.png')
    compact(plan['focus'][3],[('Epoch 124: existing withholding',OLD/'measurements/epoch124_existing'),
        ('C2: conservative decoder',RUN/stage_names[1]/'measurements')],RUN/'figures/readable_control.png')
    curves=read_csv(OLD/'coverage_error_curves.csv'); points=[json.loads((RUN/s/'summary.json').read_text()) for s in stage_names]
    fig,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
    metrics=[('unreadable_leakage','Leakage into human exclusions (%)',100),
        ('boundary_p95_um','Boundary p95 error (um)',1),('boundary_gross_fraction','Retained errors >25 um (%)',100),
        ('worst_retained_gross_run','Longest retained gross-error run (columns)',1)]
    for ax,(metric,label,scale) in zip(axes.ravel(),metrics):
        for method,ordered,color in [('simple','False','#a47e49'),('simple','True','#9977b2'),('learned','False','#79a9ce'),('learned','True','#79b29a')]:
            rows=sorted([r for r in curves if r['method']==method and r['ordered']==ordered],key=lambda r:float(r['supported_coverage']))
            ax.plot([100*float(r['supported_coverage']) for r in rows],[scale*float(r[metric]) for r in rows],'.-',color=color,alpha=.65,
                label=method+(' + previous decoder' if ordered=='True' else ' gate'))
        for i,p in enumerate(points):
            x=100*p['supported_coverage']; y=scale*p[metric]
            ax.scatter([x],[y],s=70,marker='D',color=['#1264a3','#c94f2f','#302a65'][i],zorder=5)
            ax.annotate(f'C{i+1}',(x,y),xytext=(5,8),textcoords='offset points',fontsize=10,fontweight='bold')
        ax.set_xlabel('Manually supported positions retained (%)'); ax.set_ylabel(label); ax.grid(alpha=.2); ax.legend(fontsize=7)
    fig.suptitle('Exploratory development tradeoff | 2 corrected animals | fixed earlier grid and 3 saved iterations',fontsize=12)
    fig.savefig(RUN/'figures/accuracy_coverage.png',dpi=145); plt.close(fig)
    queue=read_csv(RUN/'annotation_queue_proposal.csv')
    for key in dict.fromkeys(r['key'] for r in queue):
        rows=[r for r in queue if r['key']==key]; t=read_npz(OLD/'cache'/(key+'.npz'))
        fig,axes=plt.subplots(1,2,figsize=(14,7),layout='constrained')
        image_panel(axes[1],t,t['raw_rows'],'Raw model diagnostic + frozen eligible manual reference')
        axes[0].imshow(t['x'][0],cmap='gray',aspect='auto',origin='upper',vmin=0,vmax=1)
        axes[0].set_xlim(axes[1].get_xlim()); axes[0].set_ylim(axes[1].get_ylim()); axes[0].set_title('Inspect the recorded image first; no prediction overlay')
        for a in axes: a.set_xlabel('A-line'); a.set_ylabel('Canonical depth (px)')
        tasks='; '.join(f'{r["surface"]}: {r["start"]}-{int(r["end_exclusive"])-1} ({r["reason"].replace("_"," ")})' for r in rows)
        fig.suptitle(key+' | '+rows[0]['split']+'\nPROPOSAL ONLY: ranges are review suggestions, not labels.\n'+textwrap.fill(tasks,125),fontsize=10)
        fig.savefig(RUN/'annotation_cards'/(key+'.png'),dpi=135); plt.close(fig)
    write_json(RUN/'figures_complete.json',dict(comparison_figures=3,accuracy_coverage_figures=1,annotation_cards=len({r['key'] for r in queue}),
        scientific_figures=True,image_generation_used=False,annotation_labels_written=False))


if __name__=='__main__': run()
