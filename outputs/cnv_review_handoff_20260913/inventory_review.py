"""Read-only saved-label inventory for the GUI handoff; no target export or label edits."""
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
import numpy as np
from scipy import ndimage as ndi
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def mask(runs,shape):
    a=np.zeros(shape,bool)
    for y,x0,x1 in runs:
        if not (0<=y<shape[0] and 0<=x0<x1<=shape[1]):raise ValueError('Invalid native mask run')
        a[y,x0:x1]=True
    return a
visits=[r for r in read(ROOT/'outputs/longitudinal_assessment/manifest.json')['visits'] if r['animal']=='TS267']
rows=[];region_details=[];issues=[];hashes={}
for visit in visits:
    sid=visit['scan_id'];p=ROOT/'outputs/octa-auto_cnv_v5/review/regions'/f'{sid}_regions.json'
    row=dict(scan_id=sid,day=visit['day_label'],eye=visit['eye'],v5_file_exists=p.exists(),path=str(p))
    if not p.exists():
        row['prior_review_files']=[str(q) for v in ('v4','v3') if (q:=ROOT/f'outputs/octa-auto_cnv_{v}/review/regions'/p.name).exists()]
        rows.append(row);continue
    hashes[str(p)]=sha(p);d=read(p);shape=tuple(d['native_shape']);assert d['scan_id']==sid and shape==(512,512)
    positive=np.zeros(shape,bool);uncertain=np.zeros(shape,bool);sum_positive=np.zeros(shape,np.uint16)
    counts=dict(confirmed_cnv_entries=0,unsure_entries=0,rejected_entries=0,draft_entries=0,approved_normal_entries=0,seeded_positive_entries=0,unseeded_positive_entries=0)
    for i,r in enumerate(d['regions'],1):
        a=mask(r['runs'],shape);lab,n=ndi.label(a,np.ones((3,3)));areas=np.bincount(lab.ravel())[1:];large=int(np.sum(areas>=25))
        decision=r.get('decision','unreviewed');category=r.get('draft_category',r.get('category','Unclassified'))
        detail=dict(scan_id=sid,list_entry=i,region_id=r['id'],category=category,decision=decision,seed_ids=r.get('seed_ids',[]),
            origin=r.get('origin',''),pixels=int(a.sum()),components_8_connected=int(n),components_at_least_25px=large,
            component_areas_px=sorted(map(int,areas),reverse=True),notes=r.get('notes',''))
        region_details.append(detail)
        if decision=='approved':
            if not np.array_equal(a,mask(r.get('reviewed_runs',[]),shape)):issues.append(dict(scan_id=sid,issue='approved runs mismatch',region_id=r['id']))
            if category=='Full Lesion':
                counts['confirmed_cnv_entries']+=1;counts['seeded_positive_entries' if r.get('seed_ids') else 'unseeded_positive_entries']+=1
                positive|=a;sum_positive+=a
                if large>1:issues.append(dict(scan_id=sid,issue='multiple substantial disconnected pieces in one kept CNV entry',region_id=r['id'],list_entry=i,component_areas_px=detail['component_areas_px']))
            elif category=='Other':counts['unsure_entries']+=1;uncertain|=a
            elif category=='Normal':counts['approved_normal_entries']+=1
        elif decision=='rejected':counts['rejected_entries']+=1
        else:counts['draft_entries']+=1
    sr=d.get('scan_review',{});context=d.get('review_context',{})
    row.update(counts,revision=d['revision'],saved_at=d.get('saved_at'),status=sr.get('status','unspecified'),
        whole_field_checked=bool(sr.get('whole_field_checked')),reviewed_absence=bool(sr.get('reviewed_absence')),
        saved_confirmed_count=sr.get('confirmed_cnv_count'),positive_pixels=int(positive.sum()),unsure_pixels=int(uncertain.sum()),
        positive_unsure_overlap_pixels=int((positive&uncertain).sum()),positive_entry_overlap_pixels=int((sum_positive>1).sum()),
        automatic_proposals_seen=context.get('automatic_proposals_seen'),active_review_seconds=context.get('active_review_seconds'))
    if row['positive_entry_overlap_pixels']:issues.append(dict(scan_id=sid,issue='kept CNV entries overlap',pixels=row['positive_entry_overlap_pixels']))
    if row['positive_unsure_overlap_pixels']:issues.append(dict(scan_id=sid,issue='kept CNV and unsure masks overlap',pixels=row['positive_unsure_overlap_pixels']))
    if row['whole_field_checked'] and row['saved_confirmed_count']!=counts['confirmed_cnv_entries']:issues.append(dict(scan_id=sid,issue='finished count mismatch'))
    rows.append(row)
saved=[r for r in rows if r['v5_file_exists']]
totals=dict(selected_scans=len(rows),saved_v5_scans=len(saved),whole_field_finished=sum(r['whole_field_checked'] and r['status']=='complete' for r in saved),
    reviewed_absence_scans=sum(r['reviewed_absence'] for r in saved),missing_v5=[r['scan_id'] for r in rows if not r['v5_file_exists']],
    unfinished_saved=[r['scan_id'] for r in saved if not r['whole_field_checked'] or r['status']!='complete'],
    **{k:sum(r[k] for r in saved) for k in ('confirmed_cnv_entries','unsure_entries','rejected_entries','draft_entries','seeded_positive_entries','unseeded_positive_entries')})
audit=dict(audited_at=datetime.now(timezone.utc).isoformat(),scope='saved JSON inventory only; no visual adjudication, label correction, training-target export, or model fitting',
    totals=totals,scans=rows,regions=region_details,triage_flags=issues,label_sha256=hashes)
for path,digest in hashes.items():assert sha(Path(path))==digest
(OUT/'REVIEW_BATCH_INVENTORY.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps(totals,indent=2));print('FLAGS',json.dumps(issues,indent=2))
print('STATUS',json.dumps([{k:r.get(k) for k in ('scan_id','status','confirmed_cnv_entries','unsure_entries','draft_entries','reviewed_absence','active_review_seconds')} for r in rows],indent=2))
