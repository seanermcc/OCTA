"""Separate inherited CNV knowledge from vessel/ONH context provenance."""
from common import *
from context import loader
from collections import Counter
def scalar(d,key,default=None):
 v=d.get(key,default)
 return v[0] if isinstance(v,list) and len(v)==1 else v
rows=[]
for r in read(HERE/'data/supervision.json')['records']:
 a=r['acquisition'];z,p=loader.load_masks(a['scan_id'],a['source']);metadata=json.loads(str(z['metadata_json']))
 cnv_review=metadata.get('reviewed_targets',[False])[0];cnv_pixels=scalar(metadata,'lesion_pixel_count',0)
 rows.append(dict(scan_id=a['scan_id'],source=p['selection'],vessel_reviewed=p['vessel_reviewed'],onh_reviewed=p['onh_reviewed'],manual_record_contains_prior_cnv_review=bool(cnv_review),manual_record_prior_cnv_pixels=int(cnv_pixels),inherited_label_path=scalar(metadata,'inherited_label_path',''),inherited_label_sha256=scalar(metadata,'inherited_label_sha256',''),vessel_origin=scalar(metadata,'vasculature_origin','frozen classical'),manual_timestamp=p.get('labelled_at'),current_cnv_revision=r['revision'],v8_cnv_training_exposure=a['model1_training_exposure'],notes=p['notes'],direct_cnv_mask_used_as_context=False,interpretation='Prior CNV knowledge may inform human context editing; no independent end-to-end accuracy claim.'))
write(HERE/'reports/context_history_audit.json',dict(records=rows,manual_records_with_prior_cnv_review=sum(r['manual_record_contains_prior_cnv_review'] for r in rows),manual_records_with_prior_cnv_pixels=sum(r['manual_record_prior_cnv_pixels']>0 for r in rows),policy='Qualify manually assisted evaluation separately; never train CNV truth from these inherited context-record masks.'))
print(json.dumps(dict(manual_records_with_prior_cnv_review=sum(r['manual_record_contains_prior_cnv_review'] for r in rows),manual_records_with_prior_cnv_pixels=sum(r['manual_record_prior_cnv_pixels']>0 for r in rows))))
