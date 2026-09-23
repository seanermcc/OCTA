"""Read frozen overlay masks by scan ID, checking acquisition identity and grid."""
from pathlib import Path
import hashlib
import json
import numpy as np

HERE = Path(__file__).resolve().parent


def load_masks(scan_id, source_volume, shape=(512, 512)):
    records = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))['records']
    rec = next((r for r in records if r['scan_id'] == scan_id), None)
    if rec is None:
        raise KeyError('No vessel/ONH export for ' + scan_id)
    def identity(path):
        return str(path).replace('\\', '/').casefold().split('/octa_rawdata/', 1)[-1]
    if identity(source_volume) != identity(rec['source_volume']):
        raise ValueError('Acquisition source mismatch')
    path = HERE / rec['masks']
    if hashlib.sha256(path.read_bytes()).hexdigest() != rec['masks_sha256']:
        raise ValueError('Export hash mismatch')
    with np.load(path, allow_pickle=False) as z:
        data = {k: z[k].copy() for k in z.files}
    if str(data['axis_order']) != 'B-scan,A-line' or any(data[k].shape != tuple(shape) for k in ('vessel_mask', 'onh_mask')):
        raise ValueError('Overlay grid mismatch; do not resize or transpose silently')
    return data, rec
