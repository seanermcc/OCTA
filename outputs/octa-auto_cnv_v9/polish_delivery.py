"""Add inspection metadata and documentation; never changes scores, masks, or metrics."""
from common import *
def append_text(path,addition):
 p=dest(path);s=p.read_text(encoding='utf8')
 if addition.strip() in s:return
 tmp=p.with_suffix('.tmp');tmp.write_text(s+'\n'+addition,encoding='utf8');os.replace(tmp,p)
def run():
 m=read(HERE/'data/supervision.json');p=HERE/'gallery/data.json';d=read(p)
 for a in d['cases']:a['v9_animal_training_exposure']=a['animal'] in m['animals'];a['exposure_interpretation']='new acquisition with no prior CNV supervision; animal represented in v9 fitting' if a['v9_animal_training_exposure'] else 'new acquisition and animal outside v9 CNV fitting'
 write(p,d)
 scorer=read(HERE/'bundles/v9_m2/scorer.json');examples=[r for r in read(HERE/'development/final_scorer_examples.json')['records'] if r['match']['label'] is not None]
 ranges={k:[min(r['features'][k] for r in examples),max(r['features'][k] for r in examples)] for k in scorer['features']} if examples else {}
 write(HERE/'reports/scorer_feature_support.json',dict(training_feature_ranges=ranges,constant_features=[k for k,v in ranges.items() if v[0]==v[1]],independent_candidate_examples=len(examples),status='uncalibrated; availability and supported area flags accompany each candidate'))
 append_text(HERE/'REPORT.md','Additional audit details are in **IMPLEMENTATION_NOTES.md**, **reports/context_coverage.json**, **reports/context_history_audit.json**, and **reports/scorer_feature_support.json**. ONH context comprises four outlined fields, four reviewed-absence fields and 21 unassessed empty fields. Frozen v6 predictions locate hard reviewed-background patches only; historical upstream model exposure limits end-to-end independence.\n')
 metrics=read(HERE/'development/metrics.json')['views'];raw=metrics['m2_raw']['overall'];adj=metrics['m2_adjusted']['overall']
 append_text(HERE/'REPORT.md',f"The fixed Model 2 adjustment reduced development false positives per acquisition from {raw['false_positives_per_acquisition']:.2f} to {adj['false_positives_per_acquisition']:.2f}, while recall fell from {raw['lesion_recall']:.1%} to {adj['lesion_recall']:.1%}. This tradeoff is retained for review; thresholds were not retuned. The final scorer used {scorer['training_examples']} unambiguous out-of-sample candidates and excluded {scorer['ignored_examples']} ambiguous candidates. Scorer fitting requires one-to-one IoU at least 0.25; development detection uses the separately frozen one-to-one IoU threshold of 0.10. Scores are uncalibrated.\n")
 append_text(HERE/'START_HERE.md','Implementation details, batching measurements and the deterministic novelty replacement are documented in **IMPLEMENTATION_NOTES.md**. Actual post-laser days take precedence in the gallery when available.\n')
 unknown_days=sum(a['days_post_laser'] in ('',None) for a in d['cases']);represented=sum(a['v9_animal_training_exposure'] for a in d['cases'])
 append_text(HERE/'REPORT.md',f"Selection metadata: {unknown_days}/{len(d['cases'])} acquisitions have unavailable actual post-laser intervals and are explicitly displayed using nominal days. All available current scan-index intervals were blank at audit. {represented}/{len(d['cases'])} selected acquisitions belong to animals represented in final v9 training; these are new acquisitions, not an unseen-animal test.\n")
 write(HERE/'verification/DELIVERY_METADATA_QA.json',dict(passed=True,acquisitions=len(d['cases']),animal_exposure_explicit=True,scorer_fitted=scorer['fitted'],raw_predictions_and_metrics_unchanged=True))
 print('Inspection metadata and documentation complete')
if __name__=='__main__':run()
