"""Frozen-array withholding experiment; no training, no package mutation."""
import json
import hashlib
from pathlib import Path
import numpy as np
import readability_helpers_snapshot as rd
from stage_a.common import write_json, write_csv, verify, fingerprint

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
V2 = ROOT / 'outputs/stage_a/20260908_v2'
V3 = ROOT / 'outputs/stage_a/20260908_v3_readability'
EVAL = {'train': V3/'eval_train', 'validation': V2/'dev_seed20260908/eval_validation'}

def package_hash():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'code/stage_a').glob('*.py'))}

def fstat():
    # Metadata inventory only; never open final-test arrays.
    return {str(p.relative_to(ROOT)): [p.stat().st_size, p.stat().st_mtime_ns]
            for folder in (V2, V3) for p in folder.rglob('*') if p.is_file()}

def ratio(a, b):
    return float(a/b) if b else None

def metrics(ret, D, mask):
    hp, valid, hn = D['human_positive'][mask], D['valid'][mask], D['human_negative'][mask]
    r, base, ae = ret[mask], D['existing_retained'][mask], D['abs_err_um'][mask]
    score = hp & r & np.isfinite(ae)
    errs = ae[score]
    failure = score & (ae > 25)
    longest = max(rd._runs_in_groups(failure[:, k], D['key_idx'][mask]) for k in range(8))
    return dict(n_columns=int(mask.sum()), supported_total=int(hp.sum()),
        supported_retained=int((hp & r).sum()), supported_coverage=ratio((hp&r).sum(), hp.sum()),
        supported_withheld=int((hp & ~r).sum()),
        additional_supported_lost=int((hp & base & ~r).sum()),
        additional_alines_affected=int((base & ~r).any(1).sum()),
        additional_surface_columns_lost=int((base & ~r).sum()),
        legacy_valid_coverage=ratio((valid&r).sum(), valid.sum()),
        unreadable_total_surface_columns=int(hn.sum()*8),
        unreadable_measured=int(r[hn].sum()), unreadable_leakage=ratio(r[hn].sum(), hn.sum()*8),
        retained_p95_um=float(np.quantile(errs,.95)) if errs.size else None,
        retained_median_um=float(np.median(errs)) if errs.size else None,
        retained_gross_fraction=ratio((errs>25).sum(), errs.size),
        longest_gross_run=longest)

def crossing_counts(reason, retained):
    flag=(reason & 8)!=0; count=flag.sum(1); cross=count>0
    fully=~retained.any(1); scope_shadow=((reason & 3)!=0).all(1)
    return dict(n_alines=len(reason), crossing_alines=int(cross.sum()),
        crossing_fraction=ratio(cross.sum(),len(reason)), crossing_surface_columns=int(flag.sum()),
        already_fully_withheld=int((cross&fully).sum()),
        already_scope_or_shadow_withheld=int((cross&scope_shadow).sum()),
        newly_fully_withheld=int((cross&~fully).sum()),
        crossing_currently_fully_retained=int((cross&retained.all(1)).sum()),
        additional_surface_columns_lost=int(retained[cross].sum()),
        **{f'flagged_{i}_surfaces':int((count==i).sum()) for i in range(1,9)})

def match_score(score, target_count, D, mask):
    """Descriptive closest attainable supported count; ties kept together."""
    weights=(D['human_positive'] & D['existing_retained']).sum(1)
    s=score[mask]; w=weights[mask]
    vals, inv=np.unique(s,return_inverse=True)
    cum=np.cumsum(np.bincount(inv,weights=w,minlength=len(vals)))
    opts=np.r_[0,cum]
    idx=int(np.argmin(np.abs(opts-target_count)))
    threshold=-np.inf if idx==0 else vals[idx-1]
    return D['existing_retained'] & (score<=threshold)[:,None], float(threshold)

def main():
    before=fstat(); pkg=package_hash()
    write_json(OUT/'integrity_before.json',dict(files=before,package_hashes=pkg))
    D=rd.load_npz(V3/'features/columns.npz')
    manifest=json.loads((V2/'manifest.json').read_text())
    part=json.loads((V2/'partitions.json').read_text())
    cache=json.loads((V2/'cache_manifest.json').read_text())
    records={r['key']:r for r in manifest['records']}
    allowed=set(rd.TRAIN_ANIMALS+rd.VAL_ANIMALS)
    assert set(D['animal']) <= allowed
    assert not set(part['animals']['test']) & allowed
    n=len(D['key_idx']); reason=np.zeros((n,8),np.uint8); rows=np.zeros((n,8))
    qc=np.empty(n,dtype='U20'); col=np.empty(n,int)
    fps=[]; per=[]
    for i,key in enumerate(D['keys'].astype(str)):
        rec=records[key]; ix=np.flatnonzero(D['key_idx']==i)
        sp=str(D['split'][ix[0]])
        assert rec['animal'] in part['animals'][sp] and rec['animal'] in allowed
        path=EVAL[sp]/f'{key}.npz'; p=rd.load_npz(path)
        verify(rec['targets_fingerprint'])
        target=rd.load_npz(rec['targets'])
        hp,hn=rd._supervision_categories(target['reason_bits'])
        assert np.array_equal(hp.T,D['human_positive'][ix])
        assert np.array_equal(hn[0],D['human_negative'][ix])
        assert np.array_equal(p['retained'].T,D['existing_retained'][ix])
        reason[ix]=p['reason_bits'].T; rows[ix]=p['rows'].T
        qc[ix]=rec['qc_group']; col[ix]=np.arange(len(ix))
        assert np.array_equal(reason[ix]==0,D['existing_retained'][ix])
        fps.append(fingerprint(path))
        per.append(dict(key=key,split=sp,animal=rec['animal'],qc_group=rec['qc_group'],
                        **crossing_counts(reason[ix],D['existing_retained'][ix])))
    D['reason']=reason; D['qc']=qc; D['column']=col; D['rows']=rows
    write_csv(OUT/'crossing_by_bscan.csv',per)
    groups=[('pooled','all',np.ones(n,bool))]
    groups += [('split',s,D['split']==s) for s in ('train','validation')]
    groups += [('animal',s,D['animal']==s) for s in sorted(set(D['animal']))]
    groups += [('qc',s,qc==s) for s in sorted(set(qc))]
    grouped=[dict(group=g,value=str(v),**crossing_counts(reason[m],D['existing_retained'][m]))
             for g,v,m in groups]
    volreason=[]; volret=[]
    volpaths=sorted((V2/'dev_seed20260908/volume_TS165').glob('b*.npz'))
    assert len(volpaths)==512
    for path in volpaths:
        with np.load(path,allow_pickle=False) as p:
            volreason.append(p['reason_bits'].T); volret.append(p['retained'].T)
    grouped.append(dict(group='volume',value='TS165_training_WT',
                        **crossing_counts(np.concatenate(volreason),np.concatenate(volret))))
    write_csv(OUT/'crossing_summary.csv',grouped)
    write_json(OUT/'crossing_summary.json',grouped)

    # Reproduce frozen feature score exactly; no fitting on validation.
    F=np.where(np.isfinite(D['features']),D['features'],0.).astype(float)
    tr=D['split']=='train'; va=D['split']=='validation'
    mu=F[tr].mean(0); sd=F[tr].std(0)+1e-9; Z=(F-mu)/sd
    fi={str(v):i for i,v in enumerate(D['feature_names'])}
    simple=Z[:,fi['entropy_mean']]+Z[:,fi['entropy_max']]-Z[:,fi['cnr']]+Z[:,fi['band_lowsig_frac']]
    entropy=Z[:,fi['entropy_max']]
    thresholds={str(q):float(np.quantile(simple[tr&D['valid'].all(1)],q)) for q in (.94,.96)}
    hn=D['human_negative']; shadow=((reason&2)!=0).any(1); cross=((reason&8)!=0).any(1)
    scope=((reason&1)!=0).any(1); misses=hn&~shadow
    nothing=hn&~shadow&~scope&~cross
    overlap=[]
    for g,v,m in groups:
        for label,sel in [('shadow_miss',misses),('caught_by_nothing',nothing),
                          ('manual_crossing_overlap',hn&cross)]:
            a=sel&m
            overlap.append(dict(group=g,value=str(v),category=label,n=int(a.sum()),
                existing_fully_withheld=int((a&~D['existing_retained'].any(1)).sum()),
                existing_partially_withheld=int((a&D['existing_retained'].any(1)&~D['existing_retained'].all(1)).sum()),
                existing_fully_retained=int((a&D['existing_retained'].all(1)).sum()),
                edge32_count=int((a&((col<32)|(col>=480))).sum()),
                **{f'caught_q{q}':int((a&(simple>t)).sum()) for q,t in thresholds.items()}))
    write_csv(OUT/'shadow_overlap.csv',overlap)
    dist=[]
    categories={'manual_shadow_miss':misses,'manual_shadow_detected':hn&shadow,
        'human_positive_all8':D['human_positive'].all(1),
        'supported_shadow_exclusion':shadow&D['human_positive'].any(1),
        'manual_nothing_caught':nothing}
    for g,v,m in groups:
        for label,sel in categories.items():
            for name in ('cnr','band_lowsig_frac','col_energy_z','band_grad_p90','neigh_corr'):
                x=D['features'][m&sel,fi[name]]; x=x[np.isfinite(x)]
                qs=np.quantile(x,[.1,.25,.5,.75,.9]).tolist() if len(x) else [None]*5
                dist.append(dict(group=g,value=str(v),category=label,feature=name,n=len(x),
                    **dict(zip(['p10','p25','median','p75','p90'],qs))))
    write_csv(OUT/'shadow_feature_distributions.csv',dist)

    base=D['existing_retained']; count=((reason&8)!=0).sum(1)
    candidates={'existing':base,'whole_crossing':base&~cross[:,None]}
    # All-pair inversion spans, including nonadjacent crossings absent from existing rule.
    span=np.zeros_like(base)
    for i in range(8):
        for j in range(i+1,8):
            bad=np.isfinite(rows[:,i])&np.isfinite(rows[:,j])&(rows[:,i]>rows[:,j])
            span[:,i:j+1] |= bad[:,None]
    candidates['inversion_span']=base&~span
    for k in (4,6,8):
        candidates[f'whole_crossing_count_ge{k}']=base&~(count>=k)[:,None]
    for q,t in thresholds.items():
        candidates[f'simple_q{q}']=base&~(simple>t)[:,None]
    assert all(not np.any(r&~base) for r in candidates.values())
    results=[]
    for name,ret in candidates.items():
        for g,v,m in groups:
            results.append(dict(method=name,group=g,value=str(v),**metrics(ret,D,m)))
    write_csv(OUT/'candidate_metrics.csv',results)
    write_json(OUT/'candidate_metrics.json',results)

    # Exact denominator and closest achievable tie-respecting match. No operating
    # point selected on held-out errors. Quantiles above remain train-only.
    matched=[]
    for name,ret in candidates.items():
        if name=='existing' or name.startswith('simple'): continue
        for sp,m in [('train',tr),('validation',va)]:
            target=int((D['human_positive'][m]&ret[m]).sum())
            own=metrics(ret,D,m)
            for label,scr in [('simple_entropy_signal',simple),('entropy_max',entropy)]:
                r,t=match_score(scr,target,D,m); cmp=metrics(r,D,m)
                matched.append(dict(candidate=name,split=sp,comparator=label,
                    threshold=t if np.isfinite(t) else None,
                    candidate_supported_count=target,comparator_supported_count=cmp['supported_retained'],
                    count_mismatch=cmp['supported_retained']-target,
                    candidate_coverage=own['supported_coverage'],comparator_coverage=cmp['supported_coverage'],
                    candidate_leakage=own['unreadable_leakage'],comparator_leakage=cmp['unreadable_leakage'],
                    candidate_p95=own['retained_p95_um'],comparator_p95=cmp['retained_p95_um'],
                    candidate_run=own['longest_gross_run'],comparator_run=cmp['longest_gross_run']))
    write_csv(OUT/'matched_supported_coverage.csv',matched)
    write_json(OUT/'matched_supported_coverage.json',matched)

    # Small machine-readable output for independent checks and review generation.
    np.savez_compressed(OUT/'analysis_arrays.npz',reason=reason,rows=rows,qc=qc,column=col,
        simple_score=simple,entropy_score=entropy,**{f'retained_{k}':v for k,v in candidates.items()})
    write_json(OUT/'score_definition.json',dict(feature_names=D['feature_names'].tolist(),
        train_mean=mu.tolist(),train_sd=sd.tolist(),thresholds=thresholds,
        calibration='Frozen v3 train-valid-all8 quantiles; exploratory only',
        matching='Closest attainable human_positive surface-column count, including shadowed support; descriptive only'))
    write_json(OUT/'input_fingerprints.json',fps+[fingerprint(V3/'features/columns.npz'),
        fingerprint(V2/'dev_seed20260908/best.pt')])
    after=fstat()
    assert before==after,'Frozen artifact metadata changed during investigation'
    assert pkg==package_hash(),'Training package changed during investigation'
    write_json(OUT/'integrity_after_analysis.json',dict(frozen_files_unchanged=before==after,
        training_package_unchanged=pkg==package_hash(),dataset_id=manifest['dataset_id'],
        partition_id=part['partition_id'],labels_manifest_count=len(manifest['records']),
        packs_manifest_count=len(manifest['sources']),
        footprints_manifest_count=sum(s['footprint'] is not None for s in manifest['sources'].values()),
        final_test_arrays_read=False,repeatability_data_read=False,
        full_label_integrity_reverified=False,
        note='All 110 selected train/validation target fingerprints verified. Frozen file size/mtime inventory unchanged; final-test arrays not opened.'))
    print(json.dumps({'crossings':grouped[:3]+grouped[-1:],
        'overlap':[r for r in overlap if r['group']=='pooled'],
        'validation':[r for r in results if r['group']=='split' and r['value']=='validation']},indent=2))

if __name__=='__main__':
    main()
