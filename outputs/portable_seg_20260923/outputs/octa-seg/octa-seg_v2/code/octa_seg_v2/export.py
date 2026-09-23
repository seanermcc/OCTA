"""Complete native volumes, matched v1 baseline and explicit v2 provenance."""
from .common import *
from .policy import apply,POLICY_REVISION
from octa_seg_v1.decisions import decide,alignment,estimate_context,thickness
from octa_seg_v1.export import live_decisions
from eight_surface.config import SURFACE_NAMES,LAYER_DEFS,CASCADE_VERSION

def run(round_dir=ROUND):
    ROUND=Path(round_dir)
    learned=(ROUND/'model_manifest.json').exists()
    model_manifest=read(ROUND/'model_manifest.json') if learned else initialize()
    manifest=initialize();cal=read(V1/'calibration/deployment_vessels.json')['thresholds'];old=read(V1/'data/manifest.json')
    for sid in SCANS:
        out=ROUND/'volumes'/sid
        if not (out/'prepared.json').exists():continue
        if (out/'exported.json').exists() and read(out/'exported.json').get('policy_revision')==POLICY_REVISION:continue
        prep=read(out/'prepared.json');preds=Path(prep['reused_neural'] or out/'neural')
        if len(list(preds.glob('b*.npz')))!=512:continue
        print('Exporting',sid,flush=True)
        g=npz(out/'geometry.npz');images=np.load(prep['images'],mmap_mode='r')
        ps=[npz(preds/f'b{b:04d}.npz') for b in range(512)]
        rows=np.stack([p['rows'] for p in ps]);prob=np.stack([p['probabilities'] for p in ps]);entropy=np.stack([p['entropy'] for p in ps]);del ps
        guards,provenance=live_decisions(old,sid,g)
        if learned:
            frozen=OUT/'round_000/volumes'/sid;fg=npz(frozen/'guards.npz')
            guards={b:{key:value[b] for key,value in fg.items()} for b in range(512)}
            provenance=read(frozen/'human_guard_provenance.json')
            baseline=npz(frozen/'v1_matched_baseline.npz');brep=baseline['reported_positions']
            save(out/'v1_matched_baseline.npz',**baseline)
        else:
            baseline=[decide(rows[b],prob[b],cal,g['vessel'][b],**guards.get(b,{})) for b in range(512)]
            brep,bstate,breason=[np.stack([r[k] for r in baseline]) for k in range(3)]
            save(out/'v1_matched_baseline.npz',reported_positions=brep,state=bstate,reason=breason,probabilities=prob,
                 raw_position_branch=rows,primary_thickness_um=thickness(brep,g['shadow']))
        a=None
        for src in (out,PILOT/'volumes'/sid,V1/'volumes'/sid):
            if (src/'alignment.npz').exists():a=npz(src/'alignment.npz');break
        if a is None:
            shifts,scores=alignment(images);a=dict(shifts=shifts,scores=scores)
        if not (out/'alignment.npz').exists():save(out/'alignment.npz',**a)
        offset=int(g['label_offset']);depth=images.shape[1]
        preliminary=[apply(rows[b],prob[b],cal,g['vessel'][b],offset,depth,guards.get(b)) for b in range(512)]
        rep,state,reason=[np.stack([r[k] for r in preliminary]) for k in ('reported_positions','state','reason')]
        context,context_reason,records=estimate_context(rows,rep,state,reason,images,a['shifts'],a['scores'],offset=offset)
        output=[apply(rows[b],prob[b],cal,g['vessel'][b],offset,depth,guards.get(b),context=context[b]) for b in range(512)]
        d={key:np.stack([r[key] for r in output]) for key in output[0]};d.pop('working_positions')
        d.update(raw_position_branch=rows,probabilities=prob,entropy=entropy,context_reason=context_reason,
            primary_thickness_um=thickness(d['reported_positions'],g['shadow']),
            surface_names=np.array(SURFACE_NAMES),thickness_names=np.array([x[0] for x in LAYER_DEFS]+['INNER_RETINA']),
            label_offset=g['label_offset'],shadow=g['shadow'],vessel=g['vessel'],cnv=g['cnv'],
            policy_reason=d['reason'],model_version=np.array('octa-seg_v2'),round_id=np.array(str(ROUND.relative_to(OUT))),
            regional_feedback_revision=np.array(0),validated=np.array(False),
            candidate_source_names=np.array(['none','registered_context','neural_proposal','human_position']),
            ilm_working_policy=np.array('ilm_working_default'),policy_revision=np.array(POLICY_REVISION),checkpoint_sha256=np.array([fp['sha256'] for fp in model_manifest['checkpoints']]))
        assert rows.shape==(512,8,512)
        assert not np.isfinite(d['uncertain_estimates'][d['state']==2]).any()
        assert not np.isfinite(d['primary_thickness_um'].transpose(0,2,1)[g['shadow']]).any()
        save(out/'measurements.npz',**d)
        provider=dict(d,surfaces=d['reported_positions']-offset,uncertain_estimates=d['uncertain_estimates']-offset,
            confidence=np.full_like(rows,np.nan),scan_id=np.array([sid]),cascade_version=np.array([CASCADE_VERSION]),
            source=np.array([prep['source']['path']]),retina_band=g['retina_band'],bscan_index=np.arange(512),px_um=np.array([1.12]))
        save(ROUND/'review_packs'/f'{sid}.npz',**provider)
        # Freeze applicable original denials separately for live GUI policy replay.
        save(out/'guards.npz',trace=np.stack([guards.get(b,{}).get('trace',np.full((8,512),-1)) for b in range(512)]),
             reliability=np.stack([guards.get(b,{}).get('reliability',np.full((8,512),-1)) for b in range(512)]),
             excluded=np.stack([np.broadcast_to(guards.get(b,{}).get('excluded',False),(8,512)) for b in range(512)]),
             rejected=np.array([guards.get(b,{}).get('rejected',False) for b in range(512)]))
        write(out/'human_guard_provenance.json',provenance);write(out/'context_records.json',records)
        write(out/'exported.json',dict(scan_id=sid,n_bscans=512,policy_revision=POLICY_REVISION,position_model_changed=learned and model_manifest['position_mode']!='frozen',
             v2_reported_fraction=np.isfinite(d['reported_positions']).mean(),v2_candidate_fraction=np.isfinite(d['uncertain_estimates']).mean(),
             matched_baseline_reported_fraction=np.isfinite(brep).mean(),measurements=fingerprint(out/'measurements.npz')))
        print('Exported',sid,flush=True)

if __name__=='__main__':run()
