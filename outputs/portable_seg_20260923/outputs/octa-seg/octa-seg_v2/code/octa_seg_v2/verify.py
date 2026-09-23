"""Ten-volume coordinate/contract verification and external-file integrity."""
from .common import *
from .policy import geometry_valid
from octa_seg_v1.decisions import thickness

def protect():
    dest=OUT/'external_files_read_only.json'
    if dest.exists():
        for fp in read(dest)['files']:verify(fp)
        return
    files=list((ROOT/'code').rglob('*.py'))
    for directory in [ROOT/'outputs/labels',ROOT/'outputs/eight_surface/labels',ROOT/'outputs/cnv_labels',ROOT/'outputs/cnv_review_v1/surface_labels',V1/'reviewer/surface_labels',V1/'reviewer/estimate_feedback']:
        files.extend(p for p in directory.glob('*') if p.is_file())
    write(dest,dict(files=[fingerprint(p) for p in files],scope='Existing code and human feedback are read-only dependencies. V2 writes confined to its own folder.'))

def run(native=False):
    protect();m=initialize();results=[]
    for sid in SCANS:
        out=ROUND/'volumes'/sid;d=npz(out/'measurements.npz');g=npz(out/'geometry.npz');p=read(out/'prepared.json')
        assert d['raw_position_branch'].shape==(512,8,512)
        assert d['probabilities'].shape==(512,8,2,512)
        rep=d['reported_positions'];cand=d['uncertain_estimates'];state=d['state']
        assert not np.isfinite(rep[state!=1]).any()
        assert not np.isfinite(cand[state!=3]).any()
        assert not (np.isfinite(cand)&np.isfinite(rep)).any()
        assert np.array_equal(thickness(rep,g['shadow']),d['primary_thickness_um'],equal_nan=True)
        assert not np.isfinite(d['primary_thickness_um'].transpose(0,2,1)[g['shadow']]).any()
        offset=int(g['label_offset']);images=np.load(p['images'],mmap_mode='r');valid=geometry_valid(d['raw_position_branch'],offset,images.shape[1])
        assert not np.isfinite(rep[~valid]).any();assert not np.isfinite(cand[~valid]).any()
        provider=npz(ROUND/'review_packs'/f'{sid}.npz');assert np.array_equal(provider['surfaces'],rep-offset,equal_nan=True)
        assert np.array_equal(provider['bscan_index'],np.arange(512));assert np.array_equal(provider['uncertain_estimates'],cand-offset,equal_nan=True)
        # All originals with compatible footprint retain exact position outputs.
        old=PILOT/'volumes'/sid/'measurements.npz'
        if old.exists():assert np.array_equal(npz(old)['raw_position_branch'],d['raw_position_branch'])
        native_rows=[]
        if native:
            from octa.volio import ProcessedVolume
            from eight_surface.segment import prepare_bscan
            # One bulk band read; never repeatedly decompress a volume per B-scan.
            with ProcessedVolume(p['source']['path']) as v:band=np.asarray(v.struct[:,:,slice(*map(int,g['retina_band']))],np.float32)
            for b in (0,256,511):
                np.testing.assert_allclose(prepare_bscan(band[b],bool(g['vitreous_high'])),images[b],atol=1e-5,rtol=0);native_rows.append(b)
            del band
        results.append(dict(scan_id=sid,bscans=512,solid_fraction=np.isfinite(rep).mean(),candidate_fraction=np.isfinite(cand).mean(),native_rows_checked=native_rows,
            orientation='canonical vitreous 0',native_shape=g['native_shape'].tolist(),crop_offset=offset,shadow_nan=True,compatibility_surfaces_reported_only=True))
        print('Verified',sid,flush=True)
    # Validate the frozen v1 artifacts that this work reads, plus all its human-label dependencies.
    old=read(V1/'data/manifest.json')
    for r in old['records']:verify(r['label'])
    for fp in read(OUT/'external_files_read_only.json')['files']:verify(fp)
    write(OUT/'tests/volume_verification.json',dict(volumes=results,total_native_bscans=5120,original_label_fingerprints_valid=True,existing_code_unchanged=True,policies_are_not_accuracy_claims=True))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--native',action='store_true');p.add_argument('--protect',action='store_true');a=p.parse_args();protect() if a.protect else run(a.native)
