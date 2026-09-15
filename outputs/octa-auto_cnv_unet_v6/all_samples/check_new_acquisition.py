"""Exercise missing-export preparation on one real acquisition; no labels written."""
from batch import *

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--headers',action='store_true');args=parser.parse_args()
    if args.headers:
        from octa.volio import ProcessedVolume
        checks=[]
        for r in read(HERE/'inventory.json')['scans']:
            if not Path(r['upstream_volume']).is_relative_to(HERE):continue
            with ProcessedVolume(r['source']) as v:
                ok=v.angio is not None and v.struct.shape==v.angio.shape==(512,512,1024)
                checks.append(dict(scan_id=r['scan_id'],passed=ok,structural_shape=list(v.struct.shape),
                    octa_shape=list(v.angio.shape) if v.angio is not None else None,
                    structural_channel=v.struct.name,octa_channel=v.angio.name if v.angio is not None else None,
                    source=fingerprint(r['source'],sampled=True)))
        write(HERE/'verification/new_acquisition_headers.json',dict(passed=all(c['passed'] for c in checks),scans=checks))
        assert all(c['passed'] for c in checks),checks
        print('All new acquisition channel/grid headers passed:',len(checks),flush=True)
        raise SystemExit(0)
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    r=next(r for r in read(HERE/'inventory.json')['scans'] if Path(r['upstream_volume']).is_relative_to(HERE))
    d,meta,images=recover_inputs(r)
    assert images.shape[0]==512 and images.shape[2]==512
    assert d['optical'].shape==(2,512,512) and np.isfinite(d['optical']).all()
    assert np.array_equal(d['availability'],np.isfinite(d['thickness_um']))
    assert np.isnan(d['thickness_um'][:,d['shadow']]).all()
    stats=read(PILOT/'data/normalization.json')
    for e,n in [('B',11),('C',19)]:
        x=tensor_inputs(d,stats,e)
        assert x.shape==(n,512,512) and np.isfinite(x).all()
    write(HERE/'verification/new_acquisition_inputs.json',dict(passed=True,scan_id=r['scan_id'],native_images_shape=images.shape,input_shapes={k:v.shape for k,v in d.items()},input_hashes={k:array_hash(v) for k,v in d.items()},automatic_only=meta['automatic_only']))
    print('New acquisition frozen automatic-input preparation passed',r['scan_id'],flush=True)
