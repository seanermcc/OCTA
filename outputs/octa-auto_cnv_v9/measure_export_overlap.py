"""Measure exact raw export separately from availability-masked model context."""
from common import *
from context import loader
rows=[]
for r in read(HERE/'data/supervision.json')['records']:
 a=r['acquisition'];z,meta=loader.load_masks(a['scan_id'],a['source']);truth=npz(r['target_file']['path'])['target'];channels=npz(HERE/'cache'/a['scan_id']/'context.npz')['channels']
 rows.append(dict(scan_id=a['scan_id'],source=meta['selection'],positive_pixels=int(truth.sum()),raw_vessel_overlap_pixels=int((truth&z['vessel_mask']).sum()),raw_onh_overlap_pixels=int((truth&z['onh_mask']).sum()),availability_masked_vessel_overlap_pixels=int((truth&(channels[0]>0)).sum()),availability_masked_onh_overlap_pixels=int((truth&(channels[1]>0)).sum()),mask_sha256=meta['masks_sha256']))
totals={k:sum(r[k] for r in rows) for k in rows[0] if k.endswith('_pixels')}
write(HERE/'reports/export_overlap_audit.json',dict(export_manifest=fingerprint(EXPORT/'manifest.json'),totals=totals,records=rows,raw_export_measured_separately=True))
print(json.dumps(totals))
