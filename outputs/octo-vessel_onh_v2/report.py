"""Transparent target-specific evaluation reports; never score the all-label fit."""
from collections import defaultdict
import csv
import numpy as np
from common import *
from network import scored

def pool(rows,key):
    return scored({k:sum(r[key][k] for r in rows) for k in ['tp','fn','fp','tn']})

def fmt(x):return 'not estimable' if x is None else f'{100*x:.1f}%'

def main():
    audit=read_json(HERE/'audit_manifest.json');protocol=read_json(HERE/'protocol.json')
    folds=[read_json(HERE/'evaluation'/f'{s["name"]}.json') for s in protocol['folds']]
    rows=[r for f in folds for r in f['scans']]
    assert len({r['scan_id'] for r in rows})==len(rows)
    animals=[]
    for fold in folds:
        rs=fold['scans'];onh=[r for r in rs if r['onh_eligible']];pos=[r for r in onh if r['onh']['positive_pixels']>0];absent=[r for r in onh if r['onh_false_detection'] is not None]
        animals.append(dict(animal=fold['evaluation_animal'],calibration_animal=fold['calibration_animal'],training_animals=fold['training_animals'],
            vessel_cases=sum(r['vessel_eligible'] for r in rs),onh_cases=len(onh),onh_positive_cases=len(pos),onh_absent_cases=len(absent),
            vessel=pool(rs,'vessel'),v1_vessel=pool(rs,'v1_vessel'),onh=pool(onh,'onh'),
            onh_positive_mean_dice=float(np.mean([r['onh']['dice'] for r in pos])) if pos else None,
            onh_absent_false_detections=sum(r['onh_false_detection'] for r in absent),
            thresholds=fold['thresholds'],min_onh_area=fold['min_onh_area'],frozen_human_onh_assisted_scans=sum(r['frozen_human_onh_pixels']>0 for r in rs)))
    absent=[r for r in rows if r['onh_false_detection'] is not None]
    pos=[r for r in rows if r['onh']['positive_pixels']>0]
    paired=np.array([r['vessel']['dice']-r['v1_vessel']['dice'] for r in animals],float)
    rng=np.random.default_rng(20260914);boot=np.array([rng.choice(paired,len(paired),replace=True).mean() for _ in range(5000)])
    summary=dict(evaluation_type='Six animal-excluded development folds; calibration animal also absent from training. No untouched prospective final test.',
        total_evaluation_scans=len(rows),vessel_cases=sum(r['vessel_eligible'] for r in rows),onh_cases=sum(r['onh_eligible'] for r in rows),
        pooled_vessel=pool(rows,'vessel'),pooled_v1_vessel=pool(rows,'v1_vessel'),
        animal_mean_vessel_dice=float(np.mean([r['vessel']['dice'] for r in animals])),animal_mean_v1_vessel_dice=float(np.mean([r['v1_vessel']['dice'] for r in animals])),
        animal_mean_dice_improvement=float(paired.mean()),animal_bootstrap_improvement_interval=np.quantile(boot,[.025,.975]).tolist(),
        interval_caution='Exploratory paired resampling of only six animals; overlapping training folds and selected review cases limit inference.',
        onh_positive_mean_dice=float(np.mean([r['onh']['dice'] for r in pos])),onh_positive_cases=len(pos),
        onh_absent_cases=len(absent),onh_absent_false_detections=sum(r['onh_false_detection'] for r in absent),
        onh_absent_total_false_area_pixels=sum(r['onh_false_area_pixels'] for r in absent),
        vessel_scored_pixels=sum(r['vessel']['scored_pixels'] for r in rows),vessel_scored_fraction=sum(r['vessel']['scored_pixels'] for r in rows)/(sum(r['vessel_eligible'] for r in rows)*512*512),
        onh_scored_pixels=sum(r['onh']['scored_pixels'] for r in rows),
        onh_visibility_results={state:dict(cases=len(rr),mean_dice=float(np.mean([r['onh']['dice'] for r in rr]))) for state in ['Visible — outlined','Partially visible — outlined'] if (rr:=[r for r in pos if r['onh_visibility']==state])},
        common_onh_exclusion_new_vessel=pool(rows,'common_onh_exclusion_new_vessel'),common_onh_exclusion_v1_vessel=pool(rows,'common_onh_exclusion_v1_vessel'),
        frozen_human_onh_assisted_scans=sum(r['frozen_human_onh_pixels']>0 for r in rows),animals=animals)
    write_json(HERE/'metrics.json',summary);write_json(HERE/'evaluation/per_scan_metrics.json',rows)
    flat=[]
    for r in rows:
        row={k:r[k] for k in ['scan_id','animal','onh_visibility','onh_eligible','vessel_eligible','frozen_human_onh_pixels','onh_false_detection','onh_false_area_pixels']}
        for target in ['vessel','v1_vessel','onh']:
            row.update({target+'_'+k:v for k,v in r[target].items()})
        flat.append(row)
    with (HERE/'evaluation/per_scan_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    worst=sorted(rows,key=lambda r:r['vessel']['dice'] if r['vessel']['dice'] is not None else 2)[:6]
    worst_onh=sorted(pos,key=lambda r:r['onh']['dice'])[:6]
    changes=[]
    frozen={r['scan_id']:r for r in audit['annotations']}
    for path in sorted(LABELS.glob('*_cnv.npz')):
        sid=path.name[:-8]
        old=frozen.get(sid)
        if old is None or digest(path)!=old['source_sha256']:changes.append(dict(scan_id=sid,status='new since snapshot' if old is None else 'changed since snapshot'))
    write_json(HERE/'annotation_changes_since_snapshot.json',changes)
    text=['# Major vessels and ONH — experimental learned v2','',
          f'Annotation snapshot: {audit["frozen_at"]}. Human annotations and frozen v1 outputs remain external read-only sources; the exact annotation bytes are archived in `data/source_annotations_snapshot.zip`.',
          '', '## Annotation inventory','',
          f'{audit["counts"]["saved_records"]} saved records: {audit["counts"]["vessel_eligible"]} eligible vessel reviews and {audit["counts"]["onh_eligible"]} assessable ONH reviews ({audit["counts"]["onh_positive"]} visible/partial and {audit["counts"]["onh_absent"]} reviewed absence). Two explicitly poor-quality acquisitions are excluded from all training, tuning, evaluation and analysis. Cannot judge is not absence.',
          '', '## Independent development evaluation','',
          'Each row uses a network trained without the evaluated animal or its calibration animal. Calibration selects checkpoints, thresholds and ONH component filtering. Final all-label predictions are never included in these accuracy figures.',
          '', '| Evaluated animal | Calibration animal | Vessel cases | v1 vessel Dice | Learned vessel Dice | ONH positive Dice | ONH false detections / absent cases |',
          '|---|---|---:|---:|---:|---:|---:|']
    for a in animals:text.append(f'| {a["animal"]} | {a["calibration_animal"]} | {a["vessel_cases"]} | {fmt(a["v1_vessel"]["dice"])} | {fmt(a["vessel"]["dice"])} | {fmt(a["onh_positive_mean_dice"])} | {a["onh_absent_false_detections"]}/{a["onh_absent_cases"]} |')
    text+=['','### Counts by model role','',
           '| Held-out animal | Training vessel / ONH | Calibration vessel / ONH | Evaluation vessel / ONH |',
           '|---|---:|---:|---:|']
    for spec in protocol['folds']:
        values=[]
        for role in ['train','calibration','evaluation']:
            cc=spec['counts'][role]
            values.append(f'{sum(r["vessel"] for r in cc.values())} / {sum(r["onh"] for r in cc.values())}')
        text.append('| '+spec['evaluation_animal']+' | '+' | '.join(values)+' |')
    text+=['',f'The separate final model uses all {audit["counts"]["vessel_eligible"]} eligible vessel and {audit["counts"]["onh_eligible"]} eligible ONH reviews. Its fit is not evaluated as independent accuracy.',
           '',f'Equal-animal vessel Dice: **{fmt(summary["animal_mean_v1_vessel_dice"])} v1 → {fmt(summary["animal_mean_vessel_dice"])} learned**. Pooled-pixel Dice: {fmt(summary["pooled_v1_vessel"]["dice"])} → {fmt(summary["pooled_vessel"]["dice"])}.',
           f'Paired equal-animal improvement: {100*summary["animal_mean_dice_improvement"]:.1f} percentage points. Exploratory animal bootstrap interval: {100*summary["animal_bootstrap_improvement_interval"][0]:.1f} to {100*summary["animal_bootstrap_improvement_interval"][1]:.1f} points. Only six animals; this is not a prospective validation guarantee.',
           f'Vessel scoring covers **{fmt(summary["vessel_scored_fraction"])} of the {summary["vessel_cases"]} reviewed images** ({summary["vessel_scored_pixels"]:,} pixels), concentrated on brush edits. These are conditional correction-region metrics, not exhaustive vessel recall, capillary density, or whole-image precision.',
           f'ONH positive-case mean Dice: **{fmt(summary["onh_positive_mean_dice"])}** across {len(pos)} cases. Reviewed-absence false detections: **{summary["onh_absent_false_detections"]}/{len(absent)}**; total false area {summary["onh_absent_total_false_area_pixels"]:,} native pixels. Absence detection means any surviving predicted ONH in the reviewed negative region.',
           '', '## Baseline assistance and interpretation','',
           f'Frozen v1 had existing human ONH exclusions on {summary["frozen_human_onh_assisted_scans"]}/{len(rows)} evaluation scans. Its broader batch can use human ONH assistance, but no evaluated scan in this snapshot received it. It is not an automatic ONH method. The learned evaluation uses its own ONH predictions. Both vessel masks are scored on identical supervision. The supplementary common-ONH-exclusion vessel-head comparison is saved separately in metrics.json; it excludes reviewed/frozen ONH from both scorings and does not alter either original mask.',
           '', '## Supervision policy','',
           'Vessels: positive = completed review AND recorded direct brush footprint AND final vessel. Negative = completed review AND recorded brush footprint AND final non-vessel. Uncertain areas, ONH pixels and ONH-derived-only removal pixels are excluded. Untouched automatic pixels are ignored even under a completed review flag. Inherited brush provenance remains recorded and cannot be reconstructed. This conservative policy does not infer a caliber cutoff from ambiguous small branches.',
           'ONH: completed visible/partial reviews provide their footprint and reviewed complement, minus uncertain regions. Completed Outside image provides negatives. Unreviewed, Not assessed and Cannot judge provide no ONH targets. Excluded scans provide no target for either head. Saved masks never substitute for model predictions.',
           'Every supervision archive contains explicit positive, negative and ignored arrays. Images are reduced 512→256 by area averaging; supervision retains separate positive and negative pixel mass in every 2×2 block. Thus an unknown pixel does not become a negative when resizing. Full-field dihedral and mild intensity augmentation are applied only to training animals.',
           '', '## Important failures to inspect','', '### Lowest vessel scores','']
    for r in worst:text.append(f'- {r["scan_id"]}: learned Dice {fmt(r["vessel"]["dice"])}, v1 {fmt(r["v1_vessel"]["dice"])}, scored area {fmt(r["vessel"]["coverage_fraction"])}.')
    text+=['','### Lowest positive ONH scores','']
    for r in worst_onh:text.append(f'- {r["scan_id"]}: {r["onh_visibility"]}, Dice {fmt(r["onh"]["dice"])}.')
    text+=['','## Visual review and release decision','',
           '**Do not replace frozen v1 with this U-Net release.** The improved score on sparse brush-edited regions does not establish better whole-image masks. Browser inspection found substantial added vessel false positives in background texture and acquisition borders, along with poor partial-ONH detection. The user also reports that the new masks look worse than frozen v1 overall.',
           'Representative comparisons: TS165_OS_2025-04-29_WT_s06_123911 shows a good held-out central ONH match; TS241_OS_2024-09-11_D28_s03_103730 misses a partial ONH and adds border/background vessel predictions; TS169_OD_2025-01-14_D35_s05_113034 has false ONH regions despite reviewed absence; TS336_OD_2026-06-16_D42_s05_134542 shows extensive vessel predictions in background texture on an animal absent from training. These are qualitative observations, not new whole-image accuracy measurements.',
           'The practical next step discussed with the user is to finish correcting the flagged frozen-v1 queue and review the remaining v1 proposals for acceptance as major-vessel masks. Human-corrected, explicitly accepted automatic and still-unreviewed masks must retain distinct provenance. Vessel acceptance does not establish a completed ONH assessment. The two explicitly rejected scans remain excluded. No acceptance flags, annotations, composite analysis inputs or downstream releases have been changed by this run.',
           '', '## Model and deployment limits','',
           'A compact U-Net with separate vessel/ONH outputs learns directly from the structural en-face images; no automatic masks are used as targets or inputs. It starts from random weights. The sparse-mask loss computes errors only on supplied evidence. Architecture background: [original U-Net paper](https://arxiv.org/abs/1505.04597).',
           'Native 512×512 coordinates are preserved in exported masks. Raw sigmoid outputs are stored as float16 on the 256×256 model grid and restored with bilinear interpolation, align_corners=False. This introduces limited numerical quantization and a resolution tradeoff; the exact stored arrays regenerate the delivered masks. ONH takes precedence over vessels after the calibrated ONH component filter.',
           'The six reviewed animals and issue-selected review queue do not represent all 11 cohort animals or all acquisition qualities. Ten of 22 ONH-positive cases are TS250. Narrow vessels and seams can be confused; correction-region metrics cannot establish exhaustive generalization. The model has no validated acquisition-quality rejection mechanism. Poor results remain experimental predictions and are not promoted into downstream analyses.',
           f'{len(changes)} annotation records were added or changed after the frozen snapshot; those later revisions are not silently included. See annotation_changes_since_snapshot.json.',
           '', '## Files and launch','',
           '- `index.html`: all 314 acquisitions; original, v1, final automatic, held-out and human comparison views.',
           '- `OPEN_GALLERY.cmd`: open the gallery in the default browser; no server needed.',
           '- `RUN_OR_RESUME.cmd`: activate octa and resume matching stages. Do not start a second copy.',
           '- `protocol.json`: frozen settings, partitions and implementation hashes.',
           '- `models/held_TS*/`: six evaluation networks, histories, calibration trials and checkpoint provenance.',
           '- `models/all_eligible/`: separate inference model; all eligible reviewed animals entered its training.',
           '- `evaluation/`: original animal-held-out predictions and metrics. These remain independent of the final all-label predictions.',
           '- `predictions/` and `records/`: final automatic outputs and per-scan source/model fingerprints.',
           '- `audit_manifest.json`, `exclusions.json`, `data/`: review inventory, exclusions and derived supervision.',
           '- `metrics.json`: target-specific per-animal and aggregate evaluation.',
           '- `FINAL_VERIFIED.json`: completion verification; inspect its status before using the release.',
           '', 'No layer segmentation, octa-seg export, human review decision, or downstream analysis is changed.']
    if (HERE/'FINAL_VERIFIED.json').exists():
        status=read_json(HERE/'FINAL_VERIFIED.json')
        text[2:2]=[f'**Release status: {status["status"]}.** {status["complete_predictions"]}/312 eligible predictions verified; {status["excluded_scans"]} excluded; gallery verified: {status["gallery_verified"]}. `RUN_OR_RESUME.cmd` continues a matching interrupted run.','']
    (HERE/'START_HERE.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return summary

if __name__=='__main__':main()
