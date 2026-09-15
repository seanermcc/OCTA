"""Actual processed OCTA, averaged over the saved retinal depth crop. No RAW reads."""
from common import *
from octa.volio import ProcessedVolume
from octa.segment import detect_orientation
from eight_surface.cnv_data import _streamed_depth_profile, _mean_db_dataset

def projection(sid):
    out=volume_path(sid);neural=read(out/'neural_complete.json')
    source=Path(neural['source']['path']);stat=source.stat()
    g=npz(out/'geometry.npz');lo,hi=map(int,g['retina_band'])
    key=dict(source=str(source),bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,
        geometry_sha256=sha(out/'geometry.npz'),depth_crop=[lo,hi],channel='frame_OCTAAvg',
        method='mean of 20*log10(max(channel,0.001)) over original saved retinal depth crop',axis_order='B-scan,A-line')
    path=HERE/'octa_cache'/f'{sid}.npz'
    if path.exists():
        cached=npz(path)
        if json.loads(str(cached['key_json']))==key:return cached['octa'],json.loads(str(cached['metadata_json']))
    with ProcessedVolume(source) as volume:
        if volume.angio is None:raise ValueError('No frame_OCTAAvg channel in this acquisition')
        if volume.angio.shape!=volume.struct.shape:raise ValueError('OCTA and structural grids differ')
        if tuple(volume.struct.shape[:2])!=(512,512):raise ValueError('Unexpected native grid')
        high=bool(detect_orientation(_streamed_depth_profile(volume.struct)))
        if high!=bool(g['vitreous_high']):raise ValueError('Detected orientation differs from the linked B-scan export')
        image=_mean_db_dataset(volume.angio,slice(lo,hi))
    meta=dict(**key,orientation_detected=high,projection='saved retinal crop; not a layer-specific slab',
        scan_id=sid,experimental=True)
    save_npz(path,octa=image,key_json=np.array(json.dumps(key)),metadata_json=np.array(json.dumps(meta)))
    return image,meta

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--scan');args=p.parse_args()
    records=[]
    for visit in selected():
        sid=visit['scan_id']
        if args.scan and sid!=args.scan:continue
        print('OCTA',sid,flush=True)
        a,meta=projection(sid)
        records.append(dict(scan_id=sid,shape=list(a.shape),finite_pixels=int(np.isfinite(a).sum()),metadata=meta))
        write(HERE/'verification/octa_sources.json',records)
    print('OCTA projections ready:',len(records),flush=True)
