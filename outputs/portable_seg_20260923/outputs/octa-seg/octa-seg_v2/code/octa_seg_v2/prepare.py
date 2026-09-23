"""CPU input preparation, current footprints and isolated automatic proposals."""
from types import SimpleNamespace
import gc
from .common import *
from octa.volio import ProcessedVolume
from eight_surface.segment import prepare_bscan,detect_orientation
from stage_a.geometry import label_offset
from cnv_review_v1.data import load_enface
from quality_pilot.prepare import shadow_only
from scan_quality import _mad

def run():
    initialize()
    with (ROOT/'outputs/scan_quality_metrics.csv').open(encoding='utf-8-sig') as f:qc={r['scan_id']:r for r in csv.DictReader(f)}
    for sid in SCANS:
        out=ROUND/'volumes'/sid
        if (out/'prepared.json').exists():continue
        print('Preparing',sid,flush=True);q=qc[sid];old=PILOT/'volumes'/sid
        if (old/'prepared.json').exists():
            p=read(old/'prepared.json');g=npz(old/'geometry.npz');images=np.load(p['images'],mmap_mode='r');band=g['retina_band'];source=p['source']
            image_path=Path(p['images']);reused=p['reused_neural'] or str(old/'neural')
        else:
            band=np.array([int(q['retina_lo']),int(q['retina_hi'])]);source=fingerprint(q['source'],sampled=True)
            existing=ROOT/'outputs/eight_surface/segmented'/f'{sid}.npz'
            if existing.exists():
                with np.load(existing,allow_pickle=False) as data:band=data['retina_band'].copy()
            with ProcessedVolume(q['source']) as v:full=v.read_volume()
            vhi=bool(detect_orientation(full.mean(axis=(0,1))));offset=label_offset(band,full.shape[2],vhi)
            image_path=writable(out/'images.npy');images=np.lib.format.open_memmap(image_path,mode='w+',dtype=np.float32,shape=(512,int(np.diff(band)[0]),512))
            for b in range(512):images[b]=prepare_bscan(full[b],vhi)[offset:offset+images.shape[1]]
            lo,hi=map(int,band);stop=full.shape[2]-4 if q['noise_window_side']=='high_depth' else max(4,lo-4)
            start=max(hi+4,stop-48) if q['noise_window_side']=='high_depth' else max(0,stop-48)
            noise=full[:,:,start:stop];sigma=max(float(_mad(noise.ravel())),1e-6)
            cnr=((np.percentile(full[:,:,lo:hi],75,axis=2)-np.median(noise,axis=2))/sigma).astype(np.float32)
            del noise,full;gc.collect()
            shadow=np.stack([shadow_only(np.mean(images[max(0,b-1):min(512,b+2)],axis=0)) for b in range(512)])
            images.flush();g=dict(shadow=shadow,local_cnr=cnr,low_signal=cnr<3,retina_band=band,label_offset=np.array(offset),vitreous_high=np.array(vhi),native_shape=np.array([512,512,1024]));reused=None
        scan=SimpleNamespace(scan_id=sid,native_shape=(512,512),source_volume=Path(source['path']),retina_band=tuple(map(int,band)))
        cnv,vessel,onh,edge,prov,label=load_enface(scan,ROOT/'outputs/cnv_labels',ROOT/'outputs/eight_surface/vasculature_proposals')
        if prov['status']=='no vessel mask available':
            from vasculature_baseline import vessel_evidence,make_mask
            from vasculature_shape_gate import shape_gate,PARAMETERS
            evidence,_,_=vessel_evidence(np.mean(images,axis=1));vessel,audit=shape_gate(make_mask(evidence,.18,onh),**PARAMETERS)
            dest=OUT/'proposals'/f'{sid}_proposal.npz'
            from eight_surface.vasculature_proposals import PROPOSAL_VERSION
            save(dest,predicted_vasculature_mask=vessel,evidence=evidence,scan_id=np.array([sid]),source_volume=np.array([source['path']]),retina_band=band,native_shape=np.array([512,512]),axis_order=np.array(['B-scan,A-line']),proposal_format_version=np.array([PROPOSAL_VERSION]),human_reviewed=np.array([False]),method=np.array(['major-vessel-shape-gate-v2']),parameters_json=np.array([json.dumps(PARAMETERS)]))
            write(dest.with_suffix('.json'),audit);prov=dict(path=str(dest),status='automatic vessel proposal — unreviewed',sha256=fingerprint(dest)['sha256'])
        changed=bool('vessel' in g and not np.array_equal(vessel,g['vessel']))
        if changed:reused=None # vessel enters neural reliability head as well as decision policy
        g.update(vessel=vessel,cnv=cnv,onh=onh,onh_edge=edge)
        save(out/'geometry.npz',**g)
        write(out/'prepared.json',dict(scan_id=sid,source=source,images=str(image_path),reused_neural=reused,footprints=prov,enface_label=fingerprint(label) if label else None,acquisition=q,footprint_changed_from_pilot=changed,orientation='fresh detection for new volumes; verified frozen canonical cache for original six'))
        print('Prepared',sid,'reuse neural:',bool(reused),flush=True)
        del images;gc.collect()

if __name__=='__main__':run()
