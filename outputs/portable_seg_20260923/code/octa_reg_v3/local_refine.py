"""Bounded, read-only-source polishing of an existing human montage.

No global search, scaling, new placements, or alteration of source review files.
Changed poses are new automatic drafts; flags and notes are carried unchanged.
"""
import argparse,copy,json,shutil
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from scipy import ndimage as ndi
from scipy.optimize import minimize
from PIL import Image,ImageDraw
from octa_reg_v2.run import ROOT,read,write,sha,apply
from octa_reg_v2.cohort import load_group
from octa_reg_v2.cohort_report import render_group
from .review_server import current,analysis_records

CENTER=np.array([255.5,255.5])
CORNERS=np.array([[0,0],[511,0],[511,511],[0,511]])
LIMIT_PX=8.
LIMIT_DEG=1.

def adjusted(base,p):
    """p = angle in degrees, world dx/dy at native field center."""
    theta=np.deg2rad(p[0]);r=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    m=np.array(base,copy=True);c=apply(CENTER,base)
    m[:2,:2]=r@base[:2,:2];m[:2,2]=c+np.asarray(p[1:])-m[:2,:2]@CENTER
    return m

def motion(base,m):
    delta=m[:2,:2]@base[:2,:2].T
    return dict(rotation_deg=float(np.degrees(np.arctan2(delta[1,0],delta[0,0]))),
                center_shift_px=float(np.linalg.norm(apply(CENTER,m)-apply(CENTER,base))),
                max_corner_shift_px=float(np.max(np.linalg.norm(apply(CORNERS,m)-apply(CORNERS,base),axis=1))))

def corr(x,y):
    x=x-x.mean();y=y-y.mean();den=np.linalg.norm(x)*np.linalg.norm(y)
    return float(x@y/den) if den>1e-8 else 0.

def prepare(s):
    im=s['image'];smooth=ndi.gaussian_filter(im,8)
    hp=(im-smooth)/np.maximum(ndi.gaussian_filter((im-smooth)**2,8)**.5,.035)
    s['channels']=np.stack([ndi.gaussian_filter(im,1.5)-ndi.gaussian_filter(im,18),
                            ndi.gaussian_filter(np.clip(hp,-3,3),.6)]).astype('float32')
    s['thin_valid']=s['valid']&~ndi.binary_dilation(s['vessel'],iterations=5)

def pair_points(a,b,m):
    yy,xx=np.mgrid[20:492:6,20:492:6];pts=np.c_[xx.ravel(),yy.ravel()].astype(float)
    q=apply(pts,m)
    ok=(q.min(1)>24)&(q.max(1)<487)&a['valid'][pts[:,1].astype(int),pts[:,0].astype(int)]
    ok&=ndi.map_coordinates(b['valid'].astype(float),q[:,::-1].T,order=0,mode='constant',cval=0)>.5
    # Checkerboard held-out samples are not used to fit the transform.
    split=((xx.ravel()//6+yy.ravel()//6)%2).astype(bool)
    return pts[ok&~split],pts[ok&split]

def evidence(a,b,ma,mb,pts):
    if len(pts)<180:return None
    q=apply(pts,np.linalg.inv(mb)@ma)
    ok=(q.min(1)>8)&(q.max(1)<503)
    ok&=ndi.map_coordinates(b['valid'].astype(float),q[:,::-1].T,order=0,mode='constant',cval=0)>.5
    pts=pts[ok];q=q[ok]
    if len(q)<180:return None
    aa=a['channels'][:,pts[:,1].astype(int),pts[:,0].astype(int)]
    bb=np.array([ndi.map_coordinates(ch,q[:,::-1].T,order=1,mode='nearest') for ch in b['channels']])
    large=corr(aa[0],bb[0]);detail=corr(aa[1],bb[1])
    thin=a['thin_valid'][pts[:,1].astype(int),pts[:,0].astype(int)]
    thin&=ndi.map_coordinates(b['thin_valid'].astype(float),q[:,::-1].T,order=0,mode='constant',cval=0)>.5
    small=corr(aa[1,thin],bb[1,thin]) if thin.sum()>=150 else None
    value=.45*large+.35*detail+.2*(small if small is not None else detail)
    return dict(score=value,large_corr=large,detail_corr=detail,small_corr=small,pixels=len(q),small_pixels=int(thin.sum()))

def run(source,out,limit_px=LIMIT_PX,limit_deg=LIMIT_DEG,source_url='http://127.0.0.1:8771/TS241_OD/index.html'):
    LIMIT_PX=float(limit_px);LIMIT_DEG=float(limit_deg)
    if not (0<LIMIT_PX<=50 and 0<LIMIT_DEG<=10):raise ValueError('Local refinement requires positive bounded limits')
    source=Path(source).resolve();out=Path(out)
    if out.exists():raise ValueError('Use a fresh output directory')
    group=source.name;folder=out/group;folder.mkdir(parents=True)
    doc=read(source/'montage.json');review=current(source,doc);rows=analysis_records(doc,review)
    source_hashes={str(source/n):sha(source/n) for n in ('montage.json','human_review.json') if (source/n).exists()}
    source_record=source/('human_review.json' if (source/'human_review.json').exists() else 'montage.json')
    review['_source_description']=str(source_record)
    review['_limits']=dict(center_translation_px=LIMIT_PX,rotation_deg=LIMIT_DEG)
    write(out/'source_review_snapshot.json',review);write(out/'source_analysis_records.json',rows)
    scans,context=load_group(group,folder)
    assert [s['info']['scan_id'] for s in scans]==[r['scan_id'] for r in rows]
    base={i:np.array(r['matrix_to_current_origin_pixels']) for i,r in enumerate(rows)
          if r['matrix_to_current_origin_pixels'] is not None and r['review_tier']!='excluded'}
    poses={i:m.copy() for i,m in base.items()};tiers={i:r['review_tier'] for i,r in enumerate(rows)}
    reference=doc['summary']['reference_index'];assert reference in base
    for i in base:prepare(scans[i])
    edges=[];pairlog=[]
    for a in base:
        for b in base:
            if a>=b:continue
            tr,va=pair_points(scans[a],scans[b],np.linalg.inv(base[b])@base[a])
            ev=evidence(scans[a],scans[b],base[a],base[b],tr)
            if ev is None:continue
            accepted=ev['large_corr']>.22 and ev['detail_corr']>.10 and ev['score']>.17 and len(tr)>=250
            pairlog.append(dict(a=a,b=b,initial=ev,accepted=bool(accepted)))
            if accepted:edges.append(dict(a=a,b=b,train=tr,validation=va,before=ev))
    # Limit repeated scans' influence; supported nodes cannot follow flagged nodes.
    neighbors={i:[] for i in base}
    for i in base:
        candidates=[e for e in edges if i in (e['a'],e['b']) and (tiers[i]!='supported' or tiers[e['b'] if i==e['a'] else e['a']]=='supported')]
        candidates.sort(key=lambda e:e['before']['score']*min(1,len(e['train'])/1200),reverse=True)
        neighbors[i]=candidates[:5]
    history=[];params={i:np.zeros(3) for i in base}
    for sweep in range(2):
        order=sorted(base,key=lambda i:(tiers[i]!='supported',-len(neighbors[i]),i))
        for i in order:
            if i==reference or not neighbors[i]:continue
            es=neighbors[i]
            def values(p,key):
                m=adjusted(base[i],p);vals=[]
                for e in es:
                    ma=m if e['a']==i else poses[e['a']];mb=m if e['b']==i else poses[e['b']]
                    vals.append(evidence(scans[e['a']],scans[e['b']],ma,mb,e[key]))
                return vals
            def average(v):return np.mean([r['score'] for r in v if r is not None]) if any(r is not None for r in v) else -1.
            def objective(p):
                # Gentle prior plus a hard radius limit prevents accumulation/drift.
                return -average(values(p,'train'))+.003*(np.sum(np.asarray(p[1:])**2)/LIMIT_PX**2+(p[0]/LIMIT_DEG)**2)
            constraint={'type':'ineq','fun':lambda p:LIMIT_PX**2-p[1]**2-p[2]**2}
            starts=[params[i].copy(),np.zeros(3)]
            if sweep==0:
                step=min(10.,LIMIT_PX*.4)
                starts.extend([np.array([0.,dx,dy]) for dx,dy in [(-step,0),(step,0),(0,-step),(0,step)]])
                if LIMIT_DEG>1:starts.extend([np.array([angle,0.,0.]) for angle in [-LIMIT_DEG/2,LIMIT_DEG/2]])
            results=[minimize(objective,p,method='SLSQP',bounds=[(-LIMIT_DEG,LIMIT_DEG),(-LIMIT_PX,LIMIT_PX),(-LIMIT_PX,LIMIT_PX)],constraints=[constraint],options={'maxiter':45,'ftol':1e-6,'eps':.03}) for p in starts]
            valid=[r for r in results if np.isfinite(r.fun) and np.linalg.norm(r.x[1:])<=LIMIT_PX+1e-5]
            if not valid:continue
            best=min(valid,key=lambda r:r.fun);old=values(params[i],'validation');new=values(best.x,'validation')
            gain=average(new)-average(old)
            losses=[n['score']-o['score'] for n,o in zip(new,old) if n and o]
            detail_loss=np.mean([n['detail_corr']-o['detail_corr'] for n,o in zip(new,old) if n and o])
            accept=bool(gain>.002 and detail_loss>=-.002 and min(losses,default=0)>-.035)
            if accept:params[i]=best.x;poses[i]=adjusted(base[i],best.x)
            history.append(dict(sweep=sweep+1,index=i,accepted=accept,heldout_gain=float(gain),detail_change=float(detail_loss),worst_pair_change=float(min(losses,default=0)),proposal=best.x.tolist(),neighbors=len(es)))
            print(f'pass {sweep+1} field {i+1:02}: {"kept" if accept else "unchanged"}; held-out gain {gain:.4f}',flush=True)
    # Final per-field regression guard compares the completed montage to the human baseline.
    for _ in range(3):
        bad=[]
        for i in base:
            if np.allclose(poses[i],base[i]):continue
            es=neighbors[i];old=[];new=[]
            for e in es:
                old.append(evidence(scans[e['a']],scans[e['b']],base[e['a']],base[e['b']],e['validation']))
                new.append(evidence(scans[e['a']],scans[e['b']],poses[e['a']],poses[e['b']],e['validation']))
            if average(new)<average(old)-.002:bad.append(i)
        if not bad:break
        for i in bad:poses[i]=base[i].copy();params[i]=np.zeros(3)
    deltas=[]
    for i in base:
        d=motion(base[i],poses[i]);d.update(index=i,scan_id=rows[i]['scan_id'],changed=not np.allclose(base[i],poses[i],atol=1e-8))
        assert d['center_shift_px']<=LIMIT_PX+1e-4 and abs(d['rotation_deg'])<=LIMIT_DEG+1e-4
        assert d['max_corner_shift_px']<=LIMIT_PX+2*np.linalg.norm(CENTER)*np.sin(np.deg2rad(LIMIT_DEG)/2)+1e-4
        np.testing.assert_allclose(poses[i][:2,:2].T@poses[i][:2,:2],np.eye(2),atol=1e-8)
        deltas.append(d)
    np.testing.assert_array_equal(poses[reference],base[reference])
    evaluations=[]
    for e in edges:
        before=evidence(scans[e['a']],scans[e['b']],base[e['a']],base[e['b']],e['validation'])
        after=evidence(scans[e['a']],scans[e['b']],poses[e['a']],poses[e['b']],e['validation'])
        evaluations.append(dict(a=e['a'],b=e['b'],before=before,after=after))
    write(out/'refinement_evidence.json',dict(source=source_hashes,source_revision=review['revision'],limits=dict(center_translation_px=LIMIT_PX,rotation_deg=LIMIT_DEG),anchor_index=reference,deltas=deltas,pairs=evaluations,candidates=pairlog,history=history))
    # Publish a new baseline. Human approval never transfers to a changed pose.
    registration=read(source/'review_registration.json');graph=registration['graph']
    graph['poses']={str(i):m.tolist() for i,m in poses.items()};graph['tiers']={str(i):tiers[i] for i in range(len(rows))}
    graph['edges']=[];graph['rejected']=[];graph['reference']=reference
    graph['origin_kind']=review.get('onh_origin_kind',doc['summary']['origin_kind'])
    graph['reasons']={str(i):['Local refinement from saved human placement; original review category retained.'] for i in range(len(rows))}
    write(folder/'review_registration.json',registration);render_group(folder,[group])
    refined=read(folder/'montage.json');carried=copy.deepcopy(rows)
    for i,r in enumerate(carried):
        r['matrix_to_current_origin_pixels']=poses[i].tolist() if i in poses else None
        if i in poses and not np.allclose(poses[i],base[i],atol=1e-8):r['placement_confirmed']=False
        r['eligible_for_primary_analysis']=False
    refined['inherited_review']=dict(source=str(source_record),revision=review['revision'],montage_confirmed=False,records=carried)
    refined['local_refinement']=dict(source_revision=review['revision'],limits=dict(translation_px=LIMIT_PX,rotation_deg=LIMIT_DEG),deltas=deltas)
    refined['summary']['version']='octa-reg_v3 bounded local refinement'
    # Preserve v3's documented frozen CNV overlays as display context only.
    previous=read(ROOT/'outputs/octa-reg_v3'/group/'montage.json');cnvs={s['scan_id']:s for s in previous['scans']}
    for s in refined['scans']:
        prior=cnvs.get(s['scan_id'],{})
        if 'cnv' in prior:s['cnv']=prior['cnv']
        if prior.get('cnv_image'):
            s['cnv_image']=prior['cnv_image'];shutil.copyfile(ROOT/'outputs/octa-reg_v3'/group/prior['cnv_image'],folder/s['cnv_image'])
    write(folder/'montage.json',refined)
    (folder/'data.js').write_text('window.MONTAGE='+json.dumps(refined,allow_nan=False)+';',encoding='utf-8')
    for name in ('cohort_viewer.html','cohort_viewer.js'):
        shutil.copyfile(Path(__file__).with_name(name),folder/('index.html' if name.endswith('.html') else name))
    page=(folder/'index.html').read_text(encoding='utf-8')
    page=page.replace('<header>',f'<div style="padding:10px;background:#fff2ce;color:#493600;flex:none">TS241 OD local refinement · max {LIMIT_PX:g} px / {LIMIT_DEG:g}° from the previous reviewer · changed images need confirmation. <a href="../comparison.html">Compare before / after</a></div><header>',1)
    page=page.replace('All animal–eye groups','Before / after comparison').replace('Release PNGs include inherited TS165 edits; they do not incorporate later v3 edits.','Release PNGs show this local refinement; later manual edits are saved separately.')
    (folder/'index.html').write_text(page,encoding='utf-8')
    # Both comparison renders share origin, extent, pixel scale and draw order.
    comparison(out,scans,base,poses,tiers,reference,deltas,LIMIT_PX,LIMIT_DEG,source_url)
    for p,h in source_hashes.items():assert sha(p)==h,'Source review changed during run; preserve output and rerun from current review.'
    for p,h in context['sources'].items():assert sha(p)==h
    from .review_server import current as v3current,analysis_records as v3records
    loaded=v3records(refined,v3current(folder,refined))
    for old,new in zip(rows,loaded):assert old['review_tier']==new['review_tier'] and old['notes']==new['notes']
    assert not v3current(folder,refined)['montage_confirmed']
    for d,r in zip(deltas,[loaded[i] for i in base]):assert not d['changed'] or not r['placement_confirmed']
    report(out,review,deltas,evaluations,reference)
    write(out/'VERIFIED.json',dict(passed=True,source_review_revision=review['revision'],unchanged_source_hashes=source_hashes,prepared_sources_checked=len(context['sources']),pose_bounds_checked=True,rigid_only=True,anchor_unchanged=True,flags_notes_preserved=True,changed_poses_unconfirmed=True,code_sha256=sha(__file__)))
    print('COMPLETE',str(out),flush=True)

def comparison(out,scans,before,after,tiers,reference,deltas,limit_px=LIMIT_PX,limit_deg=LIMIT_DEG,source_url='http://127.0.0.1:8771/TS241_OD/index.html'):
    coords=np.concatenate([apply(CORNERS,m) for poses in (before,after) for m in poses.values()])
    low=np.floor(coords.min(0)-30);high=np.ceil(coords.max(0)+30);scale=min(1,1600/max(high-low));size=np.ceil((high-low)*scale).astype(int)
    offset=np.eye(3);offset[:2,2]=-low;rescale=np.diag([scale,scale,1])
    # Same deterministic layering puts supported scans above flagged scans.
    order=sorted(before,key=lambda i:(tiers[i]=='supported',i))
    for name,poses in [('before',before),('after',after)]:
        canvas=Image.new('RGB',tuple(size),'#e9edf0')
        for i in order:
            m=rescale@offset@poses[i];inv=np.linalg.inv(m)
            raw=np.uint8(scans[i]['image']*255);mask=scans[i]['finite'].copy();mask[:6]=mask[-6:]=False;mask[:,:6]=mask[:,-6:]=False
            coeff=tuple(inv[:2].ravel())
            im=Image.fromarray(raw).transform(tuple(size),Image.Transform.AFFINE,coeff,Image.Resampling.BILINEAR)
            mm=Image.fromarray(np.uint8(mask)*255).transform(tuple(size),Image.Transform.AFFINE,coeff,Image.Resampling.NEAREST)
            canvas.paste(im.convert('RGB'),(0,0),mm)
            draw=ImageDraw.Draw(canvas);point=apply([20,480],m);draw.text(tuple(point),str(i+1),fill='#ffd16b',stroke_width=1,stroke_fill='#26333c')
        canvas.save(out/(name+'.png'))
    table=''.join(f'<tr><td>{d["index"]+1}</td><td>{d["center_shift_px"]:.2f} px</td><td>{d["rotation_deg"]:+.3f}°</td><td>{"Refined draft" if d["changed"] else "Unchanged"}</td></tr>' for d in deltas)
    (out/'comparison.html').write_text('''<!doctype html><meta charset="utf-8"><title>TS241 OD — gentle refinement</title><style>body{font:16px system-ui;background:#eef2f4;color:#183b45;margin:24px}a{color:#176e83}button{padding:10px 16px;font:inherit;cursor:pointer}img{max-width:100%;background:white;border:1px solid #bac9cf}table{border-collapse:collapse}td,th{padding:7px 16px;border-bottom:1px solid #c9d4d9}p{max-width:1000px}#label{font-weight:700}</style><h1>TS241 OD · gentle refinement</h1><p>Your placements are the starting point. Each image stays within 8 native pixels of translation and 1° of rotation; the reference is fixed. No resizing. Flags and notes are retained. Changed placements are drafts for your review.</p><p><a href="TS241_OD/index.html">Open save-enabled refined reviewer</a> · <a href="http://127.0.0.1:8771/TS241_OD/index.html">Original saved montage</a> · <a href="REPORT.md">Measurements</a></p><button id="toggle">Show refined</button> <span id="label">Your saved placements</span><p>Click the button or press Space to blink. Both views use identical pixel scale, origin, and layering. All images are included.</p><img id="view" src="before.png" alt="TS241 OD montage"><h2>Changes by reviewer field number</h2><table><tr><th>Field</th><th>Center movement</th><th>Rotation</th><th>Result</th></tr>'''+table+'''</table><script>let after=false;const images=[new Image(),new Image()];images[0].src='before.png';images[1].src='after.png';function flip(){after=!after;document.querySelector('#view').src=after?'after.png':'before.png';document.querySelector('#label').textContent=after?'Refined proposal':'Your saved placements';document.querySelector('#toggle').textContent=after?'Show original':'Show refined'}document.querySelector('#toggle').onclick=flip;document.onkeydown=e=>{if(e.code==='Space'){e.preventDefault();flip()}};</script>''',encoding='utf-8')
    page=(out/'comparison.html').read_text(encoding='utf-8')
    page=page.replace('8 native pixels of translation and 1°',f'{limit_px:g} native pixels of translation and {limit_deg:g}°')
    page=page.replace('http://127.0.0.1:8771/TS241_OD/index.html',source_url).replace('Original saved montage','Previous reviewer').replace('Your saved placements','Starting placements').replace('Your placements are the starting point.','The previous reviewer’s placements are the starting point.')
    (out/'comparison.html').write_text(page,encoding='utf-8')
    shutil.copyfile(out/'comparison.html',out/'index.html')

def report(out,review,deltas,edges,reference):
    moved=[d for d in deltas if d['changed']];before=np.array([e['before']['score'] for e in edges]);after=np.array([e['after']['score'] for e in edges])
    lines=['# TS241 OD: bounded local alignment','',f'Started from {review.get("_source_description", "saved source review")}; local review revision {review["revision"]}. Source montage confirmed: {review["montage_confirmed"]}. Source files remain unchanged. Inherited history: {review.get("inherited_from")}. Limits: {review.get("_limits")}.', '',
           f'{len(moved)} of {len(deltas)} fields received small automatic adjustments. Field {reference+1} is fixed. Maximum center movement: {max(d["center_shift_px"] for d in deltas):.3f} native px; maximum absolute rotation: {max(abs(d["rotation_deg"]) for d in deltas):.3f}°; maximum corner movement: {max(d["max_corner_shift_px"] for d in deltas):.3f} px.', '',
           f'{len(edges)} usable existing overlaps. Mean held-out alignment score: {before.mean():.4f} before -> {after.mean():.4f} after. Improved pairs: {int((after>before+.002).sum())}; decreased by more than .002: {int((after<before-.002).sum())}. These are internal registration scores, not independent anatomical accuracy.', '',
           'The objective combines broad structural vessel contrast, locally normalized detail, and detail outside dilated large-vessel masks. Only already overlapping images were considered. Spatially interleaved pixels held out from fitting were used to accept/reject each proposal. At most five stronger neighbors influence a field; flagged fields cannot pull supported fields. All limits are relative to the original saved pose, not cumulative between passes. Scale, shear, and reflection are forbidden.', '',
           'The original flagged/supported categories and notes are retained exactly. Modified images lose individual confirmation in this new proposal; unchanged confirmations are retained with source attribution. The new whole montage is unconfirmed. Source review history is untouched. Pink CNV overlays retain the frozen v3 display sources and did not drive this local fit.', '',
           'Residual mismatch can remain from image contrast, vessel projection width, motion, or scale differences. Local rigid adjustment cannot remove those distortions. No layer or CNV segmentation was rerun.', '',
           '| Field | Center shift (px) | Rotation (degrees) | Maximum corner shift (px) |','|---|---:|---:|---:|']
    lines.extend(f'| {d["index"]+1} | {d["center_shift_px"]:.3f} | {d["rotation_deg"]:+.3f} | {d["max_corner_shift_px"]:.3f} |' for d in deltas)
    (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    shutil.copyfile(out/'REPORT.md',out/'TS241_OD/REPORT.md')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--max-translation',type=float,default=LIMIT_PX);ap.add_argument('--max-rotation',type=float,default=LIMIT_DEG);ap.add_argument('--source-url',default='http://127.0.0.1:8771/TS241_OD/index.html');args=ap.parse_args();run(args.source,args.output,args.max_translation,args.max_rotation,args.source_url)
