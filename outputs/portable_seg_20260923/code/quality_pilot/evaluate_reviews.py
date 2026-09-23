"""Compare independently saved ratings with metrics; no learning or label writes."""
from collections import Counter
import numpy as np
from scipy.stats import rankdata
from .common import *
from .review_store import strip_rating
from .metrics import stats,warnings

def auc(values,bad):
    values=np.asarray(values,float);bad=np.asarray(bad,bool);ok=np.isfinite(values)
    values,bad=values[ok],bad[ok];n1=int(bad.sum());n0=len(bad)-n1
    if not n1 or not n0:return None
    return float((rankdata(values)[bad].sum()-n1*(n1+1)/2)/(n1*n0))

def run():
    q=read(OUT/'review_queue.json');paired=[]
    with (OUT/'reports/strips.csv').open(encoding='utf-8') as f:
        import csv
        entropy_cutoff=float(np.quantile([float(r['entropy_p95']) for r in csv.DictReader(f)],.75))
    for s in q['examples']:
        path=OUT/'reviewer/quality_reviews'/f"{s['scan_id']}_b{s['bscan']:04d}.json"
        saved=read(path) if path.exists() else None
        if saved and saved['model_identity']!=q['model_identity']:raise ValueError('Rating/model identity mismatch')
        rating=strip_rating(saved['records'],s['lo'],s['hi']) if saved else None
        overlapping=[r for r in saved['records'] if max(r['lo'],s['lo'])<min(r['hi'],s['hi'])] if saved else []
        m=s['metrics'];entropy=m['entropy_p95']>=entropy_cutoff;spike=(m['spike_max_um'] or 0)>20
        paired.append(dict(sample_id=s['id'],
             role=s['role'],driver=s['driver'],rating=rating or 'Unrated',
             reasons='; '.join(sorted(set(r['reason'] for r in overlapping if r['reason']))),
             rerated_after_metric_reveal=any(r.get('metrics_revealed_before',False) for r in overlapping),
             entropy_flag=entropy,spike_flag=spike,warning_pattern='both' if entropy and spike else 'entropy only' if entropy else 'spike only' if spike else 'neither',**m))
    # Preserve unrestricted browsing as a third exploratory sampling group.
    # Latest marks win per column; suggested spans are excluded to avoid counting twice.
    cache={}
    for path in sorted((OUT/'reviewer/quality_reviews').glob('*.json')):
        saved=read(path);sid=saved['scan_id'];b=saved['bscan']
        if saved['model_identity']!=q['model_identity']:raise ValueError('Rating/model identity mismatch')
        owner=np.full(saved['width'],-1,int)
        for i,r in enumerate(saved['records']):owner[r['lo']:r['hi']]=i
        for s in q['examples']:
            if s['scan_id']==sid and s['bscan']==b:owner[s['lo']:s['hi']]=-1
        if not np.any(owner>=0):continue
        if sid not in cache:
            base=OUT/'volumes'/sid
            cache[sid]=(npz(base/'measurements.npz'),npz(base/'diagnostics.npz'),npz(base/'geometry.npz'))
        d,z,g=cache[sid]
        edges=np.r_[0,np.flatnonzero(np.diff(owner)!=0)+1,len(owner)]
        for lo,hi in zip(edges[:-1],edges[1:]):
            if owner[lo]<0:continue
            r=saved['records'][owner[lo]];sl=np.s_[b,:,lo:hi]
            j=np.fmax(z['solid_jump_um'][sl],z['dashed_jump_um'][sl]);sp=np.fmax(z['solid_spike_um'][sl],z['dashed_spike_um'][sl])
            ep=stats(d['entropy'][sl])['p95'];sf=(stats(sp)['max'] or 0)>20;ef=ep>=entropy_cutoff
            paired.append(dict(scan_id=sid,bscan=b,lo=int(lo),hi=int(hi),sample_id=f'free-{b}-{lo}-{hi}',
                 role='free_browse',driver='user selected',rating=r['rating'],reasons=r['reason'],
                 rerated_after_metric_reveal=r.get('metrics_revealed_before',False),
                 entropy_flag=ef,spike_flag=sf,warning_pattern='both' if ef and sf else 'entropy only' if ef else 'spike only' if sf else 'neither',
                 entropy_median=stats(d['entropy'][sl])['median'],entropy_p95=ep,
                 signal_cnr_median=stats(g['local_cnr'][b,lo:hi])['median'],
                 solid_coverage=float(np.isfinite(d['reported_positions'][sl]).mean()),
                 dashed_coverage=float(np.isfinite(d['uncertain_estimates'][sl]).mean()),**warnings(j,sp)))
    summary=[]
    for role in ('random','targeted','free_browse'):
        selected=[r for r in paired if r['role']==role];counts=Counter(r['rating'] for r in selected)
        eligible=[r for r in selected if r['rating'] in ('Good','Bad') and not r['rerated_after_metric_reveal']]
        for metric in ('entropy_median','entropy_p95','jump_max_um','jump_p95_um','jump_gt20_fraction','spike_max_um','spike_p95_um','spike_gt20_fraction','signal_cnr_median','solid_coverage','dashed_coverage'):
            values=[np.nan if r[metric] is None else r[metric] for r in eligible]
            summary.append(dict(role=role,metric=metric,good=counts['Good'],bad=counts['Bad'],unsure=counts['Unsure'],unrated=counts['Unrated'],
                    eligible_blind_good_bad=len(eligible),auroc_bad_high_value=auc(values,[r['rating']=='Bad' for r in eligible]),
                    good_median=median([r[metric] for r in eligible if r['rating']=='Good']),
                    bad_median=median([r[metric] for r in eligible if r['rating']=='Bad'])))
    patterns=[]
    for role in ('random','targeted','free_browse'):
        for pattern in ('both','entropy only','spike only','neither'):
            c=Counter(r['rating'] for r in paired if r['role']==role and r['warning_pattern']==pattern)
            patterns.append(dict(role=role,warning_pattern=pattern,good=c['Good'],bad=c['Bad'],unsure=c['Unsure'],unrated=c['Unrated']))
    csvwrite(OUT/'reports/rating_pairs.csv',paired);csvwrite(OUT/'reports/metric_rating_comparison.csv',summary);csvwrite(OUT/'reports/entropy_spike_overlap.csv',patterns)
    counts=Counter(r['rating'] for r in paired if r['role']!='free_browse')
    free_count=sum(r['role']=='free_browse' for r in paired)
    lines=['# Regional human assessment', '',f"Suggested strips: {len(q['examples'])-counts['Unrated']}/{len(q['examples'])} rated; Good {counts['Good']}, Bad {counts['Bad']}, Unsure {counts['Unsure']}. Free-browsing portions: {free_count}.", '',
      'Random and targeted results are kept separate. Unsure is not treated as Good or Bad. AUROC is undefined until both Good and Bad judgments exist in a sampling group. Higher metric values predict Bad for the reported AUROC; the signal/coverage metrics can have the opposite association. No fitted metric or probability calibration is claimed.', '',
      'The entropy warning uses the fixed 75th percentile of all six volumes’ 64-column strip P95 entropy (%.6f), not a threshold tuned to ratings. The spike warning is a displayed-curve excursion >20 µm. entropy_spike_overlap.csv separates failures flagged by entropy only, spikes only, both, or neither.'%entropy_cutoff, '',
      'The blinded comparison excludes reratings after metric revelation, preserving them in rating_pairs.csv. Estimates are descriptive within this small, clustered six-volume pilot, not independent A-line statistics or a population failure rate. Free-browsing ratings have a separate exploratory group, with latest marks winning per column and suggested spans excluded to avoid double counting.', '',
      'No regional judgments have been collected yet; no metric success, failure rate, or optimization decision can be established.' if not any(r['rating']!='Unrated' for r in paired) else 'Review the paired rows and stated reasons before choosing reporting/candidate, positional, or obscuration work.']
    (OUT/'reports/HUMAN_ASSESSMENT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(lines[2])

def median(values):
    x=[v for v in values if v is not None and np.isfinite(v)]
    return float(np.median(x)) if x else None

if __name__=='__main__':run()
