"""Exact common-support comparisons and decoder-recovered crossing diagnostics."""
from collections import defaultdict
import json
import numpy as np
from .experiment import RUN, read_npz, scores
from stage_a.common import write_csv, write_json
from .ordered import crossing_flags
from stage_a.inference import thickness
from eight_surface.config import SURFACE_NAMES


def run():
    prep=json.loads((RUN/'prepared.json').read_text())
    pairs=[('epoch124_existing','ordered_only'),('epoch124_existing','readability_ordered'),
           ('simple_rule','readability_ordered'),('readability_only','readability_ordered')]
    accum=defaultdict(list); displacement=[]; regained=[]
    for r in prep['records']:
        if r['split']!='validation': continue
        t=read_npz(RUN/'cache'/(r['key']+'.npz'))
        cache={m:read_npz(RUN/'measurements'/m/(r['key']+'.npz')) for m in {m for pair in pairs for m in pair}}
        for ma,mb in pairs:
            a,b=cache[ma],cache[mb]
            both=a['retained']&b['retained']&t['valid']
            ea=(a['canonical_retained_rows']-t['truth'])*r['px_um']
            eb=(b['canonical_retained_rows']-t['truth'])*r['px_um']
            for k,name in enumerate(SURFACE_NAMES):
                accum[ma,mb,'boundary',name].append((ea[k,both[k]],eb[k,both[k]]))
            accum[ma,mb,'boundary','ALL'].append((ea[both],eb[both]))
            truth=thickness(t['truth'],t['valid'],r['px_um'])
            for k,name in enumerate(a['thickness_names'].astype(str)):
                ta,tb=a['experimental_thickness_um'][k],b['experimental_thickness_um'][k]
                valid=np.isfinite(truth[name])&np.isfinite(ta)&np.isfinite(tb)
                accum[ma,mb,'thickness',name].append((ta[valid]-truth[name][valid],tb[valid]-truth[name][valid]))
        base,ordered=cache['epoch124_existing'],cache['ordered_only']
        new=ordered['retained']&~base['retained']&t['valid']
        err=abs(ordered['canonical_retained_rows']-t['truth'])*r['px_um']
        regained.append(dict(key=r['key'],newly_retained_supported=int(new.sum()),
            gross_newly_retained=int((new&(err>25)).sum()),new_absolute_error_sum=float(err[new].sum()),
            raw_crossing_on_ordered_retained=int((crossing_flags(t['raw_rows'])&ordered['retained']).sum()),
            ordered_retained=int(ordered['retained'].sum())))
    rows=[]
    for (a,b,kind,name),parts in accum.items():
        ea,eb=[np.concatenate([p[k] for p in parts]).astype(float) for k in (0,1)]
        row=dict(method_a=a,method_b=b,kind=kind,name=name,n_common=len(ea))
        for suffix,e in [('a',ea),('b',eb)]:
            row.update({f'median_{suffix}':float(np.median(abs(e))) if len(e) else None,
                f'p95_{suffix}':float(np.quantile(abs(e),.95)) if len(e) else None,
                f'mae_{suffix}':float(np.mean(abs(e))) if len(e) else None,
                f'gross_{suffix}':int((abs(e)>25).sum())})
        row.update(improved_gt1um=int((abs(eb)<abs(ea)-1).sum()),worsened_gt1um=int((abs(eb)>abs(ea)+1).sum()))
        rows.append(row)
    write_csv(RUN/'paired_common_support.csv',rows)
    write_csv(RUN/'ordered_newly_retained.csv',regained)
    write_json(RUN/'paired_complete.json',dict(exact_common_support=True,comparisons=len(pairs),
        paired_rows=len(rows),note='A and B use identical eligible endpoint/column sets within each row; no approximate coverage matching.'))
    # Keep PyTorch inference separate from the figure-rendering process: the
    # installed plotting/scientific and Torch stacks load conflicting OpenMP DLLs.
    plan=json.loads((RUN/'PRESPECIFIED_PLAN.json').read_text())
    vals=scores(prep,plan)
    for split in ('train','validation'):
        records=[r for r in prep['records'] if r['split']==split]
        np.savez_compressed(RUN/f'readability_scores_{split}.npz',
            target=np.concatenate([vals[r['key']]['data']['readability_target'] for r in records]),
            score=np.concatenate([1.-vals[r['key']]['learned'] for r in records]))


if __name__=='__main__': run()
