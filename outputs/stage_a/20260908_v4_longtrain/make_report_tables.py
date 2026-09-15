"""Export compact, auditable tables for the final scientific report."""
import csv
import json
from pathlib import Path
from eight_surface.config import SURFACE_NAMES, LAYER_DEFS
HERE=Path(__file__).resolve().parent
RUN=HERE/'dev_seed20260908'
def jc(p):return json.loads(p.read_text())
def cc(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def num(x,d=3):
    return '—' if x is None or x=='' else f'{float(x):.{d}f}'
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
raw=cc(RUN/'headline_raw_metrics.csv')
def metric(predictor,kind,name):
    return next(r for r in raw if r['predictor']==predictor and r['kind']==kind and r['name']==name)
sections=[]
for kind,names,heading in [('boundary',SURFACE_NAMES,'Boundary error, complete cohort, raw'),('thickness',[r[0] for r in LAYER_DEFS],'Thickness error, complete cohort, raw')]:
    rows=[]
    for name in names:
        line=[name]
        for predictor in ('unet_40','unet_long','stored_auto','classical_v2'):
            m=metric(predictor,kind,name)
            line.append(' / '.join([num(m['median_abs_um'],2),num(m['p95_abs_um'],2),num(m['gross_error_fraction_of_eligible'],4)]))
        rows.append(line)
    sections.append('## '+heading+'\n\nMedian / p95 absolute error (µm) / gross >25 µm fraction of eligible columns. Classical v2 covers only 11/14 eligible B-scans; its missing predictions also count as failures in the full comparison files.\n\n'+table(['Surface or band','40 epochs','Longer run','Stored auto','Classical v2 (incomplete)'],rows))
rows=[]
for band,_,_ in LAYER_DEFS:
    rows.append([band]+[num(metric(p,'thickness',band)['mean_signed_um'],2) for p in ('unet_40','unet_long','stored_auto')])
sections.append('## Signed thickness bias (µm)\n\n'+table(['Band','40 epochs','Longer run','Stored auto'],rows))
new=jc(RUN/'eval_validation/metrics.json')['summary']
rows=[]
for animal in ('TS169','TS325'):
    for name in SURFACE_NAMES:
        r=next(r for r in new if r['axis']=='animal' and r['group']==animal and r['kind']=='boundary' and r['name']==name and r['mode']=='raw')
        rows.append([animal,name,num(r['median_abs_um'],2),num(r['p95_abs_um'],2),num(r['gross_error_fraction_of_eligible'],4)])
sections.append('## Per-animal longer-run boundary error\n\n'+table(['Animal','Surface','Median (µm)','p95 (µm)','Gross fraction'],rows))
analysis=jc(RUN/'analysis_summary.json')
rows=[]
for model,rows_in in analysis['worst_bscans'].items():
    for r in rows_in:
        rows.append([model,r['key'],r['longest_gross_columns'],num(r['median_abs_um'],2),num(r['mean_entropy'],3)])
sections.append('## Worst localized failures\n\n'+table(['Model','B-scan','Longest gross run (columns)','Median error (µm)','Mean entropy'],rows))
rows=[]
for model,matched in analysis['readability_matched'].items():
    for item in matched:
        level=item['matched_supported_coverage_level']
        for method in ('simple_entropy_signal','learned_logreg'):
            m=item[method+'_val']
            rows.append([model,num(level,2),method,num(m['readable_col_coverage'],4),num(m['supported_coverage'],4),num(m['unreadable_leakage'],4),num(m['retained_p95_abs_um'],2),m['retained_max_contiguous_gross_cols']])
sections.append('## Readability comparison at approximately matched coverage\n\nThe existing comparison selects the nearest achieved validation coverage from a fixed training-quantile grid. These are approximate matches for exploratory comparison; no deployment threshold is selected. Readable-column coverage and supported-surface coverage have different denominators.\n\n'+table(['Model','Target readable coverage','Method','Actual readable coverage','Supported-surface coverage','Unreadable leakage','Retained p95 (µm)','Worst run (columns)'],rows))
rows=[]
for model,coeff in analysis['readability_coefficients'].items():
    for name,value in sorted(coeff.items(),key=lambda kv:-abs(kv[1]))[:6]:rows.append([model,name,num(value,4)])
sections.append('## Largest readability regression coefficients\n\n'+table(['Model','Feature','Coefficient'],rows))
rows=[]
for model,rows_in in analysis['entropy_error'].items():
    for r in rows_in:
        if r['axis'] in ('pooled','animal'):
            rows.append([model,r['axis'],r['group'],num(r['spearman_entropy_vs_abs_error'],3),num(r['auroc_entropy_predicts_gross'],3),num(r['gross_rate'],4)])
sections.append('## Entropy versus eligible boundary error\n\n'+table(['Model','Axis','Group','Spearman','AUROC gross error','Gross rate'],rows))
(RUN/'REPORT_TABLES.md').write_text('\n\n'.join(sections)+'\n',encoding='utf-8')
print('Report tables written')
