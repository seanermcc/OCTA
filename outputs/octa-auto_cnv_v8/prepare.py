"""Read-only automatic inputs and bulk full-depth structural caching."""
from common import *
from audit import freeze
from legacy import automatic_thickness
import gc, shutil

def prepare_enface(a):
    sid=a['scan_id'];out=HERE/'cache'/sid
    if (out/'enface_manifest.json').exists():
        m=read(out/'enface_manifest.json')
        for fp in m['outputs']:verify(fp)
        return m
    progress('Preparing frozen automatic en-face inputs',scan=sid)
    mp=V6/'inputs'/(sid+'.json');meta=read(mp)
    assert meta['scan_id']==sid and meta['native_shape']==[512,512,1024] and meta['axis_order']=='B-scan,A-line'
    assert Path(meta['source']['path']).resolve()==Path(a['source']).resolve()
    assert meta['automatic_only'] and meta['octa_channel']=='frame_OCTAAvg'
    assert meta['source']['sha256']==a['source_fingerprint']['sha256']
    fps=[fingerprint(mp),meta['source'],meta['geometry'],meta['optical_cache']]
    for fp in fps:verify(fp)
    g=npz(meta['geometry']['path']);optical=npz(meta['optical_cache']['path'])['optical']
    assert optical.shape==(2,512,512) and np.isfinite(optical).all()
    rawfp=meta.get('regenerated_neural') or meta.get('raw_neural_measurements')
    if not rawfp:raise ValueError('Missing automatic-only frozen neural source')
    verify(rawfp);fps.append(rawfp);raw=npz(rawfp['path'])
    rows=raw['rows'] if 'rows' in raw else raw['raw_position_branch'];prob=raw['probabilities']
    calp=ROOT/'outputs/octa-seg/octa-seg_v1/calibration/deployment_vessels.json';fps.append(fingerprint(calp))
    depth=int(g['retina_band'][1]-g['retina_band'][0])
    thick,reasons,end=automatic_thickness(rows,prob,g,read(calp)['thresholds'],depth)
    assert np.isnan(thick[:,g['shadow'].astype(bool)]).all()
    # Only whitelisted automatic arrays are exported. Geometry's CNV/exclusion masks are not inputs.
    save(out/'enface.npz',optical=optical,thickness_um=thick,availability=np.isfinite(thick),shadow=g['shadow'].astype(bool),reason_bits=reasons)
    predp=V6/'predictions/C_267'/(sid+'.npz');provp=V6/'predictions/provenance'/(sid+'.json')
    prov=read(provp)['models']['C_267'];verify(prov['prediction']);verify(prov['checkpoint'])
    pred=npz(predp);assert str(pred['scan_id'])==sid and str(pred['axis_order'])=='B-scan,A-line'
    assert str(pred['checkpoint_sha256'])==prov['checkpoint']['sha256']
    assert prov['native_shape']==[512,512] and Path(prov['prediction']['path']).resolve()==predp.resolve()
    shutil.copyfile(predp,dest(out/'v6.npz'));write(out/'v6_provenance.json',prov)
    fps.extend([fingerprint(provp),fingerprint(predp),prov['checkpoint']])
    m=dict(scan_id=sid,inputs=fps,outputs=[fingerprint(out/n) for n in ('enface.npz','v6.npz','v6_provenance.json')])
    write(out/'enface_manifest.json',m);return m

def prepare_case(a):
    sid=a['scan_id'];out=HERE/'cache'/sid;meta_path=out/'manifest.json'
    if meta_path.exists():
        m=read(meta_path)
        for fp in m['outputs']:verify(fp)
        return m
    em=prepare_enface(a);fps=em['inputs'];meta=read(V6/'inputs'/(sid+'.json'))
    g=npz(meta['geometry']['path']);optical=npz(out/'enface.npz')['optical']
    depth=int(g['retina_band'][1]-g['retina_band'][0])
    progress('Preparing full-depth native inputs',scan=sid)
    from octa.volio import ProcessedVolume
    from octa.segment import detect_orientation
    from eight_surface.segment import prepare_bscan
    with ProcessedVolume(a['source']) as volume:
        assert volume.shape==(512,512,1024) and volume.angio.shape==volume.shape
        full=volume.read_volume()
    assert np.isfinite(full).all()
    high=bool(detect_orientation(full.mean((0,1))))
    assert high==bool(meta['orientation_fresh_detected'])==bool(g['vitreous_high'])
    cp=dest(out/'structural.npy');tmp=cp.with_suffix('.tmp.npy')
    arr=np.lib.format.open_memmap(tmp,mode='w+',dtype='float32',shape=(512,1024,512))
    maxerr=0.;offset=int(g['label_offset'])
    for b in range(512):
        arr[b]=prepare_bscan(full[b],high)
        maxerr=max(maxerr,float(np.abs(arr[b,offset:offset+depth].mean(0)-optical[0,b]).max()))
    assert maxerr<.001,('En-face/B-scan alignment mismatch',sid,maxerr)
    sample=np.array(arr[::16,::8,::8]).ravel()
    arr.flush();del arr,full;gc.collect();tmp.replace(cp)
    # Hash the processed source once for full source identity, in addition to inherited sampled hashes.
    full_source=fingerprint(a['source'])
    m=dict(scan_id=sid,source_identity=a['source_identity'],source_full=full_source,inputs=fps,
        orientation_detected=high,axis_order='B-scan,depth,A-line',native_shape=[512,1024,512],
        canonical_depth_zero='vitreous',axial_crop=None,axial_resolution_um=1.12,
        intensity_transform='established prepare_bscan: 20 log10(max(amplitude,0.001)); canonical orientation only',
        structural_enface_max_error_db=maxerr,normalization_sample=sample.tolist(),
        outputs=[fingerprint(out/n) for n in ('enface.npz','structural.npy','v6.npz','v6_provenance.json')])
    write(meta_path,m);return m

def run(optics_only=False):
    m=freeze();preview=read(HERE/'data/preview.json')['cases'];unique={r['scan_id']:r['acquisition'] for r in m['records']}
    unique.update({r['scan_id']:r['acquisition'] for r in preview})
    if not optics_only:
        manifest=[]
        for i,a in enumerate(unique.values()):
            manifest.append(prepare_case(a));progress('Native input cache',completed=i+1,total=len(unique))
        train_ids={r['scan_id'] for r in m['records']};train=[x for x in manifest if x['scan_id'] in train_ids]
        a=np.concatenate([np.asarray(x['normalization_sample']) for x in train]);q=np.percentile(a,[25,50,75])
        stats=read(HERE/'data/normalization_enface.json')
        stats['structural']=dict(center=float(q[1]),scale=float(max((q[2]-q[0])/1.349,.001)),sample='regular 16 B-scan x 8 depth x 8 lateral stride; training volumes only')
        write(HERE/'data/normalization_structural.json',stats)
        write(HERE/'data/inputs.json',dict(cases=[{k:v for k,v in x.items() if k!='normalization_sample'} for x in manifest]))
        progress('All native inputs and training-only normalization frozen',cases=len(manifest));return
    manifest=[]
    for i,a in enumerate(unique.values()):
        manifest.append(prepare_enface(a));progress('En-face inputs frozen',completed=i+1,total=len(unique))
    train_ids={r['scan_id'] for r in m['records']};train=[x for x in manifest if x['scan_id'] in train_ids]
    stats={}
    for name,n in [('optical',2),('thickness_um',8)]:
        vals=[npz(HERE/'cache'/r['scan_id']/'enface.npz')[name] for r in train]
        centers=[];scales=[]
        for k in range(n):
            a=np.concatenate([x[k].ravel() for x in vals]);a=a[np.isfinite(a)]
            if not len(a):raise ValueError('Entire training channel unavailable')
            q=np.percentile(a,[25,50,75]);centers.append(float(q[1]));scales.append(float(max((q[2]-q[0])/1.349,.001)))
        stats[name]=dict(center=centers,scale=scales)
    stats['training_scan_ids']=sorted(train_ids)
    write(HERE/'data/normalization_enface.json',stats)
    write(HERE/'data/inputs_enface.json',dict(cases=manifest))
    progress('En-face inputs and training-only normalization frozen',cases=len(manifest))
if __name__=='__main__':run('--optics-only' in sys.argv)
