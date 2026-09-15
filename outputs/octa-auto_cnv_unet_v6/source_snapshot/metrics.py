"""Prespecified component matching and review-burden proxies; no holdout tuning."""
from common import *
from scipy import ndimage as ndi
from scipy.optimize import linear_sum_assignment

PROTOCOL=dict(connectivity=8,matching='Maximum-cardinality one-to-one IoU matching, then maximum total IoU',
    iou_thresholds=[.1,.25,.5],threshold_grid=[.1,.2,.3,.4,.5,.6,.7,.8,.9],
    threshold_objective='Maximum pooled known-pixel validation Dice, ties prefer higher threshold',
    unknown_policy='Full raw components retain identity when restricted to known pixels. Entirely unknown components unscored; unmatched partially ignored components ambiguous, excluded from FP count.',
    negatives='Only complete fields support FP/count/area errors; empty-empty Dice is null, not 1',
    border_policy='Matched pairs with entirely reviewed reference outline, no ignored overlap or FOV clipping; symmetric surface distance in approximate physical micrometers',
    correction_proxy='Matched outline needs suggested correction if IoU < 0.8 or mean boundary distance > 25 um; thresholds are workflow proxies, not human judgments',
    merge_split='An edge in the overlap graph requires intersection >= 10% of the smaller known object',
    postprocessing='None: no size filter, shape rule, hole filling or count cap',
    time='Record focus-active elapsed time only during actual human review; never infer time savings from scores')

def components(mask):
    labels,n=ndi.label(mask,np.ones((3,3),int))
    return labels,[labels==i for i in range(1,n+1)]

def boundary(mask): return mask&~ndi.binary_erosion(mask)

def border_error(a,b):
    aa=boundary(a);bb=boundary(b)
    if not aa.any() or not bb.any():return None,None
    dist=np.r_[ndi.distance_transform_edt(~aa)[bb],ndi.distance_transform_edt(~bb)[aa]]*UM
    return float(dist.mean()),float(np.percentile(dist,95))

def match(iou,cutoff):
    if not iou.size:return []
    # Cardinality dominates IoU so a single high IoU cannot hide two valid matches.
    rows,cols=linear_sum_assignment(-((iou>=cutoff)*1000+iou*(iou>=cutoff)))
    return [(int(r),int(c)) for r,c in zip(rows,cols) if iou[r,c]>=cutoff]

def score(raw_mask,d,complete,cutoff=.1,instance_labels=None):
    known=d['known'];target=d['target'];gt=[m for m in d['instances'] if m.any()]
    if instance_labels is None: labels,raw=components(raw_mask)
    else:
        labels=instance_labels;raw=[labels==i for i in np.unique(labels) if i>0]
    observed=[(i,p&known,p) for i,p in enumerate(raw) if (p&known).any()]
    iou=np.zeros((len(gt),len(observed)));overlap=iou.copy()
    for i,g in enumerate(gt):
        for j,(_,p,_) in enumerate(observed):
            inter=int((g&p).sum());iou[i,j]=inter/max(1,int((g|p).sum()))
            overlap[i,j]=inter/max(1,min(int(g.sum()),int(p.sum())))
    pairs=match(iou,cutoff);mg={i for i,j in pairs};mp={j for i,j in pairs}
    fp=[j for j,(_,p,rawp) in enumerate(observed) if j not in mp and complete and not (rawp&~known).any()]
    ambiguous=[j for j,(_,p,rawp) in enumerate(observed) if j not in mp and (rawp&~known).any()]
    details=[];borders=[];corrections=0
    for i,j in pairs:
        g=gt[i];p=observed[j][1];rp=observed[j][2]
        border_known=not ((ndi.binary_dilation(g)&~known).any() or g[0].any() or g[-1].any() or g[:,0].any() or g[:,-1].any() or (rp&~known).any())
        bd,p95=border_error(g,p) if border_known else (None,None)
        if bd is not None:borders.append(bd)
        correction=bool(iou[i,j]<.8 or (bd is not None and bd>25));corrections+=correction
        details.append(dict(reference=i,prediction=observed[j][0],iou=float(iou[i,j]),border_mean_um=bd,border_p95_um=p95,correction_proxy=correction))
    tp=int((raw_mask&target&known).sum());predn=int((raw_mask&known).sum());truth=int(target.sum())
    dice=2*tp/(predn+truth) if truth else None
    pix_iou=tp/(predn+truth-tp) if truth else None
    recall=len(pairs)/len(gt) if gt else None
    precision=len(pairs)/(len(pairs)+len(fp)) if len(pairs)+len(fp)>0 and complete else None
    missing=[i for i in range(len(gt)) if i not in mg]
    low_availability=[]
    for i,g in enumerate(gt):
        low_availability.append(dict(reference=i,detected=i in mg,available_fraction=float(d['availability'][:,g].mean()),
                                     area_mm2=float(g.sum()*UM**2/1e6)))
    artifact=[]
    for j in fp:
        _,p,_=observed[j]
        artifact.append(dict(prediction=observed[j][0],pixels=int(p.sum()),shadow_fraction=float(d['shadow'][p].mean()),
            vessel_fraction=float(d['vessel'][p].mean()),low_signal_fraction=float(d['low_signal'][p].mean()),
            available_fraction=float(d['availability'][:,p].mean())))
    counts=dict(reference_lesions=len(gt),raw_suggestions=len(raw),matched=len(pairs),
        false_positives=len(fp) if complete else None,recall=recall,precision=precision,known_dice=dice,known_iou=pix_iou,
        pixel_tp=tp,predicted_known_pixels=predn,reference_pixels=truth,known_pixels=int(known.sum()),
        known_false_positive_pixels=int((raw_mask&known&~target).sum()),
        border_mean_um=float(np.mean(borders)) if borders else None,border_pairs=len(borders),
        merges=int(((overlap>=.1).sum(0)>1).sum()),
        splits=int(((overlap>=.1).sum(1)>1).sum()),
        count_error=(len(pairs)+len(fp)-len(gt)) if complete else None,
        raw_known_component_count_error=(len(observed)-len(gt)) if complete else None,
        area_error_mm2=(predn-truth)*UM**2/1e6 if complete else None,
        additions_proxy=len(missing),removals_proxy=len(fp) if complete else None,outline_corrections_proxy=corrections,
        entirely_unknown_suggestions=len(raw)-len(observed),partially_ignored_unmatched=len(ambiguous),
        human_review_seconds=None)
    return counts,dict(matches=details,missed_reference=missing,false_predictions=[observed[j][0] for j in fp],
                       ambiguous_predictions=[observed[j][0] for j in ambiguous],lesion_availability=low_availability,false_positive_artifacts=artifact)

def aggregate(rows):
    tp=sum(r['pixel_tp'] for r in rows);p=sum(r['predicted_known_pixels'] for r in rows);g=sum(r['reference_pixels'] for r in rows)
    n=sum(r['reference_lesions'] for r in rows);hit=sum(r['matched'] for r in rows)
    complete=[r for r in rows if r['complete']];fp=sum(r['false_positives'] or 0 for r in complete)
    completed_hits=sum(r['matched'] for r in complete)
    return dict(scans=len(rows),completed_scans=len(complete),reference_lesions=n,matched=hit,
        lesion_recall=hit/n if n else None,false_positives=fp,fp_per_completed_scan=fp/len(complete) if complete else None,
        precision=completed_hits/(completed_hits+fp) if completed_hits+fp else None,pooled_known_dice=2*tp/(p+g) if g else None,
        pooled_known_iou=tp/(p+g-tp) if g else None,additions_proxy=sum(r['additions_proxy'] for r in rows),
        removals_proxy=fp,outline_corrections_proxy=sum(r['outline_corrections_proxy'] for r in rows),
        merges=sum(r['merges'] for r in rows),splits=sum(r['splits'] for r in rows),
        total_area_error_mm2=sum(r['area_error_mm2'] or 0 for r in complete),
        human_review_seconds=None)
