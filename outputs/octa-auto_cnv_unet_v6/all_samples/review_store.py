"""GUI-only decisions; ephemeral proposals never become saved labels by browsing."""
from common import *
from legacy_store import ReviewRegion
from cnv_review_v1.data import fingerprint as disk_fingerprint,decode_mask,atomic_json
from datetime import datetime,timezone

class ReviewStore:
    def __init__(self,directory,scan,model='B_267',proposal_root=None):
        self.path=dest(Path(directory)/f'{scan.scan_id}_regions.json');self.scan=scan
        self.proposal_root=Path(proposal_root) if proposal_root else HERE/'predictions'
        self.regions=[];self.revision=0;self.disk_hash=disk_fingerprint(self.path)
        self.scan_review=dict(status='in_progress',whole_field_checked=False)
        self.review_context=dict(automatic_proposals_seen=False,visible_models=[],active_seconds_by_model={},events=[])
        self.loaded_review_path=self.path if self.path.exists() else None
        if self.path.exists():
            data=read(self.path)
            assert data['scan_id']==scan.scan_id and tuple(data['native_shape'])==scan.native_shape
            assert Path(data['source_volume']).resolve()==scan.source_volume.resolve()
            self.revision=data['revision'];self.scan_review=data['scan_review'];self.review_context=data['review_context']
            for rec in data['regions']:
                r=ReviewRegion(rec['id'],decode_mask(rec['runs'],scan.native_shape),rec.get('draft_category',rec['category']),rec['notes'],rec['origin']).initialize()
                r.core=decode_mask(rec['core_runs'],scan.native_shape);r.touched=decode_mask(rec['edited_runs'],scan.native_shape)
                r.core_touched=decode_mask(rec['core_edited_runs'],scan.native_shape);r.decision=rec['decision'];r.events=rec['events'];r.seed_ids=rec['seed_ids']
                self.regions.append(r)
        self.switch(model);self.saved_signature=self.signature()

    @staticmethod
    def persistent(r):
        return bool(r.events or r.notes or r.decision!='unreviewed' or (r.touched is not None and r.touched.any()) or not r.seed_ids)

    def signature(self):
        return json.dumps(dict(regions=[r.record() for r in self.regions if self.persistent(r)],scan_review=self.scan_review),sort_keys=True)

    @property
    def dirty(self):return self.signature()!=self.saved_signature

    def invalidate_complete(self):self.scan_review=dict(status='in_progress',whole_field_checked=False)

    def switch(self,model):
        self.regions=[r for r in self.regions if self.persistent(r)]
        self.model=model;path=self.proposal_root/model/f'{self.scan.scan_id}.npz'
        provenance=prediction_provenance(self.proposal_root,model,self.scan.scan_id,missing_ok=True)
        if provenance is not None:verify(provenance['prediction'])
        self.seed_path=str(path);self.seed_sha256=disk_fingerprint(path)
        a=npz(path);labels=a['candidate_labels'];self.proposal_mask=a['mask'];self.proposal_score=a['score']
        assert labels.shape==self.scan.native_shape and np.array_equal(labels>0,self.proposal_mask)
        ids={r.id for r in self.regions}
        for k in range(1,int(labels.max())+1):
            uid=f'{model}:{k}'
            if uid not in ids:self.regions.append(ReviewRegion(uid,labels==k,origin='unreviewed automatic seed '+model,seed_ids=[k]).initialize())

    def save(self,*unused):
        if not self.dirty:return False
        lock=self.path.with_suffix('.lock')
        try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise RuntimeError('Another window is saving this scan; edits remain in memory.')
        try:
            os.close(fd)
            if disk_fingerprint(self.path)!=self.disk_hash:raise RuntimeError('Another window changed this review; edits remain in memory.')
            records=[r.record() for r in self.regions if self.persistent(r)]
            data=dict(format='1-cnv-region-review',reviewer_version=VERSION,scan_id=self.scan.scan_id,
                source_volume=str(self.scan.source_volume.resolve()),native_shape=list(self.scan.native_shape),axis_order='B-scan,A-line',
                category_names=['Full Lesion','Normal','Other'],revision=self.revision+1,saved_at=datetime.now(timezone.utc).isoformat(),
                regions=records,scan_review=self.scan_review,review_context=self.review_context,
                reference_sources=self.scan.metadata.get('reference_review',{}).get('sources',[]),
                models_manifest=fingerprint(HERE/'models.json') if (HERE/'models.json').exists() else None,
                proposal_policy='Immutable six-model proposals; only explicit edits/decisions are saved. No suggestion is approved by switching or browsing.',
                seed_path=self.seed_path,seed_sha256=self.seed_sha256)
            if self.path.exists():
                history=dest(self.path.parent/'history'/f'{self.path.stem}_r{self.revision:04d}.json')
                if not history.exists():atomic_json(history,read(self.path))
            atomic_json(self.path,data);self.revision+=1;self.disk_hash=disk_fingerprint(self.path);self.saved_signature=self.signature()
            return True
        finally:lock.unlink(missing_ok=True)
