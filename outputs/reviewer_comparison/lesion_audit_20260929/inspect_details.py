import sys,json
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).parent
BASE=OUT.parent
sys.path.insert(0,str(BASE.parents[1]/'code'))
from reviewer_compare.build import read
data=json.loads((BASE/'data.js').read_text().removeprefix('window.COMPARISON = ').strip().removesuffix(';'))
summary=read(OUT/'summary.json')
for group in ('beforelaser','unmatched'):
    cs=[c for c in data['cases'] if ('beforelaser' in c['id'] if group=='beforelaser' else len(c['reviewers'])==1 and next(iter(c['reviewers'].values()))['status']=='Confirmed')]
    cols=2 if group=='beforelaser' else 4
    fig,axs=plt.subplots(int(np.ceil(len(cs)/cols)),cols,figsize=(15,5*int(np.ceil(len(cs)/cols))),squeeze=False)
    for ax,c in zip(axs.flat,cs):
        who=next(iter(c['reviewers']));r=c['reviewers'][who]
        im=np.asarray(Image.open(BASE/c['image']));ax.imshow(im,cmap='gray',aspect='auto',origin='upper')
        z=np.asarray(r['positions'],float)-c['offset'];valid=np.asarray(r['approved'],bool)
        for k in range(8):ax.plot(np.where(valid[k],z[k],np.nan),color=plt.cm.tab10(k),lw=.7)
        j=read(r['source_path']);ev=j['events'][:j['cursor']];confirm=next(e for e in reversed(ev) if e['action']=='confirm_bscan')
        ls=confirm['lesion_snapshot']
        for l,h in ls['cnv_region']:ax.axvspan(l,h,color='#ed48af',alpha=.13)
        edge=np.array([np.nan if v is None else v for v in ls['cnv_edge']],float)-c['offset']
        ax.plot(edge,color='cyan',lw=1)
        hyper=np.zeros(np.prod(ls['shape']),bool)
        for l,h in ls['hyper_ref_runs']:hyper[l:h]=True
        if hyper.any():ax.contour(hyper.reshape(ls['shape']),levels=[.5],colors=['yellow'],linewidths=.5)
        vv=z[valid]
        if len(vv):ax.set_ylim(min(im.shape[0],max(vv)+30),max(0,min(vv)-20))
        ax.set_title(c['id']+'\n'+who,fontsize=8)
    for ax in list(axs.flat)[len(cs):]:ax.set_visible(False)
    fig.tight_layout();fig.savefig(OUT/(group+'.png'),dpi=120);plt.close(fig)

print('Unique confirmed target-positive slices (either reader):')
import csv
rows=list(csv.DictReader((OUT/'review_inventory.csv').open(encoding='utf-8-sig')))
for field in ('region_columns','edge_valid_columns','hyper_usable_pixels'):
    filtered=[r for r in rows if r['status']=='Confirmed' and int(r[field])>0]
    print(field,len({r['case'] for r in filtered}),'scans',len({r['scan_id'] for r in filtered}),'animals',sorted({r['animal'] for r in filtered}))
rr=summary['lesion_pairs']
print('region iou pooled',sum(r['intersection'] for r in rr)/sum(r['union'] for r in rr))
print('nonempty-both region iou median',np.median([r['region_iou'] for r in rr if r['lead_columns'] and r['shichu_columns']]))
print('hyper pooled joint-known dice',2*sum(r['hyper_intersection'] for r in rr)/(sum(r['hyper_intersection']+r['hyper_union'] for r in rr)))
print('edge case count',sum(r['edge_overlap']>0 for r in rr))

details=[]
for c in data['cases']:
    if len(c['reviewers'])<2:continue
    a,b=c['reviewers']['lead'],c['reviewers']['shichu']
    ja,jb=[read(r['source_path']) for r in (a,b)]
    masks=[]
    for j in (ja,jb):
        e=next(e for e in reversed(j['events'][:j['cursor']]) if e['action']=='confirm_bscan')
        mask=np.zeros(c['width'],bool)
        for l,h in e['lesion_snapshot']['cnv_region']:mask[l:h]=True
        masks.append(mask)
    delta=np.abs(np.asarray(a['positions'],float)-np.asarray(b['positions'],float))*1.12
    valid=np.asarray(a['approved'])&np.asarray(b['approved'])
    for k,name in enumerate(data['names']):
        m=valid[k]&(masks[0]|masks[1])&(delta[k]>10)
        if m.any():details.append(dict(case=c['id'],boundary=name,n=int(m.sum()),start=int(np.where(m)[0].min()),end=int(np.where(m)[0].max()),max_um=float(delta[k][m].max())))
print('Largest jointly approved lesion differences',json.dumps(sorted(details,key=lambda x:x['max_um'],reverse=True)[:12],indent=2))
