"""Independent development evaluation, final bundles and unfiltered gallery exports."""
from common import *
from candidates import extract,correspondence,fit_scorer,adjust,metrics,make_examples,FEATURES
from collections import Counter,defaultdict
import shutil
from media import run as media

def summary(rows):
 n=len(rows)
 if not n:return dict(acquisitions=0)
 tp=sum(r['true_positive_matches'] for r in rows);fp=sum(r['false_positive_candidates'] for r in rows);nt=sum(r['reference_regions'] for r in rows)
 lesion=[l for r in rows for l in r['matched_lesions'] if not l['ambiguous_split_merge'] and not l['partial_due_to_unknown']]
 return dict(acquisitions=n,reference_regions=nt,true_positive_matches=tp,false_positive_candidates=fp,lesion_recall=tp/nt if nt else None,lesion_precision=tp/(tp+fp) if tp+fp else None,false_positives_per_acquisition=fp/n,mean_pixel_dice=float(np.mean([r['dice'] for r in rows])),mean_pixel_iou=float(np.mean([r['iou'] for r in rows])),mean_absolute_total_area_error_um2=float(np.mean([r['absolute_total_area_error_um2'] for r in rows])),unambiguous_matched_lesions=len(lesion),matched_lesion_mean_absolute_area_error_um2=float(np.mean([l['absolute_area_error_um2'] for l in lesion])) if lesion else None,insufficiently_assessed_candidates=sum(r['insufficiently_assessed_candidates'] for r in rows),negative_fields=sum(r['negative_field'] for r in rows))

def development(m,protocol):
 rows=[];outer_examples=[];scorers=[]
 for f in protocol['folds']:
  ev=[r for r in m['records'] if r['animal'] in f['evaluation_animals']];tr=[r for r in m['records'] if r['animal'] in f['train_animals']]
  examples=[]
  for j,inner in enumerate(f['inner']):examples+=make_examples(f"outer{f['fold']}_inner{j}_m2",[r for r in tr if r['animal'] in inner['candidate_animals']])
  if any(r['animal'] in f['evaluation_animals'] or set(r['cnv_training_animals'])&set(f['evaluation_animals']) for r in examples):raise ValueError('Nested scorer leakage')
  scorer=fit_scorer(examples,dict(role='inner animal-excluded predictions only',fold=f['fold'],excluded_evaluation_animals=f['evaluation_animals'],protocol_sha256=sha(HERE/'data/protocol.json')));write(HERE/'development'/f"outer{f['fold']}_scorer.json",scorer);scorers.append(scorer)
  write(HERE/'development'/f"outer{f['fold']}_fitting_examples.json",dict(records=examples))
  outer_examples+=make_examples(f"outer{f['fold']}_m2",ev)
  sizes=[x['pixels'] for r in tr for x in r['regions']];cuts=np.quantile(sizes,[1/3,2/3]).tolist()
  for r in ev:
   sid=r['scan_id'];truth=npz(r['target_file']['path']);context=npz(HERE/'cache'/sid/'context.npz')['channels']
   for model in (1,2):
    name=f"outer{f['fold']}_m{model}";score=npz(HERE/'fits'/name/'predictions'/(sid+'.npz'))['score'];labels,cs=extract(score,context);correspondence(labels,cs,truth)
    if model==2:cs=adjust(cs,scorer)
    views=[(f'm{model}_raw',None)]+([('m2_adjusted',[c['id'] for c in cs if c['display_selected']])] if model==2 else [])
    write(HERE/'development/candidates'/f'{sid}_m{model}.json',dict(scan_id=sid,fold=f['fold'],fit=name,candidates=cs,score_provenance=f'outer{f["fold"]}_scorer.json' if model==2 else None))
    for view,ids in views:rows.append(dict(scan_id=sid,animal=r['animal'],context_source=r['context']['source'],vessel_reviewed=r['context']['vessel_reviewed'],onh_reviewed=r['context']['onh_reviewed'],fold=f['fold'],view=view,**metrics(labels,cs,truth,ids,cuts)))
 results={}
 for view in ('m1_raw','m2_raw','m2_adjusted'):
  selected=[r for r in rows if r['view']==view]
  results[view]=dict(overall=summary(selected),per_animal={a:summary([r for r in selected if r['animal']==a]) for a in m['animals']},per_context_source={s:summary([r for r in selected if r['context_source']==s]) for s in sorted({r['context_source'] for r in selected})},per_target_review={k:{str(value):summary([r for r in selected if r[k]==value]) for value in (False,True)} for k in ('vessel_reviewed','onh_reviewed')},negative_fields=summary([r for r in selected if r['negative_field']]),size_strata={s:dict(reference_regions=sum(x['reference_regions'] for r in selected for x in r['size_strata'] if x['stratum']==s),detected=sum(x['detected'] for r in selected for x in r['size_strata'] if x['stratum']==s),definition='each fold uses training-animal lesion-area tertiles; not a pooled fixed biological size range') for s in ('small','middle','large')})
 write(HERE/'development/metrics.json',dict(views=results,records=rows,interpretation='small-cohort animal-grouped CNV development; upstream layers and manually assisted vessel/ONH context are not independent of animal history; no new-image accuracy guarantee'))
 final=fit_scorer(outer_examples,dict(role='pooled outer animal-excluded m2 predictions; deployable final scorer only, never used to report independent evaluation',fits=[f"outer{f['fold']}_m2" for f in protocol['folds']],protocol_sha256=sha(HERE/'data/protocol.json')))
 write(HERE/'development/final_scorer_examples.json',dict(records=outer_examples));write(HERE/'bundles/v9_m2/scorer.json',final)
 return results,final

def provenance_audit(m):
 batch=read(ROOT/'outputs/octa-vessel_seg_v1-batch/manifest.json');byid={r['scan_id']:r for r in batch['scans']};rows=[]
 for r in m['records']:
  sid=r['scan_id'];z=npz(r['target_file']['path']);c=npz(HERE/'cache'/sid/'context.npz')['channels'];p=z['target'];b=byid.get(sid,{})
  rows.append(dict(scan_id=sid,source=r['context']['source'],positive_pixels=int(p.sum()),vessel_overlap_pixels=int((p&(c[0]>0)).sum()),onh_overlap_pixels=int((p&(c[1]>0)).sum()),vessel_reviewed=r['context']['vessel_reviewed'],onh_reviewed=r['context']['onh_reviewed'],vessel_available_fraction=float(c[2].mean()),onh_available_fraction=float(c[3].mean()),vessel_uncertain_pixels=int(c[6].sum()),onh_uncertain_pixels=int(c[7].sum()),frozen_v1_human_onh_dependency=b.get('identity',{}).get('onh_label_sha256'),notes=r['context'].get('notes','')))
 result=dict(records=rows,source_counts=dict(Counter(r['source'] for r in rows)),positive_pixels=sum(r['positive_pixels'] for r in rows),vessel_overlap_pixels=sum(r['vessel_overlap_pixels'] for r in rows),onh_overlap_pixels=sum(r['onh_overlap_pixels'] for r in rows),provenance_findings=['Frozen v1 is classical vessel processing with parameters initially evaluated on WT vessel labels, not learned v2 predictions.','Frozen v1 can subtract pre-existing human ONH masks; this is manually assisted wherever a dependency exists.','Saved manual context includes drafts and untouched automatic pixels. Per-target review and uncertainty/brush maps are explicit channels.','No CNV mask is consumed by the vessel feature builder, but label-informed human vessel/ONH editing cannot be ruled out.','The shared automatic layer inputs use frozen all-labelled layer weights. Animal grouping applies to newly trained CNV networks/scorers, not independent validation of the whole upstream pipeline.'],sources=[fingerprint(ROOT/'code/vasculature_baseline.py'),fingerprint(ROOT/'code/vasculature_shape_gate.py'),fingerprint(ROOT/'outputs/octa-vessel_seg_v1-batch/manifest.json')])
 write(HERE/'reports/context_audit.json',result);return result

def export_bundles(m,scorer):
 for model in (1,2):
  source=HERE/'fits'/f'final_m{model}';out=HERE/'bundles'/f'v9_m{model}';complete=read(source/'complete.json')
  for name in ('final.pt','normalization.json','config.json'):
   p=dest(out/name);tmp=p.with_suffix(p.suffix+'.tmp');shutil.copyfile(source/name,tmp);os.replace(tmp,p)
  for name in ('models.py','v6_model.py','legacy.py','common.py','context.py','prepare.py','candidates.py'):shutil.copyfile(HERE/name,dest(out/'source'/name))
  write(out/'bundle.json',dict(model=f'v9_m{model}',checkpoint=fingerprint(out/'final.pt'),normalization=fingerprint(out/'normalization.json'),contract=complete['contract'],thresholds=dict(raw_pixel=.7,adjusted_candidate=.5 if model==2 else None),context_policy='none added; original 19-channel handling' if model==1 else '11 appended native mask/availability/review/uncertainty/brush/source channels; see protocol',scorer=fingerprint(out/'scorer.json') if model==2 else None,protocol=fingerprint(HERE/'data/protocol.json'),snapshot=fingerprint(HERE/'data/supervision.json'),resume_checkpoint=fingerprint(source/'latest.pt'),warning='Development adjustment transfer to all-label segmenter is unvalidated; candidate scores are uncalibrated.'))

def gallery_export(scorer):
 cases=read(HERE/'data/selection.json')['acquisitions'];media_records={r['scan_id']:r for r in read(HERE/'gallery/media_manifest.json')['records']};index=[];handoff=[]
 for a in cases:
  sid=a['scan_id'];context=npz(HERE/'cache'/sid/'context.npz')['channels'];allcs={};arrays={};status=[]
  for model in (1,2):
   pred=HERE/'fits'/f'final_m{model}'/'predictions'/(sid+'.npz');doc=read(pred.with_suffix('.json'));verify(doc['prediction']);z=npz(pred);labels,cs=extract(z['score'],context)
   if model==2:cs=adjust(cs,scorer)
   allcs[f'm{model}']=cs;arrays[f'm{model}_score']=z['score'];arrays[f'm{model}_labels']=labels;arrays[f'm{model}_raw_mask']=z['raw_mask'];status.append(dict(model=f'v9_m{model}',status='complete',prediction=doc['prediction'],checkpoint=doc['checkpoint']))
  adjusted=np.isin(arrays['m2_labels'],[c['id'] for c in allcs['m2'] if c['display_selected']]);arrays['m2_adjusted_display_mask']=adjusted
  save(HERE/'predictions'/(sid+'.npz'),scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'),**arrays)
  write(HERE/'gallery/assets'/sid/'candidates.json',dict(scan_id=sid,**allcs,scorer_sha256=sha(HERE/'bundles/v9_m2/scorer.json'),geometry_policy='raw and adjusted m2 component geometry identical; adjusted display selects whole candidates only'))
  c=read(HERE/'cache'/sid/'context.json');md=media_records[sid]
  row=dict(scan_id=sid,animal=a['animal'],eye=a['eye'],session_date=a['session_date'],day_label=a['day_label'],days_post_laser=a['days_post_laser'],day_basis=a.get('eligibility_day_basis',a.get('day_basis')),day_drift=a.get('day_drift'),source_session_folder=a.get('source_session_folder',a.get('session_folder')),source_folder_differs_from_index=a.get('source_folder_differs_from_index'),visit_group=a['visit_group'],queue_position=a['queue_position'],source_identity=a['source_identity'],context_source=c['source'],vessel_reviewed=c['vessel_reviewed'],onh_reviewed=c['onh_reviewed'],onh_available=c['onh_available'],context_notes=c.get('notes'),prior_cnv_supervision=False,prior_automatic_cnv_inference=True,prior_vessel_review=a['prior_vessel_review'],prior_upstream_animal_exposure=a.get('upstream_animal_exposure'),quality_note='No known rejection; acquisition quality not certified'+('; '+a['scan_notes'] if a.get('scan_notes') else ''),m1_count=len(allcs['m1']),m2_count=len(allcs['m2']),adjusted_count=sum(c['display_selected'] for c in allcs['m2']),hidden_count=sum(not c['display_selected'] for c in allcs['m2']),m1_pixels=int(arrays['m1_raw_mask'].sum()),m2_pixels=int(arrays['m2_raw_mask'].sum()),disagreement_pixels=int((arrays['m1_raw_mask']^arrays['m2_raw_mask']).sum()),canonical_crop_offset=md['canonical_crop_offset'],status=status)
  index.append(row);handoff.append(dict(acquisition=a,prediction_choices=status,combined_arrays=fingerprint(HERE/'predictions'/(sid+'.npz')),candidates=fingerprint(HERE/'gallery/assets'/sid/'candidates.json'),selected_model=None,reviewed=False,automatic_proposals_only=True,correction_adapter_contract='choose v9_m1 or v9_m2; decode candidate runs; preserve source identity and native grid; create drafts in a NEW correction queue only upon user request'))
 write(HERE/'gallery/data.json',dict(cases=index,selection_sha256=sha(HERE/'data/selection.json'),score_status='uncalibrated',raw_pixel_threshold=.7,adjusted_candidate_threshold=.5))
 write(HERE/'correction_handoff.json',dict(schema='cnv-v9-dual-prediction-handoff-v1',acquisitions=handoff,labels_created=False,model_selected=None));return index

def preserve(m):
 fps=read(HERE/'data/preservation_before.json')['files'];fps += [fp for p in (HERE/'cache').glob('*/manifest.json') for fp in read(p)['inputs']];fps += [r['images'] for r in read(HERE/'gallery/media_manifest.json')['records']]
 fps += [r['source'] for r in read(HERE/'data/novelty_supplement.json')['records']]
 unique={fp['path']:fp for fp in fps}
 for fp in unique.values():verify(fp)
 result=dict(checked_at=time.time(),files_checked=len(unique),unchanged=True,inputs=list(unique.values()),annotation_heads_unchanged=all(sha(r['label']['path'])==r['label']['sha256'] for r in m['records']))
 write(HERE/'reports/preservation_after.json',result);return result

def report(m,results,context,index,preservation):
 def value(x):return 'n/a' if x is None else f'{x:.3f}'
 lines=['# CNV v9 comparison release','',f"Supervision: {len(m['records'])} confirmed acquisitions, {m['eligible_counts'].get('positive',0)} positive, {m['eligible_counts'].get('negative',0)} negative, {m['kept_regions']} kept human regions across {len(m['animals'])} animals. The deferred TS247 D7 acquisition is excluded from every fit, normalization, calibration and score.",'','Open **OPEN_GALLERY.cmd**. Both models have completed inference on the same '+str(len(index))+' acquisitions selected before inference. No winner was selected and no correction queue was started.','', '## Models and actual training','', 'Both use the original compact U-Net widths 16/32/64/128/256, fresh initialization, seed 267, 100 epochs × 32 optimizer steps, effective batch 4 processed together (measured batching amendment; same per-tile mean loss), AdamW lr 0.001 and weight decay 0.0001. Both use v8 Model 1 background-weighted BCE plus 0.5 positive-tile Dice. Checkpoints include optimizer, scaler and all RNG states for epoch-boundary resume.','', 'Model 1 retains the original 19 channels. Model 2 appends 11 native context channels; the complete order is in data/protocol.json. Its L2-regularized candidate scorer uses 12 features and changes ranking/display only. Scores are uncalibrated. All raw probabilities and unfiltered threshold candidates remain in predictions/*.npz and gallery candidate JSON.','', 'Training normalization uses only each fit’s training acquisitions. Missing sampling pools retain uniform animal selection and fall back deterministically; each fit records the pool inventory and actual fallback counts. Entirely unavailable measurements remain masked under the original input recipe.','', '## Independent CNV development evaluation','', 'Three outer animal folds; each outer m2 scorer is fitted using two inner animal-excluded models with no access to its evaluation animals. Four m1 fits and ten m2 fits total, including final all-label deployment. Thresholds, matching and regularization were frozen before predictions. The final deployment scorer uses pooled outer out-of-sample candidates and is never used to report independent development metrics.','', '| View | Lesion recall | Precision | FP / acquisition | Mean Dice | Mean IoU | Total area MAE µm² |','|---|---:|---:|---:|---:|---:|---:|']
 for view,report in results.items():
  s=report['overall'];lines.append('| '+view+' | '+' | '.join(value(s[k]) for k in ['lesion_recall','lesion_precision','false_positives_per_acquisition','mean_pixel_dice','mean_pixel_iou','mean_absolute_total_area_error_um2'])+' |')
 lines += ['', 'Per-animal, negative-field, context-source and per-target-review results, training-derived size strata, matching failures, and matched-region area errors are in development/metrics.json and development/candidates/. Region correspondence is computational, not confirmed biological identity.','', '## Context provenance and limits','',f"Exact export training coverage: {context['source_counts']}. Measured against these corrected CNV targets: {context['vessel_overlap_pixels']} vessel-overlap pixels and {context['onh_overlap_pixels']} ONH-overlap pixels out of {context['positive_pixels']} positive pixels. See reports/context_audit.json for per-acquisition measurements.",'']
 lines+=['- '+s for s in context['provenance_findings']]
 lines+=['','The cohort is small and selected for correction. These folds do not establish unseen-animal or new-image accuracy for the full pipeline. Candidate confidence learned from out-of-sample fold networks may transfer imperfectly to the all-label network. Small, irregular, uncertain and overlapping footprints were never geometrically filtered from human targets.','', '## Inspection and reuse','', 'The gallery shows structural OCT and actual OCTA with synchronized zoom/pan, native linked B-scans at rows 0–511, independent overlays, raw/adjusted m2 views, all down-ranked candidates, provisional areas and score contributions. Reviewer preferences use browser storage and a separate JSON export, never annotation files.','', 'Deployable bundles: bundles/v9_m1/ and bundles/v9_m2/. Dual model choices and cached native candidates: correction_handoff.json. Human review is still required before any footprint becomes a CNV label.','', f"Verification: {preservation['files_checked']} consumed upstream files rehashed unchanged. Synthetic/real-data verification and browser screenshots are recorded in verification/. All {len(index)} selected scans have both inference statuses complete.",'', 'Approximate area calibration: (1460/512)² µm² per native pixel. No lesion volume, unique biological-lesion count across repeat scans, or vascular-density measurement is claimed.']
 dest(HERE/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
 dest(HERE/'START_HERE.md').write_text('# Compare the two CNV v9 models\n\nDouble-click **OPEN_GALLERY.cmd**. The local HTML gallery contains all '+str(len(index))+' acquisitions, including zero-candidate cases.\n\n- Click an en-face view to inspect its native B-scan; row 0 and 511 buttons reach both ends. Wheel zoom and dragging are synchronized across views.\n- Turn vessel/ONH overlays on independently. Use “Recover hidden candidates” and the down-ranked table filter to inspect m2 candidates below the display threshold.\n- Model preference and notes save only in this browser; export JSON to keep a separate copy. They are not CNV labels.\n\nRead **REPORT.md** for development results and limitations. Both deployable bundles are under **bundles/**. The deferred TS247 scan was excluded. No model has been chosen, and no correction GUI or new correction round has been started.\n\nTo resume a failed compute/delivery stage, run **RUN_OR_RESUME.cmd** in this same release. Existing frozen manifests and complete fits are verified and reused.\n',encoding='utf8')

def run():
 if not (HERE/'COMPUTE_COMPLETE.json').exists():raise RuntimeError('Training/inference not complete; cannot publish a completed gallery')
 m=read(HERE/'data/supervision.json');protocol=read(HERE/'data/protocol.json');results,scorer=development(m,protocol);context=provenance_audit(m);export_bundles(m,scorer);media();index=gallery_export(scorer);preservation=preserve(m);report(m,results,context,index,preservation)
 write(HERE/'DELIVERY_COMPLETE.json',dict(at=time.time(),acquisitions=len(index),fits=14,model_bundles=['v9_m1','v9_m2'],winner=None,preservation_checked=True,browser_verification='see verification/BROWSER_QA.json'))
if __name__=='__main__':
 with RunLock():run()
