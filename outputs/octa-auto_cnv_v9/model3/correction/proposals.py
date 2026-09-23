"""Frozen gallery candidates and notes; annotation records are written by the GUI only."""
from common import *

def candidate_document(a):
    verify(a['model3_provenance'])
    doc=read(a['model3_provenance']['path'])
    if doc['scan_id'] != a['scan_id']: raise ValueError('Candidate identity mismatch')
    return doc

def model_arrays(a):
    doc=candidate_document(a)
    raw=np.zeros((512,512),bool);selected=raw.copy()
    for c in doc['m3']:
        mask=decode(c['runs']);raw |= mask
        if c['display_selected']: selected |= mask
    return dict(filtered_mask=selected,raw_mask=raw),doc

def seed_gui_drafts(store):
    if store.path.exists(): return 0
    a=store.acquisition;doc=candidate_document(a)
    regions=[dict(id=f"m3-{c['id']}",state='draft',runs=c['runs'],
        origin=dict(kind='automatic_model3_proposal',candidate_id=c['id'],
                    candidate_file=a['model3_provenance'],prediction_contract=a['gallery_review']['prediction_contract'],
                    human_confirmed=False),created_at=now())
        for c in doc['m3'] if c['display_selected']]
    store.state['regions']=regions
    store.context['gallery_review']=a['gallery_review']
    store.context['review_notes']=a['review_notes']
    store.context['proposal_initialization']=dict(model='CNV v9 Model 3 adjusted',components=len(regions),at=now())
    return len(regions)

def prepare():
    data=read(MODEL3/'gallery/data.json');acquisitions=[];excluded=[];flagged=0
    for case in data['cases']:
        path=MODEL3/'manual_review/decisions'/(case['scan_id']+'.json')
        if not path.exists(): continue
        record=read(path)
        if not record['review_model3']: continue
        flagged+=1
        if record['confirm_m2']:
            excluded.append(dict(scan_id=case['scan_id'],reason='Confirm Model 2 CNVs checked',review=record))
            continue
        contract=record['prediction_contract']
        assert contract['source_identity']==case['source_identity']
        candidates=MODEL3/'gallery/assets'/case['scan_id']/'candidates.json'
        assert sha(candidates)==contract['candidate_file']['sha256']
        a=dict(case,review_notes=record['notes'],gallery_review=record,
               gallery_review_source=fingerprint(path),model3_provenance=fingerprint(candidates),
               preview_role='Flagged for Model 3 correction',model3_training_exposure=case['training_scan'])
        arrays,doc=model_arrays(a)
        expected=contract['models']['m3']
        assert hashlib.sha256(arrays['filtered_mask'].tobytes()).hexdigest()==expected['mask_sha256']
        assert [c['id'] for c in doc['m3'] if c['display_selected']]==expected['candidate_ids']
        verify(a['input_manifest'])
        acquisitions.append(a)
    assert flagged==67 and len(excluded)==10 and len(acquisitions)==57
    queue=dict(schema=SCHEMA,acquisitions=acquisitions,excluded=excluded,
               selection='review_model3 == true AND confirm_m2 == false',flagged=flagged,
               gallery=fingerprint(MODEL3/'gallery/data.json'))
    path=HERE/'queue/queue.json'
    if path.exists():
        if read(path)!=queue: raise ValueError('Frozen queue differs; preserve existing correction work')
    else: atomic(path,queue)
    atomic(HERE/'reports/setup.json',dict(flagged=flagged,excluded=len(excluded),selected=len(acquisitions),
        notes_preserved=sum(bool(a['review_notes']) for a in acquisitions),
        proposals=sum(len(a['gallery_review']['prediction_contract']['models']['m3']['candidate_ids']) for a in acquisitions),
        annotation_files_created=0))
    print(json.dumps(read(HERE/'reports/setup.json')))

if __name__=='__main__': prepare()
