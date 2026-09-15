"""Reproducible plain-language pattern and repeat-seed summaries."""
from common import *
import pandas as pd

def pattern_report():
    regions=pd.read_csv(HERE/'patterns/regions_by_layer.csv');contrasts=pd.read_csv(HERE/'patterns/matched_nonlesion_contrasts.csv')
    geom=pd.read_csv(HERE/'patterns/lesion_geometry.csv');visits=pd.read_csv(HERE/'patterns/visit_summaries.csv')
    lines=['# Thickness and automatic availability patterns','',
        'These are descriptive within-TS267 measurements from the recovered automatic branch, not a CNV biomarker validation. Twenty-five kept entries span nine OD visits and can represent repeated views of the same lesions. Individual entries, scans and visits remain in the tables.','',
        'The table averages regions within each visit and then gives each visit equal weight. Availability is the fraction finite under the experimental policy; it is not validated reliability. Perilesional means the 0–100 µm exterior band, not healthy tissue. Artifact-rich nonlesion locations are reviewed background with automatic vessel, shadow or low-signal flags.','',
        '| Layer | 25 µm interior availability | Footprint edge | Perilesional | Artifact-rich background |',
        '|---|---:|---:|---:|---:|']
    values=[]
    for name,_,_ in LAYERS:
        row=[]
        for region in ['geometric_interior','footprint_edge','perilesional_0_100um','artifact_rich_nonlesion']:
            a=visits[(visits.layer==name)&(visits.region==region)]['mean_region_measurable_fraction']
            row.append(f'{a.mean():.1%}' if len(a) else '—')
        lines.append('| '+name+' | '+' | '.join(row)+' |')
        vals=contrasts[contrasts.layer==name]
        av=vals.groupby('visit').availability_difference.mean().dropna()
        values.append((name,float(av.mean()) if len(av) else None,float(vals.matched_fraction.median())))
    lines += ['', '## Controlling for artifact and position strata','',
        'Matched nonlesion contrasts use the same acquisition, structural-signal quartile, automatic shadow/vessel status, 4×4 position cell and FOV-edge stratum. A stratum needs at least 25 eligible background pixels. Results are descriptive: neither matched pixels nor repeated lesions are independent experimental units.', '',
        '| Layer | Lesion minus matched-background availability | Median matched footprint coverage |',
        '|---|---:|---:|']
    for name,value,coverage in values:lines.append(f'| {name} | {value:+.1%} | {coverage:.1%} |' if value is not None else f'| {name} | unavailable | {coverage:.1%} |')
    interior=regions[(regions.region=='geometric_interior')&(regions.erosion_um==25)]
    wholly=interior[(interior.pixels>0)&(interior.measurable_fraction==0)]
    lines += ['',f"There are {len(wholly)} entirely unavailable layer/interior combinations out of {len(interior[interior.pixels>0])}. Those entries retain their unavailable fraction and have no thickness median.",
        f"Empty geometric interiors: 10 µm: {int((geom.interior_10_pixels==0).sum())}; 25 µm: {int((geom.interior_25_pixels==0).sum())}; 50 µm: {int((geom.interior_50_pixels==0).sum())}. FOV-clipped footprints: {int(geom.clipped.sum())}. Empty interiors are not zero-thickness tissue.",'',
        '## What the measurements do and do not support','',
        'Missing measurements also occur in reviewed nonlesion artifact regions. Shadow pixels are deliberately withheld by the automatic thickness policy, so the very low artifact-region availability is partly deterministic and is not evidence that CNV causes missingness. Availability alone therefore does not establish CNV specificity. A difference from matched background remains an association within one animal, and depends on the upstream experimental reporting/geometry policy. It does not identify a biological core or a particular cause of signal failure.', '',
        'The full tables retain observed-value thickness median/IQR for every layer, lesion interior, edge and perilesional region; 10/25/50 µm sensitivity analyses; missing-layer bit combinations; and automatic cause bits. Any layer with no finite values is reported as unavailable. No thickness interpolation or imputation is used for these summaries.', '',
        'Model B combines availability masks and shadow. Its comparison with A cannot isolate missingness. Model C adds numerical thickness to that combined set. Read the seed comparison before interpreting an apparent benefit.', '',
        'Files: `regions_by_layer.csv`, `visit_summaries.csv`, `missingness_combinations.csv`, `matched_nonlesion_contrasts.csv`, and `lesion_geometry.csv`.']
    dest(HERE/'patterns/REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines[:33]),flush=True)

def seed_report():
    path=HERE/'evaluation/seed_comparison.json'
    if not path.exists():return
    summary=read(path);lines=['# Three-seed sensitivity check','',
        'The recipe, visit partitions, sampling budget and architecture were unchanged. Seeds 267, 268 and 269 were each trained independently for A, B and C. Each checkpoint and threshold was selected using D49 only. Repeating seeds does not provide additional independent animals or lesion instances.','',
        '| Model / seed | Holdout recalled entries | False suggestions | Known-pixel Dice | Correction proxy |',
        '|---|---:|---:|---:|---:|']
    for r in summary:
        if r['split']=='holdout' and r['iou_cutoff']==.1:
            lines.append(f"| {r['model']} / {r['seed']} | {r['matched']}/{r['reference_lesions']} | {r['false_positives']} | {r['pooled_known_dice']:.3f} | {r['outline_corrections_proxy']} |")
    lines+=['','Mean and range below describe optimization variability on these same three scans; they are not confidence intervals.','',
            '| Model | Dice mean (range) | Mean missed entries | Mean false suggestions |','|---|---:|---:|---:|']
    for ex in 'ABC':
        a=[r for r in summary if r['model']==ex and r['split']=='holdout' and r['iou_cutoff']==.1];d=[r['pooled_known_dice'] for r in a]
        lines.append(f"| {ex} | {np.mean(d):.3f} ({min(d):.3f}–{max(d):.3f}) | {np.mean([r['additions_proxy'] for r in a]):.2f} | {np.mean([r['false_positives'] for r in a]):.2f} |")
    lines+=['','These are within-TS267 development results. B vs A tests availability plus shadow together; C vs B adds observed thickness. Border correction and artifact errors remain, and practical time savings are unmeasured. No seed was selected using holdout performance; the primary delivered overlays remain seed 267.']
    dest(HERE/'evaluation/SEED_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines),flush=True)

if __name__=='__main__':pattern_report();seed_report()
