"""Read-only selection of v9 CNVs and v2 placement reviews into a new release."""
from pathlib import Path
import importlib.util, sys, collections, shutil, hashlib, json
import numpy as np
from octa_reg_v2.run import ROOT, read, write, sha
from octa_reg_v2.review_server import current, analysis_records

OUT=ROOT/'outputs/octa-reg_v3'
V2=ROOT/'outputs/octa-reg_v2/all_samples'
MODEL=ROOT/'outputs/octa-auto_cnv_v9/model3'

def modules(folder):
    """Load exact version's validation code without instantiating writing stores."""
    old=sys.modules.get('common'); paths=sys.path[:]; loaded=[]
    for name in ('common','review_store'):
        spec=importlib.util.spec_from_file_location('_v3_read_'+name,str(folder/(name+'.py')))
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        loaded.append(mod)
        if name=='common':sys.modules['common']=mod
    if old is None:sys.modules.pop('common',None)
    else:sys.modules['common']=old
    sys.path[:]=paths
    return loaded

def freeze(output=OUT):
    if (output/'inputs/manifest.json').exists():
        doc=read(output/'inputs/manifest.json')
        for p,h in doc['source_hashes'].items():
            if sha(p)!=h:raise ValueError('Source changed since snapshot: '+p)
        return doc
    folder=output/'inputs';folder.mkdir(parents=True,exist_ok=True)
    hashes={}
    def pin(p,expected=None):
        p=Path(p); h=sha(p)
        if expected and h!=expected:raise ValueError('Hash mismatch: '+str(p))
        if str(p) in hashes and hashes[str(p)]!=h:raise ValueError('Source changed during selection')
        hashes[str(p)]=h;return h
    common,rs=modules(MODEL); cc,cr=modules(MODEL/'correction')
    gallery=read(MODEL/'gallery/data.json');pin(MODEL/'gallery/data.json')
    supervision=read(MODEL/'data/supervision.json');pin(MODEL/'data/supervision.json')
    training={r['scan_id']:r for r in supervision['records']}
    store=object.__new__(rs.ReviewStore);store.gallery=MODEL/'gallery';store.data=gallery
    store.cases={a['scan_id']:a for a in gallery['cases']}
    cnvs=[]
    for a in gallery['cases']:
        sid=a['scan_id'];mask=np.zeros((512,512),bool);ignored=mask.copy()
        dp=MODEL/'manual_review/decisions'/(sid+'.json');d=read(dp) if dp.exists() else {}
        cp=MODEL/'gallery/assets'/sid/'candidates.json';pin(cp)
        contract,token=store.contract(sid)
        if d:
            pin(dp)
            assert d['token']==token and d['prediction_contract']['models']==contract['models'],sid
        t=training.get(sid); correction=MODEL/'correction/review/regions'/(sid+'.json')
        record=read(correction) if correction.exists() else None
        meta=dict(scan_id=sid,source_identity=a['source_identity'],weight=0.,source='none',complete=False)
        if record:
            pin(correction)
            assert not record['synthetic'] and record['source_identity']==a['source_identity']
            assert record['native_shape']==[512,512] and record['axis_order']=='B-scan,A-line'
            mask,bg,ignored,drafts,_=cr.targets(record['state'],(512,512))
            assert record['masks']==dict(positive=cc.encode(mask),reviewed_background=cc.encode(bg),ignored=cc.encode(ignored))
            kind=cr.completion_kind(record['state'],(512,512));assert kind==record['kind']
            meta.update(source='manual_correction' if kind in ('positive','negative') else 'manual_partial',
                        weight=1. if kind in ('positive','negative') else .35,complete=kind in ('positive','negative'),
                        kind=kind,provenance=str(correction),revision=record['revision'])
        elif d.get('no_cnv_present'):
            meta.update(source='confirmed_absent',complete=True,weight=1.,provenance=str(dp))
        elif t:
            fp=t['target_file'];pin(fp['path'],fp['sha256'])
            with np.load(fp['path'],allow_pickle=False) as z:
                assert str(z['scan_id'])==sid and str(z['axis_order'])=='B-scan,A-line'
                mask=z['target'].astype(bool);ignored=z['ignored'].astype(bool)
            assert t['acquisition']['source_identity']==a['source_identity']
            meta.update(source='manual_training',complete=True,weight=1.,provenance=fp['path'])
        else:
            model='m3' if d.get('confirm_m3') else 'm2' if d.get('confirm_m2') else 'm3'
            confirmed=bool(d.get('confirm_'+model))
            # Correction-requested predictions do not become evidence just because present.
            rejected=bool(d.get('review_model3') and not confirmed)
            if not rejected:
                for r in read(cp)[model]:
                    if r['display_selected']:mask |= common.decode(r['runs'])
            meta.update(source='confirmed_'+model if confirmed else 'flagged_prediction_withheld' if rejected else 'automatic_m3',
                        weight=1. if confirmed else 0. if rejected else .2,complete=confirmed,provenance=str(cp))
        assert mask.shape==(512,512) and not (mask&ignored).any()
        # Pin actual prediction files/checkpoints when model masks are consumed.
        if meta['source'] in ('automatic_m3','confirmed_m2','confirmed_m3'):
            selected='m2' if meta['source']=='confirmed_m2' else 'm3'
            assert hashlib.sha256(mask.tobytes()).hexdigest()==contract['models'][selected]['mask_sha256']
            for prediction in contract['predictions']:
                if prediction['model']!=selected:continue
                for key in ('prediction','checkpoint'):
                    fp=prediction[key]
                    if fp['path'] not in hashes:pin(fp['path'],fp['sha256'])
        meta.update(pixels=int(mask.sum()),ignored_pixels=int(ignored.sum()),mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest())
        np.savez_compressed(folder/(sid+'.npz'),cnv=mask,ignored=ignored)
        cnvs.append(meta)
    reviews={}
    for group in sorted(V2.glob('TS*')):
        if not (group/'montage.json').exists():continue
        for name in ('review_registration.json','pair_evidence.json','montage.json'):
            pin(group/name)
        for p in (group/'onh_pairs').glob('*.json'):pin(p)
        if not (group/'human_review.json').exists():continue
        pin(group/'human_review.json');data=read(group/'montage.json');review=current(group,data)
        dst=folder/(group.name+'_v2_human_review.json');shutil.copyfile(group/'human_review.json',dst)
        rows=analysis_records(data,review)
        reviews[group.name]=dict(revision=review['revision'],montage_confirmed=review['montage_confirmed'],
            onh_override=review.get('onh_override'),records=rows,snapshot=str(dst),source=str(group/'human_review.json'))
    doc=dict(schema='octa-reg-v3-inputs-1',cnvs=cnvs,placement_reviews=reviews,source_hashes=hashes,
             cnv_counts=dict(collections.Counter(r['source'] for r in cnvs)),
             policy='Newest manual corrections first (kept regions only; ignored regions masked), explicit no-CNV, frozen manual supervision, confirmed Model3 then Model2, otherwise unconfirmed Model3 with low weight. Correction-requested predictions withheld. No absence inferred from unchecked reviews.')
    for p,h in hashes.items():assert sha(p)==h,p
    write(folder/'manifest.json',doc)
    print(json.dumps(dict(cnv_counts=doc['cnv_counts'],reviews={g:dict(revision=r['revision'],montage_confirmed=r['montage_confirmed']) for g,r in reviews.items()})),flush=True)
    return doc

if __name__=='__main__':freeze()
