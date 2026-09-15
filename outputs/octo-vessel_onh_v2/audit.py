"""Freeze input identity and derive supervision; never alter source annotations."""
import io, re, zipfile
from collections import Counter
import numpy as np
from common import *

KNOWN_EXCLUSIONS={'TS241_OS_2024-09-11_D28_s04_104606','TS247_OD_2024-11-06_D21_s02_103301'}

def supervision(z,excluded=False):
    v=z['vasculature_mask'].astype(bool);o=z['onh_mask'].astype(bool)
    touched=z['vasculature_brush_touched'].astype(bool)
    removed=z['vessel_removed_by_onh'].astype(bool)
    rv,ro=map(bool,z['reviewed_targets'][1:])
    vp=touched & v & ~z['vessel_region_excluded'] & ~o
    vn=touched & ~v & ~z['vessel_region_excluded'] & ~o & ~removed
    if not rv or excluded: vp[:]=False;vn[:]=False
    state=str(scalar(z,'onh_visibility'))
    op=o & ~z['onh_region_excluded'];on=~o & ~z['onh_region_excluded']
    if not ro or state not in ['Visible — outlined','Partially visible — outlined','Outside image'] or excluded:
        op[:]=False;on[:]=False
    if ro and state=='Outside image' and (o.any() or z['onh_edge_mask'].any()):
        raise ValueError('Reviewed ONH absence conflicts with saved ONH mask/edge')
    if ro and 'outlined' in state and not o.any(): raise ValueError('Reviewed positive ONH is empty')
    return np.stack([vp,op]),np.stack([vn,on])

def main():
    if (HERE/'audit_manifest.json').exists():
        manifest=read_json(HERE/'audit_manifest.json')
        assert manifest['status']=='complete'
        for r in manifest['annotations']:
            assert digest(HERE/r['supervision_file'])==r['supervision_sha256']
        print('Reusing frozen annotation snapshot',manifest['frozen_at'],flush=True)
        return manifest
    (HERE/'data').mkdir(exist_ok=True)
    frozen_at=now()
    source_inventory=read_json(BATCH/'inventory.json')
    assert len(source_inventory)==314 and len({r['scan_id'] for r in source_inventory})==314
    indexed={r['scan_id']:r for r in source_inventory}
    annotations=[];exclusions=[];snapshots=[]
    paths=sorted(LABELS.glob('*_cnv.npz'))
    for p in paths:
        blob=p.read_bytes();sha=hashlib.sha256(blob).hexdigest()
        with np.load(io.BytesIO(blob),allow_pickle=False) as nz: z={k:nz[k].copy() for k in nz.files}
        sid=str(scalar(z,'scan_id'));meta=indexed[sid]
        assert list(z['annotation_names'])==['CNV','VASCULATURE','ONH']
        assert str(scalar(z,'animal'))==meta['animal'] and sid.startswith(meta['animal']+'_')
        assert Path(str(scalar(z,'source_volume')))==Path(meta['source'])
        shape=tuple(map(int,z['native_shape']));v=z['vasculature_mask'];o=z['onh_mask']
        assert shape==(512,512)
        for k in ['vasculature_mask','onh_mask','onh_edge_mask','vasculature_brush_touched','vessel_removed_by_onh','vessel_region_excluded','onh_region_excluded','onh_brush_touched','vasculature_initial_mask','frozen_batch_mask']:
            assert z[k].shape==shape and z[k].dtype==bool,(sid,k)
        assert not (v&o).any(),sid
        unexplained=(v!=z['vasculature_initial_mask']) & ~z['vasculature_brush_touched'] & ~z['vessel_removed_by_onh']
        assert not unexplained.any(),f'Unexplained vessel edits in {sid}'
        note=str(scalar(z,'notes'))
        excluded=sid in KNOWN_EXCLUSIONS or bool(re.search(r'(?:do\s*not|don.t)\s*(?:use|include).*train|exclud\w*.*train',note,re.I|re.S))
        if excluded: exclusions.append(dict(scan_id=sid,notes=note,reason='Explicit human instruction; scan excluded from training, tuning, evaluation and analysis',source_path=str(p),source_sha256=sha))
        pos,neg=supervision(z,excluded)
        ignored=~(pos|neg)
        support_path=HERE/'data'/f'{sid}_supervision.npz'
        save_npz(support_path,positive=pos,negative=neg,ignored=ignored,
                 human_vessel=v,human_onh=o,onh_edge=z['onh_edge_mask'],
                 vessel_uncertain=z['vessel_region_excluded'],onh_uncertain=z['onh_region_excluded'],
                 scan_id=np.array([sid]),source_label_sha256=np.array([sha]))
        row=dict(scan_id=sid,animal=meta['animal'],eye=meta['eye'],source_path=str(p),source_sha256=sha,
                 revision=int(scalar(z,'revision')),labelled_at=str(scalar(z,'labelled_at')),
                 notes=note,excluded=excluded,vessel_reviewed=bool(z['reviewed_targets'][1]),onh_reviewed=bool(z['reviewed_targets'][2]),
                 onh_visibility=str(scalar(z,'onh_visibility')),vessel_eligible=bool((pos[0]|neg[0]).any()),onh_eligible=bool((pos[1]|neg[1]).any()),
                 native_shape=list(shape),supervision_file=str(support_path.relative_to(HERE)),supervision_sha256=digest(support_path),
                 inherited_label_path=str(scalar(z,'inherited_label_path')),inherited_label_sha256=str(scalar(z,'inherited_label_sha256')),
                 queue_sha256=str(scalar(z,'queue_sha256')),seed_sha256=str(scalar(z,'vasculature_proposal_sha256')),
                 direct_vessel_footprint_pixels=int(z['vasculature_brush_touched'].sum()),derived_onh_removal_pixels=int(z['vessel_removed_by_onh'].sum()),
                 unexplained_vessel_changes=int(unexplained.sum()))
        for i,t in enumerate(TARGETS):
            row[t+'_positive_pixels']=int(pos[i].sum());row[t+'_negative_pixels']=int(neg[i].sum());row[t+'_ignored_pixels']=int(ignored[i].sum())
            row[t+'_scored_fraction']=float((pos[i]|neg[i]).mean())
        annotations.append(row);snapshots.append((p.name,blob,z))
    assert KNOWN_EXCLUSIONS <= {e['scan_id'] for e in exclusions}
    inventory=[]
    by_label={r['scan_id']:r for r in annotations}
    snap_by_sid={str(scalar(z,'scan_id')):z for _,_,z in snapshots}
    for i,meta in enumerate(source_inventory):
        sid=meta['scan_id'];projection=BATCH/'projections'/f'{sid}.npz';proposal=BATCH/'proposals'/f'{sid}_proposal.npz'
        record=read_json(BATCH/'records'/f'{sid}.json')
        assert record['status']=='complete'
        assert digest(proposal)==record['proposal_sha256']
        with np.load(projection,allow_pickle=False) as q,np.load(proposal,allow_pickle=False) as p:
            im=q['structural_enface'];shape=im.shape
            assert shape==(512,512) and np.isfinite(im).all()
            assert str(scalar(q,'source'))==meta['source']==str(scalar(p,'source_volume'))
            assert np.array_equal(q['retina_band'],p['retina_band'])
            assert p['predicted_vasculature_mask'].shape==shape
            source_stat=Path(meta['source']).stat()
            assert source_stat.st_size==record['identity']['source_size']
            assert source_stat.st_mtime_ns==record['identity']['source_mtime_ns']==int(scalar(q,'source_mtime_ns'))
            if sid in snap_by_sid:
                z=snap_by_sid[sid]
                assert np.array_equal(z['retina_band'],q['retina_band'])
                assert np.array_equal(z['frozen_batch_mask'],p['predicted_vasculature_mask'])
                seed=Path(str(scalar(z,'vasculature_proposal_path')))
                if not seed.exists(): seed=BATCH/'proposals'/seed.name
                assert digest(seed)==str(scalar(z,'vasculature_proposal_sha256'))
            entry=dict(scan_id=sid,animal=meta['animal'],eye=meta['eye'],session_date=meta['session_date'],day_label=meta['day_label'],days_post_laser=meta['days_post_laser'],
                source_volume=meta['source'],source_size=source_stat.st_size,source_mtime_ns=source_stat.st_mtime_ns,
                native_shape=list(shape),axis_order='B-scan,A-line',retina_band=q['retina_band'].tolist(),field_um=1460,
                projection_path=str(projection),projection_sha256=digest(projection),proposal_path=str(proposal),proposal_sha256=record['proposal_sha256'],
                frozen_human_onh_pixels=int(p['human_onh_exclusion_mask'].sum()),
                excluded=by_label.get(sid,{}).get('excluded',False),annotation_present=sid in by_label)
            inventory.append(entry)
        if (i+1)%50==0: progress('audit',verified_inputs=i+1,total=314)
    # Archival byte-for-byte copy, not a new annotation or a label-store write.
    archive=HERE/'data'/'source_annotations_snapshot.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as out:
        for name,blob,_ in snapshots: out.writestr(name,blob)
    write_json(HERE/'exclusions.json',exclusions)
    write_json(HERE/'inventory.json',inventory)
    usable=[r for r in annotations if r['vessel_eligible'] or r['onh_eligible']]
    counts=dict(saved_records=len(annotations),excluded_scans=len(exclusions),inference_eligible=314-len(exclusions),
                vessel_eligible=sum(r['vessel_eligible'] for r in annotations),onh_eligible=sum(r['onh_eligible'] for r in annotations),
                onh_positive=sum(r['onh_eligible'] and r['onh_positive_pixels']>0 for r in annotations),
                onh_absent=sum(r['onh_eligible'] and r['onh_visibility']=='Outside image' for r in annotations),
                onh_cannot_judge=sum(r['onh_reviewed'] and r['onh_visibility']=='Cannot judge' for r in annotations),
                per_animal=count_roles(usable))
    result=dict(status='complete',frozen_at=frozen_at,counts=counts,annotations=annotations,
                snapshot_sha256=digest(archive),inventory_sha256=digest(HERE/'inventory.json'),
                frozen_manifest_sha256=digest(BATCH/'manifest.json'),exclusions_sha256=digest(HERE/'exclusions.json'))
    write_json(HERE/'audit_manifest.json',result)
    progress('audit_complete',**counts)
    return result

if __name__=='__main__':main()
