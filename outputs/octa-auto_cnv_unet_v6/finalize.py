"""Seal the bounded pilot after all artifacts and verification are complete."""
from common import *
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import platform
import shutil
import re
from importlib.metadata import version

def run():
    from supplement import pattern_report,seed_report
    from detailed_results import run as detailed_results
    pattern_report();seed_report()
    detailed_results()
    results=read(HERE/'evaluation/seed_comparison.json');checks=read(HERE/'verification/release_checks.json')
    assert checks['passed'] and checks['distinct_checkpoints']==9
    direct=read(HERE/'verification/direct_source_alignment.json');assert len(direct)==3 and all(d['passed'] for d in direct)
    m=read(HERE/'data/manifest.json')
    assert all(sha(p)==h for p,h in m['annotation_hashes'].items())
    # Scientific result figure: raw seed results, without pretending seeds are animals.
    fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
    for ax,key,title in zip(axes,['pooled_known_dice','additions_proxy','false_positives'],['Known-pixel Dice','Missed entries / additions proxy','False suggestions / removals proxy']):
        for j,ex in enumerate('ABC'):
            vals=[r[key] for r in results if r['model']==ex and r['split']=='holdout' and r['iou_cutoff']==.1]
            ax.scatter(j+np.array([-.08,0,.08]),vals,s=42,color=['#3e7cb1','#de8e30','#288c72'][j]);ax.plot([j-.15,j+.15],[np.mean(vals)]*2,color='black',lw=2)
        ax.set_xticks([0,1,2],['A: images','B: + masks / shadow','C: + thickness']);ax.tick_params(axis='x',labelsize=8);ax.set_title(title,fontsize=10);ax.spines[['top','right']].set_visible(False)
        ax.set_ylim(bottom=0)
    fig.suptitle('Same TS267 holdout · three seeds per model · marks are runs, not independent animals',fontsize=11)
    fig.savefig(dest(HERE/'evaluation/seed_comparison.png'),dpi=170);plt.close(fig)
    regions=pd.read_csv(HERE/'patterns/regions_by_layer.csv')
    fig,axes=plt.subplots(2,4,figsize=(13,7),layout='constrained')
    for ax,(name,_,_) in zip(axes.ravel(),LAYERS):
        data=regions[(regions.layer==name)&(regions.erosion_um.isin([0,25]))]
        for visit,group in data.groupby('visit'):
            vals=[group[group.region==r].measurable_fraction.mean() for r in ['geometric_interior','footprint_edge','perilesional_0_100um','artifact_rich_nonlesion']]
            ax.plot(range(4),vals,color='#487e9e',alpha=.45,lw=1,marker='.',ms=5)
        ax.set_title(name,fontsize=10);ax.set_xticks(range(4),['Interior','Edge','Around','Artifact'],rotation=30,fontsize=8);ax.set_ylim(-.03,1.03);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Automatic measurement availability · one line per visit\n25 µm geometric interiors; artifact missingness partly imposed by shadow policy',fontsize=11)
    fig.savefig(dest(HERE/'patterns/availability_by_visit.png'),dpi=160);plt.close(fig)
    path=HERE/'START_HERE.md';text=path.read_text(encoding='utf-8')
    text=re.sub(r'\nAcross three matched seeds.*?## Saved results','\n## Saved results',text,flags=re.S)
    text=text.replace('Three independent U-Nets were trained from random initialization.','Three experiments were each trained with three random initializations: nine separate trained U-Nets.')
    text=text.replace('All models use seed 267; this pilot does not establish seed-stable superiority.','Primary overlays use seed 267. Matched repeats at seeds 268 and 269 are also complete; see [the three-seed report](evaluation/SEED_REPORT.md). Seeds quantify optimization variability, not independent biological replication. No seed was chosen using holdout results.')
    source_sentence='Independent checks on one training, validation and holdout acquisition freshly redetected orientation and reproduced the complete OCTA projection plus three structural B-scans exactly (maximum absolute difference 0 dB).'
    text=text.replace(' '+source_sentence,'')
    text=text.replace('Cache orientation was freshly detected when created and is preserved with source and geometry fingerprints; no lateral flip/transpose is used.','Cache orientation was freshly detected when created and is preserved with source and geometry fingerprints; no lateral flip/transpose is used. '+source_sentence)
    if 'Sigmoid scores are uncalibrated' not in text:
        text=text.replace('Reproduce or resume with `RUN_PILOT.cmd`.','Sigmoid scores are uncalibrated model scores, not calibrated biological certainty.\n\nReproduce or resume with `RUN_PILOT.cmd`.')
    # Lead with measured three-seed behavior, retaining the full primary-seed table below.
    lead=['','Across three matched seeds on the same holdout scans:','',
          '| Inputs | Mean Dice (range) | Mean missed entries, of six | Mean false suggestions over three scans |',
          '|---|---:|---:|---:|']
    for ex in 'ABC':
        rows=[r for r in results if r['model']==ex and r['split']=='holdout' and r['iou_cutoff']==.1];dice=[r['pooled_known_dice'] for r in rows]
        lead.append(f"| {ex} | {np.mean(dice):.3f} ({min(dice):.3f}–{max(dice):.3f}) | {np.mean([r['additions_proxy'] for r in rows]):.2f} | {np.mean([r['false_positives'] for r in rows]):.2f} |")
    lead+=['','C recovered all six held-out lesion entries in every seed and had higher Dice than A in all three matched runs. B did not consistently improve over A. C still produced 2–6 false suggestions and 5–6 matched outlines needing correction by the predefined proxy per run. Thus C is promising for review suggestions, while adding availability and shadow without numerical thickness has no consistent benefit here. B adds availability and shadow together, so this cannot identify the effect of missingness alone.','',
           'These are the same six lesion entries repeatedly scored, not 18 independent lesions. Review corrections remain substantial, and no human time saving has been measured.','',
           '![Three-seed comparison](evaluation/seed_comparison.png)','']
    text=text.replace('## Saved results','\n'.join(lead)+'\n## Saved results')
    if 'evaluation/DETAILED_RESULTS.md' not in text:
        text+='\n[Border, count, area, low-availability and artifact results](evaluation/DETAILED_RESULTS.md) · [Observed thickness summaries](patterns/AVAILABLE_THICKNESS.md) · [Annotation and input audit](ANNOTATION_AND_INPUT_AUDIT.md).\n'
    path.write_text(text,encoding='utf-8')
    note=HERE/'patterns/REPORT.md'
    note.write_text(note.read_text(encoding='utf-8')+'\n![Per-visit automatic availability](availability_by_visit.png)\n',encoding='utf-8')
    # Compact reviewer/audit reports derived from the immutable data manifest.
    audit=['# Annotation and automatic-input audit','',f"Saved v5 files: {len(m['annotation_hashes'])}. No human annotation file was changed.",'',
        '15 saved acquisitions: 14 completed fields, 25 kept CNV entries, eight Unsure entries, one draft. The latest mask audit found 34 positive/uncertain conflict pixels in D0 OD; they were excluded. All other kept runs passed bounds, index and reviewed-mask checks. No draft or removed suggestion became an independent negative label.','',
        'The three historical reviewed-absence OS fields retain the recorded completion status. Their brief historical active-review times are an audit limitation, not proof of poor review; they are included with provenance. No new biological adjudication is claimed.', '',
        '| Visit / eye | Split | Completed | Positive pixels | Known negative pixels | Ignored pixels |', '|---|---|---:|---:|---:|---:|']
    for r in m['scans']:
        a=r['audit'];audit.append(f"| {r['day_label']} {r['eye']} | {r['split']} | {a['complete']} | {a['positive_pixels']} | {a['negative_pixels']} | {a['ignored_pixels']} |")
    audit+=['','`data/manifest.json` preserves exact source paths, full annotation hashes, region events, original completion/timing records, external correction fingerprints, embedded guard/override provenance, neural checkpoint hashes and input sources.','',
        'Embedded human state codes were present in the operational D28 OD export (7,808 boundary-pixels). These operational states were excluded: automatic inputs were recomputed from the raw neural positions and probabilities, verified against all 512 neural files per scan. The raw geometry CNV field and original en-face human labels were not model inputs.','',
        'For all 17 acquisitions, the upstream vessel mask exactly matched a hashed automatic unreviewed proposal. No ONH mask was present that could have injected manual ONH information into proposal generation. Code review confirmed that only structural images and the automatic vessel mask enter upstream neural inference; CNV masks are display/analysis fields. Shadow generation is image-based. External corrections were inventoried and never loaded by the input builder.','',
        f"The upstream layer-data manifest includes {m['upstream_TS267_records']} TS267 records, among animals {', '.join(m['upstream_animals'])}. No new-animal or end-to-end independent evaluation is claimed."]
    dest(HERE/'ANNOTATION_AND_INPUT_AUDIT.md').write_text('\n'.join(audit)+'\n',encoding='utf-8')
    versions=dict(python=sys.version,platform=platform.platform(),numpy=np.__version__)
    # Keep plotting separate from Torch DLL loading on this Windows workstation.
    versions.update(torch=version('torch'),scipy=version('scipy'),h5py=version('h5py'),pillow=version('Pillow'),gpu=read(HERE/'experiment_A/complete.json')['gpu'])
    write(HERE/'environment.json',versions)
    # Freeze code and exact dependencies used for provenance, including training source hash.
    source_files=list(HERE.glob('*.py'))+list(HERE.glob('*.cmd'))+[HERE/'review.html']
    dependencies=[ROOT/'code/octa/segment.py',ROOT/'code/eight_surface/segment.py',ROOT/'code/eight_surface/cnv_data.py',ROOT/'code/stage_a/common.py',V5/'octa_projection.py',ROOT/'outputs/octa-thick_v1/engine.py',ROOT/'outputs/octa-seg/octa-seg_v2/code/octa_seg_v2/infer.py',ROOT/'code/octa_seg_v1/predict.py']
    fps=[fingerprint(p) for p in source_files+dependencies]
    for p in source_files:shutil.copyfile(p,dest(HERE/'source_snapshot'/p.name))
    write(HERE/'implementation_manifest.json',fps)
    files=[p for p in HERE.rglob('*') if p.is_file() and p.suffix not in ('.log',) and p.name not in ('COMPLETE.json','artifact_manifest.json','progress.json') and 'source_snapshot' not in p.parts]
    write(HERE/'artifact_manifest.json',[fingerprint(p) for p in files])
    write(HERE/'COMPLETE.json',dict(status='bounded pilot complete',models=9,experiments=3,seeds=[267,268,269],
        acquisitions=17,native_score_maps=153,annotation_files_unchanged=True,human_review_performed=False,
        comparison_scope='within-TS267 development; upstream exposure',all_label_fit=False,
        implemented_review_timer=True,holdout_used_for_checkpoint_or_threshold_selection=False,
        source_alignment_checks=3,verification=checks))
    progress('All pilot deliverables verified',models=9,native_score_maps=153)

if __name__=='__main__':run()
