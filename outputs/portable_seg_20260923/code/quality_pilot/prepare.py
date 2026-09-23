"""Read-only native sources and frozen predictions; write pilot inputs only."""
import gc
from types import SimpleNamespace
import numpy as np
from .common import *
from octa.volio import ProcessedVolume
from eight_surface.segment import prepare_bscan, detect_orientation
from stage_a.geometry import label_offset
from cnv_review_v1.data import load_enface
from scan_quality import _mad

def shadow_only(image):
    # The unchanged eight-surface shadow stage, including its broad-mask guard.
    from eight_surface.segment import build_costs,tissue_bounds,banded_dp,median_filter1d,dp_surface,shadow_columns
    costs=build_costs(image); first,_=tissue_bounds(image)
    ilm=median_filter1d(banded_dp(costs['db'],first,halfwidth=18,max_step=2).astype(float),11)
    peak=median_filter1d(dp_surface(costs['bright'],max_step=2,lo=ilm+60,
                                   hi=np.full(image.shape[1],image.shape[0])).astype(float),15)
    shadow=shadow_columns(image,ilm,peak+20)
    return np.zeros(image.shape[1],bool) if shadow.mean()>.6 else shadow

def run():
    initialize(); qc=qc_rows(); old=read(FROZEN/'data/manifest.json')
    for sid in SCANS:
        out=OUT/'volumes'/sid; out.mkdir(parents=True,exist_ok=True)
        if (out/'prepared.json').exists():continue
        q=qc[sid]; previous=FROZEN/'volumes'/sid
        band=old['sources'][sid]['label_band'] if previous.exists() else [int(q['retina_lo']),int(q['retina_hi'])]
        print('Reading native source',sid,flush=True)
        with ProcessedVolume(q['source']) as vol: full=vol.read_volume()
        vhi=bool(detect_orientation(full.mean(axis=(0,1)))); offset=label_offset(band,full.shape[2],vhi)
        lo,hi=band; stop=full.shape[2]-4 if q['noise_window_side']=='high_depth' else max(4,lo-4)
        start=max(hi+4,stop-48) if q['noise_window_side']=='high_depth' else max(0,stop-48)
        noise=full[:,:,start:stop]; sigma=max(float(_mad(noise.ravel())),1e-6)
        contrast=np.percentile(full[:,:,lo:hi],75,axis=2)-np.median(noise,axis=2)
        signal_cnr=(contrast/sigma).astype(np.float32)
        scan=SimpleNamespace(scan_id=sid,native_shape=full.shape[:2],source_volume=Path(q['source']),retina_band=tuple(band))
        cnv,vessel,onh,edge,prov,label=load_enface(scan,ROOT/'outputs/cnv_labels',ROOT/'outputs/eight_surface/vasculature_proposals')
        # Use exactly the frozen inference footprints for the four baseline scans.
        if previous.exists():
            g=npz(previous/'geometry.npz'); frozen_masks=npz(old['footprints'][sid]['path'])
            assert offset==int(g['label_offset']) and np.array_equal(full.shape,g['native_shape'])
            shadow=g['shadow']; vessel=g['vessel']; cnv=g['cnv'];onh=frozen_masks['onh'];edge=frozen_masks['onh_edge']
            prov=old['footprints'][sid]; image_path=previous/'images.npy'
        else:
            image_path=out/'images.npy'
            imgs=np.lib.format.open_memmap(image_path,mode='w+',dtype=np.float32,shape=(len(full),hi-lo,full.shape[1]))
            for b in range(len(full)):imgs[b]=prepare_bscan(full[b],vhi)[offset:offset+hi-lo]
            shadow=np.zeros(full.shape[:2],bool)
            for b in range(len(full)):
                shadow[b]=shadow_only(np.mean(imgs[max(0,b-1):min(len(full),b+2)],axis=0))
                if b%128==0: print('Shadow mask',sid,b,flush=True)
            imgs.flush();del imgs
        save(out/'geometry.npz',shadow=shadow,vessel=vessel,cnv=cnv,onh=onh,onh_edge=edge,
             local_cnr=signal_cnr,low_signal=signal_cnr<3,label_offset=np.array(offset),
             vitreous_high=np.array(vhi),native_shape=np.array(full.shape),retina_band=np.array(band))
        metadata=dict(scan_id=sid,source=fingerprint(q['source'],sampled=True),images=str(image_path),
                      reused_neural=str(previous/'neural') if previous.exists() else None,
                      footprints=prov,enface_label=label,acquisition=q,shape=list(full.shape),
                      coordinate_check='fresh native orientation; canonical full-depth rows minus crop offset',
                      local_signal_definition='same raw tissue P75 minus local vitreous median / whole-vitreous MAD as scan_quality.py')
        atomic_json(out/'prepared.json',metadata)
        del full,noise;gc.collect();print('Prepared',sid,flush=True)

if __name__=='__main__':run()
