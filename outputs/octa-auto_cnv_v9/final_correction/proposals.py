"""Frozen assessment footprints; only the GUI creates correction annotations."""
from common import *

def candidate_document(a):
    verify(a['model3_provenance'])
    doc=read(a['model3_provenance']['path'])
    if doc['scan_id']!=a['scan_id']: raise ValueError('Candidate identity mismatch')
    return doc

def model_arrays(a):
    doc=candidate_document(a); raw=np.zeros((512,512),bool)
    for c in doc['m3']: raw|=decode(c['runs'])
    return dict(raw_mask=raw,filtered_mask=decode(a['selected_reference']['runs'])),doc

def seed_gui_drafts(store):
    if store.path.exists(): return 0
    a=store.acquisition; verify(a['seed_file'])
    seed=read(a['seed_file']['path'])
    if seed['scan_id']!=a['scan_id'] or seed['source_identity']!=a['source_identity']:
        raise ValueError('Seed identity mismatch')
    store.state['regions']=[dict(id=f'final-{n}',state=r['state'],runs=r['runs'],
        origin=dict(kind='flagged_final_assessment_footprint',source=r['source'],
                    seed_file=a['seed_file'],human_confirmed=False),created_at=now())
        for n,r in enumerate(seed['regions'])]
    store.context['final_assessment']=a['assessment_records']
    store.context['review_notes']=a['review_notes']
    store.context['proposal_initialization']=dict(source=a['selected_reference']['source_label'],
        components=len(seed['regions']),at=now(),confirmation_required=True)
    return len(seed['regions'])
