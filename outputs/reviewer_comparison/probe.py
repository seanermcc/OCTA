import sys, json, hashlib
from pathlib import Path
import numpy as np
root=Path('F:/octa')
sys.path.insert(0,str(root/'code/code'))
sys.path.insert(0,str(root/'code/outputs/octa-seg/octa-seg_v3/review/code'))
from octa_seg_v3.feedback import resolve, position_targets
for who in ['lead','shichu']:
    paths=list((root/'reviewers'/who/'journals').glob('*.json'))
    print(who,len(paths))
    counts={}
    for path in paths:
        j=json.loads(path.read_text())
        sid=j['scan_id']; row=j['bscan']
        dirs=[p/sid for p in (root/'For_Segmentation/Reviewed_Samples',root/'For_Segmentation/More_Samples') if (p/sid).exists()]
        if not dirs:
            print('MISSING',sid); continue
        d=dirs[0]
        with np.load(d/'measurements.npz') as z:
            raw=z['raw_position_branch'][row]; offset=int(z['label_offset']); shadow=z['shadow'][row]; vessel=z['vessel'][row]
        images=np.load(d/'images.npy',mmap_mode='r')
        try:
            r=resolve(j['events'][:j['cursor']],raw,offset,images.shape[1])
            t=position_targets(r,shadow,r['valid_geometry'],vessel)
            counts[r['review_status']]=counts.get(r['review_status'],0)+1
            print(path.stem,r['review_status'],'approved',t['approved_position'].sum(),'drawn',t['reliable_manual'].sum())
        except Exception as e: print('ERROR',path.stem,str(e))
    print(counts)
