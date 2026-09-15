"""Readable companion tables for border/count errors and availability strata."""
from common import *
import pandas as pd

def run():
    scan=pd.read_csv(HERE/'evaluation/per_scan.csv');lesions=pd.read_csv(HERE/'evaluation/lesion_availability.csv');fp=pd.read_csv(HERE/'evaluation/false_positive_artifacts.csv')
    lines=['# Detailed development comparison','',
        'These summaries use the primary seed (267) and the same prespecified 0.1 IoU one-to-one matching. All stricter 0.25/0.5 sensitivity results remain in `comparison.csv` and `per_scan.csv`. Empty-negative Dice is undefined; false-positive area/count is reported instead.','',
        '| Model | Holdout mean matched border error (µm) | Mean absolute count error / scan | Mean absolute area error / scan (mm²) | Merges | Splits |','|---|---:|---:|---:|---:|---:|']
    rows=[]
    for ex in ['A','B','C','v3']:
        d=scan[(scan.model==ex)&(scan.split=='holdout')&(scan.iou_cutoff==.1)]
        border=float((d.border_mean_um.fillna(0)*d.border_pairs).sum()/d.border_pairs.sum()) if d.border_pairs.sum() else None
        row=dict(model=ex,border_mean_um=border,border_pairs=int(d.border_pairs.sum()),mean_abs_count_error=float(d.count_error.abs().mean()),mean_abs_area_error_mm2=float(d.area_error_mm2.abs().mean()),merges=int(d.merges.sum()),splits=int(d.splits.sum()));rows.append(row)
        lines.append(f"| {ex} | {border:.2f} | {row['mean_abs_count_error']:.2f} | {row['mean_abs_area_error_mm2']:.4f} | {row['merges']} | {row['splits']} |")
    lines+=['','Border errors include only matched pairs whose reference outline is wholly reviewed and not FOV-clipped, and whose prediction does not touch ignored pixels. This conditional error excludes missed lesions and should be read with recall. Merges/splits use the prespecified overlap graph.','',
            '| Model | Recall in low-availability lesions | Recall in other lesions |','|---|---:|---:|']
    for ex in ['A','B','C','v3']:
        d=lesions[(lesions.model==ex)&(lesions.split=='holdout')];values=[]
        for low in [True,False]:
            x=d[d.low_availability==low];values.append(f'{int(x.detected.sum())}/{len(x)}' if len(x) else 'no eligible entries')
        lines.append('| '+ex+' | '+' | '.join(values)+' |')
    lines+=['','Low availability means a mean available fraction below 0.5 across all eight layers within the reviewed footprint. It is a descriptive measurement-support stratum, not scan-quality ground truth.','',
            '| Model | False suggestions | Mean vessel fraction | Mean shadow fraction | Mean low-signal fraction |','|---|---:|---:|---:|---:|']
    for ex in ['A','B','C','v3']:
        d=fp[(fp.model==ex)&(fp.split=='holdout')]
        values=[f'{d[k].mean():.1%}' if len(d) else '—' for k in ['vessel_fraction','shadow_fraction','low_signal_fraction']]
        lines.append(f'| {ex} | {len(d)} | '+' | '.join(values)+' |')
    lines+=['','These are average spatial overlaps with automatic artifact masks, not adjudicated error causes. Per-component fractions and sizes are in `false_positive_artifacts.csv`. B-scan inspection is provided in the depth atlas.','',
            'All six holdout lesion entries are OD. The one completed OS holdout field has zero primary-seed A/B/C suggestions and one v3 suggestion; this does not rule out an eye shortcut. Numeric eye/visit/animal/coordinate channels were excluded, but image anatomy and acquisition appearance can encode them.','',
            'Human review actions and times have not been collected for these model suggestions. Existing historical GUI times are preserved in the annotation audit but cannot measure the new models’ review burden.']
    dest(HERE/'evaluation/DETAILED_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');csv_write(HERE/'evaluation/border_count_area_summary.csv',rows)
    # Report observed numerical thickness separately from coverage.
    visits=pd.read_csv(HERE/'patterns/visit_summaries.csv');p=['# Available-value thickness summaries','',
        'Medians below summarize only available measurements. Each visit first contributes its median of region medians; the table shows the median across those visits. Conditional measurements can be selected by the availability policy, so differences are not unbiased tissue change estimates. Read coverage alongside these numbers.','',
        '| Layer | Interior (µm) | Edge (µm) | Perilesional (µm) |','|---|---:|---:|---:|']
    for layer,_,_ in LAYERS:
        values=[]
        for region in ['geometric_interior','footprint_edge','perilesional_0_100um']:
            a=visits[(visits.layer==layer)&(visits.region==region)].median_of_available_region_medians_um.dropna()
            values.append(f'{a.median():.1f} ({len(a)} visits)' if len(a) else 'unavailable')
        p.append('| '+layer+' | '+' | '.join(values)+' |')
    p+=['','Per-lesion median/IQR and 10/25/50 µm sensitivity values are retained in `regions_by_layer.csv`. Matched within-scan stratum median differences and observed pixel support are in `matched_nonlesion_contrasts.csv`; entirely missing strata have no thickness difference.']
    dest(HERE/'patterns/AVAILABLE_THICKNESS.md').write_text('\n'.join(p)+'\n',encoding='utf-8')

if __name__=='__main__':run()
