"""Scientific figures, prioritized review queue and candid within-animal report."""
from common import *
from metrics import boundary,components
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import ndimage as ndi
from collections import defaultdict

def gray(ax,image):
    lo,hi=np.percentile(image,[2,98]);ax.imshow(image,cmap='gray',vmin=lo,vmax=hi,origin='upper');ax.axis('off')

def contour(ax,mask,color):
    if mask.any() and not mask.all():ax.contour(mask.astype(float),levels=[.5],colors=[color],linewidths=.75)

def load_predictions(sid):
    out={}
    for ex in 'ABC':out[ex]=npz(HERE/f'experiment_{ex}/predictions'/f'{sid}.npz')['mask']
    out['v3']=npz(V3/'proposals'/f'{sid}.npz')['proposal_mask'].astype(bool)
    return out

def main():
    m=read(HERE/'data/manifest.json');details=read(HERE/'evaluation/details.json');comparison=read(HERE/'evaluation/comparison.json')
    queue=[];rng=np.random.default_rng(267);depth=[];figures={}
    for rec in m['scans']:
        sid=rec['scan_id'];d=npz(HERE/'data'/f'{sid}.npz');pred=load_predictions(sid)
        fig,axes=plt.subplots(2,3,figsize=(15,10),layout='constrained')
        gray(axes[0,0],d['optical'][0]);contour(axes[0,0],d['target'],'#25e48f');contour(axes[0,0],~d['known'],'#ffc447')
        axes[0,0].set_title('Structural OCT · reviewed footprint / ignored')
        gray(axes[0,1],d['optical'][1]);contour(axes[0,1],d['target'],'#25e48f');axes[0,1].set_title('Actual OCTA · saved depth crop')
        for ax,ex in zip([axes[0,2],*axes[1]],['A','B','C','v3']):
            gray(ax,d['optical'][0]);contour(ax,d['target'],'#25e48f');contour(ax,pred[ex],'#ff5ab2');ax.set_title(ex+' · suggestions (pink), reviewed CNV (green)')
        fig.suptitle(sid+'\n'+rec['split']+' · within TS267 · no animal-independent claim')
        imagepath=dest(HERE/'review/overlays'/f'{sid}.png');fig.savefig(imagepath,dpi=115);plt.close(fig)
        figures[sid]=str(imagepath.relative_to(HERE)).replace('\\','/')
        union=np.logical_or.reduce([pred[x] for x in 'ABC']);inter=np.logical_and.reduce([pred[x] for x in 'ABC'])
        candidates=[]
        for i,g in enumerate(d['instances']):
            missed=[ex for ex in 'ABC' if i in details[ex][sid]['missed_reference']]
            if missed:
                y,x=ndi.center_of_mass(g);candidates.append(dict(kind='possible miss',priority=100+len(missed)*10,models=missed,y=int(y),x=int(x),reference=i))
        for ex in 'ABC':
            labels,parts=components(pred[ex])
            for j in details[ex][sid]['false_predictions']:
                mask=parts[j];y,x=ndi.center_of_mass(mask)
                candidates.append(dict(kind='possible false suggestion',priority=60+min(20,int(mask.sum())/100),models=[ex],y=int(y),x=int(x),pixels=int(mask.sum())))
        labels,parts=components(union&~inter)
        for p in sorted(parts,key=lambda x:-x.sum())[:3]:
            y,x=ndi.center_of_mass(p);candidates.append(dict(kind='model disagreement',priority=40+min(15,int(p.sum())/100),models=list('ABC'),y=int(y),x=int(x),pixels=int(p.sum())))
        if not d['known'].any():candidates.append(dict(kind='unreviewed acquisition',priority=75,models=list('ABC'),y=256,x=256))
        candidates=sorted(candidates,key=lambda c:-c['priority'])[:8]
        candidates.append(dict(kind='fixed random sample',priority=10,models=list('ABC'),y=int(rng.integers(64,448)),x=int(rng.integers(64,448))))
        for c in candidates:
            c.update(scan_id=sid,split=rec['split'],visit=rec['day_label'],eye=rec['eye'],overlay=figures[sid],
                     id=f'{sid}_{len(queue):04d}',human_review_seconds=None,depth_information_needed='unreviewed')
            queue.append(c)
    # Consensus missed lesions plus representative disagreements/FPs for depth inspection.
    queue.sort(key=lambda c:(c['split']!='holdout',-c['priority'],c['scan_id']))
    for c in queue:
        if c['kind'] in ('possible miss','possible false suggestion','model disagreement') and len(depth)<12:
            rec=next(r for r in m['scans'] if r['scan_id']==c['scan_id']);sid=c['scan_id'];d=npz(HERE/'data'/f'{sid}.npz')
            images=np.load(volume_path(sid)/'images.npy',mmap_mode='r');pred=load_predictions(sid)
            fig,axes=plt.subplots(3,2,figsize=(13,9),layout='constrained')
            gray(axes[0,0],d['optical'][0]);gray(axes[0,1],d['optical'][1])
            for ax in axes[0]:
                contour(ax,d['target'],'#25e48f');ax.axhline(c['y'],color='#ffc447',lw=.8);ax.axvline(c['x'],color='#ffc447',lw=.8)
            axes[0,0].set_title('Structural OCT en-face');axes[0,1].set_title('Actual OCTA projection')
            for ax,dy in zip(axes[1:].ravel(),[-24,-8,8,24]):
                b=int(np.clip(c['y']+dy,0,511));gray(ax,images[b]);ax.axvline(c['x'],color='#ffc447',lw=.8)
                # Human footprints shown as top markers only, not inferred depth boundaries.
                spans=np.flatnonzero(d['target'][b]);ax.scatter(spans,np.full(len(spans),5),s=2,c='#25e48f')
                ax.set_title(f'B-scan {b} · canonical retinal crop')
            fig.suptitle(sid+'\n'+c['kind']+' · yellow crosshair; green = reviewed en-face extent only')
            p=dest(HERE/'review/depth_atlas'/f"{c['id']}.png");fig.savefig(p,dpi=125);plt.close(fig)
            depth.append(dict(**c,depth_figure=str(p.relative_to(HERE)).replace('\\','/')))
    write(HERE/'review/queue.json',queue);csv_write(HERE/'review/queue.csv',queue);write(HERE/'review/depth_atlas.json',depth)
    # All original label files must remain identical after training, scoring and report preparation.
    changed=[p for p,h in m['annotation_hashes'].items() if sha(p)!=h]
    write(HERE/'verification/annotation_integrity.json',dict(unchanged=not changed,files=len(m['annotation_hashes']),changed=changed))
    if changed:raise ValueError('Source annotations changed; results need a new reference revision')
    tests=read(HERE/'verification/preflight.json')
    counts=dict(saved_files=len(m['annotation_hashes']),complete=sum(r['audit']['complete'] for r in m['scans']),
        approved_entries=sum(sum(q['approved'] and q['category']=='Full Lesion' for q in r['audit']['regions']) for r in m['scans']))
    lines=['# CNV U-Net v6: within-TS267 suggestion pilot','',
        'Three independent U-Nets were trained from random initialization. These are suggestions for human review. Later-visit evaluation observes the same animal and potentially the same lesions; it cannot establish generalization to other animals. The upstream layer model used ALL_LABELLED data including TS267.','',
        '## Saved results','',
        '[Open the review guide](review/REVIEW_GUIDE.md). Run `OPEN_REVIEW.cmd` to inspect suggestions with linked B-scans and record actual review actions and focus-active time. Predictions are separate from human annotations.','',
        f"Audit: {counts['saved_files']} saved files, {counts['complete']} completed fields, {counts['approved_entries']} kept lesion entries; 14 scans provide supervision. D0 OS remains partial; D28 OS and D35 OS have no saved v5 file. Those three provide predictions but no negative training labels. D0 OD has 34 conflicting positive pixels, which are excluded. Human files remained unchanged.",'',
        '## Development holdout: D56 and D98','',
        '| Model | Recall (IoU ≥ 0.1) | FP / completed scan | Precision | Known-pixel Dice | Additions* | Removals* | Outline corrections* |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in comparison:
        if r['split']=='holdout' and r['iou_cutoff']==.1:
            fmt=lambda x:'—' if x is None else f'{x:.3f}'
            lines.append(f"| {r['model']} | {r['matched']}/{r['reference_lesions']} | {fmt(r['fp_per_completed_scan'])} | {fmt(r['precision'])} | {fmt(r['pooled_known_dice'])} | {r['additions_proxy']} | {r['removals_proxy']} | {r['outline_corrections_proxy']} |")
    lines += ['', '*Action counts are comparison-derived proxies, not observed human edits. Human review time for these new model suggestions has not yet been measured. No time saving is inferred. The reviewer records additions, removals, outline corrections, acceptances and focused review time separately.', '',
        'The unchanged v3 comparison uses its saved candidate cores, which were the actual displayed suggestions. They are often smaller than full reviewed lesion footprints. Its whole-footprint Dice therefore tests that mismatch as well as detection; the v3 heuristic was not retrained or retuned.', '',
        '## Training and validation','',
        'A uses structural OCT and actual OCTA (2 channels). B adds eight automatic availability masks and automatic shadow together (11). C adds eight numerical thickness maps (19). Any B–A improvement concerns the combined availability-plus-shadow inputs. Isolating missingness requires another ablation.', '',
        'Each model uses four encoder stages (16/32/64/128), a 256-channel bottleneck, GroupNorm and a mirrored decoder. AdamW starts at 0.001 with 0.0001 weight decay. Native 256×256 tiles are acquisition-balanced with positive/negative sampling; inference uses 128-pixel stride and weighted overlap. There are no lesion-count caps or circularity filters.', '',
        'Training visits: D0/D7/D14/D28/D35/D42; validation: D49; development holdout: D56/D98. Both eyes remain grouped by visit. Checkpoints and score thresholds use validation only. The overlapping epoch sampling schedules were verified identical across A/B/C. All models use seed 267; this pilot does not establish seed-stable superiority.', '',
        f"Preflight: {tests['contract_tests']} contract tests passed. The real two-tile overfit reached Dice {tests['tiny_known_dice']:.3f}. All-unknown losses, negative BCE, missing-thickness fill, native masks, one-to-one matching and blended full-field inference were tested.",'',
        '## Input provenance and limitations','',
        'All eight thickness outputs retain their established endpoints. Full retina is ILM to the outer RPE edge; photoreceptor composite includes ONL. Saved thickness NaNs remain NaNs. Only normalized model tensors use zero fill, paired with availability channels. Finite means available under the experimental policy, not validated reliability.', '',
        'Automatic thickness is recovered from the frozen raw neural branch and automatic trace-denial, crossing/out-of-crop and shadow guards. External human corrections, embedded denials, regional unreliability and contextual estimates are excluded. All 512 raw neural records per scan were compared with the preserved branch. Automatic vessel provenance and absence of human ONH influence were checked. Human CNV geometry in upstream bundles is never passed to the model.', '',
        'Actual OCTA is the mean dB projection over the saved retinal depth crop, not a layer-specific slab. It shares the exact source/grid/crop with structural OCT. Cache orientation was freshly detected when created and is preserved with source and geometry fingerprints; no lateral flip/transpose is used. Processed-volume integrity uses the upstream explicitly sampled hash; derived arrays, checkpoints and annotations have full SHA-256 hashes.', '',
        'All kept CNVs are OD. See `evaluation/eye_strata.csv` for OD/OS results; good performance on OS negatives does not rule out eye-associated shortcuts. Identity, eye, visit, coordinates, heuristic masks, and human-derived region maps are not input channels.', '',
        '## Thickness and missingness','',
        'See `patterns/REPORT.md` and the per-lesion/per-layer tables. Geometric interiors use 25 µm erosion with 10/50 µm sensitivity checks; they are not biological cores. Perilesional tissue is not assumed healthy. Same-field nonlesion comparisons stratify signal, shadow, vessel, position and edge proximity. Repeated lesions and pixels are not independent subjects.', '',
        '## Depth review before changing architecture','',
        'See `review/DEPTH_LIMITATION.md` and the depth atlas. Mean projections collapse axial location and layer relationships, so they cannot distinguish structures that overlap laterally at different depths. Native B-scans accompany persistent errors. A human depth-dependence judgment remains separate from model disagreement; do not assume a larger 2D network supplies missing depth information.', '',
        '## Next useful labels','',
        'Prioritize persistent misses, artifact-rich false suggestions, disputed outlines and image/mask model disagreements, with the fixed random sample retained. Add new animals, positive and negative eyes, poor-signal controls and lesions with unavailable thickness. Further annotation was not required to run this pilot. Any later training that uses the inspected holdout labels must call them development data.', '',
        'Reproduce or resume with `RUN_PILOT.cmd`. The data manifest, normalization, protocol, model configurations, optimizer/RNG checkpoints, histories, native score maps, raw components and complete per-scan metrics remain under this release.']
    dest(HERE/'START_HERE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write(HERE/'review/atlas_index.json',dict(scans=[dict(scan_id=r['scan_id'],split=r['split'],overlay=figures[r['scan_id']]) for r in m['scans']],queue=queue,depth=depth))
    progress('Review artifacts generated',queue_items=len(queue),depth_cases=len(depth))

if __name__=='__main__':main()
