"""Freeze live annotation heads and a shared, acquisition-excluded preview."""
from common import *
from collections import Counter,defaultdict
import random, shutil
from scipy import ndimage as ndi
from legacy import export_target

def v7_targets(d,a):
    assert not d['synthetic'] and d['schema']=='cnv-whole-field-v7.1'
    assert d['scan_id']==a['scan_id'] and d['source_identity']==a['source_identity']
    assert d['native_shape']==[512,512] and d['axis_order']=='B-scan,A-line'
    s=d['state'];c=s.get('confirmation');signature=digest({k:s[k] for k in ('regions','absence')})
    valid=bool(c and c.get('whole_field_checked') and c.get('annotation_sha256')==signature)
    p=np.zeros((512,512),bool);ig=p.copy();instances=[];draft=False
    for r in s['regions']:
        m=decode(r['runs']);state=r['state']
        assert state in ('kept','unsure','excluded','removed','draft')
        if state=='removed':continue
        draft |= state=='draft' or not m.any()
        if state=='kept':p|=m;instances.append(m)
        elif state in ('unsure','excluded'):ig|=m
    p &= ~ig
    if valid:
        assert not draft and not s.get('defer_reason')
        assert (s['absence'] and not p.any() and not ig.any()) or (not s['absence'] and p.any())
        assert c['completion_revision']<=d['revision']
    kind=('positive' if p.any() else 'negative') if valid else ('deferred' if s.get('defer_reason') else 'draft')
    known=(~ig) if valid else np.zeros_like(p)
    for key,m in [('positive',p),('reviewed_background',known&~p),('ignored',ig)]:
        assert np.array_equal(decode(d['masks'][key]),m)
    assert d['kind']==kind
    return dict(target=p,known=known,ignored=ig,instances=np.stack(instances)&~ig if instances else np.zeros((0,512,512),bool)),dict(kind=kind,complete=valid,revision=d['revision'],confirmation=c,unsure_regions=sum(r['state']=='unsure' for r in s['regions']))

def freeze():
    mp=HERE/'data/manifest.json'
    if mp.exists():return read(mp)
    inv=read(V7/'queue/inventory.json')['scans']; byid={a['scan_id']:a for a in inv}
    heads={}; history=defaultdict(list); all_fps=[]
    for p in sorted((V7/'review/regions').glob('*.json')):
        d=read(p);sid=d['scan_id'];assert sid in byid
        heads[sid]=(p,d);all_fps.append(fingerprint(p))
    for version,folder,pattern in [('v5',ROOT/'outputs/octa-auto_cnv_v5/review/regions','*_regions.json'),('v4',ROOT/'outputs/octa-auto_cnv_v4/review/regions','*_regions.json'),('v3',ROOT/'outputs/octa-auto_cnv_v3/review/regions','*_regions.json'),('original',ROOT/'outputs/cnv_labels','*_cnv.npz'),('classification',ROOT/'outputs/cnv_review_v1/regions','*_regions.json')]:
        for p in sorted(folder.glob(pattern)):
            d=npz(p) if p.suffix=='.npz' else read(p)
            sid=str(np.asarray(d['scan_id']).reshape(-1)[0]);fp=fingerprint(p)
            all_fps.append(fp);history[sid].append((version,p,d,fp))
    # Freeze exact source documents separately from derived training tensors.
    for fp in all_fps:
        p=Path(fp['path']);out=dest(HERE/'data/sources'/(fp['sha256']+p.suffix))
        shutil.copyfile(p,out);assert sha(out)==fp['sha256']
    records=[];blocked=[];counts=Counter();identity=set();audits=[]
    for sid in sorted(set(heads)|set(history)):
        if sid not in byid:raise ValueError('Unresolved historical acquisition '+sid)
        a=byid[sid]; selected=None; rejected=[]
        if sid in heads:
            p,d=heads[sid];z,au=v7_targets(d,a);counts[au['kind']]+=1
            if au['kind'] in ('draft','deferred'):
                blocked.append(dict(scan_id=sid,source_identity=a['source_identity'],reason=au['kind'],source=fingerprint(p)));continue
            selected=('v7',p,z,au)
        else:
            for v,p,d,fp in history[sid]:
                if v=='classification':continue
                source=str(np.asarray(d['source_volume']).reshape(-1)[0]);shape=list(np.asarray(d.get('native_shape',[512,512])).astype(int))
                if Path(source).resolve()!=Path(a['source']).resolve() or shape!=[512,512]:
                    rejected.append(dict(source=fp,reason='source/grid mismatch'));continue
                if v=='original':
                    reviewed=bool(np.asarray(d.get('reviewed',[False])).reshape(-1)[0]);pos=d['cnv_mask'].astype(bool)
                    if not reviewed or not pos.any():continue
                    ig=np.zeros_like(pos)
                    for cv,cp,cd,cf in history[sid]:
                        if cv!='classification':continue
                        assert Path(cd['source_volume']).resolve()==Path(a['source']).resolve()
                        for r in cd.get('regions',[]):
                            if r.get('classification_complete') and r.get('category') in ('Normal','Other'):ig|=decode(r['runs'])
                    pos &= ~ig
                    z=dict(target=pos,known=pos.copy(),ignored=ig,instances=np.array([pos]))
                    au=dict(complete=False,revision=int(np.asarray(d.get('revision',[0])).reshape(-1)[0]),issues=['Legacy reviewed positives only; unmarked pixels unknown'])
                else:
                    z,au=export_target(d,a);z['ignored']=~z['known'] & ~z['target']
                    au['revision']=d.get('revision')
                    if v!='v5':z['known']=z['target'].copy();au['complete']=False
                if z['known'].any():selected=(v,p,z,au);break
        if selected is None:
            audits.append(dict(scan_id=sid,status='no eligible confirmed pixels',rejected=rejected));continue
        v,p,z,au=selected;key=a['source_identity']
        if key in identity:raise ValueError('Duplicate native acquisition requires reconciliation: '+sid)
        identity.add(key)
        assert not (z['target']&~z['known']).any()
        out=HERE/'data/targets'/(sid+'.npz');save(out,**z)
        rec=dict(acquisition=a,scan_id=sid,animal=a['animal'],eye=a['eye'],visit=a['session_date'],source_identity=key,version=v,source=fingerprint(p),audit=au,target_file=fingerprint(out),positive_pixels=int(z['target'].sum()),reviewed_background_pixels=int((z['known']&~z['target']).sum()),unknown_pixels=int((~z['known']).sum()),superseded_sources=[f for _,q,_,f in history[sid] if q!=p],rejected_sources=rejected)
        records.append(rec)
    assert counts==dict(positive=30,negative=7,deferred=4),counts
    assert sum(r['audit'].get('unsure_regions',0) for r in records)==2
    animals=sorted({r['animal'] for r in records if r['version']=='v7' and r['positive_pixels']})
    assert len(animals)==10
    rng=random.Random(20260918);preview=[];historical_ids=set(heads)|set(history)
    historical_keys={byid[s]['source_identity'] for s in historical_ids if s in byid}
    for animal in animals:
        refs=sorted([r for r in records if r['animal']==animal and r['version']=='v7' and r['positive_pixels']],key=lambda r:r['scan_id'])
        ref=rng.choice(refs);a=ref['acquisition'];chosen=[dict(acquisition=a,scan_id=a['scan_id'],role='training/reference',training_exposure=True,animal_training_exposure=True)]
        pool=[a for a in inv if a['animal']==animal and a.get('source_identity') and a['source_identity'] not in historical_keys and a['scan_id'] not in historical_ids and a.get('inference_status')=='completed']
        pool=sorted(pool,key=lambda a:a['scan_id']);rng.shuffle(pool)
        for _ in range(2):
            used_visits={c['acquisition']['session_date'] for c in chosen}
            distinct=[a for a in pool if a['session_date'] not in used_visits]
            if not pool:raise ValueError('Insufficient unlabeled comparison acquisitions: '+animal)
            a=(distinct or pool)[0];pool=[p for p in pool if p['source_identity']!=a['source_identity']]
            chosen.append(dict(acquisition=a,scan_id=a['scan_id'],role='excluded from fitting; unlabeled',training_exposure=False,animal_training_exposure=True))
        for c in chosen:
            c['same_visit_as']=[x['scan_id'] for x in chosen if x!=c and x['acquisition']['session_date']==c['acquisition']['session_date']]
            c['same_visit_training_sources']=[r['scan_id'] for r in records if r['animal']==animal and r['visit']==c['acquisition']['session_date'] and r['scan_id']!=c['scan_id']]
        preview.extend(chosen)
    assert len({p['acquisition']['source_identity'] for p in preview})==30
    assert all(p['scan_id'] not in historical_ids for p in preview if not p['training_exposure'])
    m=dict(seed=267,comparison_seed=20260918,records=records,blocked=blocked,v7_counts=dict(counts),annotation_sources=all_fps,unused_sources=audits,animals=animals,policy='Single acquisition and selected label source; v7 drafts/deferred block fallback; v7 > valid v5 > v4 > v3 > reviewed original. No predictions or ratings as labels.')
    write(HERE/'data/preview.json',dict(cases=preview,seed=20260918,interpretation='10 training-case comparisons; 20 unlabeled acquisitions excluded from all fitting and normalization. All ten animals have training exposure. No unseen-animal tests.'))
    write(mp,m);progress('Dataset and 30-case preview frozen',training_acquisitions=len(records),v7_counts=dict(counts));return m
if __name__=='__main__':freeze()
