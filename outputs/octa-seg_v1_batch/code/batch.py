"""Isolated, resumable frozen octa-seg_v1 full acquisition batch."""
from pathlib import Path
import sys, os, json, csv, time, traceback, subprocess, shutil, argparse
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'outputs/octa-seg_v1_batch'
V1 = ROOT/'outputs/octa-seg/octa-seg_v1'
sys.path.insert(0, str(ROOT/'code'))
os.environ['PYTHONDONTWRITEBYTECODE']='1'
if os.name=='nt' and os.environ.get('CONDA_PREFIX'):
    _dll = os.add_dll_directory(str(Path(os.environ['CONDA_PREFIX'])/'Library/bin'))
import numpy as np
from stage_a.common import fingerprint, verify, digest

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d):
    p=Path(p); assert p.resolve().is_relative_to(OUT.resolve()); p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+'.tmp'); t.write_text(json.dumps(d,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else x.item() if isinstance(x,np.generic) else str(x)),encoding='utf-8'); t.replace(p)
def save(p,**d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp.npz');np.savez_compressed(t,**d);t.replace(p)
def npz(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def csvread(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csvwrite(p,rows,fields=None):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);fields=fields or list(dict.fromkeys(k for r in rows for k in r))
    t=p.with_suffix('.tmp.csv')
    with t.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
    t.replace(p)
def directory(s):return OUT/'volumes'/s
def manifest():return read(OUT/'manifest.json')
def record(s):return next(r for r in manifest()['scans'] if r['scan_id']==s)

def init():
    from batch_segment import resolve_volumes_path,scan_id_for
    from octa.volio import ProcessedVolume
    rows=csvread(ROOT/'outputs/scan_index.csv')
    disk=sorted((ROOT.parent/'OCTA_RawData').rglob('*_processedVolumes.mat'))
    diskmap={str(p.resolve()).lower():p for p in disk}; mapped={};unavailable=[]
    qc={r['scan_id']:r for r in csvread(ROOT/'outputs/scan_quality_metrics.csv')}
    for r in rows:
        p=resolve_volumes_path(r);sid=scan_id_for(r)
        if p is None:
            unavailable.append(dict(scan_id=sid,reason='not reconstructed' if r.get('raw_path') and Path(r['raw_path']).exists() else 'processed volume unavailable; RAW also unavailable',**r));continue
        key=str(p.resolve()).lower()
        if key in mapped:raise ValueError('Duplicate index identity: '+str(p))
        mapped[key]=dict(r,scan_id=sid,source=str(p.resolve()),acquisition_reference=qc.get(sid,{}))
    missing=[p for k,p in diskmap.items() if k not in mapped]
    write(OUT/'reconciliation.json',dict(index_rows=len(rows),disk_processed_files=len(disk),matched=len(mapped),unindexed=[str(p) for p in missing],unavailable=len(unavailable)))
    aliases=[]
    for p in missing:
        candidates=[r for r in mapped.values() if Path(r['source']).name==p.name]
        if len(candidates)!=1:raise ValueError('Unresolved acquisition identity: '+str(p))
        match=candidates[0];a=fingerprint(p);b=fingerprint(match['source'])
        if a['sha256']!=b['sha256']:
            # A reprocessed version of the same acquisition remains a separate input.
            alt=dict(match,scan_id=match['scan_id']+'_source_'+a['sha256'][:8],source=str(p.resolve()),acquisition_reference={},source_variant_of=match['scan_id'])
            mapped[str(p.resolve()).lower()]=alt
        else:aliases.append(dict(scan_id=match['scan_id'],duplicate=a,canonical=b,classification='byte-identical duplicate, not an additional acquisition'))
    write(OUT/'duplicate_files.json',aliases)
    write(OUT/'reconciliation.json',dict(index_rows=len(rows),disk_processed_files=len(disk),distinct_inputs=len(mapped),byte_identical_duplicate_files=len(aliases),unindexed_unresolved=0,unavailable=len(unavailable)))
    scans=[]
    for r in mapped.values():
        with ProcessedVolume(r['source']) as v:r['native_shape']=list(v.shape)
        r['source_fingerprint']=fingerprint(r['source'],sampled=True);scans.append(r)
    scans.sort(key=lambda r:r['scan_id'])
    deps=list((ROOT/'code/octa_seg_v1').glob('*.py'))+[ROOT/'code'/p for p in ['stage_a/geometry.py','eight_surface/segment.py','eight_surface/config.py','cnv_review_v1/data.py','quality_pilot/prepare.py','scan_quality.py']]+[ROOT/'outputs/octa-thick_v1/engine.py']
    m=dict(model='octa-seg_v1',scans=scans,unavailable=unavailable,checkpoints=[fingerprint(V1/'models/ALL_LABELLED'/n) for n in ('position.pt','states.pt')],calibration=fingerprint(V1/'calibration/deployment_vessels.json'),dependencies=[fingerprint(p) for p in deps],index=fingerprint(ROOT/'outputs/scan_index.csv'),policy='Unchanged v1 decisions and contextual estimates; preparation matches longitudinal v1; no v2 reporting rules',created=time.strftime('%Y-%m-%dT%H:%M:%S'))
    write(OUT/'manifest.json',m);csvwrite(OUT/'unavailable_acquisitions.csv',unavailable)
    csvwrite(OUT/'acquisitions.csv',[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in scans])
    if not (OUT/'qualitative_ratings.csv').exists():
        csvwrite(OUT/'qualitative_ratings.csv',[dict(scan_id=r['scan_id'],animal=r['animal'],eye=r['eye'],session_date=r['session_date'],rating='',comments='',rater='',rated_at='',provenance='') for r in scans])
    config=read(V1/'launch_config.json');config.pop('review_queue',None)
    config.update(segmentations=str(OUT/'review_packs'),output=str(OUT/'reviewer'),proposals=str(OUT/'proposals'),initial_scan=scans[0]['scan_id'],auto_sources=[dict(name='octa-seg_v1 batch',directory=str(OUT/'review_packs'))])
    write(OUT/'launch_config.json',config);write(OUT/'thick/volumes.json',[])
    print(json.dumps(read(OUT/'reconciliation.json')),flush=True)

def check_dependencies():
    m=manifest()
    for fp in m['checkpoints']+[m['calibration']]+m['dependencies']:verify(fp)

def prepare(sid):
    from types import SimpleNamespace
    from octa.volio import ProcessedVolume,find_retina_band
    from eight_surface.segment import prepare_bscan,detect_orientation
    from stage_a.geometry import label_offset
    from cnv_review_v1.data import load_enface
    from quality_pilot.prepare import shadow_only
    import scan_quality as sq
    r=record(sid);o=directory(sid);o.mkdir(parents=True,exist_ok=True);verify(r['source_fingerprint'])
    if (o/'prepared.json').exists():
        p=read(o/'prepared.json');verify(p['geometry']);verify(p['images_fingerprint']);return
    print('Reading and measuring native source',sid,flush=True)
    with ProcessedVolume(r['source']) as v:full=v.read_volume()
    assert list(full.shape)==r['native_shape'];n,w,depth=full.shape
    if (n,w,depth)!=(512,512,1024):raise ValueError('Native shape differs from frozen v1 protocol; investigate before processing')
    high=bool(detect_orientation(full.mean(axis=(0,1))))
    q=r['acquisition_reference'];band=[int(q['retina_lo']),int(q['retina_hi'])] if q else list(find_retina_band(full.mean(axis=(0,1))))
    pilot=ROOT/'outputs/octa-seg/quality_pilot_20260910/volumes'/sid
    old=None
    if (pilot/'prepared.json').exists():
        pp=read(pilot/'prepared.json');verify(pp['source']);assert pp['source']==r['source_fingerprint'];old=npz(pilot/'geometry.npz');band=old['retina_band'].tolist()
    elif (ROOT/'outputs/eight_surface/segmented'/f'{sid}.npz').exists():
        band=npz(ROOT/'outputs/eight_surface/segmented'/f'{sid}.npz')['retina_band'].tolist()
    offset=label_offset(band,depth,high);lo,hi=band
    imgs=np.lib.format.open_memmap(o/'images.npy',mode='w+',dtype=np.float32,shape=(n,hi-lo,w))
    for b in range(n):imgs[b]=prepare_bscan(full[b],high)[offset:offset+hi-lo]
    imgs.flush()
    if old is not None:
        assert bool(old['vitreous_high'])==high and int(old['label_offset'])==offset and np.array_equal(old['native_shape'],full.shape)
        cached=np.load(pp['images'],mmap_mode='r');assert np.array_equal(cached,imgs);shadow=old['shadow'];del cached
    else:
        shadow=np.stack([shadow_only(imgs[max(0,b-1):min(n,b+2)].mean(axis=0)) for b in range(n)])
    # Run the existing independent workflow on the already-read raw volume.
    # Only its I/O adapter changes; all metric calculations are the existing code.
    class MemoryVolume:
        def __init__(self,*a):self.shape=full.shape
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read_volume(self,depth_slice=slice(None)):return full[:,:,depth_slice]
    sq.ProcessedVolume=MemoryVolume;sq.resolve_volumes_path=lambda row:Path(r['source'])
    aq,fp=sq.measure_one(r,{sid:(lo,hi)})
    if aq['status']!='ok':raise RuntimeError(aq['error'])
    noise,side=sq._read_noise(MemoryVolume(),lo,hi)
    cnr=((np.percentile(full[:,:,lo:hi],75,axis=2)-np.median(noise,axis=2))/max(float(sq._mad(noise.ravel())),1e-6)).astype(np.float32)
    scan=SimpleNamespace(scan_id=sid,native_shape=(n,w),source_volume=Path(r['source']),retina_band=tuple(band))
    cnv,vessel,onh,edge,prov,label=load_enface(scan,ROOT/'outputs/cnv_labels',ROOT/'outputs/eight_surface/vasculature_proposals')
    if prov['status']=='no vessel mask available':
        from vasculature_baseline import vessel_evidence,make_mask
        from vasculature_shape_gate import shape_gate,PARAMETERS
        from eight_surface.vasculature_proposals import PROPOSAL_VERSION
        evidence,_,_=vessel_evidence(imgs.mean(axis=1));vessel,audit=shape_gate(make_mask(evidence,.18,onh),**PARAMETERS)
        dest=OUT/'proposals'/f'{sid}_proposal.npz'
        save(dest,predicted_vasculature_mask=vessel,evidence=evidence,scan_id=np.array([sid]),source_volume=np.array([r['source']]),retina_band=np.array(band),native_shape=np.array([n,w]),axis_order=np.array(['B-scan,A-line']),proposal_format_version=np.array([PROPOSAL_VERSION]),human_reviewed=np.array([False]),method=np.array(['major-vessel-shape-gate-v2']),parameters_json=np.array([json.dumps(PARAMETERS)]))
        write(dest.with_suffix('.json'),audit);prov=dict(path=str(dest),status='automatic vessel proposal — unreviewed',sha256=fingerprint(dest)['sha256'])
    elif prov.get('path') and 'automatic vessel proposal' in prov['status']:
        dest=OUT/'proposals'/Path(prov['path']).name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(prov['path'],dest)
    save(o/'geometry.npz',shadow=shadow,local_cnr=cnr,low_signal=cnr<3,retina_band=np.array(band),label_offset=np.array(offset),vitreous_high=np.array(high),native_shape=np.array(full.shape),vessel=vessel,cnv=cnv,onh=onh,onh_edge=edge)
    save(o/'acquisition_fingerprint.npz',fingerprint=fp);write(o/'acquisition_qc.json',aq)
    imgs.flush();imgs._mmap.close();del imgs
    write(o/'prepared.json',dict(scan_id=sid,source=r['source_fingerprint'],images=str(o/'images.npy'),footprints=prov,enface_label=fingerprint(label) if label else None,geometry=fingerprint(o/'geometry.npz'),images_fingerprint=fingerprint(o/'images.npy'),pilot_shadow_provenance=fingerprint(pilot/'geometry.npz') if old is not None else None,full_native_grid=True,orientation_fresh=True,acquisition=aq))

def infer(sid):
    import torch
    from octa_seg_v1.predict import one,state_model
    from octa_seg_v1.train import load_position
    from octa.volio import ProcessedVolume
    from eight_surface.segment import detect_orientation,prepare_bscan
    torch.set_num_threads(4);o=directory(sid);p=read(o/'prepared.json');g=npz(o/'geometry.npz');verify(p['source']);verify(p['geometry'])
    if (o/'neural_complete.json').exists():return
    # Reuse only raw neural arrays, after verifying complete source, grid, mask,
    # image and checkpoint provenance. Operational decisions are always rebuilt.
    for old in [ROOT/'outputs/longitudinal_assessment/v1/volumes'/sid,V1/'volumes'/sid]:
        if not (old/'complete.json').exists() or not (old/'neural_complete.json').exists():continue
        try:
            nm=read(old/'neural_complete.json');cm=read(old/'complete.json');og=npz(old/'geometry.npz')
            assert nm['source']==p['source'];verify(nm['source']);verify(cm['measurements'])
            assert nm['position_checkpoint']==manifest()['checkpoints'][0] and nm['state_checkpoint']==manifest()['checkpoints'][1]
            for key in ['native_shape','retina_band','label_offset','vitreous_high','vessel','shadow','cnv']:
                np.testing.assert_equal(og[key],g[key])
            np.testing.assert_equal(np.load(old/'images.npy',mmap_mode='r'),np.load(o/'images.npy',mmap_mode='r'))
            od=npz(old/'measurements.npz');assert od['raw_position_branch'].shape==(512,8,512)
            for b in range(512):save(o/'neural'/f'b{b:04d}.npz',rows=od['raw_position_branch'][b],probabilities=od['probabilities'][b],entropy=od['entropy'][b])
            nm.update(reused=True,reused_from=str(old),reused_measurements=fingerprint(old/'measurements.npz'),reuse_checks='source fingerprint, native grid, crop, orientation, all images, vessel/shadow/CNV masks, full checkpoint fingerprints; decisions rebuilt')
            write(o/'neural_complete.json',nm);print('Verified raw neural reuse',sid,str(old),flush=True);return
        except (AssertionError,KeyError,RuntimeError,ValueError) as exc:
            print('Reuse declined',str(old),str(exc)[:250],flush=True)
    net,_=load_position(V1/'models/ALL_LABELLED/position.pt');states=state_model('ALL_LABELLED')
    with ProcessedVolume(p['source']['path']) as v:full=v.read_volume()
    high=bool(detect_orientation(full.mean(axis=(0,1))));assert high==bool(g['vitreous_high'])
    imgs=np.load(o/'images.npy',mmap_mode='r');offset=int(g['label_offset'])
    for b in range(len(full)):
        dest=o/'neural'/f'b{b:04d}.npz'
        if not dest.exists():
            result,db=one(net,states,full[b],high,g['vessel'][b]);np.testing.assert_equal(db[offset:offset+imgs.shape[1]],imgs[b]);save(dest,**result)
        else:
            d=npz(dest);assert d['rows'].shape==(8,512) and d['probabilities'].shape==(8,2,512)
        if b%64==0:print('Frozen v1 inference',sid,b+1,'/512',flush=True)
    m=manifest();write(o/'neural_complete.json',dict(scan_id=sid,source=p['source'],n_bscans=len(full),orientation_detected=high,label_offset=offset,axis_order='B-scan,boundary,A-line; full canonical depth; vitreous 0',position_checkpoint=m['checkpoints'][0],state_checkpoint=m['checkpoints'][1],reused=False))

def export(sid):
    from octa_seg_v1.decisions import decide,alignment,estimate_context,thickness
    from octa_seg_v1.export import live_decisions
    from eight_surface.config import SURFACE_NAMES,LAYER_DEFS,CASCADE_VERSION
    o=directory(sid);p=read(o/'prepared.json');g=npz(o/'geometry.npz')
    if (o/'complete.json').exists():verify(read(o/'complete.json')['measurements']);return
    preds=[npz(o/'neural'/f'b{b:04d}.npz') for b in range(512)]
    rows=np.stack([p['rows'] for p in preds]);prob=np.stack([p['probabilities'] for p in preds]);entropy=np.stack([p['entropy'] for p in preds]);del preds
    guards,provenance=live_decisions(read(V1/'data/manifest.json'),sid,g)
    cal=read(V1/'calibration/deployment_vessels.json')['thresholds']
    ds=[decide(rows[b],prob[b],cal,g['vessel'][b],**guards.get(b,{})) for b in range(512)]
    rep,state,reason=[np.stack([a[k] for a in ds]) for k in range(3)]
    imgs=np.load(o/'images.npy',mmap_mode='r')
    if (o/'alignment.npz').exists():a=npz(o/'alignment.npz');shifts,scores=a['shifts'],a['scores']
    else:shifts,scores=alignment(imgs);save(o/'alignment.npz',shifts=shifts,scores=scores)
    est,cr,items=estimate_context(rows,rep,state,reason,imgs,shifts,scores,offset=int(g['label_offset']))
    d=dict(reported_positions=rep,uncertain_estimates=est,state=state,reason=reason,context_reason=cr,probabilities=prob,entropy=entropy,raw_position_branch=rows,primary_thickness_um=thickness(rep,g['shadow']),shadow=g['shadow'],vessel=g['vessel'],cnv=g['cnv'],label_offset=g['label_offset'],surface_names=np.array(SURFACE_NAMES),validated=np.array(False),model_version=np.array('octa-seg_v1'),thickness_names=np.array([x[0] for x in LAYER_DEFS]+['INNER_RETINA']))
    save(o/'measurements.npz',**d)
    provider=dict(d,surfaces=rep-int(g['label_offset']),uncertain_estimates=est-int(g['label_offset']),confidence=np.full_like(rep,np.nan),scan_id=np.array([sid]),cascade_version=np.array([CASCADE_VERSION]),source=np.array([p['source']['path']]),retina_band=g['retina_band'],bscan_index=np.arange(512),px_um=np.array([1.12]))
    save(OUT/'review_packs'/f'{sid}.npz',**provider)
    write(o/'human_overrides_provenance.json',provenance);write(o/'context_records.json',items)
    write(o/'complete.json',dict(scan_id=sid,n_bscans=512,measurements=fingerprint(o/'measurements.npz'),meaning='segmentation export complete; batch completion additionally requires QC marker'))

def engine():
    sys.path.insert(0,str(ROOT/'outputs/octa-thick_v1'));import engine as e
    e.HERE=OUT/'thick';return e

def locked_stage(action,sid):
    import msvcrt
    write(OUT/'runtime'/f'{sid}.json',dict(scan_id=sid,stage=action,worker_pid=os.getpid(),runner_pid=os.getppid(),started=time.time()))
    lock=OUT/'locks'/f'{sid}.lock';lock.parent.mkdir(exist_ok=True)
    with lock.open('a+b') as f:
        if f.tell()==0:f.write(b'0');f.flush()
        while True:
            try:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:time.sleep(.5)
        try:
            check_dependencies()
            if action=='qc':
                from qc import run;run(sid)
            elif action=='infer':
                with (OUT/'locks/gpu.lock').open('a+b') as gpu:
                    if gpu.tell()==0:gpu.write(b'0');gpu.flush()
                    while True:
                        try:gpu.seek(0);msvcrt.locking(gpu.fileno(),msvcrt.LK_NBLCK,1);break
                        except OSError:time.sleep(.5)
                    try:infer(sid)
                    finally:gpu.seek(0);msvcrt.locking(gpu.fileno(),msvcrt.LK_UNLCK,1)
            else:globals()[action](sid)
        finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

def run(only=None):
    if not (OUT/'manifest.json').exists():init()
    check_dependencies();m=manifest();logs=OUT/'logs';logs.mkdir(exist_ok=True)
    write(OUT/'runner.json',dict(pid=os.getpid(),started=time.time()))
    for i,r in enumerate(m['scans']):
        sid=r['scan_id']
        if only and sid!=only:continue
        for action in ('prepare','infer','export','qc'):
            write(OUT/'status.json',dict(status='running',number=i+1,total=len(m['scans']),scan=sid,stage=action))
            print(f'[{i+1}/{len(m["scans"])}] {action} {sid}',flush=True)
            with (logs/f'{sid}_{action}.log').open('a',encoding='utf-8') as log:
                result=subprocess.run([sys.executable,'-u',str(Path(__file__)),action,'--scan',sid],stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:
                write(OUT/'failures'/f'{sid}.json',dict(scan_id=sid,stage=action,exit_code=result.returncode,log=str(logs/f'{sid}_{action}.log'),investigated=False));break
        else:
            (OUT/'failures'/f'{sid}.json').unlink(missing_ok=True)
        from qc import aggregate;aggregate()
    from qc import aggregate;aggregate()
    from ratings import compare;compare()

def launch():
    e=engine();import viewer
    viewer.HERE=OUT/'thick';viewer.Volume=e.Volume
    def correction(self):subprocess.Popen([sys.executable,str(Path(__file__)),'review','--scan',self.volume.scan_id],cwd=ROOT)
    viewer.Window.correction=correction
    sys.argv=[sys.argv[0],'--list',str(OUT/'thick/volumes.json'),'--correction-config',str(OUT/'launch_config.json')]
    return viewer.main()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['init','run','prepare','infer','export','qc','aggregate','thick','review']);ap.add_argument('--scan');a=ap.parse_args()
    if a.action=='init':init()
    elif a.action=='run':run(a.scan)
    elif a.action=='aggregate':
        from qc import aggregate;aggregate()
        from ratings import compare;compare()
    elif a.action=='thick':launch()
    elif a.action=='review':
        from cnv_review_v1.main import main
        sys.argv=[sys.argv[0],'--config',str(OUT/'launch_config.json')]+(['--scan',a.scan] if a.scan else []);main()
    else:locked_stage(a.action,a.scan)
