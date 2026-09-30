"""Read-only assessment; never imports or calls an annotation writer."""
import sys, json, csv
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
from scipy.ndimage import binary_dilation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))
from reviewer_compare.build import read,digest,safe,stats,inventory,load_review
from octa_seg_v3.feedback import resolve,training_targets
from octa_seg_v3 import lesions as L

OUT=ROOT/'outputs/reviewer_comparison/lesion_audit_20260929'
OUT.mkdir(exist_ok=True)
SNAP=read(ROOT/'outputs/reviewer_comparison/source_manifest.json')
inv={w:inventory(Path('F:/octa/reviewers')/w,w) for w in ('lead','shichu')}
snapshot_journals={x['path']:x['sha256'] for x in SNAP['sources'] if x['kind']=='journal'}
assert set(snapshot_journals)=={str(x[0]) for v in inv.values() for x in v.values()}
assert all(snapshot_journals[str(x[0])]==x[2] for v in inv.values() for x in v.values())
providers={p.parent.name:p.parent for base in ('Reviewed_Samples','More_Samples') for p in (Path('F:/octa/For_Segmentation')/base).glob('*/prepared.json')}
cases=[]; records=[]; all_hashes=[]
cache=None
for key in sorted(set(inv['lead'])|set(inv['shichu'])):
    j=next(v[key][1] for v in inv.values() if key in v)
    sid,row=j['scan_id'],int(j['bscan'])
    if cache!=sid:
        p=providers[sid]; prep=read(p/'prepared.json')
        image=np.load(p/'images.npy',mmap_mode='r',allow_pickle=False)
        with np.load(p/'measurements.npz',allow_pickle=False) as z:
            raw=z['raw_position_branch']; shadow=z['shadow']; vessel=z['vessel']; offset=int(z['label_offset']); names=z['surface_names'].tolist()
        if (p/'context.npz').exists():
            with np.load(p/'context.npz',allow_pickle=False) as z:vessel=vessel|z['vessel'].astype(bool)
        provider={'sha':digest(p/'measurements.npz'),'prep':prep}
        all_hashes.append({'path':str(p/'measurements.npz'),'sha256':provider['sha']})
        cache=sid
    case={'id':key,'scan_id':sid,'row':row,'offset':offset,'image':np.asarray(image[row]),'reviews':{}}
    for who in inv:
        if key not in inv[who]:continue
        item=inv[who][key]; j=item[1]
        validated=load_review(item,provider,raw[row],shadow[row],vessel[row],offset,image.shape)
        r=resolve(j['events'][:j['cursor']],raw[row],offset,image.shape[1])
        role=j.get('pinned_data_role') or r['metadata']['data_role']
        t=training_targets(j,raw[row],offset,image.shape[1],shadow[row],role=role,vessel=vessel[row])
        tn=training_targets(j,raw[row],offset,image.shape[1],shadow[row],role=role,vessel=vessel[row],include_shadow_overrides=False)
        case['reviews'][who]={'r':r,'t':t,'baseline':raw[row]}
        ls=r['lesions']; core=ls['cnv_region']; ap=t['approved_position']; denied=(r['trace']==0)|(r['reliability']==0)
        rec=dict(case=key,reviewer=who,animal=sid.split('_')[0],scan_id=sid,bscan=row,status=r['review_status'],role=role,
                 training_eligible=t['eligible'],lesion_eligible=t['lesion_eligible'],seconds=j.get('active_seconds',0),
                 region_columns=int(core.sum()),edge_drawn_columns=int(np.isfinite(ls['cnv_edge']).sum()),edge_valid_columns=int(t['cnv_edge_valid'].sum()),
                 hyper_pixels=int(ls['hyper_ref'].sum()),hyper_usable_pixels=int((ls['hyper_ref']&t['hyper_ref_known']).sum()),
                 approved_points=int(ap.sum()),approved_drawn_points=int((ap&t['reliable_manual']).sum()),
                 core_approved_points=int((ap&core).sum()),core_points=int(core.sum()*8),
                 core_unclear_points=int((denied&core).sum()),core_absent_points=int(((r['anatomy']==0)&core).sum()),
                 unresolved_points=int(r['unresolved'].sum()),shadow_override_columns=int(t['shadow_override_columns'].sum()),
                 approval_lost_without_shadow_override=int(ap.sum()-tn['approved_position'].sum()),notes=r['metadata']['notes'])
        records.append(rec)
        all_hashes.append({'path':str(item[0]),'sha256':item[2]})
    cases.append(case)

paired_rows=[]; region_rows=[]; pools=defaultdict(list); count=defaultdict(Counter)
for c in cases:
    if len(c['reviews'])!=2:continue
    a,b=[c['reviews'][w] for w in ('lead','shichu')]
    la,lb=[x['r']['lesions'] for x in (a,b)]
    ca,cb=la['cnv_region'],lb['cnv_region']; union=ca|cb; inter=ca&cb
    near=binary_dilation(union,iterations=35)&~union
    edge=a['t']['cnv_edge_valid']&b['t']['cnv_edge_valid']
    hk=a['t']['hyper_ref_known']&b['t']['hyper_ref_known']
    ha,hb=la['hyper_ref']&hk,lb['hyper_ref']&hk
    region_rows.append(dict(case=c['id'],lead_columns=int(ca.sum()),shichu_columns=int(cb.sum()),intersection=int(inter.sum()),union=int(union.sum()),
        region_iou=float(inter.sum()/union.sum()) if union.any() else None,
        edge_lead=int(a['t']['cnv_edge_valid'].sum()),edge_shichu=int(b['t']['cnv_edge_valid'].sum()),
        edge_overlap=int(edge.sum()),edge_mae_um=stats((lb['cnv_edge']-la['cnv_edge'])[edge]*1.12)['mae_um'],
        hyper_lead=int(la['hyper_ref'].sum()),hyper_shichu=int(lb['hyper_ref'].sum()),
        hyper_dice_joint_known=float(2*(ha&hb).sum()/(ha.sum()+hb.sum())) if ha.any() or hb.any() else None,
        hyper_intersection=int((ha&hb).sum()),hyper_union=int((ha|hb).sum())))
    pools['edge'].append((lb['cnv_edge']-la['cnv_edge'])[edge]*1.12)
    for zone,mask in dict(lesion_union=union,lesion_intersection=inter,near_100um=near,distant=~(union|near),all=np.ones_like(union)).items():
        da=(a['r']['trace']==0)|(a['r']['reliability']==0)
        db=(b['r']['trace']==0)|(b['r']['reliability']==0)
        aa,ab=a['t']['approved_position'],b['t']['approved_position']
        cc=count[zone]
        for name,v in dict(possible=8*mask.sum(),lead_approved=(aa&mask).sum(),shichu_approved=(ab&mask).sum(),
            lead_unclear=(da&mask).sum(),shichu_unclear=(db&mask).sum(),
            lead_unclear_shichu_approved=(da&ab&mask).sum(),shichu_unclear_lead_approved=(db&aa&mask).sum(),
            one_approved=((aa^ab)&mask).sum(),both_approved=(aa&ab&mask).sum()).items():cc[name]+=int(v)
        for scope in ('approved_position','reliable_manual'):
            valid=a['t'][scope]&b['t'][scope]&mask
            delta=(b['r']['positions']-a['r']['positions'])*1.12
            pools[zone+'/'+scope].append(delta[valid])
            for k,name in enumerate(names):
                pools[zone+'/'+scope+'/'+name].append(delta[k][valid[k]])
                paired_rows.append(dict(case=c['id'],zone=zone,scope=scope,boundary=name,possible=int(mask.sum()),**stats(delta[k][valid[k]])))

summary={'source_snapshot_journals_unchanged':True,'reviewer_counts':{},'unique_saved':len(cases),
         'unique_confirmed':sum(any(x['r']['confirmation'] for x in c['reviews'].values()) for c in cases),
         'unique_confirmed_scans':len({c['scan_id'] for c in cases if any(x['r']['confirmation'] for x in c['reviews'].values())}),
         'paired':len(region_rows),'zones':dict(count),'agreement':{k:stats(np.concatenate(v)) for k,v in pools.items()},
         'lesion_pairs':region_rows,'confirmed_animals':{},'notes':'Near = 35 A-lines (~100 um) outside union of reader-marked CNV lateral spans, within the selected B-scan, not 2D en-face distance. Pooled points are correlated; not accuracy or independent sample counts.'}
for who in inv:
    rr=[r for r in records if r['reviewer']==who]; conf=[r for r in rr if r['status']=='Confirmed']
    summary['reviewer_counts'][who]={'saved':len(rr),'states':dict(Counter(r['status'] for r in rr)),
        'roles':dict(Counter(r['role'] for r in conf)), 'confirmed_scans':len({r['scan_id'] for r in conf}),
        'confirmed_seconds_median':float(np.median([r['seconds'] for r in conf])),
        'confirmed_region_positive':sum(r['region_columns']>0 for r in conf),
        'confirmed_edge_positive':sum(r['edge_valid_columns']>0 for r in conf),
        'confirmed_hyper_positive':sum(r['hyper_usable_pixels']>0 for r in conf),
        'lesion_confirmed':sum(r['lesion_eligible'] for r in conf),
        'totals':{k:sum(r[k] for r in conf) for k in ('approved_points','approved_drawn_points','core_approved_points','core_points','core_unclear_points','core_absent_points','edge_valid_columns','hyper_usable_pixels','unresolved_points','approval_lost_without_shadow_override')}}
    summary['confirmed_animals'][who]=dict(Counter(r['animal'] for r in conf))
for name,rows in [('review_inventory',records),('paired_boundaries_by_region',paired_rows),('lesion_agreement',region_rows)]:
    with (OUT/(name+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(OUT/'summary.json').write_text(json.dumps(safe(summary),indent=2),encoding='utf-8')

colors=plt.cm.tab10(np.arange(8))
plot_cases=[c for c in cases if len(c['reviews'])==2]
for c in plot_cases:
    fig,axs=plt.subplots(2,3,figsize=(15,8),sharex=True,sharey=True)
    im=c['image'];lo,hi=np.percentile(im[np.isfinite(im)],[1,99.5])
    yy=[]
    for ri,who in enumerate(('lead','shichu')):
        r=c['reviews'][who]['r'];t=c['reviews'][who]['t'];ls=r['lesions'];x=np.arange(im.shape[1])
        for ax in axs[ri]:
            ax.imshow(im,cmap='gray',vmin=lo,vmax=hi,aspect='auto',origin='upper')
            for l,h in L.runs(ls['cnv_region']):ax.axvspan(l,h,color='#ed48af',alpha=.09)
        for k,n in enumerate(names):
            y=r['positions'][k]-c['offset'];valid=t['approved_position'][k]
            axs[ri,1].plot(x,np.where(valid,y,np.nan),color=colors[k],lw=1,label=n)
            yy.extend(y[valid].tolist())
        axs[ri,2].plot(x,np.where(t['cnv_edge_valid'],ls['cnv_edge']-c['offset'],np.nan),color='cyan',lw=1.5)
        if ls['hyper_ref'].any():axs[ri,2].contour(ls['hyper_ref'],levels=[.5],colors=['yellow'],linewidths=.65)
        for ci,title in enumerate(('OCT + CNV lateral region','Eligible retinal boundaries','CNV edge (cyan), Hyper_Ref (yellow)')):
            axs[ri,ci].set_title(who+' | '+title,fontsize=10)
    if yy:
        bottom=min(im.shape[0],max(yy)+20);top=max(0,min(yy)-20)
        for ax in axs.flat:ax.set_ylim(bottom,top);ax.set_xlim(0,im.shape[1]-1);ax.set_xlabel('Native A-line (zero-based)')
    axs[0,1].legend(fontsize=7,ncol=4,loc='upper center',bbox_to_anchor=(.5,1.22))
    fig.suptitle(c['id']+' | denied/unconfirmed retinal positions omitted',fontsize=11)
    fig.tight_layout(rect=[0,0,1,.93]);fig.savefig(OUT/(c['id']+'.png'),dpi=140);plt.close(fig)

assert all(digest(x['path'])==x['sha256'] for x in all_hashes),'Source changed during analysis'
(OUT/'source_hashes.json').write_text(json.dumps(all_hashes,indent=2),encoding='utf-8')
print(json.dumps(safe({k:v for k,v in summary.items() if k!='agreement'}),indent=2))
print('POOLED REGIONAL AGREEMENT')
for k,v in summary['agreement'].items():
    if k.count('/')<2:print(k,v)
