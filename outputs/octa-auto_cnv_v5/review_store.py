"""GUI-only CNV region saving, plus explicit whole-field review provenance."""
from common import *
from legacy_store import ReviewStore as LegacyStore, ReviewRegion
from cnv_review_v1.data import fingerprint, atomic_json
from datetime import datetime,timezone

class ReviewStore(LegacyStore):
    def __init__(self,directory,scan,existing_mask,seed_path='',previous_directory=None):
        self.scan_review={'status':'in_progress','whole_field_checked':False}
        self.review_context={'automatic_proposals_seen':False}
        name=f'{scan.scan_id}_regions.json'
        if previous_directory is None:
            previous_directory=next((ROOT/f'outputs/octa-auto_cnv_{v}/review/regions' for v in ('v4','v3')
                if (ROOT/f'outputs/octa-auto_cnv_{v}/review/regions'/name).exists()),ROOT/'outputs/octa-auto_cnv_v4/review/regions')
        existing=Path(directory)/name
        prior=existing if existing.exists() else Path(previous_directory)/name
        self.loaded_review_path=prior if prior.exists() else None
        super().__init__(directory,scan,existing_mask,seed_path,previous_directory)
        if prior.exists():
            record=read(prior)
            self.scan_review=record.get('scan_review',self.scan_review)
            self.review_context=record.get('review_context',self.review_context)
        self.saved_signature=self.signature()

    def signature(self):
        return json.dumps(dict(regions=[r.record() for r in self.regions],scan_review=self.scan_review),sort_keys=True)

    def invalidate_complete(self):
        self.scan_review={'status':'in_progress','whole_field_checked':False}

    def save(self,auto_source=None,surface_sources=None,vessel_source=None):
        if not self.dirty:return False
        self.path.parent.mkdir(parents=True,exist_ok=True)
        lock=self.path.with_suffix('.lock')
        try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise RuntimeError('Another window is saving this scan. Your edits are still here; retry after it finishes.')
        try:
            os.close(fd)
            if fingerprint(self.path)!=self.disk_hash:raise RuntimeError('This scan changed in another window. Your edits remain here; resolve that saved revision first.')
            data=dict(format='1-cnv-region-review',reviewer_version=VERSION,scan_id=self.scan.scan_id,
                source_volume=str(self.scan.source_volume.resolve()),native_shape=list(self.scan.native_shape),axis_order='B-scan,A-line',
                category_names=['Full Lesion','Normal','Other'],revision=self.revision+1,saved_at=datetime.now(timezone.utc).isoformat(),
                seed_path=self.seed_path,seed_sha256=self.seed_sha256,auto_source=auto_source,surface_sources=surface_sources or [],vessel_source=vessel_source or {},
                regions=[r.record() for r in self.regions],scan_review=self.scan_review,review_context=self.review_context)
            if self.path.exists():
                history=self.path.parent/'history'/f'{self.path.stem}_r{self.revision:04d}.json'
                if not history.exists():atomic_json(history,read(self.path))
            atomic_json(self.path,data)
            self.revision+=1;self.disk_hash=fingerprint(self.path);self.saved_signature=self.signature()
            return True
        finally:lock.unlink(missing_ok=True)
