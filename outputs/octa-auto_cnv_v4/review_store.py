"""RegionStore-compatible adapter with pixel provenance and explicit decisions.

Runs remain native [row,start,stop]. `runs` is a draft structural footprint;
only `reviewed_runs` is approved. Candidate core edits are a separate field.
The original automatic seed is immutable in proposals/. No CNV label writer
is invoked. Only reviewer GUI actions call save; tests use isolated fixtures.
"""
from common import *
from cnv_review_v1.data import Region, RegionStore, encode_mask, decode_mask, fingerprint
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class ReviewRegion(Region):
    core: object = None
    touched: object = None
    core_touched: object = None
    decision: str = 'unreviewed'
    events: list = field(default_factory=list)
    seed_ids: list = field(default_factory=list)

    def initialize(self):
        if self.core is None: self.core=self.mask.copy()
        if self.touched is None: self.touched=np.zeros_like(self.mask)
        if self.core_touched is None: self.core_touched=np.zeros_like(self.mask)
        return self

    @property
    def complete(self):
        return self.decision in ('approved','rejected')

    def record(self):
        self.initialize()
        result = dict(**super().record(), core_runs=encode_mask(self.core), edited_runs=encode_mask(self.touched),
            core_edited_runs=encode_mask(self.core_touched), decision=self.decision,
            reviewed_runs=encode_mask(self.mask) if self.decision=='approved' else [],
            unreviewed_runs=encode_mask(self.mask) if self.decision=='unreviewed' else [],
            events=self.events, seed_ids=self.seed_ids,
            annotation_semantics='draft structural footprint and separate candidate core; never a quantitative contour')
        result['draft_category'] = self.category
        if self.decision == 'unreviewed':
            result['category'] = 'Unclassified'
        return result

    def event(self, action, **details):
        self.events.append(dict(action=action, at=datetime.now(timezone.utc).isoformat(), **details))

class ReviewStore(RegionStore):
    def __init__(self,directory,scan,existing_mask,seed_path='',previous_directory=None):
        destination_path=Path(directory)/f'{scan.scan_id}_regions.json'
        previous_directory=Path(previous_directory) if previous_directory is not None else ROOT/'outputs/octa-auto_cnv_v3/review/regions'
        inherited=not destination_path.exists() and (previous_directory/destination_path.name).exists()
        super().__init__(previous_directory if inherited else directory,scan,existing_mask,seed_path)
        saved=read(self.path) if self.path.exists() else None
        if saved and self.seed_sha256 != fingerprint(seed_path):
            raise RuntimeError('Automatic seed changed since this review. Preserve the existing review and explicitly reconcile revisions before continuing.')
        if saved:
            regions=[]
            for rec in saved['regions']:
                if 'core_runs' not in rec: raise ValueError('Review lacks v2 pixel provenance')
                r=ReviewRegion(rec['id'],decode_mask(rec['runs'],scan.native_shape),rec.get('draft_category',rec['category']),rec['notes'],rec['origin'])
                r.core=decode_mask(rec['core_runs'],scan.native_shape)
                r.touched=decode_mask(rec['edited_runs'],scan.native_shape)
                r.core_touched=decode_mask(rec['core_edited_runs'],scan.native_shape)
                r.decision=rec['decision']; r.events=rec['events']; r.seed_ids=rec['seed_ids']; regions.append(r)
            self.regions=regions
        else:
            labels=npz(seed_path)['candidate_labels']
            self.regions=[ReviewRegion(f'auto-{k}',labels==k,origin='unreviewed automatic seed',seed_ids=[int(k)]).initialize() for k in np.unique(labels) if k]
        if inherited:
            source_path=self.path
            for region in self.regions:
                region.event('opened saved v3 review in v4',source=str(source_path),sha256=fingerprint(source_path),revision=self.revision)
            self.path=destination_path;self.disk_hash=None;self.revision=0
            self.seed_path=str(seed_path);self.seed_sha256=fingerprint(seed_path)
        self.saved_signature=self.signature()

    def save(self,*args):
        if not self.dirty: return False
        self.path.parent.mkdir(parents=True,exist_ok=True)
        lock=self.path.with_suffix('.lock')
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:
            raise RuntimeError('Another reviewer is saving this acquisition. Edits remain in memory; retry after its save finishes.')
        try:
            os.close(fd)
            return super().save(*args)
        finally: lock.unlink(missing_ok=True)

