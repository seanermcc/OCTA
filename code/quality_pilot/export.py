"""Identical pre-human reporting/candidate rules on all six saved predictions."""
import numpy as np
from .common import *
from octa_seg_v1.decisions import decide,alignment,estimate_context,thickness
from eight_surface.config import SURFACE_NAMES,LAYER_DEFS,CASCADE_VERSION

def run():
    initialize();cal=read(FROZEN/'calibration/deployment_vessels.json')['thresholds']
    for sid in SCANS:
        out=OUT/'volumes'/sid
        if (out/'complete.json').exists():continue
        prep=read(out/'prepared.json');g=npz(out/'geometry.npz');images=np.load(prep['images'],mmap_mode='r')
        paths=sorted(Path(prep['reused_neural'] or out/'neural').glob('b*.npz'))
        assert [p.name for p in paths]==[f'b{b:04d}.npz' for b in range(512)]
        preds=[npz(p) for p in paths];rows=np.stack([p['rows'] for p in preds]);prob=np.stack([p['probabilities'] for p in preds]);entropy=np.stack([p['entropy'] for p in preds]);del preds
        assert rows.shape==(512,8,512) and np.isfinite(entropy).all()
        results=[decide(rows[b],prob[b],cal,g['vessel'][b]) for b in range(512)]
        reported,state,reason=[np.stack([r[k] for r in results]) for k in range(3)]
        previous=FROZEN/'volumes'/sid
        if previous.exists():
            a=npz(previous/'alignment.npz')
            with np.load(previous/'measurements.npz') as d:assert np.array_equal(state,d['automatic_state'])
        elif (out/'alignment.npz').exists():a=npz(out/'alignment.npz')
        else:
            print('Registering',sid,flush=True);shifts,scores=alignment(images);a=dict(shifts=shifts,scores=scores);save(out/'alignment.npz',**a)
        print('Automatic candidates',sid,flush=True)
        estimates,context_reason,gaps=estimate_context(rows,reported,state,reason,images,a['shifts'],a['scores'],offset=int(g['label_offset']))
        primary=thickness(reported,g['shadow'])
        assert not np.isfinite(estimates[state==2]).any()
        assert not np.isfinite(primary.transpose(0,2,1)[g['shadow']]).any()
        save(out/'measurements.npz',raw_position_branch=rows,reported_positions=reported,uncertain_estimates=estimates,
             state=state,reason=reason,context_reason=context_reason,probabilities=prob,entropy=entropy,
             primary_thickness_um=primary,surface_names=np.array(SURFACE_NAMES),label_offset=g['label_offset'],
             thickness_names=np.array([l[0] for l in LAYER_DEFS]+['INNER_RETINA']),automatic_before_human_overrides=np.array(True))
        provider=dict(surfaces=reported-int(g['label_offset']),uncertain_estimates=estimates-int(g['label_offset']),
             state=state,reason=reason,probabilities=prob,context_reason=context_reason,
             confidence=np.full_like(rows,np.nan),surface_names=np.array(SURFACE_NAMES),scan_id=np.array([sid]),
             cascade_version=np.array([CASCADE_VERSION]),source=np.array([prep['source']['path']]),
             retina_band=g['retina_band'],label_offset=g['label_offset'],shadow=g['shadow'],bscan_index=np.arange(512),
             model_version=np.array('octa-seg_v1'),px_um=np.array([1.12]))
        save(OUT/'review_packs/automatic'/f'{sid}.npz',**provider)
        save(OUT/'review_packs/scan_queue'/f'{sid}.npz',**provider)
        atomic_json(out/'gaps.json',gaps)
        atomic_json(out/'complete.json',dict(scan_id=sid,n_bscans=512,boundaries=8,automatic_before_human_overrides=True,
             predictions_reused=bool(prep['reused_neural']),measurements=fingerprint(out/'measurements.npz')))
        print('Complete export',sid,flush=True)

if __name__=='__main__':run()
