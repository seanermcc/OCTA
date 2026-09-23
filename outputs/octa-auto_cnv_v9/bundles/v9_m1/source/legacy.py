from common import *
from scipy import ndimage as ndi

def export_target(record, visit):
    shape=(512,512); positive=np.zeros(shape,bool); ignored=np.zeros(shape,bool)
    instances=[]; audit=[]; issues=[]; normal=np.zeros(shape,bool)
    if record is None:
        return dict(target=positive,known=positive.copy(),instances=np.zeros((0,*shape),bool)), dict(complete=False,issues=['No v5 review: no labels'],regions=[],positive_pixels=0,negative_pixels=0,ignored_pixels=512*512)
    if record['scan_id']!=visit['scan_id'] or Path(record['source_volume']).resolve()!=Path(visit['source']).resolve(): raise ValueError('Annotation identity mismatch')
    if record['native_shape']!=list(shape) or record['axis_order']!='B-scan,A-line': raise ValueError('Annotation grid mismatch')
    seen=set(); kept=0; unsure_ids=[]
    for r in record['regions']:
        if r['id'] in seen: raise ValueError('Duplicate region id')
        seen.add(r['id']); mask=decode(r['runs']); reviewed=decode(r.get('reviewed_runs',[]))
        for key in ('edited_runs','core_runs','core_edited_runs','unreviewed_runs'):
            decode(r.get(key,[]))
        reasons=[]; decision=r.get('decision'); cat=r.get('category')
        approved=decision=='approved' and bool(r.get('classification_complete'))
        events=[e for e in r.get('events',[]) if e.get('action')=='explicit CNV review']
        if approved and (not events or events[-1].get('category')!=cat): reasons.append('Missing or conflicting explicit classification event')
        if approved and not np.array_equal(mask,reviewed): reasons.append('Reviewed runs differ from footprint')
        if r.get('bscan_indices')!=np.flatnonzero(mask.any(1)).tolist(): reasons.append('B-scan index metadata inconsistent')
        if approved and not mask.any(): reasons.append('Empty approved footprint')
        if reasons:
            ignored |= mask | reviewed; issues.extend(r['id']+': '+x for x in reasons)
        elif approved and cat=='Full Lesion':
            kept+=1; instances.append(mask); positive |= mask
        elif approved and cat=='Normal': normal |= mask
        elif decision!='rejected':
            ignored |= mask | reviewed
            if approved and cat=='Other': unsure_ids.append(r['id'])
        # Removed proposals generate no labels; only complete-field coverage can supply background.
        audit.append(dict(id=r['id'],category=cat,decision=decision,approved=approved and not reasons,
                          pixels=int(mask.sum()),origin=r.get('origin'),seed_ids=r.get('seed_ids'),
                          reviewed_runs_equal=np.array_equal(mask,reviewed),issues=reasons,
                          connected_components=int(ndi.label(mask)[1]),events=r.get('events',[])))
    stack=np.stack(instances) if instances else np.zeros((0,*shape),bool)
    conflict=(stack.sum(0)>1) | (positive & (ignored|normal))
    if conflict.any():
        issues.append(f'Conflicting positive pixels ignored: {int(conflict.sum())}'); ignored |= conflict
    for key in ('excluded_runs','region_excluded_runs','ignore_runs'):
        if key in record: ignored |= decode(record[key])
    review=record.get('scan_review',{})
    complete=review.get('status')=='complete' and review.get('whole_field_checked') is True
    if complete and (review.get('confirmed_cnv_count')!=kept or set(review.get('uncertainty_region_ids',[]))!=set(unsure_ids) or bool(review.get('reviewed_absence')) != (kept==0 and not unsure_ids)):
        issues.append('Inconsistent completion metadata: background excluded'); complete=False
    positive &= ~ignored
    known=(np.ones(shape,bool) if complete else positive.copy()) & ~ignored
    stack &= known[None]
    return dict(target=positive,known=known,instances=stack),dict(complete=complete,scan_review=review,
        review_context=record.get('review_context',{}),issues=issues,regions=audit,
        positive_pixels=int(positive.sum()),negative_pixels=int((known&~positive).sum()),ignored_pixels=int((~known).sum()))

def automatic_thickness(rows, probabilities, geometry, calibration, depth):
    """Same available-position pilot policy, with human and contextual branches removed."""
    offset=int(geometry['label_offset']); valid=np.isfinite(rows)&(rows>=offset)&(rows<offset+depth)
    denied=np.zeros_like(valid)
    for a in range(8):
        for b in range(a+1,8):
            cross=np.isfinite(rows[:,a])&np.isfinite(rows[:,b])&(rows[:,a]>=rows[:,b])
            valid[:,a]&=~cross;valid[:,b]&=~cross
        c=calibration[a]
        if c['supported']: denied[:,a]=probabilities[:,a,0]<=c['not_traceable_cutoff']
    end=np.where(valid&~denied,rows-offset,np.nan)
    values=[];causes=[]
    for _,a,b in LAYERS:
        delta=(end[:,b]-end[:,a])*1.12
        reason=(denied[:,a]|denied[:,b]).astype('uint8')
        reason |= ((~valid[:,a]|~valid[:,b]).astype('uint8')*2)
        reason |= geometry['shadow'].astype('uint8')*4
        values.append(np.where((reason==0)&(delta>0),delta,np.nan))
        causes.append(reason)
    return np.stack(values).astype('float32'),np.stack(causes),end.astype('float32')

def tensor_inputs(d,stats,experiment):
    optical=(d['optical']-np.array(stats['optical']['center'])[:,None,None])/np.array(stats['optical']['scale'])[:,None,None]
    parts=[np.clip(optical,-8,8)]
    if experiment in ('B','C'): parts += [d['availability'].astype('float32'),d['shadow'][None].astype('float32')]
    if experiment=='C':
        t=(d['thickness_um']-np.array(stats['thickness_um']['center'])[:,None,None])/np.array(stats['thickness_um']['scale'])[:,None,None]
        parts += [np.where(d['availability'],np.clip(t,-8,8),0)]
    a=np.concatenate(parts).astype('float32'); assert np.isfinite(a).all();return a


