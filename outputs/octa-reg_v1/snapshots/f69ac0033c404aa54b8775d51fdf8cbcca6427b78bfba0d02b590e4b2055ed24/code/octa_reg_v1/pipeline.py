"""One writer, up to two compute threads, atomic scan/pair resume products."""
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from collections import Counter
from pathlib import Path
import json
import os
import platform
import time
import traceback
import numpy as np
import scipy
import skimage
from . import CONFIG, VERSION
from .io import read,write,save,sha,digest,input_rows,load_scan
from .geometry import features,register,fit_onh,branches,convergence,build_components

def code_hashes():
    folder=Path(__file__).parent
    paths=list(folder.glob('*.py'))+list(folder.glob('*.html'))+[folder.parent/'control_map_v1/geometry.py',folder.parent/'control_map_v1/__init__.py']
    return {str(p):sha(p) for p in sorted(paths)}

def snapshot(out,inventory,export,cfg):
    manifest=read(export/'manifest.json');verified=read(export/'VERIFIED.json')
    checked=sha(export/'manifest.json')
    if verified['manifest_sha256']!=checked:raise ValueError('Export manifest differs from VERIFIED snapshot')
    records={r['scan_id']:r for r in manifest['records']}
    if len(records)!=len(manifest['records']):raise ValueError('Duplicate export scan ID')
    pin=dict(version=VERSION,inventory_path=str(inventory),inventory_sha256=sha(inventory),
             vessel_export=str(export),vessel_manifest_sha256=checked,verified_sha256=sha(export/'VERIFIED.json'),
             config=cfg,code_hashes=code_hashes(),cnv_snapshot=None,
             environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,skimage=skimage.__version__))
    pin['signature']=digest(pin)
    folder=out/'snapshots'/pin['signature'];folder.mkdir(parents=True,exist_ok=True)
    write(folder/'manifest.json',pin);write(folder/'vessel_manifest.json',manifest);write(folder/'VERIFIED.json',verified)
    write(folder/'source_inventory.json',read(inventory))
    for p,h in pin['code_hashes'].items():
        src=Path(p);target=folder/'code'/src.parent.name/src.name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(src.read_bytes())
    write(out/'manifest.json',pin);write(out/'config.json',cfg)
    return pin,records

def prepare(row,inventory,records,export,cfg,pin):
    start=time.monotonic()
    arrays,info=load_scan(row,inventory,records,export)
    info['signature']=digest([pin['signature'],info['input_hashes']])
    feat=features(arrays['enface'],arrays['vessel'],arrays['registration_blocked'],arrays['spacing'])
    arrays.update({'feature_'+k:v for k,v in feat.items()})
    br,junction=branches(arrays['vessel']&~arrays['registration_blocked'],arrays['spacing'],cfg)
    arrays['junction_mask']=junction
    info['branches']=br;info['convergence']=convergence(br,cfg)
    if info['onh_available']:
        mask=arrays['selected_onh_mask'] & ~arrays.get('selected_onh_region_excluded',np.zeros_like(arrays['vessel']))
        edge=arrays.get('selected_onh_edge_mask',np.zeros_like(mask)).copy()
        edge &= ~arrays.get('selected_onh_region_excluded',np.zeros_like(mask))
        info['visible_onh']=fit_onh(mask,edge,arrays['spacing'],cfg)
        info['visible_onh']['evidence_status']='reviewed_assessable' if info['onh_assessable'] else 'unreviewed_or_unassessable_proposal'
    else:info['visible_onh']=dict(resolved=False,reason='ONH unavailable')
    info.update(status='excluded' if info['excluded_from_analysis'] else 'prepared',
                feature_count=len(feat['points']),junction_count=len(feat['branches']),
                vessel_pixels=int(arrays['vessel'].sum()),blocked_fraction=float(arrays['registration_blocked'].mean()),
                preparation_seconds=time.monotonic()-start)
    return info,arrays

def pair_signature(a,b,pin):
    return digest([pin['signature'],a['signature'],b['signature']])

def match_pair(a,b,arrays,cfg,pin):
    t=time.monotonic();sa,sb=a['scan_id'],b['scan_id']
    result=dict(pair_id=sa+'__'+sb,scan_a=sa,scan_b=sb,direction='native physical A -> native physical B',
        signature=pair_signature(a,b,pin),interval='within_session' if a['session_date']==b['session_date'] else 'across_date',
        mask_source_pair='fallback_involved' if 'legacy_geometry_fallback' in (a.get('mask_source'),b.get('mask_source')) else 'primary_only',
        review_pair='both_reviewed' if a.get('vessel_reviewed') and b.get('vessel_reviewed') else 'mixed' if a.get('vessel_reviewed') or b.get('vessel_reviewed') else 'neither_reviewed',
        feature_counts=[a.get('feature_count'),b.get('feature_count')],matrix=None,matches=0,inliers=0,
        residual_um=None,overlap_fraction=None,vessel_dice=None,structural_correlation=None,
        branch_matches=0,branch_residual_um=None,cycle_error_um=None)
    bad=[s for s in (a,b) if s['status']!='prepared']
    if bad:
        result.update(status='blocked',reason='; '.join(s['scan_id']+': '+s.get('error',s.get('exclusion_reason') or s['status']) for s in bad))
    else:
        try:
            aa,bb=arrays[sa],arrays[sb]
            fa={k:aa['feature_'+k] for k in ('points','descriptors','branches')}
            fb={k:bb['feature_'+k] for k in ('points','descriptors','branches')}
            # Reuse exactly the pure inherited matcher. Its "verified" means internal gates only.
            res=register(aa,bb,fa,fb,cfg);passed=res.pop('verified')
            result.update(res,status='automatic_proposal' if passed else 'rejected')
            reasons=[]
            if not passed:
                for metric,threshold in [('overlap_fraction','registration_min_overlap'),('vessel_dice','registration_min_vessel_dice'),
                                         ('structural_correlation','registration_min_structural_correlation'),('branch_matches','registration_min_branch_matches')]:
                    if result[metric] is not None and result[metric]<cfg[threshold]:reasons.append(metric)
                if result['matrix'] is None: reasons=['insufficient_vessel_anchored_inliers']
            result['rejection_gates']=reasons
            # Diagnostic correspondences retained even when RANSAC fails; no alternate matching method.
            from skimage.feature import match_descriptors
            if min(len(fa['points']),len(fb['points']))>=cfg['registration_min_matches']:
                mm=match_descriptors(fa['descriptors'],fb['descriptors'],cross_check=True,max_ratio=.75)
                result['matches']=len(mm)
                pa,pb=fa['points'][mm[:,0]],fb['points'][mm[:,1]]
                result['correspondences_a_um']=pa.tolist();result['correspondences_b_um']=pb.tolist()
                if result['matrix'] is not None:
                    from .geometry import apply
                    result['correspondence_residuals_um']=np.linalg.norm(apply(pa,np.asarray(result['matrix']))-pb,axis=1).tolist()
        except Exception as e:
            result.update(status='implementation_failure',reason=type(e).__name__+': '+str(e),traceback=traceback.format_exc())
    result['runtime_seconds']=time.monotonic()-t
    return result

def inventory_only(out,inventory,export,cfg):
    pin,records=snapshot(out,inventory,export,cfg);rows=input_rows(inventory);results=[]
    for row in rows:
        try:
            _,info=load_scan(row,inventory,records,export);info['status']='excluded' if info['excluded_from_analysis'] else 'available'
        except Exception as e:info=dict(row,status='blocked',error=type(e).__name__+': '+str(e))
        results.append(info)
    write(out/'inventory.json',results)
    return results

def run(out,inventory,export,cfg,eye=None):
    start=time.monotonic();out.mkdir(parents=True,exist_ok=True)
    # OS byte lock is released on process exit, including crashes; no stale PID assumptions.
    import msvcrt
    lock=(out/'writer.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:lock.close();raise RuntimeError('Another writer owns this output directory')
    try:
        pin,records=snapshot(out,inventory,export,cfg);rows=input_rows(inventory)
        if eye:rows=[r for r in rows if r['animal']+'_'+r['eye']==eye]
        if not rows:raise ValueError('No acquisitions selected')
        infos={};allpairs=[];reused=0
        def status(stage,**kw):
            write(out/'status.json',dict(status='running',stage=stage,elapsed_seconds=time.monotonic()-start,
                  acquisitions=len(rows),prepared=len(infos),pairs_completed=len(allpairs),signature=pin['signature'],**kw))
        status('preparation')
        # Scan preparation is deliberately recomputed; only pair matching artifacts resume.
        with ThreadPoolExecutor(max_workers=cfg['workers']) as pool:
            def safe_prepare(row):
                try:return prepare(row,inventory,records,export,cfg,pin)
                except Exception as e:
                    rec=records.get(row['scan_id'],{})
                    return dict(row,status='blocked',error=type(e).__name__+': '+str(e),traceback=traceback.format_exc(),
                        excluded_from_analysis=rec.get('excluded_from_analysis',False),exclusion_reason=rec.get('exclusion_reason',''),
                        signature=digest([pin['signature'],row,str(e)])),None
            for info,arr in pool.map(safe_prepare,rows):
                sid=info['scan_id'];infos[sid]=info
                if arr is not None:save(out/'prepared'/(sid+'.npz'),**arr);info['prepared_sha256']=sha(out/'prepared'/(sid+'.npz'))
                write(out/'prepared'/(sid+'.json'),info)
                if len(infos)%10==0:status('preparation');print('Prepared',len(infos),'/',len(rows),flush=True)
        write(out/'inventory.json',list(infos.values()))
        candidates=[]
        for group in sorted({(r['animal'],r['eye']) for r in rows}):
            ids=sorted(s for s,i in infos.items() if (i['animal'],i['eye'])==group)
            candidates.extend(combinations(ids,2))
        candidates.sort(key=lambda ab:(infos[ab[0]]['session_date']!=infos[ab[1]]['session_date'],ab))
        write(out/'candidate_pairs.json',[dict(scan_a=a,scan_b=b) for a,b in candidates])
        # Arrays are compact; all 324 scans are ~1 GB. A small LRU loads just worker needs.
        from functools import lru_cache
        @lru_cache(maxsize=8)
        def get_arrays(sid):
            with np.load(out/'prepared'/(sid+'.npz'),allow_pickle=False) as z:
                return {k:z[k] for k in ('enface','vessel','registration_blocked','spacing','feature_points','feature_descriptors','feature_branches')}
        def compute(ab):
            a,b=ab;ip=out/'pairs'/(a+'__'+b+'.json');sig=pair_signature(infos[a],infos[b],pin)
            if ip.exists():
                try:
                    old=read(ip)
                    check=old.pop('artifact_digest',None)
                    if old['signature']==sig and old['status']!='implementation_failure' and check==digest(old):
                        old['artifact_digest']=check
                        return old,True
                except (ValueError,KeyError):pass
            try:
                arrays={s:get_arrays(s) for s in ab if infos[s]['status']=='prepared'}
                return match_pair(infos[a],infos[b],arrays,cfg,pin),False
            except Exception as e:
                return dict(pair_id=a+'__'+b,scan_a=a,scan_b=b,status='implementation_failure',reason=str(e),signature=sig,traceback=traceback.format_exc()),False
        with ThreadPoolExecutor(max_workers=cfg['workers']) as pool:
            for res,resumed in pool.map(compute,candidates):
                if not resumed:
                    res['artifact_digest']=digest(res)
                    write(out/'pairs'/(res['pair_id']+'.json'),res)
                reused+=resumed;allpairs.append(res)
                if len(allpairs)%25==0:status('matching',candidate_pairs=len(candidates),pairs_resumed=reused);print('Pairs',len(allpairs),'/',len(candidates),Counter(p['status'] for p in allpairs),flush=True)
        components,transforms=build_components(infos,allpairs,cfg)
        write(out/'components.json',components);write(out/'transforms.json',transforms);write(out/'pairs.json',allpairs)
        status('report',candidate_pairs=len(candidates),pairs_resumed=reused)
        from .report import report
        report(out)
        # Verify every file consumed is unchanged at completion, including selected sources.
        sources={str(inventory):pin['inventory_sha256'],str(export/'manifest.json'):pin['vessel_manifest_sha256'],str(export/'VERIFIED.json'):pin['verified_sha256']}
        for i in infos.values():sources.update(i.get('input_hashes',{}))
        changed=[p for p,h in sources.items() if not Path(p).exists() or sha(p)!=h]
        counts=Counter(p['status'] for p in allpairs)
        final='failed' if changed or counts['implementation_failure'] else 'complete-with-blocked-inputs' if any(i['status']=='blocked' for i in infos.values()) else 'complete'
        write(out/'source_integrity.json',dict(files_checked=len(sources),changed=changed,unchanged=not changed,hashes=sources))
        write(out/'status.json',dict(status=final,elapsed_seconds=time.monotonic()-start,acquisitions=len(rows),candidate_pairs=len(candidates),
            pair_counts=dict(counts),pairs_resumed=reused,signature=pin['signature'],source_files_unchanged=not changed))
        report(out,assets=False)
        print(json.dumps(read(out/'status.json')),flush=True)
    except BaseException as e:
        write(out/'status.json',dict(status='failed',error=str(e),traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-start));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
