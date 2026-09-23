"""Read-only release audit and independent synthetic physical-grid check.
Run after conda activate octa: python outputs/octa-reg_v1/verify_release.py
"""
from pathlib import Path
import sys
import json
from collections import Counter
import numpy as np
from skimage.transform import EuclideanTransform

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'code'))
from octa_reg_v1 import CONFIG
from octa_reg_v1.io import read,sha,digest,write
from octa_reg_v1.geometry import apply,xy_grid,register,footprint
from octa_reg_v1.pipeline import pair_signature

OUT=Path(__file__).resolve().parent

def synthetic():
    mat=EuclideanTransform(rotation=.12,translation=[26,-13]).params
    def field(xy):
        x,y=xy[...,0],xy[...,1]
        en=np.sin(x/11)+np.cos(y/17)+np.sin((x+y)/23)+np.cos(x*y/2200)
        vessel=(abs(np.sin(x/24))<.23)|(abs(np.sin(y/32))<.22)
        return en,vessel
    axy=xy_grid((160,200),[2,3]);bxy=xy_grid((230,340),[1.5,2.])
    ae,av=field(axy);be,bv=field(apply(bxy,np.linalg.inv(mat)))
    a=dict(enface=ae,vessel=av,spacing=[2.,3.],registration_blocked=np.zeros_like(av))
    b=dict(enface=be,vessel=bv,spacing=[1.5,2.],registration_blocked=np.zeros_like(bv))
    rng=np.random.default_rng(21);pa=rng.uniform([60,60],[450,250],(40,2));desc=rng.random((40,256))>.5
    fa=dict(points=pa,descriptors=desc,branches=pa[:10]);fb=dict(points=apply(pa,mat),descriptors=desc,branches=apply(pa[:10],mat))
    result=register(a,b,fa,fb,CONFIG)
    assert result['verified'],result
    np.testing.assert_allclose(result['matrix'],mat,atol=1e-8)
    return dict(recovered_rotation_radians=.12,recovered_translation_um=[26,-13],spacing_a=[2,3],spacing_b=[1.5,2],result=result)

def audit():
    assert read(OUT/'status.json')['status']=='complete', 'Cohort must finish without implementation/input failures before final audit'
    infos={r['scan_id']:r for r in read(OUT/'inventory.json')};pairs=read(OUT/'pairs.json');components=read(OUT/'components.json');transforms=read(OUT/'transforms.json')
    pin=read(OUT/'manifest.json')
    assert all(sha(p)==h for p,h in pin['code_hashes'].items())
    for s,i in infos.items():
        if i['status']!='blocked':assert sha(OUT/'prepared'/(s+'.npz'))==i['prepared_sha256']
    groups=Counter((r['animal'],r['eye']) for r in infos.values())
    assert len(pairs)==sum(n*(n-1)//2 for n in groups.values())
    assert len({p['pair_id'] for p in pairs})==len(pairs)
    assert not any(p['status']=='implementation_failure' for p in pairs)
    assert sorted(s for c in components for s in c['members'])==sorted(infos)
    for p in pairs:
        a,b=infos[p['scan_a']],infos[p['scan_b']]
        assert p['signature']==pair_signature(a,b,pin)
        assert (a['animal'],a['eye'])==(b['animal'],b['eye'])
        if a['status']!='prepared' or b['status']!='prepared':assert p['status']=='blocked'
        disk=read(OUT/'pairs'/(p['pair_id']+'.json'));checksum=disk.pop('artifact_digest');assert checksum==digest(disk)
        if p['matrix'] is not None:
            m=np.asarray(p['matrix']);np.testing.assert_allclose(m[:2,:2].T@m[:2,:2],np.eye(2),atol=1e-9);np.testing.assert_allclose(np.linalg.det(m[:2,:2]),1,atol=1e-9)
        if p['status']=='automatic_proposal':
            for metric,gate in [('inliers','registration_min_matches'),('overlap_fraction','registration_min_overlap'),('vessel_dice','registration_min_vessel_dice'),('structural_correlation','registration_min_structural_correlation'),('branch_matches','registration_min_branch_matches')]:assert p[metric]>=CONFIG[gate]
    worst=0.
    for s,t in transforms.items():
        m=np.asarray(t['matrix_to_component']);inverse=np.asarray(t['matrix_from_component'])
        np.testing.assert_allclose(m@inverse,np.eye(3),atol=1e-9)
        if t['footprint_um'] is not None:
            corners=footprint(infos[s]);np.testing.assert_allclose(apply(corners,m),t['footprint_um'],atol=1e-8)
            pts=np.array([[0,0],[25,100],[255.5,255.5],[511,511]])
            pixel=np.asarray(t['pixel_to_component']);back=apply(apply(pts,pixel),np.linalg.inv(pixel));worst=max(worst,float(abs(back-pts).max()))
    assert worst<1e-8
    for c in components:
        if len(c['members'])==1:np.testing.assert_allclose(transforms[c['members'][0]]['matrix_to_component'],np.eye(3))
        assert c['component_to_fundus'] is None
        if not c['registration_consistent']:assert c['status']=='withheld_loop_inconsistent'
    queue=read(OUT/'human_review_queue.json');assert len(queue)==len({q['pair_id'] for q in queue})
    assert all(q['human_accuracy_um'] is None and q['independent_landmarks']==[] for q in queue)
    queue_ids={q['pair_id'] for q in queue}
    for group in groups:
        ps=sorted([p for p in pairs if p['status']=='automatic_proposal' and (infos[p['scan_a']]['animal'],infos[p['scan_a']]['eye'])==group],key=lambda p:p['vessel_dice'])
        if ps:assert {ps[0]['pair_id'],ps[len(ps)//2]['pair_id'],ps[-1]['pair_id']}<=queue_ids
    for mosaic in read(OUT/'mosaics.json'):
        assert all(infos[s]['status']=='prepared' and infos[s]['session_date']==mosaic['date'] for s in mosaic['scan_ids'])
        assert all(Path(OUT/mosaic[k]).exists() for k in ('structural','octa','coordinate_map'))
    integrity=read(OUT/'source_integrity.json');assert integrity['unchanged']
    assert all(sha(p)==h for p,h in integrity['hashes'].items())
    upstream=read(OUT/'verification'/'upstream_integrity_baseline.json')
    annotation_changes=[]
    for p,before in upstream['annotation_and_proposal_metadata'].items():
        st=Path(p).stat()
        if dict(bytes=st.st_size,mtime_ns=st.st_mtime_ns)!=before:annotation_changes.append(p)
    model_changes=[p for p,h in upstream['model_hashes'].items() if sha(p)!=h]
    assert not annotation_changes and not model_changes
    expected={r['scan_id'] for r in read(ROOT/'outputs/octo-vessel_onh_v2/final_output_v1/manifest.json')['records']}
    for s,i in infos.items():
        if i['status']=='blocked':continue
        assert (i['mask_source']=='primary_export')==(s in expected)
        if i['mask_source']=='legacy_geometry_fallback':assert i['onh_available'] is False and not i['vessel_reviewed']
    return dict(acquisitions=len(infos),pairs=len(pairs),components=len(components),source_files_rehashed=len(integrity['hashes']),
                original_annotation_and_proposal_metadata_unchanged=len(upstream['annotation_and_proposal_metadata']),
                upstream_model_hashes_unchanged=len(upstream['model_hashes']),annotation_mask_arrays_read=False,
                maximum_pixel_roundtrip_error=worst,all_pairs_and_acquisitions_accounted=True,rigid_only=True,
                independent_landmarks_pending=True,synthetic_unequal_grid_rotation=synthetic())

def examples():
    from PIL import Image,ImageDraw
    from octa_reg_v1.report import gray
    from octa_reg_v1.geometry import sample_native
    pairs=read(OUT/'pairs.json');passing=sorted([p for p in pairs if p['status']=='automatic_proposal'],key=lambda p:p['vessel_dice'])
    chosen={}
    if passing:
        for i,label in ((0,'lowest passing Dice'),(len(passing)//2,'median passing Dice'),(-1,'highest passing Dice')):
            chosen[passing[i]['pair_id']]=(passing[i],label)
    gates=set()
    for p in sorted(pairs,key=lambda p:p.get('vessel_dice') or 0,reverse=True):
        for g in p.get('rejection_gates',[]):
            if g not in gates:chosen[p['pair_id']]=(p,'rejection: '+g);gates.add(g)
    folder=OUT/'verification'/'panels';folder.mkdir(parents=True,exist_ok=True)
    lines=['# Representative observed cases','',
        'These are automatic diagnostic examples, not human landmark validation. Green/red vessel differences can reflect mask disagreement, registration error or tissue differences. Original image seams are retained.','',
        '| Example | Pair | Dice | Inliers | Junction matches | Panel |','|---|---|---:|---:|---:|---|']
    for n,(p,label) in enumerate(chosen.values(),1):
        a,b=p['scan_a'],p['scan_b']
        with np.load(OUT/'prepared'/(a+'.npz')) as z:ae=z['enface'];av=z['vessel'];asp=z['spacing']
        with np.load(OUT/'prepared'/(b+'.npz')) as z:be=z['enface'];bv=z['vessel'];bsp=z['spacing']
        h,w=be.shape;panel=Image.new('RGB',(w*2,h*2+110),(14,22,29));d=ImageDraw.Draw(panel)
        d.text((10,8),f'{label} | {p["status"]} | Dice {p.get("vessel_dice")} | inliers {p.get("inliers")} | junctions {p.get("branch_matches")}',fill='white')
        d.text((10,28),'A native: '+a,fill='white');d.text((w+10,28),'B native: '+b,fill='white')
        panel.paste(Image.fromarray(gray(ae)).convert('RGB'),(0,50));panel.paste(Image.fromarray(gray(be)).convert('RGB'),(w,50))
        if p['matrix'] is not None:
            from_b=apply(xy_grid(be.shape,bsp),np.linalg.inv(np.asarray(p['matrix'])))
            moved,valid=sample_native(gray(ae),from_b,asp);vessel,_=sample_native(av,from_b,asp)
            base=gray(be).astype(float);blend=base.copy();blend[valid]=(base[valid]+moved[valid])/2
            panel.paste(Image.fromarray(blend.astype('uint8')).convert('RGB'),(0,h+100))
            diff=np.stack([base*.45]*3,axis=-1).astype('uint8');diff[(vessel==1)&valid]=[255,60,80];diff[bv]=[50,240,170];diff[(vessel==1)&bv&valid]=[245,235,70]
            panel.paste(Image.fromarray(diff),(w,h+100));d.text((10,h+70),'50% alpha in B native grid (no interpolation)',fill='white');d.text((w+10,h+70),'Vessels: red A / green B / yellow both',fill='white')
        else:
            d.text((10,h+80),'NO ACCEPTABLE FIT: native images above are not mutually positioned.',fill=(255,180,100))
        filename=f'case_{n:02d}.png';panel.save(folder/filename)
        lines.append(f'| {label} | {a} → {b} | {p.get("vessel_dice")} | {p.get("inliers")} | {p.get("branch_matches")} | [view](panels/{filename}) |')
    (OUT/'verification'/'REPRESENTATIVE_CASES.md').write_text('\n'.join(lines),encoding='utf-8')
    report=OUT/'RUN_REPORT.md';body=report.read_text(encoding='utf-8');marker='\n\n## Audited examples and checks\n'
    body=body.split(marker)[0]+marker+'\nSee [representative cases](verification/REPRESENTATIVE_CASES.md), [verification notes](verification/VERIFICATION.md), [release audit](verification/release_audit.json), and [resume/invalidation check](verification/resume_invalidation.json).\n'
    report.write_text(body,encoding='utf-8')

def coverage():
    import csv
    infos=read(OUT/'inventory.json');pairs=read(OUT/'pairs.json');components=read(OUT/'components.json')
    connected={s for c in components if c['status']=='automatic_proposal' for s in c['members']}
    rows=[]
    for animal,eye in sorted({(i['animal'],i['eye']) for i in infos}):
        scans=[i for i in infos if (i['animal'],i['eye'])==(animal,eye)];ids={i['scan_id'] for i in scans};ps=[p for p in pairs if p['scan_a'] in ids]
        rows.append(dict(animal=animal,eye=eye,acquisitions=len(scans),eligible=sum(i['status']=='prepared' for i in scans),
            connected_scans=len(ids&connected),candidate_pairs=len(ps),blocked=sum(p['status']=='blocked' for p in ps),
            within_session_proposals=sum(p['status']=='automatic_proposal' and p['interval']=='within_session' for p in ps),
            across_date_proposals=sum(p['status']=='automatic_proposal' and p['interval']=='across_date' for p in ps)))
    with (OUT/'verification'/'coverage_by_eye.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    text=['\n\n## Coverage by animal and eye\n','\n| Animal | Eye | Scans | Eligible | Connected | Candidate pairs | Blocked pairs | Within-session proposals | Across-date proposals |\n|---|---|---:|---:|---:|---:|---:|---:|---:|\n']
    text.extend('| '+' | '.join(str(v) for v in r.values())+' |\n' for r in rows)
    path=OUT/'RUN_REPORT.md';body=path.read_text(encoding='utf-8').split('\n\n## Coverage by animal and eye\n')[0]
    path.write_text(body+''.join(text),encoding='utf-8')
    summary=read(OUT/'summary.json');g=summary['rejection_gates'];cycles=sum(len(c['non_tree_cycles']) for c in components)
    branch_failures=[p for p in pairs if p['status']=='rejected' and 'branch_matches' in p.get('rejection_gates',[]) and p.get('vessel_dice') is not None]
    best=max(branch_failures,key=lambda p:p['vessel_dice']) if branch_failures else None
    note='\n\n## Next measured experiment\n\n'
    note+=f"The primary bottleneck is vascular correspondence: {g.get('insufficient_vessel_anchored_inliers',0)} of {summary['pair_status'].get('rejected',0)} rejected pairs lacked sufficient vessel-anchored inliers; {g.get('branch_matches',0)} failed junction support. "
    if best:note+=f"A concrete review example has Dice {best['vessel_dice']:.3f}, {best['inliers']} inliers and {best['branch_matches']} matched junctions ({best['scan_a']} to {best['scan_b']}). Its major trunks align closely in the diagnostic overlay, but no independent human accuracy has been measured. "
    note+='Use the saved independent-landmark queue to separate mask omissions and motion artifacts from descriptor failures, then test curved-vessel/bend and centerline-constellation matching for fields with few junctions. This is a separately versioned comparison, not a change to these gates. '
    note+=f"Global optimization is a later priority: only {cycles} non-tree loop check is available in this sparse graph. ONH localization cannot repair missing tissue correspondences and remains a separate proposal task.\n"
    with path.open('a',encoding='utf-8') as f:f.write(note)

if __name__=='__main__':
    result=audit();write(OUT/'verification'/'release_audit.json',dict(passed=True,audit_script_sha256=sha(__file__),**result));examples();coverage();print(json.dumps(result,indent=2))
