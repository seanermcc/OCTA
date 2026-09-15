"""Independent reconstruction checks on one train, validation and holdout acquisition."""
from common import *
from octa.volio import ProcessedVolume
from octa.segment import detect_orientation
from eight_surface.segment import prepare_bscan
from eight_surface.cnv_data import _streamed_depth_profile,_mean_db_dataset

def run():
    m=read(HERE/'data/manifest.json');results=[]
    for day in ['D0','D49','D98']:
        rec=next(r for r in m['scans'] if r['day_label']==day and r['eye']=='OD');sid=rec['scan_id']
        progress('Independent source alignment check',scan=sid)
        g=npz(volume_path(sid)/'geometry.npz');d=npz(HERE/'data'/f'{sid}.npz');images=np.load(volume_path(sid)/'images.npy',mmap_mode='r')
        with ProcessedVolume(rec['source']) as v:
            high=bool(detect_orientation(_streamed_depth_profile(v.struct)))
            assert high==bool(g['vitreous_high'])
            lo,hi=map(int,g['retina_band']);octa=_mean_db_dataset(v.angio,slice(lo,hi))
            error=float(np.max(np.abs(octa-d['optical'][1])));assert error<1e-4
            # One bulk selected-row read, never a per-B-scan read loop.
            indices=[64,256,448];raw=np.asarray(v.struct[indices,:,:],np.float32)
            offset=int(g['label_offset']);recreated=np.stack([prepare_bscan(a,high)[offset:offset+images.shape[1]] for a in raw])
            structural_error=float(np.max(np.abs(recreated-images[indices])))
            assert structural_error<1e-4
        results.append(dict(scan_id=sid,split=rec['split'],fresh_detected_vitreous_high=high,
            octa_full_native_projection_max_abs_error_db=error,structural_three_bscan_max_abs_error_db=structural_error,
            canonical_crop_rows_checked=indices,axis_order='B-scan,A-line; canonical depth vitreous first',passed=True))
        write(HERE/'verification/direct_source_alignment.json',results)
    progress('Independent source checks passed',scans=len(results))

if __name__=='__main__':run()
