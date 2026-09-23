"""Overlap graph, robust rigid pose fitting and review products."""
import json, math
import numpy as np
from scipy.optimize import least_squares
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont
from .run import OUT, BASE, ROOT, read, write, load, matrix, params, apply, sha

ROOT_INDEX=6 # Reviewed, fully visible disc in before-laser s10.
CORNERS=np.array([[0,0],[511,0],[511,511],[0,511],[255.5,255.5]])

def edges():
    items=[]
    for folder in ['pairs','curve_pairs','consensus_pairs']:
        for path in sorted((OUT/folder).glob('*.json')):
            r=read(path)
            if r.get('accepted'):items.append(r)
    unique={}
    for r in items:
        key=tuple(sorted((r['a'],r['b'])))
        if key not in unique or r['score']>unique[key]['score']:unique[key]=r
    return sorted(unique.values(),key=lambda r:-r['score'])

def solve(scans, ee):
    eligible={i for i,s in enumerate(scans) if not s['excluded']}
    ee=[e for e in ee if e['a'] in eligible and e['b'] in eligible]
    disc=np.array(scans[ROOT_INDEX]['info']['visible_onh']['center_um'])/np.array(scans[ROOT_INDEX]['info']['spacing'])[::-1]
    origin=matrix([0,*-disc]);poses={ROOT_INDEX:origin};tree=[]
    while True:
        candidates=[e for e in ee if (e['a'] in poses)!=(e['b'] in poses)]
        if not candidates:break
        e=max(candidates,key=lambda x:x['score']);a,b=e['a'],e['b'];m=np.array(e['matrix'])
        if a in poses:poses[b]=poses[a]@np.linalg.inv(m)
        else:poses[a]=poses[b]@m
        tree.append((a,b))
    # A high-scoring wrong trunk can enter the initial tree. Prefer agreement
    # across multiple established neighbors before rejecting loop edges.
    for iteration in range(4):
        changed=False
        for i in sorted(set(poses)-{ROOT_INDEX}):
            incident=[e for e in ee if i in (e['a'],e['b']) and e['a'] in poses and e['b'] in poses]
            proposals=[]
            for e in incident:
                a,b=e['a'],e['b'];m=np.array(e['matrix'])
                proposals.append(poses[b]@m if a==i else poses[a]@np.linalg.inv(m))
            def agreement(p):
                distances=np.array([np.sqrt(np.mean((apply(CORNERS,p)-apply(CORNERS,q))**2)) for q in proposals])
                return int((distances<30).sum()),float(sum(e['score'] for e,d in zip(incident,distances) if d<30))
            if proposals:
                candidate=max(proposals,key=agreement)
                if agreement(candidate)[0]>=max(3,agreement(poses[i])[0]+2):
                    poses[i]=candidate;changed=True
        if not changed:break
    usable=[];quarantine=[]
    for e in ee:
        a,b=e['a'],e['b']
        if a not in poses or b not in poses:continue
        delta=apply(CORNERS,poses[a])-apply(apply(CORNERS,np.array(e['matrix'])),poses[b])
        e['initial_loop_rms_px']=float(np.sqrt(np.mean(delta**2)))
        e['tree_edge']=(a,b) in tree
        if e['initial_loop_rms_px']<=30:usable.append(e)
        else:quarantine.append(e)
    members=sorted(set(poses)-{ROOT_INDEX}); lookup={idx:k for k,idx in enumerate(members)}
    def unpack(p):return {ROOT_INDEX:origin,**{idx:matrix(p[3*k:3*k+3]) for idx,k in lookup.items()}}
    def residual(p):
        ps=unpack(p);result=[]
        for e in usable:
            delta=apply(CORNERS,ps[e['a']])-apply(apply(CORNERS,np.array(e['matrix'])),ps[e['b']])
            result.extend((delta*np.sqrt(e['score'])).ravel())
        return np.array(result)
    if members and usable:
        x0=np.concatenate([params(poses[i]) for i in members])
        fit=least_squares(residual,x0,loss='soft_l1',f_scale=4,max_nfev=200)
        poses=unpack(fit.x)
    for e in usable:
        d=apply(CORNERS,poses[e['a']])-apply(apply(CORNERS,np.array(e['matrix'])),poses[e['b']])
        e['final_loop_rms_px']=float(np.sqrt(np.mean(d**2)))
    return poses,usable,quarantine

def render(scans,poses,ee,quarantine):
    pts=np.concatenate([apply(CORNERS[:4],m) for m in poses.values()]);lo=np.floor(pts.min(0)-65);hi=np.ceil(pts.max(0)+65)
    width,height=(hi-lo).astype(int);offset=matrix([0,*-lo]);size=(width,height)
    folder=OUT/'assets';folder.mkdir(exist_ok=True)
    masks={};warped={};coverage=np.zeros((height,width),np.uint16)
    records=[]
    for i,s in enumerate(scans):
        info=s['info'];r=dict(index=i,scan_id=info['scan_id'],date=info['session_date'],scan_no=info['scan_no'],
            excluded=s['excluded'],status='excluded by existing review' if s['excluded'] else 'unplaced',
            exclusion_reason=info.get('exclusion_reason',''))
        if not s['excluded']:
            Image.fromarray(np.uint8(s['image']*255)).save(folder/f'{i:02d}.png');r['image']=f'assets/{i:02d}.png'
        if i in poses:
            m=poses[i];canvas=offset@m;inv=np.linalg.inv(canvas)
            # scipy order is rows/cols; matrix is x/y.
            transform=inv[:2,:2][::-1,::-1];shift=inv[:2,2][::-1]
            valid=np.ones((512,512),bool);valid[:5]=False;valid[-5:]=False;valid[:,:5]=False;valid[:,-5:]=False
            mask=ndi.affine_transform(valid.astype(np.uint8),transform,shift,output_shape=(height,width),order=0)>0
            im=ndi.affine_transform(s['image'],transform,shift,output_shape=(height,width),order=1)
            masks[i]=mask;warped[i]=np.uint8(np.clip(im,0,1)*255);coverage+=mask.astype(np.uint16)
            neighbors=[e for e in ee if i in (e['a'],e['b'])]
            r.update(status='overlap-supported automatic placement',matrix_to_onh_pixels=m.tolist(),
                     matrix_from_onh_pixels=np.linalg.inv(m).tolist(),matrix_to_canvas=canvas.tolist(),
                     footprint_onh_um=(apply(CORNERS[:4],m)*info['spacing'][0]).tolist(),
                     links=len(neighbors),best_support=max((e['support'] for e in neighbors),default=1),
                     best_dice=max((e['dice'] for e in neighbors),default=1))
            calibration=np.diag([info['spacing'][1],info['spacing'][0],1.])
            r['pixel_to_onh_um']=(calibration@m).tolist()
            r['native_um_to_onh_um']=(calibration@m@np.linalg.inv(calibration)).tolist()
            r['onh_um_to_native_um']=np.linalg.inv(calibration@m@np.linalg.inv(calibration)).tolist()
            if neighbors and all(e.get('evidence_tier')=='geometry_consensus_low_contrast' for e in neighbors):
                r['placement_evidence']='Geometry consensus · low contrast'
                r['status']='Automatic placement supported by multiple vessel overlaps and ONH convergence; low structural contrast'
            if info.get('onh_assessable') and info.get('visible_onh',{}).get('resolved'):
                c=np.array(info['visible_onh']['center_um'])/np.array(info['spacing'])[::-1]
                r['reviewed_disc_center_in_atlas_um']=(apply(c,m)*info['spacing'][0]).tolist()
            conv=info.get('convergence',{})
            if conv.get('center_um') and conv.get('residual_um',999)<50:
                c=np.array(conv['center_um'])/np.array(info['spacing'])[::-1]
                r['convergence_proposal_in_atlas_um']=(apply(c,m)*info['spacing'][0]).tolist()
                r['convergence_was_resolved']=conv.get('resolved',False)
        records.append(r)
    # Cover the observed territory with a small, explicitly reproducible set of fields.
    chosen=[ROOT_INDEX];covered=masks[ROOT_INDEX].copy()
    while True:
        remaining=[i for i in poses if i not in chosen]
        if not remaining:break
        best=max(remaining,key=lambda i:np.count_nonzero(masks[i]&~covered))
        gain=int(np.count_nonzero(masks[best]&~covered))
        if gain<.035*512*512:break
        chosen.append(best);covered|=masks[best]
    # Peripheral fields first, ONH anchor on top, as in the supplied reference.
    draw_order=list(reversed(chosen))
    canvas=Image.new('RGB',size,'white')
    for i in draw_order:
        rgb=Image.fromarray(warped[i]).convert('RGB');mask=Image.fromarray(np.uint8(masks[i])*255)
        canvas.paste(rgb,(0,0),mask)
        poly=apply(np.array([[5,5],[506,5],[506,506],[5,506]]),offset@poses[i])
        d=ImageDraw.Draw(canvas);d.line([tuple(p) for p in np.vstack([poly,poly[0]])],fill='#58616b',width=1)
        label=apply([18,488],offset@poses[i]);d.text(tuple(label),f'{i+1:02d}',fill='#ffcc52',stroke_width=1,stroke_fill='#222222')
    # Put enough context inside the exported scientific figure to survive sharing.
    final=Image.new('RGB',(width,height+125),'white');final.paste(canvas,(0,75));d=ImageDraw.Draw(final)
    try:font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    except OSError:font=small=ImageFont.load_default()
    d.text((25,15),'TS247 OD | ONH-centered retinal montage',fill='#16232d',font=font)
    d.text((25,43),f'Pooled dates | {len(poses)} placed scans | {len(chosen)} fields shown | automatic registration proposal',fill='#46535d',font=small)
    d.text((25,height+87),'Rigid placement; native display orientation. Anatomical directions unconfirmed. No invented tissue.',fill='#46535d',font=small)
    anchor=apply([0,0],offset)+[0,75];d.ellipse((anchor[0]-5,anchor[1]-5,anchor[0]+5,anchor[1]+5),outline='#efac26',width=2)
    final.save(OUT/'montage.png');canvas.save(OUT/'montage_clean.png')
    # Count observed coverage; never treat rectangle bounding-box area as observed retina.
    union=int((coverage>0).sum());spacing=scans[ROOT_INDEX]['info']['spacing'][0]
    summary=dict(subject='TS247_OD',date_policy='all dates pooled at user request; dates retained as metadata',
        eligible=sum(not s['excluded'] for s in scans),excluded=sum(s['excluded'] for s in scans),placed=len(poses),
        unplaced=[i for i,s in enumerate(scans) if not s['excluded'] and i not in poses],
        reference_index=ROOT_INDEX,representative_indices=chosen,draw_order=draw_order,
        canvas_size=[int(width),int(height)],canvas_origin=(-lo).tolist(),spacing_um=spacing,
        coverage_native_pixels=union,coverage_mm2=union*spacing**2/1e6,coverage_single_field_equivalents=union/(502*502),
        extent_mm=((hi-lo-130)*spacing/1000).tolist(),accepted_edges=len(ee),quarantined_edges=len(quarantine),
        loop_residual_median_um=float(np.median([e['final_loop_rms_px'] for e in ee])*spacing) if ee else None,
        quality_claim='Internal overlap support only; no independent registration ground truth',anatomical_directions='unconfirmed')
    data=dict(summary=summary,scans=records,edges=ee,quarantined_edges=quarantine)
    write(OUT/'montage.json',data)
    (OUT/'data.js').write_text('window.MONTAGE='+json.dumps(data,allow_nan=False)+';',encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)
    return data

def main():
    scans=load();poses,ee,q=solve(scans,edges());render(scans,poses,ee,q)

if __name__=='__main__':main()
