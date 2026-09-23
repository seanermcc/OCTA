"""Separate regional assessments. Called for mutations only by GUI actions."""
import copy
import time
from .common import read
from cnv_review_v1.data import atomic_json,fingerprint

class QualityStore:
    def __init__(self,directory,sid,bscan,width,model):
        self.path=directory/f'{sid}_b{bscan:04d}.json'
        self.data=dict(format='regional-quality-review-1',scan_id=sid,bscan=int(bscan),width=int(width),
                      model_identity=model,coordinate_frame='native B-scan and A-line; half-open [lo,hi)',
                      training_use='none; not positional targets, visibility, reliability, or exclusions',
                      records=[],undo=[],events=[])
        if self.path.exists():
            saved=read(self.path)
            for key in ('format','scan_id','bscan','width','model_identity'):
                if saved[key]!=self.data[key]:raise ValueError(f'Quality record {key} mismatch')
            self.data=saved
        self.disk_hash=fingerprint(self.path)

    def _save(self,action):
        if fingerprint(self.path)!=self.disk_hash:raise RuntimeError('Quality ratings changed in another window; reopen before editing.')
        self.data['events'].append(dict(action=action,timestamp=time.time()))
        atomic_json(self.path,self.data);self.disk_hash=fingerprint(self.path)

    def rate(self,lo,hi,rating,reason='',sample_id=None,metrics_revealed_before=False):
        if rating not in ('Good','Bad','Unsure'):raise ValueError('Invalid rating')
        if not 0<=lo<hi<=self.data['width']:raise ValueError('Invalid native strip')
        self.data['undo'].append(copy.deepcopy(self.data['records']))
        self.data['records'].append(dict(lo=int(lo),hi=int(hi),rating=rating,reason=reason,
               sample_id=sample_id,timestamp=time.time(),metrics_revealed_before=bool(metrics_revealed_before)))
        self._save('rate')

    def clear(self):
        self.data['undo'].append(copy.deepcopy(self.data['records']));self.data['records']=[];self._save('clear B-scan')

    def undo(self):
        if self.data['undo']:
            self.data['records']=self.data['undo'].pop();self._save('undo')

def strip_rating(records,lo,hi):
    marks=[None]*(hi-lo)
    for r in records:
        for col in range(max(lo,r['lo']),min(hi,r['hi'])):marks[col-lo]=r['rating']
    if not all(marks):return None
    if 'Unsure' in marks:return 'Unsure'
    # Mixed good/bad portions are not collapsed to an unqualified good judgment.
    return 'Bad' if 'Bad' in marks else 'Good'
