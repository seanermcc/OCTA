"""Explicit image confirmation, transactional revisions, no implicit human labels."""
from common import *
import copy

STATES = {'draft','kept','unsure','excluded','removed'}

def annotation_signature(state):
    return digest({k:state[k] for k in ('regions','absence')})

def targets(state, shape, require_complete=False):
    positive = np.zeros(shape,bool); ignored = positive.copy()
    drafts = []
    for r in state['regions']:
        if r['state'] not in STATES: raise ValueError('Invalid region state')
        m = decode(r['runs'], shape)
        if r['state']=='removed': continue
        if not m.any(): drafts.append(r['id'] + ': empty footprint')
        if r['state']=='draft': drafts.append(r['id'] + ': unresolved draft')
        if r['state']=='kept': positive |= m
        elif r['state'] in ('unsure','excluded'): ignored |= m
    overlap = positive & ignored
    # Conflicts are always ignored, and must be acknowledged explicitly at confirmation.
    positive &= ~ignored
    complete = valid_confirmation(state)
    if require_complete and not complete: raise ValueError('No valid whole-image confirmation')
    background = ~(positive|ignored) if complete else np.zeros(shape,bool)
    return positive, background, ignored, drafts, int(overlap.sum())

def valid_confirmation(state):
    c = state.get('confirmation')
    return bool(c and c.get('annotation_sha256')==annotation_signature(state) and c.get('whole_field_checked'))

def completion_kind(state, shape):
    if not valid_confirmation(state): return 'deferred' if state.get('defer_reason') else 'draft'
    p,b,i,d,c = targets(state,shape)
    if d or (state['absence'] and (p.any() or i.any())): raise ValueError('Invalid completed field')
    if state['absence'] and not p.any() and not i.any(): return 'negative'
    if p.any(): return 'positive'
    raise ValueError('Completed field has neither confirmed CNV nor explicit absence')

class Store:
    def __init__(self, acquisition, directory=None, reviewer=None, synthetic=False):
        self.acquisition = acquisition; self.shape = tuple(acquisition.get('native_shape',[512,512]))[:2]
        self.directory = destination(directory or HERE/'review/regions')
        sid = acquisition['scan_id']
        if not sid or any(x in sid for x in '/\\:'): raise ValueError('Invalid acquisition ID')
        if synthetic and not self.directory.is_relative_to(HERE/'verification'): raise ValueError('Synthetic records require verification directory')
        if not synthetic and self.directory.is_relative_to(HERE/'verification'): raise ValueError('Verification records must be synthetic')
        self.synthetic=synthetic; self.path=self.directory/(sid+'.json')
        self.reviewer=reviewer or os.environ.get('USERNAME','unknown')
        self.state=dict(regions=[],absence=False,confirmation=None,defer_reason='')
        self.revision=0; self.undo_stack=[]; self.redo_stack=[]; self.context=dict(exposures=[],focused_seconds=0.)
        self.disk_hash=sha(self.path) if self.path.exists() else None
        if self.path.exists():
            data=read(self.path)
            if data['schema']!=SCHEMA or data['source_identity']!=acquisition['source_identity'] or data['native_shape']!=list(self.shape):
                raise ValueError('Saved record source/grid mismatch; reconcile explicitly')
            if data['synthetic']!=synthetic: raise ValueError('Synthetic namespace mismatch')
            self.state=data['state'];self.revision=data['revision'];self.context=data['context']
            self.undo_stack=data.get('undo',[]); self.redo_stack=data.get('redo',[])
            p,b,i,_,_=targets(self.state,self.shape)
            if data['masks']!={'positive':encode(p),'reviewed_background':encode(b),'ignored':encode(i)}:
                raise ValueError('Stored targets disagree with annotation state')
            completion_kind(self.state,self.shape)
        self.saved_signature=digest(self.state);self.saved_context=digest(self.context)

    @property
    def dirty(self):
        return digest(self.state)!=self.saved_signature or (self.disk_hash is not None and digest(self.context)!=self.saved_context)

    def checkpoint(self):
        self.undo_stack.append(copy.deepcopy(self.state)); self.undo_stack=self.undo_stack[-40:];self.redo_stack.clear()

    def edit(self, fn):
        proposed=copy.deepcopy(self.state);fn(proposed)
        if proposed==self.state:return
        self.checkpoint();self.state=proposed;self.state['confirmation']=None;self.state['defer_reason']=''

    def add(self, source=None, mask=None):
        r=dict(id=uuid.uuid4().hex[:12],state='draft',runs=encode(mask) if mask is not None else [],
               origin=source or dict(kind='manual',reviewer=self.reviewer),created_at=now())
        self.edit(lambda s:(s['regions'].append(r),s.update(absence=False)))
        return len(self.state['regions'])-1

    def set_region(self,index,mask=None,state=None):
        if state and state not in STATES:raise ValueError(state)
        if self.state['absence'] and state and state!='removed':
            raise ValueError('Uncheck No-CNV present before restoring this region as CNV, unsure or excluded. No annotations were erased.')
        def change(s):
            r=s['regions'][index]
            if mask is not None:
                if mask.shape!=self.shape:raise ValueError('Mask grid mismatch')
                r['runs']=encode(mask)
            if state:r['state']=state
        self.edit(change)

    def absence(self,checked):
        if checked and any(r['state']!='removed' for r in self.state['regions']):
            raise ValueError('No-CNV means the entire image is assessable and absent. Explicitly remove active CNV, draft, unsure and excluded regions first.')
        self.edit(lambda s:s.update(absence=bool(checked)))

    def defer(self,reason):
        if not reason.strip():raise ValueError('Enter a reason for deferring')
        self.edit(lambda s:s.update(defer_reason=reason))
        self.state['defer_reason']=reason

    def confirm(self,ignore_conflicts=False):
        p,_,i,d,overlap=targets(self.state,self.shape)
        if d:raise ValueError('Resolve all drafts and empty footprints before confirming: '+', '.join(d))
        if self.state['absence'] and any(r['state']!='removed' for r in self.state['regions']):raise ValueError('Absence conflicts with active regions')
        if not p.any() and not self.state['absence']:raise ValueError('No kept CNV: select No-CNV only if the entire field is assessable; otherwise defer.')
        if overlap and not ignore_conflicts:raise ValueError(f'{overlap} positive/uncertain overlap pixels. Resolve them, or explicitly confirm with conflicts ignored.')
        self.checkpoint();self.state['defer_reason']=''
        self.state['confirmation']=dict(whole_field_checked=True,at=now(),reviewer=self.reviewer,
            annotation_sha256=annotation_signature(self.state),completion_revision=self.revision+1,
            ignored_conflict_pixels=overlap,overlap_policy='explicitly ignored' if overlap else 'no overlap')

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(copy.deepcopy(self.state));self.state=self.undo_stack.pop()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy(self.state));self.state=self.redo_stack.pop()

    def save(self):
        if not self.dirty:return False
        destination(self.path);lock=self.path.with_suffix('.lock')
        try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise RuntimeError('Another writer holds the lock. Edits remain in memory. If a process crashed, preserve its files and remove the stale lock only after checking that it has exited.')
        try:
            os.write(fd,json.dumps(dict(pid=os.getpid(),at=now())).encode());os.close(fd)
            if (sha(self.path) if self.path.exists() else None)!=self.disk_hash:
                raise RuntimeError('Stale writer: another window saved this acquisition. Your edits remain in memory; do not overwrite the newer revision.')
            p,b,i,_,_=targets(self.state,self.shape)
            data=dict(schema=SCHEMA,scan_id=self.acquisition['scan_id'],source_identity=self.acquisition['source_identity'],
                acquisition=self.acquisition,native_shape=list(self.shape),axis_order='B-scan,A-line',synthetic=self.synthetic,
                revision=self.revision+1,saved_at=now(),reviewer=self.reviewer,state=self.state,context=self.context,
                kind=completion_kind(self.state,self.shape),masks=dict(positive=encode(p),reviewed_background=encode(b),ignored=encode(i)),
                undo=self.undo_stack,redo=self.redo_stack)
            # Revision is durable before head replacement. Orphan revisions after failure are recoverable, never authoritative.
            history=self.directory/'history'/self.path.stem/(f'r{self.revision+1:06d}_{uuid.uuid4().hex[:8]}.json')
            atomic(history,data);atomic(self.path,data)
            self.revision+=1;self.disk_hash=sha(self.path);self.saved_signature=digest(self.state);self.saved_context=digest(self.context)
            return True
        finally:lock.unlink(missing_ok=True)

def progress(acquisitions, directory=None, active=None, verify_synthetic=False):
    directory=Path(directory or HERE/'review/regions');counts=dict(positive=0,negative=0,draft=0,deferred=0)
    if verify_synthetic and not directory.resolve().is_relative_to(HERE/'verification'):raise ValueError('Synthetic counts only in verification')
    animals={a['animal']:dict(positive=0,negative=0) for a in acquisitions};seen=set();errors=[]
    for a in acquisitions:
        key=a['source_identity']
        if key in seen:continue
        seen.add(key);path=directory/(a['scan_id']+'.json')
        try:
            if active and active.acquisition['scan_id']==a['scan_id'] and (not active.synthetic or verify_synthetic):
                state=active.state
                if not active.path.exists() and not active.dirty:continue
            elif path.exists():
                doc=read(path)
                if (doc['synthetic'] and not verify_synthetic) or doc['source_identity']!=key:continue
                if doc['schema']!=SCHEMA or doc['native_shape']!=list(a.get('native_shape',[512,512]))[:2]:raise ValueError('Schema/grid mismatch')
                state=doc['state']
                p,b,ig,_,_=targets(state,tuple(doc['native_shape']))
                if doc['masks']!={'positive':encode(p),'reviewed_background':encode(b),'ignored':encode(ig)}:raise ValueError('Stored target masks mismatch')
            else:continue
            kind=completion_kind(state,tuple(a.get('native_shape',[512,512]))[:2]);counts[kind]+=1
            if kind in ('positive','negative'):animals[a['animal']][kind]+=1
        except Exception as exc:errors.append(dict(scan_id=a['scan_id'],error=str(exc)))
    return dict(**counts,per_animal=animals,target=len(acquisitions),target_reached=counts['positive']+counts['negative']==len(acquisitions),errors=errors)
