"""Read-only CNV review audit. Writes reports only; never writes human labels."""
from pathlib import Path
import collections
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'outputs'

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

hashes = {}
def sha(p):
    p = Path(p)
    if p not in hashes:
        hashes[p] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes[p]

def module(folder, name):
    sys.modules.pop('common', None)
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location('audit_' + name, folder / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.path.pop(0)
    return m

v7 = module(OUT / 'octa-auto_cnv_v7', 'review_store')
v9 = module(OUT / 'octa-auto_cnv_v9', 'review_store')
# Bypass constructor: only use its read-only contract and interpretation methods.
web = object.__new__(v9.ReviewStore)
web.gallery = OUT / 'octa-auto_cnv_v9/gallery'
web.data = read(web.gallery / 'data.json')
web.cases = {a['scan_id']: a for a in web.data['cases']}

records, excluded, errors = [], [], []
for release in sorted(OUT.glob('octa-auto*')):
    version = 6 if release.name.endswith('unet_v6') else int(release.name.rsplit('_v', 1)[1])
    for p in sorted(release.rglob('*.json')):
        if p.parent.name not in ('regions', 'decisions'):
            continue
        if any(x in p.parts for x in ('verification', 'history', 'demo_this_computer', 'legacy_all_samples', 'old_review')):
            excluded.append(dict(path=str(p), reason='history, migrated copy, demo or verification namespace'))
            continue
        d = read(p)
        if d.get('synthetic'):
            excluded.append(dict(path=str(p), reason='synthetic record'))
            continue
        sid = d['scan_id']
        r = dict(scan_id=sid, animal=sid.split('_')[0], eye=sid.split('_')[1],
                 version=version, path=str(p), sha256=sha(p), revision=d.get('revision'),
                 saved_at=d.get('updated_at', d.get('saved_at')), confirmed=False,
                 kind='partial', regions=0, positive_pixels=0, ignored_pixels=0,
                 source_identity=d.get('source_identity'), source_volume=d.get('source_volume'),
                 region_ids=[], validation='passed')
        try:
            if version in (7, 8):
                shape = tuple(d['native_shape'])
                pos, bg, ign, drafts, overlap = v7.targets(d['state'], shape)
                kind = v7.completion_kind(d['state'], shape)
                assert kind == d['kind'], 'Stored completion kind disagrees'
                assert d['masks'] == dict(positive=v7.encode(pos), reviewed_background=v7.encode(bg), ignored=v7.encode(ign)), 'Stored masks disagree'
                kept = [a for a in d['state']['regions'] if a['state']=='kept' and (v7.decode(a['runs'], shape) & ~ign).any()]
                r.update(kind=kind, confirmed=kind in ('positive','negative'), regions=len(kept),
                         positive_pixels=int(pos.sum()), ignored_pixels=int(ign.sum()),
                         region_ids=[a['id'] for a in kept], confirmation=d['state'].get('confirmation'),
                         defer_reason=d['state'].get('defer_reason'),
                         source_volume=d['acquisition'].get('source_volume'))
            elif version == 9:
                contract, token = web.contract(sid)
                assert token == d['token'], 'Prediction contract changed'
                assert contract['models'] == d['prediction_contract']['models'], 'Mask contract mismatch'
                for model in contract['predictions']:
                    for key in ('prediction','checkpoint'):
                        fp = model[key]
                        assert Path(fp['path']).stat().st_size == fp['bytes'] and sha(fp['path']) == fp['sha256'], 'Prediction/checkpoint hash mismatch'
                interpreted = v9.interpret_approval(d)
                chosen = interpreted['preferred_shared_target_model']
                r.update(source_identity=contract['source_identity'], preferred_model=chosen,
                         confirm_m1=d['confirm_m1'], confirm_m2_adjusted=d['confirm_m2_adjusted'],
                         review_model2=d['review_model2'], notes=d.get('notes',''),
                         both_models_accepted=interpreted['both_models_accepted'],
                         accepted_outline_variation=interpreted['accepted_outline_variation'],
                         prediction_contract=contract)
                if chosen:
                    m = contract['models'][chosen]
                    r.update(confirmed=True, kind='positive' if m['area_pixels'] else 'negative',
                             regions=len(m['candidate_ids']), region_ids=m['candidate_ids'], positive_pixels=m['area_pixels'])
                else:
                    r['kind'] = 'correction_requested' if d['review_model2'] else 'unconfirmed'
            else:
                regs = [a for a in d['regions'] if a.get('decision')=='approved' and a.get('category')=='Full Lesion' and a.get('reviewed_runs')]
                shape = tuple(d['native_shape'])
                pos = np.zeros(shape, bool)
                ign = pos.copy()
                for a in regs:
                    pos |= v7.decode(a['reviewed_runs'], shape)
                for a in d['regions']:
                    if a.get('decision')=='approved' and a.get('category')=='Other':
                        ign |= v7.decode(a.get('reviewed_runs',[]), shape)
                pos &= ~ign
                sr = d.get('scan_review',{})
                complete = version==5 and sr.get('status')=='complete' and sr.get('whole_field_checked')
                kind = ('positive' if pos.any() else 'negative' if sr.get('reviewed_absence') and not ign.any() else 'uncertain_only') if complete else 'partial'
                r.update(confirmed=bool(complete), kind=kind, regions=len(regs), region_ids=[a['id'] for a in regs],
                         positive_pixels=int(pos.sum()), ignored_pixels=int(ign.sum()), scan_review=sr,
                         model_ratings=d.get('model_ratings',{}))
        except Exception as exc:
            r.update(confirmed=False, kind='invalid', validation=str(exc))
            errors.append(dict(path=str(p), error=str(exc)))
        records.append(r)

# Canonical native identity is the source fingerprint identity used by v7-v9.
# Map older scan IDs onto those identities; flag any collisions rather than guessing.
identities = collections.defaultdict(set)
for r in records:
    if r['source_identity']:
        identities[r['scan_id']].add(r['source_identity'])
assert all(len(ids)==1 for ids in identities.values()), 'Conflicting source identities for scan ID'
paths_by_sid = collections.defaultdict(set)
for r in records:
    if r['source_volume']:
        paths_by_sid[r['scan_id']].add(str(Path(r['source_volume'])).lower())
assert all(len(paths)==1 for paths in paths_by_sid.values()), 'Conflicting native paths'
groups = collections.defaultdict(list)
for r in records:
    r['acquisition_key'] = next(iter(identities[r['scan_id']]), None) if identities[r['scan_id']] else str(r['source_volume']).lower()
    assert r['acquisition_key'] not in ('', 'none', None)
    groups[r['acquisition_key']].append(r)

selected, overlaps = [], []
for key, rr in sorted(groups.items(), key=lambda pair: pair[1][0]['scan_id']):
    # v6 is a model-error review, not whole-field footprint approval.
    eligible = [r for r in rr if r['version'] != 6]
    pick = max(eligible or rr, key=lambda r:(r['version'],r['saved_at'] or ''))
    row = dict(pick)
    row['all_source_paths'] = [r['path'] for r in rr]
    row['prior_confirmed_versions'] = [r['version'] for r in rr if r['confirmed'] and r is not pick]
    row['v6_error_review_requires_reconciliation'] = any(r['version']==6 for r in rr)
    selected.append(row)
    if len(rr)>1:
        overlaps.append(dict(scan_id=pick['scan_id'], selected_version=pick['version'],selected_kind=pick['kind'],
                             sources=[dict(version=r['version'],kind=r['kind'],regions=r['regions'],path=r['path']) for r in rr]))

def counts(rows):
    done=[r for r in rows if r['confirmed']]
    return dict(saved=len(rows), confirmed=len(done), positive=sum(r['kind']=='positive' for r in done),
                negative=sum(r['kind']=='negative' for r in done), uncertain_only=sum(r['kind']=='uncertain_only' for r in done),
                regions=sum(r['regions'] for r in done), pending=len(rows)-len(done))

per_version={f'v{v}':counts([r for r in records if r['version']==v]) for v in range(1,10)}
per_animal={a:counts([r for r in selected if r['animal']==a]) for a in sorted({r['animal'] for r in selected})}
summary=dict(created_at=datetime.now(timezone.utc).isoformat(), scope='octa-auto CNV versions 1-9 current real review heads',
             current_unique=counts(selected), per_version=per_version, per_animal=per_animal,
             unique_ever_confirmed_in_current_version_heads=len({r['acquisition_key'] for r in records if r['confirmed']}),
             v9_m1_confirmations=sum(r.get('confirm_m1',False) for r in records),
             v9_m2_confirmations=sum(r.get('confirm_m2_adjusted',False) for r in records),
             v9_both_confirmed=sum(r.get('both_models_accepted',False) for r in records),
             v9_correction_flags=sum(r.get('review_model2',False) for r in records),
             errors=errors)

# Older source labels are inventoried separately, never promoted to whole-field completion.
supplement=[]
for p in sorted((OUT/'cnv_labels').glob('*_cnv.npz')):
    with np.load(p,allow_pickle=False) as a:
        scalar=lambda key,default='':a[key].reshape(-1)[0].item() if key in a else default
        sid=scalar('scan_id')
        supplement.append(dict(scan_id=sid,path=str(p),sha256=sha(p),reviewed=bool(scalar('reviewed',False)),
                               positive_pixels=int(a['cnv_mask'].sum()),overlaps_versioned_scan=any(r['scan_id']==sid for r in records),
                               scope='legacy footprint; no whole-field confirmation inferred'))

# Detect annotations changed during this audit; never silently mix revisions.
for r in records:
    assert hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'], 'Review changed during audit; rerun'

payload=dict(summary=summary, policy='One acquisition per native source identity; newest version current head wins, including pending/deferred heads; v6 model-error records retained separately. V9 prefers explicitly confirmed adjusted Model 2, otherwise explicitly confirmed Model 1. Never union sources. Historical annotation files remain untouched.',
             selected_acquisitions=selected,all_current_records=records,overlapping_acquisitions=overlaps,
             excluded_namespaces=excluded,legacy_original_labels=supplement)
(HERE/'inventory.json').write_text(json.dumps(payload,indent=2),encoding='utf8')

lines=['# Consolidated manual CNV confirmation inventory','',f"Snapshot: {summary['created_at']}",'',
       f"**{summary['current_unique']['confirmed']} unique acquisitions have a current whole-field confirmation**, including **{summary['current_unique']['positive']} CNV-positive scans**, **{summary['current_unique']['negative']} confirmed no-CNV scans**, and **{summary['current_unique']['uncertain_only']} completed fields containing only uncertain regions**.",'',
       f"The confirmed positive scans contain **{summary['current_unique']['regions']} kept lesion observations**. These are annotation regions across acquisitions/visits, not unique biological lesions. **{summary['current_unique']['pending']} additional acquisitions have partial, deferred or correction-requested records.**",'',
       '## By version, before deduplication','',
       '| Version | Saved scans | Whole-field completed | CNV-positive | No CNV | Uncertain only | Kept regions in completed scans | Pending |',
       '|---|---:|---:|---:|---:|---:|---:|---:|']
for v,c in per_version.items():
    lines.append(f"| {v} | {c['saved']} | {c['confirmed']} | {c['positive']} | {c['negative']} | {c['uncertain_only']} | {c['regions']} | {c['pending']} |")
lines += ['', '## Interpretation and checks','',
          '- Current real review records were read directly. Historical revisions, copied v6 records, demonstration data, synthetic tests and automatic proposals do not add samples.',
          '- The consolidated view uses the newest version for each exact acquisition. A newer deferred/incomplete review blocks automatic fallback to an older confirmation. All older source paths and statuses remain in inventory.json.',
          '- V7/v8 confirmation signatures and stored positive/background/ignored masks were recomputed. V9 decision tokens, candidate masks, prediction files and checkpoint hashes were verified against the current gallery.',
          '- V5 uses its explicit whole-field completion flags; it has no v7-style signature. Two completed fields contain only uncertain regions and must not be used as clean negatives.',
          '- V6 reviews concern model errors and do not certify whole-field background. Their two scans are flagged for reconciliation in the inventory even where a v5 completion exists.',
          f"- V9: {summary['v9_m1_confirmations']} Model 1 approvals, {summary['v9_m2_confirmations']} Model 2 approvals, {summary['v9_both_confirmed']} approved both. Count each acquisition once; choose approved Model 2 where available, otherwise approved Model 1. {summary['v9_correction_flags']} scans request Model 2 correction.",
          f"- {summary['unique_ever_confirmed_in_current_version_heads']} unique acquisitions have a confirmation in at least one version's current head; the current consolidated total above honors newer deferrals.",
          '- Original labels remain in place. This folder is a read-only-source index/report, not a newly authored ground-truth dataset or training export.',
          f"- Validation errors: {len(errors)}.",'', '## Current counts by animal','',
          '| Animal | Completed | Positive | No CNV | Uncertain only | Lesion observations | Pending |', '|---|---:|---:|---:|---:|---:|---:|']
for a,c in per_animal.items():
    lines.append(f"| {a} | {c['confirmed']} | {c['positive']} | {c['negative']} | {c['uncertain_only']} | {c['regions']} | {c['pending']} |")
for complete,title in [(True,'Confirmed acquisitions'),(False,'Pending acquisitions')]:
    lines += ['',f'## {title}','','| Acquisition | Selected version | Status | Kept regions | Source |','|---|---|---|---:|---|']
    for r in selected:
        if r['confirmed'] != complete:continue
        lines.append(f"| {r['scan_id']} | v{r['version']} | {r['kind']} | {r['regions']} | [record](<{r['path']}>) |")
lines += ['', '## Additional original manual labels','',
          f"Found {len(supplement)} original CNV NPZ files in outputs/cnv_labels: {sum(r['reviewed'] and r['positive_pixels']>0 for r in supplement)} marked reviewed with nonempty CNV masks. They are preserved in the supplementary manifest; their older review flag is not counted as the newer whole-field confirmation contract.",
          '', 'Re-run audit.py in the activated octa environment to refresh this report. inventory.json contains exact source paths, hashes, all current records, selected acquisitions, overlap provenance and the original-label supplement.']
(HERE/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(json.dumps(summary,indent=2))
