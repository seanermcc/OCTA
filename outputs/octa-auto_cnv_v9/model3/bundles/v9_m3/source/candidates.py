"""Unfiltered components, auditable matching and regularized candidate ranking."""
from common import *
from scipy import ndimage as ndi
from scipy.optimize import minimize,linear_sum_assignment
from scipy.special import expit
FEATURES=['mean_probability','max_probability','log_area','vessel_overlap','vessel_proximity','onh_overlap','onh_proximity','vessel_available','onh_available','vessel_reviewed','onh_reviewed','manual_source']

def extract(score,context):
 labels,n=ndi.label(score>=.7,structure=np.ones((3,3)));records=[]
 vessel=context[0]>0;onh=context[1]>0;va=context[2]>0;oa=context[3]>0
 vd=ndi.distance_transform_edt(~vessel) if vessel.any() else np.full(score.shape,np.inf)
 od=ndi.distance_transform_edt(~onh) if onh.any() else np.full(score.shape,np.inf)
 for i,box in enumerate(ndi.find_objects(labels),1):
  if box is None:continue
  m=labels[box]==i;full=np.zeros(score.shape,bool);full[box]=m;p=score[box][m];pixels=int(m.sum())
  vvalid=full&va;ovalid=full&oa
  def overlap(mask,known):return float((full&mask&known).sum()/max(1,(full&known).sum()))
  vdist=float(vd[full].min());odist=float(od[full].min())
  features=[float(p.mean()),float(p.max()),float(np.log1p(pixels)),overlap(vessel,va),float(np.exp(-vdist/32)),overlap(onh,oa),float(np.exp(-odist/32)),float(vvalid.sum()/pixels),float(ovalid.sum()/pixels),float(context[4][full].mean()),float(context[5][full].mean()),float(context[10][full].mean())]
  records.append(dict(id=i,area_pixels=pixels,area_um2=pixels*PX_UM**2,area_mm2=pixels*PX_UM**2/1e6,raw_score=features[0],max_probability=features[1],features=dict(zip(FEATURES,features)),bbox=[box[0].start,box[1].start,box[0].stop,box[1].stop],vessel_distance_px=vdist if np.isfinite(vdist) else None,onh_distance_px=odist if np.isfinite(odist) else None,vessel_overlap=features[3],onh_overlap=features[5],touches_fov_edge=bool(full[0].any() or full[-1].any() or full[:,0].any() or full[:,-1].any()),runs=encode(full)))
 return labels.astype('int32'),records

def correspondence(labels,records,truth):
 inst=truth['instances'];known=truth['known'];pos=truth['target'];n=len(records);nt=len(inst)
 inter=np.zeros((n,nt),int);iou=np.zeros((n,nt),float);refareas=inst.sum((1,2)) if nt else np.zeros(0)
 for j in range(nt):inter[:,j]=np.bincount(labels[inst[j]],minlength=n+1)[1:]
 areas=np.array([r['area_pixels'] for r in records]);union=areas[:,None]+refareas[None,:]-inter
 np.divide(inter,union,out=iou,where=union>0)
 candidate_degree=(inter>0).sum(1);target_degree=(inter>0).sum(0)
 for i,r in enumerate(records):
  mask=labels==r['id'];assessed=float(known[mask].mean());touch_ignored=bool((ndi.binary_dilation(mask,structure=np.ones((3,3)))&~known).any());hits=np.flatnonzero(inter[i]>0)
  label=None;reason='ambiguous partial overlap';merge=len(hits)>1;split=any(target_degree[j]>1 for j in hits)
  if assessed<.95 or touch_ignored:reason='insufficient assessment or ignored-boundary contact'
  elif merge or split:reason='merge' if merge else 'split'
  elif not len(hits):label=0;reason='fully reviewed background; zero positive intersection'
  elif float(iou[i].max())>=.25:label=1;reason='unambiguous one-to-one IoU >= 0.25'
  r['match']=dict(label=label,reason=reason,assessed_fraction=assessed,touches_ignored=touch_ignored,reference_indices=hits.tolist(),best_iou=float(iou[i].max()) if nt else 0.,split=split,merge=merge)
 return inter,iou

def fit_scorer(examples,provenance):
 rows=[r for r in examples if r['match']['label'] is not None];classes={r['match']['label'] for r in rows}
 base=dict(features=FEATURES,provenance=provenance,training_examples=len(rows),ignored_examples=len(examples)-len(rows),class_counts={str(k):sum(r['match']['label']==k for r in rows) for k in (0,1)},status='uncalibrated',threshold=.5,regularization_l2=10.,training_animals=sorted({r['animal'] for r in rows}))
 if classes!={0,1}:return dict(base,fitted=False,fallback='raw mean probability; two fitting classes unavailable',supported_area_pixels=None)
 x=np.array([[r['features'][k] for k in FEATURES] for r in rows]);y=np.array([r['match']['label'] for r in rows]);center=x.mean(0);scale=x.std(0);scale[scale<1e-6]=1
 counts={a:sum(r['animal']==a for r in rows) for a in base['training_animals']};weights=np.array([1/counts[r['animal']] for r in rows]);weights*=len(rows)/weights.sum();z=(x-center)/scale
 def objective(theta):
  logits=z@theta[:-1]+theta[-1];loss=np.sum(weights*(np.logaddexp(0,logits)-y*logits))+5*np.sum(theta[:-1]**2)
  err=weights*(expit(logits)-y);grad=np.r_[z.T@err+10*theta[:-1],err.sum()]
  return loss,grad
 result=minimize(objective,np.zeros(x.shape[1]+1),jac=True,method='L-BFGS-B',options=dict(maxiter=1000,ftol=1e-12))
 if not result.success:raise RuntimeError('Candidate adjustment failed: '+result.message)
 return dict(base,fitted=True,center=center,scale=scale,coefficients=result.x[:-1],intercept=float(result.x[-1]),supported_area_pixels=[min(r['area_pixels'] for r in rows),max(r['area_pixels'] for r in rows)],fitting_objective=float(result.fun),weighting='equal total candidate weight per training animal',calibration_claim=False)

def adjust(records,scorer):
 result=[]
 for original in records:
  r=dict(original);features=r['features'];contributions={};area=scorer.get('supported_area_pixels')
  if scorer['fitted']:
   x=np.array([features[k] for k in FEATURES]);effects=(x-np.array(scorer['center']))/np.array(scorer['scale'])*np.array(scorer['coefficients']);score=float(expit(effects.sum()+scorer['intercept']));contributions=dict(zip(FEATURES,map(float,effects)))
  else:score=r['raw_score']
  r.update(adjusted_score=score,display_selected=score>=.5,display_reason='adjusted score >= fixed 0.5' if score>=.5 else 'below fixed adjusted display threshold; raw footprint retained',score_status='uncalibrated',size_extrapolation=bool(area and not area[0]<=r['area_pixels']<=area[1]),missing_context=features['vessel_available']<.95 or features['onh_available']<.95,score_contributions=contributions,geometry_changed=False)
  result.append(r)
 return result

def metrics(labels,records,truth,selected_ids=None,size_cutoffs=None):
 active=records if selected_ids is None else [r for r in records if r['id'] in selected_ids]
 mask=np.isin(labels,[r['id'] for r in active]);known=truth['known'];p=mask&known;t=truth['target'];intersect=int((p&t).sum());union=int((p|t).sum());den=int(p.sum()+t.sum())
 # All reference region identities retained. Components only define predictions.
 inst=truth['instances'];matrix=np.zeros((len(active),len(inst)));overlap=np.zeros_like(matrix)
 for i,r in enumerate(active):
  pred=(labels==r['id'])&known
  for j,ref in enumerate(inst):
   both=int((pred&ref).sum());overlap[i,j]=both;u=int((pred|ref).sum());matrix[i,j]=both/u if u else 0
 matches=[]
 if matrix.size:
  ii,jj=linear_sum_assignment(-((matrix>=.1).astype(float)+matrix))
  matches=[(int(i),int(j)) for i,j in zip(ii,jj) if matrix[i,j]>=.1]
 matched_ids={active[i]['id'] for i,j in matches};ambiguous=[r for r in active if r.get('match',{}).get('assessed_fraction',1)<.95 or r.get('match',{}).get('touches_ignored',False)]
 unknown_ids={r['id'] for r in ambiguous};fp=sum(r['id'] not in matched_ids and r['id'] not in unknown_ids for r in active);tp=len(matches);nt=len(inst)
 lesion=[]
 for i,j in matches:
  truth_area=int(inst[j].sum());observed=active[i]['area_pixels'];split=int((overlap[:,j]>0).sum())>1;merge=int((overlap[i]>0).sum())>1
  partial=bool((ndi.binary_dilation(inst[j],structure=np.ones((3,3)))&~known).any()) or active[i].get('match',{}).get('touches_ignored',False)
  lesion.append(dict(candidate_id=active[i]['id'],reference_index=j,iou=float(matrix[i,j]),reference_area_pixels=truth_area,predicted_area_pixels=observed,signed_area_error_um2=(observed-truth_area)*PX_UM**2,absolute_area_error_um2=abs(observed-truth_area)*PX_UM**2,relative_area_error=(observed-truth_area)/max(1,truth_area),ambiguous_split_merge=split or merge,partial_due_to_unknown=partial,area_interpretation='observed footprint; edge-clipped regions remain provisional'))
 strata=[]
 if size_cutoffs is not None:
  for group in range(3):
   refs=[j for j,ref in enumerate(inst) if int(np.searchsorted(size_cutoffs,ref.sum(),side='right'))==group]
   strata.append(dict(stratum=['small','middle','large'][group],reference_regions=len(refs),detected=sum(j in refs for i,j in matches),cutoffs_pixels=size_cutoffs))
 return dict(dice=2*intersect/den if den else 1.,iou=intersect/union if union else 1.,true_positive_matches=tp,false_positive_candidates=fp,reference_regions=nt,predicted_candidates=len(active),insufficiently_assessed_candidates=len(ambiguous),recall=tp/nt if nt else None,precision=tp/(tp+fp) if tp+fp else None,negative_field=not bool(t.any()),reference_area_pixels=int(t.sum()),predicted_assessed_area_pixels=int(p.sum()),signed_total_area_error_um2=float((int(p.sum())-int(t.sum()))*PX_UM**2),absolute_total_area_error_um2=float(abs(int(p.sum())-int(t.sum()))*PX_UM**2),matched_lesions=lesion,size_strata=strata,matching='maximum one-to-one native footprint IoU >= 0.10; computational correspondence only')

def make_examples(name,records):
 output=[]
 for r in records:
  sid=r['scan_id'];p=HERE/'fits'/name/'predictions'/(sid+'.npz');doc=read(p.with_suffix('.json'))
  if r['animal'] in doc['training_animals'] or not doc['animal_out_of_sample']:raise ValueError('In-sample candidate leakage')
  score=npz(p)['score'];labels,cs=extract(score,npz(HERE/'cache'/sid/'context.npz')['channels']);correspondence(labels,cs,npz(r['target_file']['path']))
  for c in cs:c.update(scan_id=sid,animal=r['animal'],fit=name,prediction_sha256=doc['prediction']['sha256'],cnv_training_animals=doc['training_animals'])
  output.extend(cs)
 return output
