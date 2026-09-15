"""Measured duration comparison, volume checks, and standalone research figures."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from eight_surface.config import SURFACE_NAMES
from stage_a.common import write_json, write_csv

HERE=Path(__file__).resolve().parent
RUN=HERE/'dev_seed20260908'
OLD=HERE.parent/'20260908_v2/dev_seed20260908'
OLD3=HERE.parent/'20260908_v3_readability'
def readcsv(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def readjson(p):return json.loads(p.read_text())

summary=readjson(RUN/'training_summary.json')
epochs=readcsv(RUN/'training_history_epochs.csv')
fig,ax=plt.subplots(figsize=(9,4.5),layout='constrained')
x=[int(r['epoch']) for r in epochs]
ax.plot(x,[float(r['train_loss']) for r in epochs],label='Mean sampled training loss',lw=1)
ax.plot(x,[float(r['validation_loss']) for r in epochs],label='Animal-macro development-validation loss',lw=1)
ax.axvline(40,c='gray',ls='--',lw=1,label='Previous budget: 40 epochs')
ax.scatter(summary['best']['epoch'],summary['best']['validation_loss'],c='black',s=35,zorder=4,label='Selected checkpoint')
ax.set(xlabel='Epoch',ylabel='Loss',title='Fixed configuration, longer training | development experiment')
ax.legend(fontsize=8)
fig.savefig(RUN/'training_curve.png',dpi=160)
plt.close(fig)

reports={name:readjson(path/'metrics.json') for name,path in (
    ('unet_40',OLD/'eval_validation'),('unet_long',RUN/'eval_validation'),
    ('stored_auto',HERE/'baseline_validation'),('classical_v2',HERE/'v2_validation'))}
raw=[]
for name,r in reports.items():
    raw.extend(dict(predictor=name,**s) for s in r['summary'] if s['axis']=='pooled' and s['mode']=='raw')
write_csv(RUN/'headline_raw_metrics.csv',raw)
baseline_reproduced={}
for name,folder in (('stored_auto','baseline_validation'),('classical_v2','v2_validation')):
    old=readjson(HERE.parent/'20260908_v2'/folder/'metrics.json')
    baseline_reproduced[name]=old['summary']==reports[name]['summary'] and old['failures']==reports[name]['failures']
    assert baseline_reproduced[name]

catkey='TS325_OD_2026-05-26_6mo_s01_112940_b0510'
localized={name:readcsv(path/'review_validation/per_bscan_localized_failure.csv') for name,path in (('unet_40',OLD),('unet_long',RUN))}
catastrophic={name:next(r for r in rows if r['key']==catkey) for name,rows in localized.items()}
worst={name:sorted(rows,key=lambda r:(-int(r['longest_gross_columns']),-float(r['max_abs_um'])))[:4] for name,rows in localized.items()}

def volume_metrics(folder):
    job=readjson(folder/'inference.json')
    assert job['full_volume_complete'] and len(job['completed_bscans'])==512
    counts=dict(boundary_columns=0,retained=0,crossing=0,shadow=0,outside_scope=0)
    fractions=[];roundtrip=0.
    for b in job['completed_bscans']:
        with np.load(folder/f'b{b:04d}.npz',allow_pickle=False) as p:
            bits=p['reason_bits'];kept=p['retained'];rows=p['canonical_rows']
            assert np.array_equal(kept,bits==0)
            assert np.isnan(p['retained_rows'][~kept]).all()
            assert np.array_equal(p['retained_rows'][kept],rows[kept])
            assert np.isnan(p['validated_thickness_um']).all() and not bool(p['validated'])
            depth=int(p['native_shape'][2])
            back=depth-1-p['disk_rows'] if bool(p['vitreous_high']) else p['disk_rows']
            roundtrip=max(roundtrip,float(np.max(np.abs(back-rows))))
            names=list(p['surface_names'].astype(str));bands=list(p['thickness_names'].astype(str))
            from eight_surface.config import LAYER_DEFS
            for band,top,bottom in LAYER_DEFS:
                i,j=names.index(top),names.index(bottom)
                good=kept[i]&kept[j]&np.isfinite(rows[i])&np.isfinite(rows[j])&(rows[j]>=rows[i])
                values=p['experimental_thickness_um'][bands.index(band)]
                assert np.isnan(values[~good]).all()
                assert np.isfinite(values[good]).all()
            counts['boundary_columns']+=bits.size
            counts['retained']+=int(kept.sum())
            for reason,bit in (('crossing',8),('shadow',2),('outside_scope',1)):
                counts[reason]+=int(((bits&bit)!=0).sum())
            fractions.append(float(((bits&8)!=0).mean()))
    return dict(**counts,bscans=512,bscans_with_crossing=sum(f>0 for f in fractions),
        crossing_fraction=counts['crossing']/counts['boundary_columns'],
        bscan_crossing_median=float(np.median(fractions)),bscan_crossing_p90=float(np.quantile(fractions,.9)),
        bscan_crossing_max=max(fractions),roundtrip_max_px=roundtrip,
        retained_mask_exact=True,withheld_rows_nan=True,experimental_thickness_endpoint_checks=True,
        validated_thickness_all_nan=True,orientation_detected=job['orientation_detected'],
        checkpoint=job['job']['checkpoint'])

volumes={name:volume_metrics(path/'volume_TS165') for name,path in (('unet_40',OLD),('unet_long',RUN))}
write_json(RUN/'volume_verification.json',volumes)

matched={name:readjson(path/'compare/matched_coverage.json') for name,path in (('unet_40',OLD3),('unet_long',HERE))}
coefficients={name:readjson(path/'compare/compare_meta.json')['learned_coefficients'] for name,path in (('unet_40',OLD3),('unet_long',HERE))}
entropy={name:readcsv(path/'review_validation/entropy_error_analysis.csv') for name,path in (('unet_40',OLD),('unet_long',RUN))}
manifest=readjson(HERE.parent/'20260908_v2/manifest.json')
records=[r for r in manifest['records'] if r['animal'] in ('TS169','TS325','TS336') and r['key']!=catkey]
sensitivity=[]
for name,folder in (('unet_40',OLD/'eval_validation'),('unet_long',RUN/'eval_validation')):
    errors=[[] for _ in SURFACE_NAMES]
    for r in records:
        with np.load(r['targets'],allow_pickle=False) as t,np.load(folder/f"{r['key']}.npz",allow_pickle=False) as p:
            err=np.abs((p['rows']-t['rows_label'])*r['px_um'])
            for k in range(len(SURFACE_NAMES)): errors[k].extend(err[k][t['valid'][k]].tolist())
    for n,values in zip(SURFACE_NAMES,errors):
        a=np.array(values)
        sensitivity.append(dict(predictor=name,surface=n,n_columns=len(a),median_abs_um=float(np.median(a)),
            p95_abs_um=float(np.quantile(a,.95)),gross_fraction=float((a>25).mean())))
write_csv(RUN/'sensitivity_without_b0510.csv',sensitivity)
result=dict(baselines_reproduced=baseline_reproduced,catastrophic_bscan=catastrophic,worst_bscans=worst,
    volumes=volumes,readability_matched=matched,readability_coefficients=coefficients,entropy_error=entropy)
write_json(RUN/'analysis_summary.json',result)
print(json.dumps(dict(baselines_reproduced=baseline_reproduced,catastrophic_bscan=catastrophic,
    volume_crossing_fraction={k:v['crossing_fraction'] for k,v in volumes.items()}),indent=2))
