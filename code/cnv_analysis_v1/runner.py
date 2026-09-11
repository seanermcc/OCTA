"""Resumable analysis stages; annotations, models and upstream outputs are read-only."""
from pathlib import Path
import argparse
import importlib.util
import json
import sys
import time
import numpy as np
from . import VERSION
from .common import (ROOT,LAYERS,POLICY,ORIENTATION,read,write,sha,fingerprint,digest,
                     csvwrite,npz,save,default_config,validate_config,gate,day_info,provisional_sector)
from . import annotations as A
from .geometry import Footprint,grid,regions,transform,rigid,recover_outline,sample_mask
from .registration import propose,fit_onh,branch_convergence,vessel_onh_proposal,match_lesions,warp_image,normalized

class Runner:
    def __init__(self,config):
        self.c=config; self.out=validate_config(config); self.out.mkdir(parents=True,exist_ok=True)
        self.batch=Path(config['batch']); self.records=read(self.batch/'manifest.json')['scans']
        self.byid={r['scan_id']:r for r in self.records}
        if len(self.byid)!=len(self.records): raise ValueError('Duplicate scan IDs')
        sources=[str(Path(r['source']).resolve()).casefold() for r in self.records]
        if len(sources)!=len(set(sources)): raise ValueError('Duplicate acquisition source')
        self.code_revision=digest({p.name:sha(p) for p in Path(__file__).parent.glob('*.py') if not p.name.startswith('test_')})
        config_path=self.out/'config.json'
        if config_path.exists() and read(config_path)!=config and (self.out/'frozen_inputs.json').exists():
            raise ValueError('Frozen release configuration changed; preserve release and use a new analysis copy')
        write(config_path,config)

    def status(self,stage,**extra):
        write(self.out/'status.json',dict(stage=stage,updated=time.strftime('%Y-%m-%dT%H:%M:%S'),**extra))

    def invalidate_completion(self,stage):
        p=self.out/'ANALYSIS_COMPLETE.json'
        if p.exists(): write(p,dict(passed=False,reason='Stage rerun requires fresh completion verification',stage=stage))

    def inventory(self):
        rows=[]; refs=[]; details={}
        for r in self.records:
            sid=r['scan_id']; a=A.load(self.c,r); info=day_info(r)
            row=dict(scan_id=sid,animal=r['animal'],eye=r['eye'],session_date=r['session_date'],
                     **info,source=r['source'],native_shape=r['native_shape'][:2],
                     lesion_count=len(a['lesions']),annotation_reviewed=a['reviewed'],
                     annotation_source=self.c['annotation_source'],annotation_revision=digest(a['refs']),
                     volume_ready=(self.batch/'volumes'/sid/'qc_complete.json').exists(),
                     prelaser_cnv_review=bool(info['prelaser'] and a['lesions']),
                     spacing_um_yx=a['spacing'].tolist())
            rows.append(row); refs.extend(a['refs'])
            details[sid]=[dict(lesion_id=i,mask_source=s,pixels=int(m.sum()),
                              diameter_incomplete=not Footprint(m,a['spacing']).complete) for i,m,s in a['lesions']]
        cohort={(r['animal'],r['eye']) for r in rows if r['lesion_count']}
        for row in rows: row['analysis_eye']=(row['animal'],row['eye']) in cohort
        data=dict(scans=rows,annotations=refs,lesions=details,source= fingerprint(self.batch/'manifest.json'),
                  upstream_gate_present=Path(self.c['gate']).exists(),experimental=True,
                  coverage=dict(scans=len(rows),scans_with_masks=sum(r['lesion_count']>0 for r in rows),
                    lesions=sum(r['lesion_count'] for r in rows),animals=sorted({r['animal'] for r in rows if r['lesion_count']})))
        prior=self.out/'inventory.json'
        if (self.out/'frozen_inputs.json').exists() and prior.exists() and read(prior)!=data:
            raise RuntimeError('Frozen inventory or annotations changed; release is preserved')
        write(prior,data); csvwrite(self.out/'tables/inventory.csv',rows)
        write(self.out/'provenance/annotations.json',refs)
        self.status('inventory',**data['coverage'],measurement_gate='user-authorized batch audit override' if self.c.get('batch_audit_override') else 'passed' if Path(self.c['gate']).exists() else 'waiting for FINAL_VERIFIED.json')
        return data

    def inventory_data(self):
        p=self.out/'inventory.json'
        return read(p) if p.exists() else self.inventory()

    def annotation(self,sid):
        a=A.load(self.c,self.byid[sid]); inv=self.inventory_data()
        old=next(r for r in inv['scans'] if r['scan_id']==sid)
        if digest(a['refs'])!=old['annotation_revision']:
            raise RuntimeError('Annotation revision changed; run inventory before freezing: '+sid)
        return a

    def image(self,sid):
        p=self.out/'registration/images'/f'{sid}.npz'; vol=self.batch/'volumes'/sid
        source=vol/'prepared.json'; masks=vol/'qc_masks.npz'
        rev=digest([sha(source),self.code_revision,sha(masks) if masks.exists() else None])
        if p.exists():
            d=npz(p)
            if str(d['revision'].item())==rev: return d['image'],d['artifact']
        images=np.load(vol/'images.npy',mmap_mode='r')
        enface=np.mean(images,axis=1); del images
        g=npz(vol/'geometry.npz'); artifact=np.zeros_like(g['shadow'])|g.get('low_signal',False)
        if masks.exists(): artifact|=npz(masks)['excluded']
        # Vessel shadows are missing thickness evidence, but their structural
        # en-face contrast is useful for image registration. Explicit exclusions
        # and low-signal tissue are masked here; thickness keeps all shadow NaNs.
        save(p,image=enface,artifact=artifact,revision=np.array(rev))
        return enface,artifact

    def register(self):
        self.invalidate_completion('register')
        inv=self.inventory_data(); rows=[r for r in inv['scans'] if r['analysis_eye'] and r['volume_ready']]
        edits_path=self.out/'alignment_edits.json'; edits=read(edits_path) if edits_path.exists() else {}
        results={}; identities=[]
        groups=sorted({(r['animal'],r['eye']) for r in rows})
        for animal,eye in groups:
            scans=sorted([r for r in rows if (r['animal'],r['eye'])==(animal,eye)],key=lambda r:(r['session_date'],r['scan_id']))
            # An annotated post-D0 scan anchors each eye; D0 is not presumed prelaser.
            ref=next((r for r in scans if r['lesion_count'] and r['post_d0']),next((r for r in scans if r['lesion_count']),scans[0]))
            refid=ref['scan_id']; fixed,bad_f=self.image(refid); ar=self.annotation(refid)
            for n,r in enumerate(scans):
                sid=r['scan_id']; a=self.annotation(sid); moving,bad_m=self.image(sid)
                revision=digest([self.code_revision,r['annotation_revision'],ref['annotation_revision'],
                    sha(self.batch/'volumes'/sid/'prepared.json'),sha(self.batch/'volumes'/refid/'prepared.json'),self.c['registration']])
                dest=self.out/'registration/records'/f'{sid}.json'
                if dest.exists() and read(dest).get('input_revision')==revision:
                    rec=read(dest)['proposal']
                elif sid==refid:
                    rec=dict(state='reference',matrix=np.eye(3).tolist(),uncertainty_um=0.,method='identity reference',diagnostics={})
                else:
                    rec=propose(moving,fixed,a['spacing'],ar['spacing'],
                                bad_m|a['union']|a['onh'],bad_f|ar['union']|ar['onh'],self.c['registration'])
                proposal=rec.copy(); edit=edits.get(sid)
                if edit:
                    if edit.get('input_revision')!=revision or edit.get('reference_scan')!=refid:
                        raise ValueError('Stale alignment edit: '+sid)
                    if edit.get('state') not in ('verified','rejected'): raise ValueError('Edit state must be verified or rejected')
                    if not edit.get('reviewer') or not edit.get('evidence'): raise ValueError('Alignment review requires reviewer and evidence')
                    matrix=rigid(edit.get('matrix',rec['matrix']))
                    uncertainty=float(edit['uncertainty_um'])
                    if not np.isfinite(uncertainty) or uncertainty<0: raise ValueError('Invalid localization uncertainty')
                    rec=dict(rec,state=edit['state'],matrix=matrix.tolist(),uncertainty_um=uncertainty,method='reviewed alignment')
                onh=fit_onh(a['onh'],a['onh_edge'],a['spacing'])
                if onh['state']=='unavailable':
                    vessel=a['vessel']
                    if not vessel.any(): vessel=npz(self.batch/'volumes'/sid/'geometry.npz')['vessel']
                    onh=vessel_onh_proposal(vessel & ~a['union'] & ~bad_m,a['spacing'])
                if edit and edit.get('vessel_branches_um') and onh['state']=='unavailable':
                    onh=branch_convergence(edit['vessel_branches_um'])
                if edit and edit.get('onh_verified') and onh['state']=='proposed': onh['state']='localized'
                results[sid]=dict(scan_id=sid,animal=animal,eye=eye,reference_scan=refid,input_revision=revision,
                    proposal=proposal,alignment=rec,onh=onh,edit=edit,spacing_um_yx=a['spacing'].tolist())
                write(dest,results[sid])
                if sid!=refid:
                    self.registration_overlay(sid,refid,moving,fixed,a['spacing'],ar['spacing'],rec)
                print(f'Registration {animal} {eye} {n+1}/{len(scans)}: {sid} {rec["state"]}',flush=True)
                self.status('register',scan_id=sid,state=rec['state'])
        # Propagate only verified ONH coordinates, preserving each source uncertainty.
        for sid,r in results.items():
            if r['alignment']['state'] not in ('reference','verified') or r['onh']['state']=='localized': continue
            candidates=[]
            for q in results.values():
                if q['reference_scan']!=r['reference_scan'] or q['alignment']['state'] not in ('reference','verified') or q['onh']['state']!='localized': continue
                if q['onh']['method']=='transferred verified ONH': continue
                m=np.linalg.inv(np.array(r['alignment']['matrix']))@np.array(q['alignment']['matrix'])
                center=transform(np.array(q['onh']['center_um']),m)
                u=float(np.hypot(q['onh']['uncertainty_um'],np.hypot(q['alignment']['uncertainty_um'],r['alignment']['uncertainty_um'])))
                candidates.append((u,center,q['scan_id']))
            if candidates:
                u,center,source=min(candidates,key=lambda x:x[0])
                disagreement=max(np.linalg.norm(center-v[1]) for v in candidates)
                if disagreement<=max(100,3*u):
                    r['onh']=dict(state='localized',center_um=center.tolist(),uncertainty_um=u,
                                  method='transferred verified ONH',source_scan=source,disagreement_um=float(disagreement),
                                  radius_um=results[source]['onh'].get('radius_um'))
        identities=self.tracks(results,inv)
        write(self.out/'registration/registrations.json',results)
        write(self.out/'registration/identities.json',identities)
        write(self.out/'registration/review_inputs.json',{name:fingerprint(self.out/name) if (self.out/name).exists() else None
            for name in ('alignment_edits.json','identity_edits.json')})
        csvwrite(self.out/'tables/lesion_identities.csv',identities)
        template={sid:dict(input_revision=r['input_revision'],reference_scan=r['reference_scan'],
            matrix=r['proposal']['matrix'],state='verified',uncertainty_um=r['proposal']['uncertainty_um'],
            reviewer='',evidence='') for sid,r in results.items() if r['proposal']['state']=='proposed'}
        write(self.out/'alignment_edits.example.json',template)
        self.status('register',scans=len(results),verified=sum(r['alignment']['state'] in ('verified','reference') for r in results.values()),
                    needs_review=sum(r['alignment']['state']=='proposed' for r in results.values()))
        return results

    def registration_overlay(self,sid,refid,moving,fixed,sm,sf,rec):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        p=self.out/'registration/overlays'/f'{sid}.png'; p.parent.mkdir(parents=True,exist_ok=True)
        if rec.get('matrix') is None:
            fig,axes=plt.subplots(1,2,figsize=(11,6))
            for ax,img,title in zip(axes,[fixed,moving],[refid,sid]):
                ax.imshow(normalized(img),cmap='gray'); ax.set_axis_off(); ax.set_title(title,fontsize=8)
            fig.suptitle('Registration unavailable — side-by-side native fields\n'+rec.get('reason',''),fontsize=11)
            fig.tight_layout(rect=(0,0,1,.9)); fig.savefig(p,dpi=110,bbox_inches='tight'); plt.close(fig)
            return
        warped=warp_image(normalized(moving),sm,fixed.shape,sf,np.array(rec['matrix']))
        base=normalized(fixed); rgb=np.stack((base,np.nan_to_num(warped),base),axis=-1)
        fig,ax=plt.subplots(figsize=(8,8)); ax.imshow(rgb); ax.set_axis_off()
        ax.set_title(f'{sid}\nonto {refid}\n{rec["state"]}; magenta reference, green moving',fontsize=10)
        fig.savefig(p,dpi=110,bbox_inches='tight'); plt.close(fig)

    def tracks(self,results,inv):
        identities=[]; invrows={r['scan_id']:r for r in inv['scans']}
        for reference in sorted({r['reference_scan'] for r in results.values()}):
            scans=sorted([r for r in results.values() if r['reference_scan']==reference],key=lambda r:(not invrows[r['scan_id']]['post_d0'],invrows[r['scan_id']]['session_date'],r['scan_id']))
            tracks=[]; track_ids=[]
            for r in scans:
                sid=r['scan_id']; a=self.annotation(sid); align=r['alignment']
                verified=align['state'] in ('reference','verified')
                matrix=np.array(align['matrix']) if align.get('matrix') else np.eye(3)
                footprints=[Footprint(m,a['spacing'],matrix) for _,m,_ in a['lesions']]
                matches=match_lesions(footprints,tracks) if align.get('matrix') else []
                for i,(lid,mask,source) in enumerate(a['lesions']):
                    match=matches[i] if matches else dict(state='unregistered',target=None,iou=0.)
                    # Only the reference establishes initial unique identities.
                    # A later unmatched footprint is not silently declared a new
                    # lesion; new identity requires explicit review.
                    proposed_track=track_ids[match['target']] if match.get('target') is not None else ''
                    if sid==reference and match['state']=='unmatched':
                        tid=f'{reference}:L{len(tracks)+1:03d}'; tracks.append(footprints[i]); track_ids.append(tid)
                        state='tracked_new'
                    elif verified and match['state']=='matched': tid=track_ids[match['target']]; state='tracked_match'
                    else: tid=''; state=('proposed_match' if match['state']=='matched' else match['state'])
                    identities.append(dict(scan_id=sid,lesion_id=lid,track_id=tid,state=state,
                        identity_eligible=bool(tid),iou=match['iou'],mask_source=source,
                        proposed_track_id=proposed_track,animal=r['animal'],eye=r['eye'],visit_id=invrows[sid]['visit_id']))
        edits_path=self.out/'identity_edits.json'
        if edits_path.exists():
            edits=read(edits_path)
            expected=digest(results)
            if edits.get('registration_revision')!=expected: raise ValueError('Stale identity edits')
            mapping={(r['scan_id'],r['lesion_id']):r for r in identities}
            for e in edits.get('identities',[]):
                r=mapping[(e['scan_id'],e['lesion_id'])]
                if not e.get('reviewer') or not e.get('evidence'): raise ValueError('Identity correction needs review provenance')
                if e.get('track_id'):
                    if results[r['scan_id']]['alignment']['state'] not in ('reference','verified'): raise ValueError('Cannot track without verified registration')
                    known=[v for v in identities if v['track_id']==e['track_id']]
                    if not known:
                        prefix=results[r['scan_id']]['reference_scan']+':'
                        if not e.get('new_track') or not e['track_id'].startswith(prefix): raise ValueError('New track requires explicit new_track and same-eye reference prefix')
                    elif any((v['animal'],v['eye'])!=(r['animal'],r['eye']) for v in known): raise ValueError('Invalid cross-eye track')
                r.update(track_id=e.get('track_id',''),state=e['state'],identity_eligible=bool(e.get('track_id')),reviewer=e['reviewer'],evidence=e['evidence'])
        seen=set()
        for r in identities:
            if not r['identity_eligible']: continue
            key=(r['scan_id'],r['track_id'])
            if key in seen: raise ValueError('Two same-scan lesions assigned to one track; flag split/merge')
            seen.add(key)
        return identities

    def freeze(self):
        proof=gate(self.c); inv=self.inventory_data()
        if not all(r['volume_ready'] for r in inv['scans']):
            raise RuntimeError('Inventory predates the completed batch; rerun inventory and register before measure')
        for fp in inv['annotations']:
            if sha(fp['path'])!=fp['sha256']: raise RuntimeError('Annotation changed since inventory')
        path=self.out/'frozen_inputs.json'
        if path.exists():
            d=read(path)
            if d['inventory_sha256']!=sha(self.out/'inventory.json'): raise RuntimeError('Frozen inventory changed')
            return d
        settings={k:self.c[k] for k in ('policy','field_um_yx','absolute_edges_um','normalized_edges','bootstrap_samples','random_seed','complete_band_fraction','registration')}
        if self.c['release']=='v2':
            reference=read(Path(self.c['thickness_reference'])/'frozen_inputs.json')
            if settings!=reference['analysis_settings']: raise RuntimeError('v2 must use frozen v1 analysis settings')
        d=dict(version=VERSION,code_revision=self.code_revision,inventory_sha256=sha(self.out/'inventory.json'),
               upstream_gate=proof,analysis_settings=settings,experimental=True,scans={})
        write(path,d); return d

    def thickness(self,sid,frozen):
        p=self.out/'thickness'/f'{sid}.npz'; meta=p.with_suffix('.json')
        if sid in frozen['scans']:
            fp=frozen['scans'][sid]
            if sha(p)!=fp['sha256']: raise RuntimeError('Frozen thickness artifact changed')
            if fp.get('metadata') and sha(meta)!=fp['metadata']['sha256']: raise RuntimeError('Frozen measurement metadata changed')
            return npz(p),read(meta)
        if self.c['release']=='v2':
            import shutil
            ref=Path(self.c['thickness_reference']); refrozen=read(ref/'frozen_inputs.json')
            if sid not in refrozen['scans']: raise RuntimeError('v2 scan lacks frozen v1 thickness: '+sid)
            src=ref/'thickness'/f'{sid}.npz'
            if sha(src)!=refrozen['scans'][sid]['sha256']: raise RuntimeError('v1 thickness changed')
            p.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,p); shutil.copyfile(src.with_suffix('.json'),meta)
        elif self.batch_export(sid,p,meta):
            pass
        else:
            # Reuse the exact viewer engine, relocating its stale-export bookkeeping.
            spec=importlib.util.spec_from_file_location('cnv_analysis_thickness_engine',ROOT/'outputs/octa-thick_v1/engine.py')
            engine=importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
            engine.HERE=self.out/'viewer_cache'
            v=engine.Volume(self.batch/'volumes'/sid,read(self.batch/'launch_config.json'))
            if v.metadata()['analysis_policy']!=POLICY: raise RuntimeError('octa-thick policy changed')
            save(p,exclude_unreliable_um=v.maps[0][0],shadow=v.g['shadow'])
            write(meta,dict(v.metadata(),engine=fingerprint(ROOT/'outputs/octa-thick_v1/engine.py'),
                exact_viewer_array_match=True,finite_pixels=[int(np.isfinite(m).sum()) for m in v.maps[0][0]]))
            del v
        frozen['scans'][sid]=dict(fingerprint(p),metadata=fingerprint(meta)); write(self.out/'frozen_inputs.json',frozen)
        return npz(p),read(meta)

    def batch_export(self,sid,path,meta_path):
        """Reuse exact completed viewer exports, checking their source revisions."""
        export=self.batch/'thick/exports'/f'{sid}_batch.npz'
        if not export.exists(): return False
        with np.load(export,allow_pickle=False) as z:
            metadata=json.loads(str(z['metadata_json'].item()))
            if metadata.get('analysis_policy')!=POLICY or metadata.get('scan_id')!=sid:
                return False
            vol=self.batch/'volumes'/sid
            if any(sha(vol/name)!=expected for name,expected in metadata['source_fingerprints'].items()):
                return False
            corrections=metadata['correction_fingerprints']
            if any(not Path(p).exists() or sha(p)!=expected for p,expected in corrections.items()): return False
            config=read(self.batch/'launch_config.json'); chosen={}
            for root in [Path(config['output'])/'surface_labels',*[Path(p) for p in config['manual_sources']]]:
                for p in sorted(root.glob(f'{sid}_b*.npz')): chosen.setdefault(p.name,p)
            if any(str(p) not in corrections for p in chosen.values()): return False
            if [layer[0] for layer in metadata['layers']]!=LAYERS: raise ValueError('Export layer definitions changed')
            arrays=z['exclude_unreliable_um']; shadow=z['shadow']; endpoints=z['reported_endpoints_crop_px']
            shape=tuple(self.byid[sid]['native_shape'][:2])
            if arrays.shape!=(8,*shape) or shadow.shape!=shape or endpoints.shape!=(shape[0],8,shape[1]):
                raise ValueError('Export native-grid mismatch')
            pairs=[(0,7),(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,7)]
            for k,(top,bottom) in enumerate(pairs):
                delta=(endpoints[:,bottom]-endpoints[:,top])*1.12
                np.testing.assert_equal(arrays[k],np.where((delta>0)&~shadow,delta,np.nan))
            save(path,exclude_unreliable_um=arrays,shadow=shadow)
            write(meta_path,dict(metadata,export_source=fingerprint(export),exact_viewer_array_match=True,
                independent_endpoint_check=True,finite_pixels=[int(np.isfinite(m).sum()) for m in arrays]))
        return True

    def measure(self):
        self.invalidate_completion('measure')
        frozen=self.freeze(); inv=self.inventory_data()
        import shutil
        snapshot=self.out/'code_snapshot'/self.code_revision
        snapshot.mkdir(parents=True,exist_ok=True)
        for source in Path(__file__).parent.glob('*.py'):
            shutil.copyfile(source,snapshot/source.name)
        shutil.copyfile(ROOT/'outputs/octa-thick_v1/engine.py',snapshot/'octathick_engine.py')
        if not (self.out/'registration/registrations.json').exists(): self.register()
        registrations=read(self.out/'registration/registrations.json')
        identities=read(self.out/'registration/identities.json')
        review_inputs=self.out/'registration/review_inputs.json'
        if review_inputs.exists():
            for name,fp in read(review_inputs).items():
                p=self.out/name
                if (p.exists() and fp is None) or (fp and (not p.exists() or sha(p)!=fp['sha256'])):
                    raise RuntimeError('Alignment/identity edits changed; rerun register first')
        identity={(r['scan_id'],r['lesion_id']):r for r in identities}
        records={r['scan_id']:r for r in inv['scans']}; anchors={}; recovered={}; anchor_usable={}
        for i in identities:
            if not i['identity_eligible']: continue
            sid=i['scan_id']; r=records[sid]; a=self.annotation(sid)
            m=next(m for lid,m,_ in a['lesions'] if lid==i['lesion_id'])
            f=Footprint(m,a['spacing'],np.array(registrations[sid]['alignment']['matrix']))
            recovered.setdefault((i['track_id'],r['visit_id']),[]).append(f)
            if r['post_d0']:
                if sid not in anchor_usable:
                    anchor_arrays,_=self.thickness(sid,frozen)
                    anchor_usable[sid]=np.isfinite(anchor_arrays['exclude_unreliable_um']).any(axis=0)
                if not anchor_usable[sid][m].any(): continue
                old=anchors.get(i['track_id'])
                if old is None or (r['session_date'],sid)<(records[old['scan_id']]['session_date'],old['scan_id']):
                    anchors[i['track_id']]=dict(scan_id=sid,lesion_id=i['lesion_id'],footprint=f,visit_id=r['visit_id'])
        recovered={key:recover_outline(fs,fs[0].spacing) if len(fs)>1 and any(not f.complete for f in fs) else None for key,fs in recovered.items()}
        for tid,a in anchors.items():
            if recovered.get((tid,a['visit_id'])) is not None: a['footprint']=recovered[(tid,a['visit_id'])]
        allrows=[]; maprecords=[]
        context_revision=digest([self.code_revision,self.c,registrations,identities,inv])
        for number,r in enumerate(inv['scans']):
            sid=r['scan_id']
            if not (self.batch/'volumes'/sid/'qc_complete.json').exists(): raise RuntimeError('Audited volume missing: '+sid)
            # Freeze all batch thickness inputs, including animals without manual
            # masks, so later automatic coverage uses the same measurement revision.
            arrays,metadata=self.thickness(sid,frozen); thick=arrays['exclude_unreliable_um']
            if not r['analysis_eye']: continue
            checkpoint=self.out/'checkpoints'/f'{sid}.json'
            revision=digest([context_revision,metadata['revision']])
            if checkpoint.exists():
                cached=read(checkpoint)
                if cached['revision']==revision and all(Path(p['path']).exists() and sha(p['path'])==p['sha256'] for p in cached['artifacts']):
                    allrows.extend(cached['rows']); maprecords.extend(cached['maps'])
                    print('Resume verified measurements: '+sid,flush=True)
                    continue
            row_start=len(allrows); map_start=len(maprecords)
            a=self.annotation(sid); reg=registrations.get(sid)
            usable=reg and reg['alignment']['state'] in ('reference','verified')
            invmat=np.linalg.inv(np.array(reg['alignment']['matrix'])) if usable else np.eye(3)
            onh_mask=a['onh'].copy(); onh_mask_source='native annotation' if onh_mask.any() else 'unavailable'
            if reg and reg['onh'].get('state')=='localized' and not onh_mask.any():
                onh_info=reg['onh']; source=onh_info.get('source_scan')
                if source and usable:
                    source_a=self.annotation(source)
                    matrix=invmat@np.array(registrations[source]['alignment']['matrix'])
                    onh_mask=sample_mask(source_a['onh'],source_a['spacing'],grid(thick.shape[1:],a['spacing']),matrix)
                    if onh_mask.any(): onh_mask_source='transferred verified annotation'
                if not onh_mask.any() and onh_info.get('radius_um'):
                    onh_mask=np.linalg.norm(grid(thick.shape[1:],a['spacing'])-np.array(onh_info['center_um']),axis=-1)<=onh_info['radius_um']
                    onh_mask_source='estimated visible-edge disc; radius and uncertainty in registration record'
            changing=[]
            for lid,mask,source in a['lesions']:
                ident=identity.get((sid,lid),dict(track_id='',state='unregistered',identity_eligible=False))
                f=Footprint(mask,a['spacing']); recovery=recovered.get((ident['track_id'],r['visit_id']))
                if recovery is not None and usable:
                    f=Footprint(recovery.mask,recovery.spacing,invmat@recovery.matrix,complete=recovery.complete)
                changing.append((lid,f,ident,source))
            fixed=[]
            if usable:
                for tid,anchor in anchors.items():
                    ar=records[anchor['scan_id']]
                    if (ar['animal'],ar['eye'])!=(r['animal'],r['eye']): continue
                    af=anchor['footprint']; f=Footprint(af.mask,af.spacing,invmat@af.matrix,complete=af.complete)
                    fixed.append((anchor['lesion_id'],f,dict(track_id=tid,state='fixed_registered',identity_eligible=True),
                                  'fixed first usable post-laser footprint'))
            families=[('changing',changing),('fixed',fixed)]
            if self.c['annotation_source']=='automatic_core':
                broad=A.load(dict(self.c,annotation_source='automatic_footprint'),self.byid[sid])
                broad_items=[]
                broad_fp=[Footprint(m,broad['spacing']) for _,m,_ in broad['lesions']]
                matches=match_lesions(broad_fp,[v[1] for v in changing]) if changing else []
                for j,(lid,mask,source) in enumerate(broad['lesions']):
                    match=matches[j] if matches else dict(state='unmatched',target=None)
                    ident=changing[match['target']][2] if match['state']=='matched' else dict(track_id='',state=match['state'],identity_eligible=False)
                    broad_items.append((lid,broad_fp[j],ident,'automatic_footprint_sensitivity'))
                families.append(('changing_footprint_sensitivity',broad_items))
            for definition,items in families:
                if not items: continue
                for basis in ('normalized','absolute_um'):
                    edges_for=lambda f: np.array(self.c['normalized_edges'])*f.diameter if basis=='normalized' else np.array(self.c['absolute_edges_um'])
                    measured=regions([v[1] for v in items],thick.shape[1:],a['spacing'],onh_mask,edges_for)
                    for (lid,f,ident,source),(bands,distances,diag) in zip(items,measured):
                        # Exclude contemporaneous other lesion interiors from fixed surroundings too.
                        if definition=='fixed':
                            for band in range(1,7):
                                extra=(bands==band)&a['union']
                                diag[band]['other_lesion_area_um2']+=float(extra.sum()*np.prod(a['spacing']))
                            bands[(bands>0)&a['union']]=-1
                        stem=f'{sid}__{digest([lid,definition,basis])[:12]}'
                        save(self.out/'maps'/f'{stem}.npz',bands=bands,distance_um=distances.astype('float32'),
                             diameter_um=np.array(f.diameter),centroid_um=f.centroid,spacing_um_yx=a['spacing'])
                        maprecords.append(dict(scan_id=sid,lesion_id=lid,definition=definition,basis=basis,map=stem,
                                               diameter_complete=f.complete,alignment_supported=bool(usable)))
                        onh=reg['onh'] if reg else dict(state='unavailable')
                        dx=dy=dist_onh=uncertainty=None; sector='unavailable'
                        if onh['state']=='localized':
                            delta=f.centroid-np.array(onh['center_um'])
                            # Sector coordinates use the eye reference frame, consistently across visits.
                            if usable: delta=delta@np.array(reg['alignment']['matrix'])[:2,:2].T
                            dx,dy=map(float,delta); dist_onh=float(np.linalg.norm(delta)); uncertainty=onh['uncertainty_um']
                            sector=provisional_sector(dx,dy)
                        for k,layer in enumerate(LAYERS):
                            for band,d in enumerate(diag):
                                selected=bands==band; valid=selected&np.isfinite(thick[k]); n=int(valid.sum())
                                expected=d['expected_area_um2']; fov=d['fov_area_um2']
                                available=float(selected.sum()*np.prod(a['spacing'])); valid_area=float(n*np.prod(a['spacing']))
                                edges=edges_for(f)
                                allrows.append(dict(scan_id=sid,animal=r['animal'],eye=r['eye'],lesion_id=lid,
                                    track_id=ident['track_id'],identity_state=ident['state'],identity_eligible=ident['identity_eligible'],
                                    visit_id=r['visit_id'],session_date=r['session_date'],day=r['day'],day_basis=r['day_basis'],day_label=r['day_label'],
                                    prelaser=r['prelaser'],post_d0=r['post_d0'],layer=layer,band=band,
                                    region_definition=definition,distance_basis=basis,mask_source=source,
                                    annotation_revision=r['annotation_revision'],measurement_revision=metadata['revision'],
                                    diameter_um=f.diameter,diameter_complete=f.complete,lesion_area_um2=f.area,
                                    normalized_eligible=bool(f.complete or basis=='absolute_um'),
                                    distance_lo_um=0. if band==0 else float(edges[band-1]),
                                    distance_hi_um=0. if band==0 else float(edges[band]),
                                    mean_distance_um=float(distances[valid].mean()) if n else None,
                                    mean_thickness_um=float(thick[k][valid].mean()) if n else None,
                                    **{key:value for key,value in d.items() if key not in ('band','available_area_um2')},
                                    available_area_um2=available,valid_area_um2=valid_area,valid_pixels=n,
                                    fov_coverage=min(1.,fov/expected) if expected else None,
                                    measurement_coverage=valid_area/available if available else None,
                                    complete_band=bool(f.complete and expected and fov/expected>=self.c['complete_band_fraction']),
                                    registration_state=reg['alignment']['state'] if reg else 'unavailable',
                                    onh_exclusion_source=onh_mask_source,
                                    onh_distance_um=dist_onh,onh_dx_um=dx,onh_dy_um=dy,onh_uncertainty_um=uncertainty,
                                    dvnt_sector=sector,experimental=True,policy=POLICY))
            print(f'Measure {number+1}/{len(inv["scans"])} {sid}',flush=True)
            write(checkpoint,dict(revision=revision,rows=allrows[row_start:],maps=maprecords[map_start:],
                artifacts=[fingerprint(self.out/'maps'/f'{r["map"]}.npz') for r in maprecords[map_start:]]))
            self.status('measure',scan_id=sid,rows=len(allrows))
        csvwrite(self.out/'tables/lesion_visit_layer_band.csv',allrows)
        write(self.out/'maps/index.json',maprecords)
        write(self.out/'measurement_complete.json',dict(passed=True,rows=len(allrows),code_revision=self.code_revision,
            table=fingerprint(self.out/'tables/lesion_visit_layer_band.csv'),frozen_inputs=fingerprint(self.out/'frozen_inputs.json'),
            registration=fingerprint(self.out/'registration/registrations.json'),identities=fingerprint(self.out/'registration/identities.json')))
        self.status('measure',complete=True,rows=len(allrows))

    def figures(self):
        self.invalidate_completion('figures')
        from .figures import build
        gate(self.c)
        proof=read(self.out/'measurement_complete.json')
        for key in ('table','frozen_inputs','registration','identities'):
            fp=proof[key]
            if sha(fp['path'])!=fp['sha256']: raise RuntimeError('Measurements need rerun: '+key)
        if proof['code_revision']!=self.code_revision:
            raise RuntimeError('Analysis code changed; rerun measure before figures')
        build(self)

    def run(self):
        self.inventory(); gate(self.c); self.register(); self.measure(); self.figures()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['inventory','register','measure','figures','run'])
    parser.add_argument('--config',type=Path)
    parser.add_argument('--release',choices=['v1','v2'],default='v1')
    parser.add_argument('--annotation-source',choices=['manual','automatic_core','automatic_footprint'])
    args=parser.parse_args()
    source=args.annotation_source or ('manual' if args.release=='v1' else 'automatic_core')
    config=read(args.config) if args.config else default_config(args.release,source)
    runner=Runner(config)
    try: getattr(runner,args.stage)()
    except Exception as exc:
        runner.status(args.stage,state='blocked_or_failed',reason=str(exc)); raise

if __name__=='__main__': main()
