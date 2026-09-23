"""Freeze last-round queue and accepted cohort. Never write human label files."""
from common import *
from collections import defaultdict, Counter
import urllib.request

ASSESS=HERE.parent/'final_assessment'
STATEMENT='OK i flagged the last set of CNV samples that need review---everything else looks good including the no CNV samples. So lets set those up into the final gui reviewer and then we will have a complete cnv labeled dataset--correct?'

def run():
    if (HERE/'queue/queue.json').exists():
        raise ValueError('Queue already frozen; do not replace ongoing corrections.')
    data=read(ASSESS/'gallery/data.json')
    assessments=json.load(urllib.request.urlopen('http://127.0.0.1:8805/assessments'))
    source_hashes={str(ASSESS/'gallery/data.json'):sha(ASSESS/'gallery/data.json')}
    def checked(fp):
        if 'bytes' in fp: verify(fp)
        else: assert sha(fp['path'])==fp['sha256'],fp['path']
        source_hashes[fp['path']]=sha(fp['path'])
    gallery=read(MODEL3/'gallery/data.json'); inputs={r['scan_id']:r for r in gallery['cases']}
    training={r['scan_id']:r for r in read(MODEL3/'data/supervision.json')['records']}
    groups=defaultdict(list)
    for r in data['cases']+data['secondary_cases']:
        assert r['token']==assessments[r['entry_id']]['token']
        groups[r['scan_id']].append(r)
    assert len(groups)==324
    def masks(r):
        sid=r['scan_id']; ig=np.zeros((512,512),bool)
        if r['source']=='manual' or r['selection_reason']=='training_no_cnv':
            fp=training[sid]['target_file'];checked(fp)
            with np.load(fp['path'],allow_pickle=False) as z:
                target=z['target'].astype(bool);known=z['known'].astype(bool)
                ig=z['ignored'].astype(bool);instances=z['instances'].astype(bool)
                assert str(z['scan_id'])==sid and str(z['axis_order'])=='B-scan,A-line'
        elif r['source']=='m3_corrected':
            checked(r['original_label']); doc=read(r['original_label']['path'])
            assert not doc['synthetic'] and doc['source_identity']==r['source_identity']
            from review_store import targets, completion_kind
            assert completion_kind(doc['state'],(512,512))=='positive'
            target,bg,ig,draft,overlap=targets(doc['state'],(512,512),True)
            known=target|bg
            instances=np.array([decode(c['runs'])&~ig for c in doc['state']['regions'] if c['state']=='kept'],dtype=bool)
        elif r['source'] in ('m2','m3'):
            checked(r['reference_provenance']);doc=read(r['reference_provenance']['path'])
            instances=np.array([decode(c['runs']) for c in doc[r['source']] if c['display_selected']],dtype=bool)
            target=instances.any(0);known=~ig
        elif r['source']=='no_cnv':
            target=ig.copy();known=~ig;instances=np.zeros((0,512,512),bool)
        else: raise ValueError('No target for unassessable sample')
        assert target.shape==known.shape==ig.shape==(512,512)
        assert np.array_equal(target,decode(r['runs']))
        assert not (target&ig).any() and np.array_equal(known,~ig)
        assert np.array_equal(instances.any(0),target)
        return target,known,ig,instances
    acquisitions=[];cohort=[]
    for sid,refs in groups.items():
        a=inputs[sid]; assert all(r['source_identity']==a['source_identity'] for r in refs)
        flags=[r for r in refs if assessments[r['entry_id']]['status']=='review']
        # The most recently corrected footprint is the editable starting point;
        # all other reviewed versions remain available as immutable references.
        chosen=next((r for r in refs if r['source']=='m3_corrected'),refs[0])
        record=dict(scan_id=sid,animal=a['animal'],eye=a['eye'],session_date=a['session_date'],
            source_identity=a['source_identity'],selected_reference=chosen,
            assessment_records={r['entry_id']:assessments[r['entry_id']] for r in refs})
        if chosen['source']=='deferred':
            record.update(status='excluded_poor_image',reason=chosen['original_decision']['notes'])
        elif flags:
            target,known,ig,instances=masks(chosen)
            regions=[dict(state='draft',runs=encode(m),source=chosen['source_label']) for m in instances if m.any()]
            # Preserve unknown areas from BOTH flagged versions of a duplicate.
            for r in refs: ig |= masks(r)[2]
            if ig.any(): regions.append(dict(state='unsure',runs=encode(ig),source='Unknown pixels preserved from reviewed reference(s)'))
            seedpath=HERE/'queue/seeds'/(sid+'.json')
            atomic(seedpath,dict(scan_id=sid,source_identity=a['source_identity'],regions=regions))
            cp=MODEL3/'gallery/assets'/sid/'candidates.json'; checked(fingerprint(cp));checked(a['input_manifest'])
            notes='Flagged in final assessment: '+', '.join(r['source_label'] for r in flags)+'.'
            if len(refs)>1:
                notes+=' Both versions were flagged. Edit the corrected footprint; Reference: assessment versions shows both. Prior unknown pixels remain Unsure until resolved.'
            for r in refs:
                if assessments[r['entry_id']]['notes']:notes+='\n'+r['source_label']+': '+assessments[r['entry_id']]['notes']
            acquisitions.append(dict(a,selected_reference=chosen,assessment_references=refs,
                assessment_records=record['assessment_records'],review_notes=notes,seed_file=fingerprint(seedpath),
                model3_provenance=fingerprint(cp),preview_role='Final assessment correction',
                model3_training_exposure=a['training_scan']))
            record.update(status='correction_pending',flagged_entries=[r['entry_id'] for r in flags])
        else:
            target,known,ig,instances=masks(chosen)
            path=destination(HERE/'queue/accepted_targets'/(sid+'.npz'))
            with path.open('wb') as f:np.savez_compressed(f,target=target,known=known,ignored=ig,instances=instances,
                scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'))
            record.update(status='confirmed_positive' if target.any() else 'confirmed_negative',targets=fingerprint(path),
                acceptance='Explicit user message accepting all unflagged CNV and confirmed no-CNV samples')
        cohort.append(record)
    assert len(acquisitions)==14 and sum(len(r.get('flagged_entries',[])) for r in cohort)==15
    assert Counter(r['status'] for r in cohort)==dict(confirmed_positive=203,confirmed_negative=105,correction_pending=14,excluded_poor_image=2)
    acceptance=dict(at=now(),user_statement=STATEMENT,assessment_collection_token=data['collection_token'],
        assessments=assessments,policy='Explicit user acceptance of unflagged positives and confirmed negatives. Poor-image deferrals retain exclusion status. No new manual label records created.')
    atomic(HERE/'queue/acceptance.json',acceptance)
    atomic(HERE/'queue/cohort.json',dict(schema='cnv-final-cohort-v1',records=cohort,acceptance=fingerprint(HERE/'queue/acceptance.json')))
    atomic(HERE/'queue/queue.json',dict(schema=SCHEMA,acquisitions=acquisitions,selection='Unique acquisitions with Needs review in final assessment',source_hashes=source_hashes))
    assert source_hashes=={p:sha(p) for p in source_hashes}
    atomic(HERE/'reports/setup.json',dict(at=now(),counts=dict(Counter(r['status'] for r in cohort)),flagged_entries=15,
        queue_acquisitions=len(acquisitions),original_annotations_written=0,source_files_verified=len(source_hashes)))
    print(json.dumps(read(HERE/'reports/setup.json'),indent=2))

if __name__=='__main__':run()
