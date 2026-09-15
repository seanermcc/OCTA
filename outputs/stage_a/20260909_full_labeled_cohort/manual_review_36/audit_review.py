"""Read-only label audit and review figures; never calls a label writer."""
from pathlib import Path
from collections import Counter
import csv, hashlib, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from eight_surface.labels import load_label
from eight_surface import provenance as P

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'audit'
OUT.mkdir(exist_ok=True)
files = sorted((ROOT / 'labels').glob('*.npz'))
before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
records = {p.stem: load_label(p) for p in files}
rows, expected = [], []
packs = {}
for p in sorted((ROOT.parent / 'review_queue/packs').glob('*.npz')):
    with np.load(p, allow_pickle=False) as d:
        packs[p.stem.removesuffix('_pack')] = {k:d[k].copy() for k in ['images','bscan_index','shadow','surface_names']}
    expected.extend(f'{p.stem.removesuffix("_pack")}_b{int(b):04d}' for b in packs[p.stem.removesuffix('_pack')]['bscan_index'])
for key, r in records.items():
    draw=r['local_drawn']; vis=P.record_visibility(r); rel=P.record_reliability(r)
    valid=P.local_position_valid(r) & ~r['local_displaced']
    sid,b=key.rsplit('_b',1); pack=packs[sid]; i=list(pack['bscan_index']).index(int(b))
    valid &= ~pack['shadow'][i][None,:]
    valid &= np.isfinite(r['surfaces']) & (r['surfaces']>=0) & (r['surfaces']<pack['images'].shape[1])
    if r['verdict']!='corrected': valid[:]=False
    rows.append(dict(key=key,verdict=r['verdict'],strokes=int(r['n_strokes']),
        drawn=int(draw.sum()),drawn_unreliable=int((draw&(rel==2)).sum()),
        drawn_unidentifiable=int((draw&(vis==2)).sum()),drawn_displaced=int((draw&r['local_displaced']).sum()),
        excluded_columns=int(r['region_excluded'].sum()),candidate_position_columns=int(valid.sum())))
with (OUT/'label_audit.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary=dict(saved=len(files),expected=len(expected),missing=sorted(set(expected)-set(records)),
    verdicts=dict(Counter(r['verdict'] for r in rows)),
    totals={k:sum(r[k] for r in rows) for k in list(rows[0])[2:]},
    count_unit='Boundary-column positions, not independent annotations; categories overlap.',
    candidate_policy='Corrected verdict, direct non-displaced stroke, no visibility/reliability denial, no image exclusion/shadow, finite in-image position. Candidate evidence, not independently established accuracy.')
selected=[
 'TS165_OS_2025-04-29_WT_s02_121711_b0080',
 'TS247_OD_2024-11-06_D21_s03_104157_b0131',
 'TS283_OD_2025-01-29_D7_s02_123712_b0089',
 'TS325_OD_2026-05-26_6mo_s01_112940_b0106']
colors=['#00ffff','#ffad33','#ff55dd','#99ff33','#aa88ff','#ffff55','#ff7777','#ffffff']
for key in selected:
    r=records[key];sid,b=key.rsplit('_b',1);p=packs[sid];i=list(p['bscan_index']).index(int(b));im=p['images'][i]
    fig,axes=plt.subplots(1,3,figsize=(17,6),sharex=True,sharey=True)
    lo,hi=np.nanpercentile(im,[2,99.5]);x=np.arange(im.shape[1])
    for ax in axes:
        ax.imshow(im,cmap='gray',vmin=lo,vmax=hi,aspect='auto',origin='upper')
        ax.set_xlabel('A-line (column)');ax.set_ylim(im.shape[0]-.5,-.5)
    axes[0].set_title('Image only');axes[0].set_ylabel('Canonical crop depth (pixels; vitreous at top)')
    axes[1].set_title('All saved curves (includes automatic / uncertain)')
    axes[2].set_title('Actual strokes: solid = not denied; dashed = uncertain')
    vis=P.record_visibility(r);rel=P.record_reliability(r)
    for k,name in enumerate(r['surface_names']):
        axes[1].plot(x,r['surfaces'][k],color=colors[k],lw=.9,label=str(name))
        direct=r['local_drawn'][k]&~r['local_displaced'][k]&~r['region_excluded']
        uncertain=(vis[k]==2)|(rel[k]==2)
        axes[2].plot(x,np.where(direct&~uncertain,r['surfaces'][k],np.nan),color=colors[k],lw=1.2)
        axes[2].plot(x,np.where(direct&uncertain,r['surfaces'][k],np.nan),color=colors[k],lw=1.2,ls='--')
    for ax in axes[1:]:
        for c in np.flatnonzero(r['region_excluded']):ax.axvspan(c-.5,c+.5,color='red',alpha=.12,lw=0)
    axes[1].legend(loc='lower left',fontsize=7,ncol=2,facecolor='#333333',labelcolor='white')
    fig.suptitle(key+' | '+r['verdict']+' | red = whole-column exclusion',fontsize=11)
    fig.text(.5,.01,'Saved crop geometry; no reorientation. Solid strokes are not a new accuracy certificate. Ordering-displaced strokes omitted at right.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.035,1,.94]);fig.savefig(OUT/f'{key}.png',dpi=135);plt.close(fig)
after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
assert before==after, 'Labels changed during read-only audit'
summary['label_hashes_unchanged']=True
(OUT/'summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'label_fingerprints.json').write_text(json.dumps(before,indent=2))
print(json.dumps(summary,indent=2))
