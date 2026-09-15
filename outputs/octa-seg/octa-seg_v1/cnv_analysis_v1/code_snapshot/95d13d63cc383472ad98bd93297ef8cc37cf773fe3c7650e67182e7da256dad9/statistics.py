"""Equal repeats -> visits -> tracked lesions -> eyes -> animals, with cluster CIs."""
import numpy as np
import pandas as pd

def balanced(table,group):
    if table.empty: return pd.DataFrame()
    d=table.copy()
    d=d[d.identity_eligible.astype(bool)&d.normalized_eligible.astype(bool)&d.post_d0.astype(bool)]
    d=d[np.isfinite(d.mean_thickness_um)]
    if d.empty: return pd.DataFrame()
    # A repeated acquisition cannot contribute twice, even if accidentally imported twice.
    d=d.drop_duplicates(['scan_id','lesion_id','layer','band','distance_basis','region_definition'])
    keys=list(dict.fromkeys(group+['animal','eye','track_id','visit_id']))
    repeats=d.groupby(keys,dropna=False).mean_thickness_um.mean().reset_index()
    visits=repeats.groupby(list(dict.fromkeys(group+['animal','eye','track_id'])),dropna=False).mean_thickness_um.mean().reset_index()
    lesions=visits.groupby(list(dict.fromkeys(group+['animal','eye'])),dropna=False).mean_thickness_um.mean().reset_index()
    animals=lesions.groupby(list(dict.fromkeys(group+['animal'])),dropna=False).mean_thickness_um.mean().reset_index()
    count=d.groupby(list(dict.fromkeys(group+['animal'])),dropna=False).agg(
        n_lesions=('track_id','nunique'),n_visits=('visit_id','nunique'),n_scans=('scan_id','nunique')).reset_index()
    return animals.merge(count,on=list(dict.fromkeys(group+['animal'])))

def cohort(animals,group,n_boot=2000,seed=417):
    if animals.empty: return pd.DataFrame()
    rng=np.random.default_rng(seed); records=[]
    # Shared cluster draws across all panels preserve the animal cluster.
    ids=sorted(animals.animal.unique()); draws=rng.choice(ids,(n_boot,len(ids)),replace=True)
    for key,g in animals.groupby(group,dropna=False):
        if not isinstance(key,tuple): key=(key,)
        values=dict(zip(g.animal,g.mean_thickness_um))
        estimate=float(g.mean_thickness_um.mean())
        bootstrap=[]
        if len(g)>=2:
            for sample in draws:
                selected=[values[i] for i in sample if i in values]
                if selected: bootstrap.append(np.mean(selected))
        lo,hi=np.percentile(bootstrap,[2.5,97.5]) if bootstrap else (np.nan,np.nan)
        records.append(dict(zip(group,key),mean_thickness_um=estimate,ci_low_um=lo,ci_high_um=hi,
                            n_animals=len(g),n_lesions=int(g.n_lesions.sum()),
                            n_animal_visits=int(g.n_visits.sum()),animals=';'.join(sorted(g.animal))))
    return pd.DataFrame(records)
