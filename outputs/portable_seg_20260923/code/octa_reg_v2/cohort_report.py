"""Publish the eye-separated reviewer and audit coverage without source edits."""
from pathlib import Path
from collections import Counter
import argparse,json,math,shutil
import numpy as np
from scipy import ndimage as ndi
from PIL import Image,ImageDraw,ImageFont
from .run import ROOT,BASE,read,write,sha,apply,matrix
from .cohort import DEFAULT_OUT,VERSION
from .reviewer_publish import visit, publish

def gray(info):
    with np.load(BASE/'prepared'/(info['scan_id']+'.npz')) as z:im=z['enface'].copy()
    finite=np.isfinite(im);lo,hi=np.percentile(im[finite],[2,98])
    return np.uint8(np.clip((np.nan_to_num(im,nan=lo)-lo)/max(hi-lo,1e-6),0,1)*255),finite

def render_group(folder,groups):
    source=folder/'review_registration.json'
    data=read(source if source.exists() else folder/'registration.json');graph=data['graph'];infos=data['scans'];group=data['group'];spacing=1460/512
    poses={int(i):np.array(m) for i,m in graph['poses'].items()};tiers={int(i):t for i,t in graph['tiers'].items()}
    corners=np.array([[5,5],[507,5],[507,507],[5,507]])
    if poses:
        points=np.concatenate([apply(corners,m) for m in poses.values()]);lo=np.floor(points.min(0)-55);hi=np.ceil(points.max(0)+55)
    else:lo=np.zeros(2);hi=np.array([622,622])
    size=(hi-lo).astype(int);offset=matrix([0,*-lo]);raster_scale=min(1,1400/max(size));pixel_size=np.maximum(1,np.ceil(size*raster_scale).astype(int))
    asset=folder/'assets';asset.mkdir(exist_ok=True);images={};masks={};records=[];source_checked={}
    for i,info in enumerate(infos):
        r=dict(index=i,scan_id=info['scan_id'],date=info['session_date'],animal=info['animal'],eye=info['eye'],scan_no=info['scan_no'],
               tier=tiers.get(i,'unlocalized'),reasons=graph['reasons'].get(str(i),[]),excluded=bool(info.get('excluded_from_analysis')),shape=info['shape'])
        r.update(visit(info))
        if not r['excluded'] and (BASE/'prepared'/(info['scan_id']+'.npz')).exists():
            im,finite=gray(info);Image.fromarray(im).save(asset/f'{i:03d}.png');images[i]=im;r['image']=f'assets/{i:03d}.png'
        if i in poses:
            m=poses[i];cal=np.diag([spacing,spacing,1]);canvas=offset@m
            inc=[e for e in graph['edges'] if i in (e['a'],e['b'])]
            r.update(matrix_to_onh_pixels=m.tolist(),matrix_from_onh_pixels=np.linalg.inv(m).tolist(),matrix_to_canvas=canvas.tolist(),
                     pixel_to_atlas_um=(cal@m).tolist(),native_um_to_atlas_um=(cal@m@np.linalg.inv(cal)).tolist(),
                     links=len(inc),best_dice=max((e.get('dice',0) for e in inc),default=None),
                     footprint=apply(corners,canvas).tolist(),reference=(i==graph['reference']))
            warped=np.diag([raster_scale,raster_scale,1])@canvas;inv=np.linalg.inv(warped)
            valid=finite.copy();valid[:5]=False;valid[-5:]=False;valid[:,:5]=False;valid[:,-5:]=False
            masks[i]=ndi.affine_transform(valid.astype(np.uint8),inv[:2,:2][::-1,::-1],inv[:2,2][::-1],output_shape=tuple(pixel_size[::-1]),order=0)>0
        records.append(r)
    supported=[i for i in poses if tiers[i]=='supported'];uncertain=[i for i in poses if tiers[i]=='uncertain']
    blank=np.zeros(tuple(pixel_size[::-1]),bool)
    cov_support=np.logical_or.reduce([masks[i] for i in supported]) if supported else blank.copy()
    cov_uncertain=np.logical_or.reduce([masks[i] for i in uncertain]) if uncertain else blank.copy()
    cov_all=np.logical_or.reduce(list(masks.values())) if masks else blank.copy()
    def representatives(ids,first=None):
        chosen=[first] if first in ids else [];covered=masks[first].copy() if chosen else blank.copy()
        while set(ids)-set(chosen):
            i=max(sorted(set(ids)-set(chosen)),key=lambda j:int((masks[j]&~covered).sum()))
            if chosen and int((masks[i]&~covered).sum())<.035*(502*raster_scale)**2:break
            chosen.append(i);covered|=masks[i]
        return chosen
    rep=representatives(supported,graph['reference']);extra=representatives(uncertain)
    def export(name,order):
        canvas=Image.new('RGB',tuple(pixel_size),'white')
        for i in order:
            m=np.diag([raster_scale,raster_scale,1])@offset@poses[i];inv=np.linalg.inv(m)
            raw=ndi.affine_transform(images[i],inv[:2,:2][::-1,::-1],inv[:2,2][::-1],output_shape=tuple(pixel_size[::-1]),order=1)
            canvas.paste(Image.fromarray(raw).convert('RGB'),(0,0),Image.fromarray(np.uint8(masks[i])*255))
            poly=apply(corners,m);draw=ImageDraw.Draw(canvas);color='#be7625' if tiers[i]=='uncertain' else '#647078'
            draw.line([tuple(p) for p in np.vstack([poly,poly[0]])],fill=color,width=2 if tiers[i]=='uncertain' else 1)
            label=apply([15,490],m);draw.text(tuple(label),str(i+1).zfill(2),fill='#ffcf68',stroke_width=1,stroke_fill='#26333c')
        canvas.save(folder/name)
    export('montage.png',list(reversed(rep)))
    export('with_uncertain.png',list(reversed(rep))+list(reversed(extra)))
    counts=Counter(tiers.values());unit=(spacing/raster_scale)**2/1e6
    summary=dict(group=group,total=len(infos),eligible=len(infos)-counts['excluded'],supported=counts['supported'],uncertain=counts['uncertain'],
        unlocalized=counts['unlocalized'],excluded=counts['excluded'],placed=len(poses),origin_kind=graph['origin_kind'],
        reference_index=graph['reference'],canvas_size=size.tolist(),canvas_origin=(-lo).tolist(),spacing_um=spacing,
        supported_coverage_mm2=float(cov_support.sum()*unit),proposed_coverage_mm2=float(cov_all.sum()*unit),
        uncertain_coverage_mm2=float(cov_uncertain.sum()*unit),
        supported_field_equivalents=float(cov_support.sum()/max(1,(502*raster_scale)**2)),
        proposed_field_equivalents=float(cov_all.sum()/max(1,(502*raster_scale)**2)),coverage_raster_step_um=spacing/raster_scale,
        representative_indices=rep,uncertain_representative_indices=extra,draw_order=list(reversed(rep)),
        accepted_edges=len(graph['edges']),quarantined_edges=len(graph['rejected']),anatomical_directions='unconfirmed',date_policy='pooled')
    result=dict(summary=summary,scans=records,groups=groups,graph=graph)
    write(folder/'montage.json',result);(folder/'data.js').write_text('window.MONTAGE='+json.dumps(result,allow_nan=False)+';',encoding='utf-8')
    shutil.copyfile(Path(__file__).with_name('cohort_viewer.html'),folder/'index.html')
    shutil.copyfile(Path(__file__).with_name('cohort_viewer.js'),folder/'cohort_viewer.js')
    (folder/'OPEN_MONTAGE.cmd').write_text('@echo off\nstart "" "%~dp0index.html"\n')
    (folder/'REPORT.md').write_text(f'''# {group}: pooled retinal montage

{len(infos)} source scans: {counts['supported']} overlap-supported, {counts['uncertain']} uncertain proposals, {counts['unlocalized']} unlocalized, {counts['excluded']} explicitly excluded.

Origin: **{graph['origin_kind']}**. Dates are pooled at the user's request; animal and eye are never mixed. Unresolved origins use a reference-field coordinate system, not a claimed optic-disc location.

Supported union coverage: approximately **{summary['supported_coverage_mm2']:.2f} mm²**, or **{summary['supported_field_equivalents']:.2f} single-field areas**. Including tentative placements gives {summary['proposed_coverage_mm2']:.2f} mm²; that separate number is not established retinal coverage. Scale is approximate, 1460/512 µm per native pixel. Coverage is rasterized at {summary['coverage_raster_step_um']:.2f} µm and excludes five border pixels and nonfinite observations.

The reviewer has independent Supported and Flagged / uncertain toggles. Uncertain proposals cannot adjust the supported graph. Fields without defensible spatial evidence remain available as native images. Explicit exclusions have no atlas transform.

{len(graph['edges'])} accepted overlap constraints; {len(graph['rejected'])} conflicting constraints quarantined. Registration uses vessel-anchored SIFT, full-rotation vessel-curve searches, rigid symmetric-distance refinement, neighbor consensus and joint pose fitting. Single-link fields, inconsistent overlaps, geometry-only low-contrast recovery and tentative connections carry visible reasons. No tissue is synthesized or stretched.

All placements are automatic research proposals. Internal agreement is not independent accuracy. Pooled scans may show different lesion appearances and acquisition artifacts. Neither temporal/nasal orientation nor a single-day biological state is inferred.

`registration.json`, `pair_evidence.json` and `montage.json` retain candidate transforms, alternatives, masks' provenance and review reasons. `cache_context.json` pins all consumed source files and registration code. The original data, human labels, v1 run and TS247 pilot remain unchanged.
''',encoding='utf-8')
    return summary

def audit(root,partial=False):
    expected={r['scan_id']:r for r in [read(p) for p in (BASE/'prepared').glob('*.json')]}
    found={};hashes={};checks=[]
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not (folder/'montage.json').exists():continue
        data=read(folder/'montage.json');context=read(folder/'cache_context.json');group=data['summary']['group']
        if not partial:
            assert (folder/'review_registration.json').exists(),'ONH consistency pass missing: '+group
            reviewed=read(folder/'review_registration.json')
            for a in reviewed.get('anatomy_audit',{}).get('centers',[]):
                if not a['consistent']:assert data['graph']['tiers'][str(a['scan'])]!='supported'
        for r in data['scans']:
            sid=r['scan_id'];assert sid not in found,sid;found[sid]=group
            assert r['animal']+'_'+r['eye']==group
            if r['tier']=='excluded':assert 'matrix_to_onh_pixels' not in r
            if 'matrix_to_onh_pixels' in r:
                m=np.array(r['matrix_to_onh_pixels']);assert np.isfinite(m).all()
                np.testing.assert_allclose(m[:2,:2].T@m[:2,:2],np.eye(2),atol=1e-7)
                assert abs(np.linalg.det(m[:2,:2])-1)<1e-7
                np.testing.assert_allclose(m@np.array(r['matrix_from_onh_pixels']),np.eye(3),atol=1e-7)
            for e in data['graph']['edges']:
                a,b=data['scans'][e['a']],data['scans'][e['b']]
                assert (a['animal'],a['eye'])==(b['animal'],b['eye'])
        hashes.update(context['sources']);checks.append(group)
    if not partial:assert set(found)==set(expected),(len(found),len(expected),set(expected)-set(found))
    for path,h in hashes.items():assert sha(path)==h,path
    result=dict(status='partial' if partial else 'passed',scans_accounted_for=len(found),expected_scans=len(expected),groups=len(checks),
                unchanged_source_files=len(hashes),identity_separation=True,exclusions_without_transform=True,rigid_inverses=True)
    write(root/'verification.json',result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=DEFAULT_OUT);ap.add_argument('--partial',action='store_true');args=ap.parse_args();root=args.output
    plan=read(root/'run_plan.json');groups=plan['groups'];summaries=[]
    for group in groups:
        folder=root/group
        if (folder/'review_registration.json').exists():summaries.append(render_group(folder,groups))
    totals={k:sum(s[k] for s in summaries) for k in ['total','eligible','supported','uncertain','unlocalized','excluded','placed']}
    write(root/'summary.json',dict(groups=summaries,totals=totals,version=VERSION))
    cards=[]
    for s in summaries:
        g=s['group'];cards.append(f'<a class="card" href="{g}/index.html"><img src="{g}/montage.png" alt="{g} supported montage"><h2>{g.replace("_"," ")}</h2><p>{s["supported"]} supported · {s["uncertain"]} flagged · {s["unlocalized"]} unlocalized</p><small>{s["origin_kind"].replace("_"," ")} · {s["supported_field_equivalents"]:.1f}× field coverage</small></a>')
    page=f'''<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>octa-reg_v2 · Retinal atlas reviewer</title><style>body{{font:15px system-ui;margin:0;background:#edf1f3;color:#1c3d49}}header{{padding:35px 5vw;background:white;border-bottom:1px solid #d5e0e4}}h1{{margin:0;font-size:30px}}header p{{color:#607781}}main{{padding:25px 5vw;display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px}}.card{{background:white;border:1px solid #d5e0e4;border-radius:10px;padding:15px;color:inherit;text-decoration:none}}.card:hover{{border-color:#347a84}}img{{width:100%;height:240px;object-fit:contain}}h2{{margin:12px 0 5px}}p{{margin:6px 0}}small{{color:#68808b}}a{{color:#246674}}</style><header><h1>Retinal atlas reviewer · octa-reg_v2</h1><p>Animal and eye separated · Dates pooled · Automatic placements for review</p><b>{totals['total']} scans · {len(summaries)}/{len(groups)} groups ready · {totals['supported']} supported · {totals['uncertain']} flagged · {totals['unlocalized']} unlocalized · {totals['excluded']} excluded</b><p>Each map has independent Supported and Flagged / uncertain toggles. Estimated or unresolved ONH origins remain labeled. <a href="REPORT.md">Methods and run report</a></p></header><main>{''.join(cards)}</main></html>'''
    (root/'index.html').write_text(page,encoding='utf-8');(root/'OPEN_REVIEWER.cmd').write_text('@echo off\nstart "" "%~dp0index.html"\n')
    result=audit(root,args.partial)
    if not args.partial:
        sources={}
        for s in summaries:sources.update(read(root/s['group']/'cache_context.json')['sources'])
        publication=dict(version=VERSION,totals=totals,groups=groups,verification=result,
            code_hashes={str(p):sha(p) for p in Path(__file__).parent.glob('cohort*') if p.is_file()},
            skill_sha256=sha(ROOT/'outputs/octa-reg_v2/skill/octa-reg_v2/SKILL.md'),
            source_hashes=sources,
            derived_registration_hashes={s['group']:sha(root/s['group']/'review_registration.json') for s in summaries})
        write(root/'PUBLICATION.json',publication)
    (root/'REPORT.md').write_text(f'''# octa-reg_v2: all-sample retinal registration

{len(summaries)} animal-eye groups; {totals['total']} scans accounted for. Dates pooled by request. OD and OS are always separate. {totals['supported']} supported placements, {totals['uncertain']} uncertain proposals, {totals['unlocalized']} unlocalized fields, {totals['excluded']} explicit exclusions.

The placement reviewer starts with both supported and flagged fields visible. **Show flagged / uncertain** toggles best-effort proposals with orange outlines and their reasons. Day checkboxes, confirmation, and drag/rotate correction are described in `REVIEW_GUIDE.md`; saved placement reviews remain separate from this automatic report. Selecting a field exposes its native image, source date, reasons and overlap evidence; opacity and blink permit visual inspection. An unlocalized field remains inspectable without a fabricated position.

Maps without a reviewed disc explicitly distinguish an estimated ONH from an unresolved reference-field origin. Vessel convergence is a directional clue, not a substitute for registration. Tentative overlaps and anatomy-only placements cannot move the supported backbone or enter the supported-coverage total.

Methods follow the `octa-reg_v2` skill: vessel-anchored SIFT, rigid RANSAC, symmetric centerline refinement, whole-vessel full-rotation searches, neighbor-consensus checks, global rigid fitting, and separately flagged low-contrast or tentative proposals. A separate ONH-consistency pass constrains alignment using reviewed disc centers, rejects anatomically contradictory edges and flags remaining origin disagreements. Thresholds and the search plan are in the source code pinned per group; `anatomy_code_hashes.json` pins the additional check. No layer segmentation, RAW reconstruction, training, label editing, nonrigid distortion or synthesized tissue was performed.

Verification: {result['status']}; {result['scans_accounted_for']} inventory rows; {result['unchanged_source_files']} consumed source files unchanged. Every stored pose and inverse is rigid and finite; explicit exclusions lack transforms; every edge remains within one animal-eye group. These checks and internal overlap scores do not establish independent registration accuracy. Review the flagged fields before interpreting coverage or making anatomical measurements.

The original TS247 OD pilot and v1 outputs are preserved. Run details and all candidate evidence are in each group's folder. Open `OPEN_REVIEWER.cmd` to use the loopback-only save-enabled review server. A generic static server cannot save placement reviews.
''',encoding='utf-8')
    publish(root)
    print(json.dumps(dict(totals=totals,verification=result),indent=2))

if __name__=='__main__':main()

