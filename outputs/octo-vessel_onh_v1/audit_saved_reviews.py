"""Read-only review audit; figures/reports only, never writes annotations."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import hashlib
from types import SimpleNamespace
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'code'))
from eight_surface import cnv_labels
app=SimpleNamespace(HERE=HERE,LABELS=HERE/'labels',BATCH=HERE.parent/'octa-vessel_seg_v1-batch',CL=cnv_labels,digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest())

out=app.HERE/'review_audit_first15'
out.mkdir(exist_ok=True)
queue=json.loads((app.HERE/'review_queue.json').read_text())['scans'][:15]
records=[];panels=[]
for n,row in enumerate(queue,1):
    p=app.CL.label_path(app.LABELS,row['scan_id'])
    if not p.exists():continue
    before_hash=app.digest(p)
    with np.load(p,allow_pickle=False) as z:
        d={k:z[k].copy() for k in z.files}
    loaded=app.CL.load_label(p)
    with np.load(app.BATCH/'projections'/f'{row["scan_id"]}.npz',allow_pickle=False) as z:
        im=z['structural_enface'].copy();source=str(z['source'][0]);band=z['retina_band']
    vessel=d['vasculature_mask'];onh=d['onh_mask'];initial=d['vasculature_initial_mask']
    added=vessel & ~initial;removed=initial & ~vessel
    touched=d['vasculature_brush_touched'];derived=d.get('vessel_removed_by_onh',np.zeros(vessel.shape,bool))
    record=dict(queue_number=n,scan_id=row['scan_id'],revision=int(d['revision'][0]),
        vessel_flag=row['vessel_issue'],onh_flag=row['onh_present'],
        vessel_reviewed=bool(d['reviewed_targets'][1]),onh_reviewed=bool(d['reviewed_targets'][2]),
        onh_visibility=str(d['onh_visibility'][0]),vessel_pixels=int(vessel.sum()),
        onh_pixels=int(onh.sum()),added_vessel_pixels=int(added.sum()),removed_vessel_pixels=int(removed.sum()),
        vessel_touched_pixels=int(touched.sum()),onh_touched_pixels=int(d['onh_brush_touched'].sum()),
        derived_removal_pixels=int(derived.sum()),overlap_pixels=int((vessel&onh).sum()),
        unexplained_vessel_changes=int(((added|removed)&~touched&~derived).sum()),
        vessel_excluded_pixels=int(d['vessel_region_excluded'].sum()),onh_excluded_pixels=int(d['onh_region_excluded'].sum()),
        geometry_matches=vessel.shape==im.shape and np.array_equal(d['retina_band'],band) and str(d['source_volume'][0])==source,
        queue_hash_matches=str(d['queue_sha256'][0])==app.digest(app.HERE/'review_queue.json'),
        notes=str(d['notes'][0]),label_sha256=before_hash)
    proposal_path=Path(str(d['vasculature_proposal_path'][0]))
    if not proposal_path.is_file():proposal_path=app.BATCH/'proposals'/proposal_path.name
    record['seed_hash_matches']=app.digest(proposal_path)==str(d['vasculature_proposal_sha256'][0]) if proposal_path.is_file() else None
    assert app.digest(p)==before_hash
    records.append(record)
    (out/'audit.json').write_text(json.dumps(records,indent=2))
    print('Audited',n,row['scan_id'],flush=True)
    lo,hi=np.percentile(im,[1,99]);gray=np.clip((im-lo)/(hi-lo),0,1)
    base=np.repeat(gray[...,None],3,axis=2);overlay=base.copy();changes=base.copy()
    overlay[vessel]=overlay[vessel]*.6+np.array([.05,.55,1])*.4
    overlay[onh]=overlay[onh]*.5+np.array([.05,1,.2])*.5
    changes[removed]=[1,.3,.12];changes[added]=[.1,.65,1];changes[onh]=changes[onh]*.5+np.array([.05,1,.2])*.5
    panels.append((n,row['scan_id'],base,overlay,changes))
for page in range((len(panels)+2)//3):
    fig,axes=plt.subplots(3,3,figsize=(15,15))
    for axesrow,scan in zip(axes,panels[page*3:page*3+3]):
        n,sid,*ims=scan
        for ax,img,title in zip(axesrow,ims,['Original image','Saved masks: blue vessel / green ONH','Edits: orange removed / blue added']):
            ax.imshow(img);ax.set_title(f'#{n} {sid}\n{title}',fontsize=8);ax.axis('off')
    fig.tight_layout();fig.savefig(out/f'page_{page+1}.jpg',dpi=110);plt.close(fig)
(out/'audit.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records,indent=2))
