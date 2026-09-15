"""Read explicit scan ratings; no label writes, calibration or composite score."""
from batch import *

def compare():
    from scipy.stats import spearmanr
    rows=csvread(OUT/'qualitative_ratings.csv');source=fingerprint(OUT/'qualitative_ratings.csv')
    scans=csvread(OUT/'scan_qc.csv') if (OUT/'scan_qc.csv').exists() else []
    pairs=[];invalid=[];byid={r['scan_id']:r for r in scans};seen=set()
    for r in rows:
        if r['scan_id'] in seen:raise ValueError('Multiple rating rows for '+r['scan_id'])
        seen.add(r['scan_id'])
        rating=r.get('rating','').strip()
        if rating not in ('','Good','Usable','Poor','Unsure'):invalid.append(r);continue
        if rating and r['scan_id'] in byid:
            pairs.append({**byid[r['scan_id']],**r,'rating':rating})
    folder=OUT/'ratings_comparison';folder.mkdir(exist_ok=True)
    csvwrite(folder/'paired_ratings.csv',pairs,fields=list(dict.fromkeys(k for r in pairs for k in r)) or ['scan_id','rating'])
    csvwrite(folder/'invalid_ratings.csv',invalid,fields=list(rows[0]) if rows else ['scan_id','rating'])
    metrics=['retina_cnr','retina_vitreous_contrast','low_signal_frac','bscan_discontinuity_p95','brightness_stripe_power_frac','brightness_stripe_mad','axial_centroid_jump_p95_px','axial_centroid_residual_p95_px','repeat_disagreement','shadow_native_pct','model_reported_native_pct','model_uncertain_native_pct','model_not_traceable_native_pct']
    # Add boundary-specific support and irregularity independently; no pooled score.
    if (OUT/'boundary_qc.csv').exists():
        lookup={p['scan_id']:p for p in pairs}
        for b in csvread(OUT/'boundary_qc.csv'):
            if b['scan_id'] not in lookup:continue
            for key in ['entropy_eligible_median','model_traceability_eligible_median','model_reliability_eligible_median','raw_um_aline_abs_jump_p95','raw_um_bscan_abs_jump_p95','reported_um_aline_abs_jump_p95','reported_um_bscan_abs_jump_p95']:
                name=b['boundary']+'__'+key;lookup[b['scan_id']][name]=b.get(key,'')
                if name not in metrics:metrics.append(name)
    if (OUT/'layer_qc.csv').exists():
        lookup={p['scan_id']:p for p in pairs}
        for layer in csvread(OUT/'layer_qc.csv'):
            if layer['scan_id'] not in lookup or layer.get('segmentation_status')=='unavailable':continue
            for policy in ['segmentation_','preliminary_']:
                for suffix in ['coverage_eligible_pct','median','sd','iqr','aline_abs_jump_p95','bscan_abs_jump_p95']:
                    key=policy+suffix
                    if not layer.get(key):continue
                    name=layer['layer']+'__'+key;lookup[layer['scan_id']][name]=layer[key]
                    if name not in metrics:metrics.append(name)
    csvwrite(folder/'paired_ratings.csv',pairs,fields=list(dict.fromkeys(k for r in pairs for k in r)) or ['scan_id','rating'])
    ordered={'Poor':0,'Usable':1,'Good':2};results=[];distributions=[];rng=np.random.default_rng(20260910)
    from qc import stats
    for metric in metrics:
        data=[]
        for p in pairs:
            try:value=float(p.get(metric,''))
            except (ValueError,TypeError):continue
            if np.isfinite(value):data.append((p['animal'],p['rating'],value))
        for rating in ['Poor','Usable','Good','Unsure']:
            values=[v for a,r,v in data if r==rating]
            distributions.append(dict(metric=metric,rating=rating,animal_n=len({a for a,r,v in data if r==rating}),**stats(values)))
        used=[d for d in data if d[1] in ordered];animals=sorted({d[0] for d in used});labels={d[1] for d in used}
        def rho(items):
            x=np.array([ordered[i[1]] for i in items]);y=np.array([i[2] for i in items])
            return float(spearmanr(x,y).statistic) if len(set(x))>1 and len(set(y))>1 else np.nan
        rr=rho(used);boot=[]
        if len(animals)>=3 and len(labels)>=2:
            groups={a:[d for d in used if d[0]==a] for a in animals}
            for _ in range(1000):
                sampled=[d for a in rng.choice(animals,len(animals),replace=True) for d in groups[a]];val=rho(sampled)
                if np.isfinite(val):boot.append(val)
        interval=np.percentile(boot,[2.5,97.5]).tolist() if len(boot)>=200 else [None,None]
        results.append(dict(metric=metric,ordered_scan_n=len(used),animal_n=len(animals),ordered_category_n=len(labels),unsure_n=sum(r=='Unsure' for a,r,v in data),spearman_rho=rr if np.isfinite(rr) else None,animal_cluster_bootstrap_lo=interval[0],animal_cluster_bootstrap_hi=interval[1],valid_bootstrap_n=len(boot),warning='sparse: fewer than 5 animals or fewer than 5 scans in an ordered category' if len(animals)<5 or any(sum(d[1]==r for d in used)<5 for r in ordered) else 'exploratory association; repeated acquisitions clustered by animal'))
    csvwrite(folder/'associations.csv',results);csvwrite(folder/'distributions.csv',distributions)
    if pairs:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        for start in range(0,len(metrics),12):
            fig,axes=plt.subplots(3,4,figsize=(17,11),layout='constrained')
            for ax,metric in zip(axes.ravel(),metrics[start:start+12]):
                for j,rating in enumerate(['Poor','Usable','Good','Unsure']):
                    vals=[]
                    for p in pairs:
                        if p['rating']!=rating:continue
                        try:val=float(p.get(metric,''))
                        except (ValueError,TypeError):continue
                        if np.isfinite(val):vals.append(val)
                    if vals:ax.scatter(j+rng.uniform(-.12,.12,len(vals)),vals,s=18,alpha=.7)
                ax.set_xticks(range(4),['Poor','Usable','Good','Unsure']);ax.set_title(metric.replace('__','\n'),fontsize=8)
            for ax in axes.ravel()[len(metrics[start:start+12]):]:ax.axis('off')
            fig.savefig(folder/f'metric_distributions_{start//12+1:02d}.png',dpi=130);plt.close(fig)
    text=f'''# Comparison with explicit scan-quality ratings

Completed scans with explicit ratings: {len(pairs)}. Unrated rows: {sum(not r.get('rating','').strip() for r in rows)}. Invalid rating rows: {len(invalid)}.

{'No compatible explicit whole-scan ratings are available. Batch processing is independent of ratings; enter Good / Usable / Poor / Unsure and comments in qualitative_ratings.csv, then run BATCH.cmd aggregate.' if not pairs else 'See distributions.csv, associations.csv and metric_distributions figures. Unsure is a separate group; Spearman uses Poor=0, Usable=1, Good=2. Intervals resample whole animals, retaining their repeated acquisitions.'}

Existing pilot GUI records rate Good/Bad/Unsure B-scan strips, not whole scans. They are not converted to the requested scan categories. Generic segmentation verdicts and prior numeric rankings are not ratings. No combined score, threshold fitting or scan exclusion is performed. Sparse ratings and sparse animal support are explicitly flagged. Associations are exploratory and do not validate segmentation accuracy.
'''
    (folder/'REPORT.md').write_text(text,encoding='utf-8');write(folder/'provenance.json',dict(ratings=source,paired=len(pairs),existing_rating_search='Repository quality-review workflow uses regional Good/Bad/Unsure only; no compatible explicit whole-scan rating file found. No automatic conversion.'))

if __name__=='__main__':compare()
