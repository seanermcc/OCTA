"""Isolated residual-warp experiments; never writes production poses or labels."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ.setdefault(key,'1')
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi
from scipy.interpolate import RBFInterpolator
from scipy.spatial import Delaunay
from skimage.feature import corner_shi_tomasi, corner_peaks, match_template
from skimage.transform import EuclideanTransform, SimilarityTransform, AffineTransform
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'outputs/octa-reg_v3/bigwarp_pilot_20260922'
YY,XX=np.mgrid[:512,:512]
GRID=np.c_[XX.ravel(),YY.ravel()].astype(float)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False),encoding='utf-8')
def sample(im,p,order=1):return ndi.map_coordinates(im,[p[:,1],p[:,0]],order=order,mode='constant',cval=0)
def feature(im):
    a=ndi.gaussian_filter(im,1)-ndi.gaussian_filter(im,12)
    return (a/np.maximum(ndi.gaussian_filter(a*a,12)**.5,.025)).astype('float32')

def match_point(source,target,point,radius=18,search=56):
    x,y=np.round(point).astype(int)
    if min(x,y)<radius or max(x,y)>=512-radius:return None
    patch=source[y-radius:y+radius+1,x-radius:x+radius+1]
    lo=np.maximum([x-search-radius,y-search-radius],0)
    hi=np.minimum([x+search+radius+1,y+search+radius+1],512)
    crop=target[lo[1]:hi[1],lo[0]:hi[0]]
    if min(crop.shape)<2*radius+1 or patch.std()<.08:return None
    scores=match_template(crop,patch)
    py,px=np.unravel_index(np.argmax(scores),scores.shape);score=float(scores[py,px])
    other=scores.copy();other[max(0,py-5):py+6,max(0,px-5):px+6]=-1
    margin=score-float(other.max())
    q=np.array([lo[0]+px+radius,lo[1]+py+radius],float)
    if score<.52 or margin<.02 or np.max(np.abs(q-point))>=search-1:return None
    # Subpixel parabolic peak, independently on each axis.
    for axis,pos in enumerate((px,py)):
        length=scores.shape[1-axis]
        if 0<pos<length-1:
            v=scores[py,px-1:px+2] if axis==0 else scores[py-1:py+2,px]
            den=v[0]-2*v[1]+v[2]
            if den<-.00001:q[axis]+=np.clip(.5*(v[0]-v[2])/den,-.75,.75)
    return q,score,margin

def correspondences(a,b,valid,vessel):
    fa,fb=feature(a),feature(b)
    response=corner_shi_tomasi(fb,sigma=2)
    allowed=ndi.binary_erosion(valid,iterations=23)&ndi.binary_dilation(vessel,iterations=18)
    response[~allowed]=0
    pts=corner_peaks(response,min_distance=11,threshold_rel=.008,num_peaks=350,exclude_border=25)[:,::-1]
    found=[]
    for p in pts:
        hit=match_point(fb,fa,p)
        if hit is None:continue
        q,score,margin=hit
        back=match_point(fa,fb,q)
        if back is None or np.linalg.norm(back[0]-p)>2:continue
        if not sample(valid.astype(float),q[None],0)[0]:continue
        found.append(dict(target=p.tolist(),moving=q.tolist(),ncc=score,margin=margin))
    # Fixed spatial blocks; these labels are not decided by model fit residuals.
    for row in found:
        x,y=row['target'];tile=(int(x)//96+2*(int(y)//96))%5
        row['split']='validation' if tile==3 else 'audit' if tile==4 else 'train'
    # Exclude training patches that touch a reserved patch, reducing leakage.
    reserved=np.array([r['target'] for r in found if r['split']!='train'])
    if len(reserved):
        for r in found:
            if r['split']=='train' and np.min(np.linalg.norm(reserved-r['target'],axis=1))<40:r['split']='buffer'
    return found

def robust_train(p,q):
    rng=np.random.default_rng(914);best=np.zeros(len(p),bool)
    for _ in range(350):
        ids=rng.choice(len(p),3,replace=False);m=AffineTransform()
        if not m.estimate(p[ids],q[ids]):continue
        take=np.linalg.norm(m(p)-q,axis=1)<4
        if take.sum()>best.sum():best=take
    return best

def taper_mask(points,valid):
    hull=Delaunay(points).find_simplex(GRID)>=0
    hull=hull.reshape(512,512)
    outside=ndi.distance_transform_edt(~hull)
    # Full correction in landmark hull, fades beyond it and at invalid/image edges.
    weight=np.clip(1-outside/60,0,1)
    padded=np.pad(valid,1,constant_values=False)
    distance=ndi.distance_transform_edt(padded)[1:-1,1:-1]
    weight*=np.clip(distance/35,0,1)
    return (weight*weight*(3-2*weight)).astype('float32')

def geometry(field):
    dx=field[:,:,0];dy=field[:,:,1]
    dxy,dxx=np.gradient(dx);dyy,dyx=np.gradient(dy)
    jac=(1+dxx)*(1+dyy)-dxy*dyx
    mats=np.stack([1+dxx,dxy,dyx,1+dyy],-1).reshape(-1,2,2)
    singular=np.linalg.svd(mats,compute_uv=False)
    return dict(max_displacement_px=float(np.linalg.norm(field,axis=2).max()),
        jacobian_min=float(jac.min()),jacobian_max=float(jac.max()),
        stretch_min=float(singular.min()),stretch_max=float(singular.max()),
        folding_pixels=int((jac<=0).sum()))

def fit_fields(p,q,valid):
    fields={}
    for name,cls in [('rigid',EuclideanTransform),('similarity',SimilarityTransform),('affine',AffineTransform)]:
        model=cls();model.estimate(p,q)
        fields[name]=(model(GRID)-GRID).reshape(512,512,2).astype('float32')
        if name=='affine':affine=model
    # Only the nonlinear residual tapers; fading a global scale/translation creates strain.
    weight=taper_mask(p,valid)
    for smoothing in (.003,.02):
        fit=RBFInterpolator(p/512,q-affine(p),kernel='thin_plate_spline',smoothing=smoothing)
        delta=np.concatenate([fit(chunk/512) for chunk in np.array_split(GRID,16)])
        fields[f'tps_{smoothing}']=fields['affine']+(delta.reshape(512,512,2)*weight[:,:,None]).astype('float32')
    return fields

def errors(field,rows,split):
    selected=[r for r in rows if r['split']==split]
    if not selected:return None
    p=np.array([r['target'] for r in selected]);q=np.array([r['moving'] for r in selected])
    delta=np.c_[sample(field[:,:,0],p),sample(field[:,:,1],p)]
    e=np.linalg.norm(p+delta-q,axis=1)
    return dict(n=len(e),median_px=float(np.median(e)),p90_px=float(np.percentile(e,90)),mean_px=float(e.mean()))

def overlay(a,b):return Image.fromarray(np.uint8(np.clip(np.stack([a,b,b],-1),0,1)*255))

def run_pair(group,out):
    src=BASE/group;folder=out/group;folder.mkdir()
    pair=read(src/'pair.json')
    a=np.array(Image.open(src/'moving_manual_aligned.tif'),float)/255
    b=np.array(Image.open(src/'target.tif'),float)/255
    va=np.array(Image.open(src/'moving_valid.tif'))>0;vb=np.array(Image.open(src/'target_valid.tif'))>0
    zp=ROOT/'outputs/octa-reg_v1/prepared'/f'{pair["target"]}.npz'
    with np.load(zp) as z:vessel=z['vessel'].astype(bool)
    valid=va&vb
    # Conservatively withhold frozen v9 lesion/ignored regions from feature placement.
    cnv_hashes={}
    for sid,is_moving in [(pair['moving'],True),(pair['target'],False)]:
        cp=ROOT/'outputs/octa-reg_v3/inputs'/f'{sid}.npz'
        if cp.exists():
            cnv_hashes[str(cp)]=sha(cp)
            with np.load(cp) as z:blocked=z['cnv']|z['ignored']
            if is_moving:
                inv=np.linalg.inv(pair['moving_to_target_native']);q=GRID@inv[:2,:2].T+inv[:2,2]
                blocked=sample(blocked.astype(float),q,0).reshape(512,512)>.5
            valid &= ~ndi.binary_dilation(blocked,iterations=8)
    rows=correspondences(a,b,valid,vessel)
    write(folder/'automatic_matches.json',rows)
    counts={s:sum(r['split']==s for r in rows) for s in ('train','validation','audit','buffer')}
    base=np.zeros((512,512,2),np.float32)
    result=dict(group=group,pair=pair,counts=counts,cnv_exclusion_hashes=cnv_hashes,
                models=[],selected='baseline',status='needs_manual_landmarks',reasons=[],human_confirmed=False)
    before=overlay(a,b);before.save(folder/'before.png')
    fields={'baseline':base}
    if counts['train']>=10 and counts['validation']>=5 and counts['audit']>=5:
        train=[r for r in rows if r['split']=='train'];p=np.array([r['target'] for r in train]);q=np.array([r['moving'] for r in train])
        inliers=robust_train(p,q);result['training_inliers']=int(inliers.sum())
        if inliers.sum()>=8 and np.min(np.ptp(p[inliers],axis=0))>=100:
            p,q=p[inliers],q[inliers]
            fields.update(fit_fields(p,q,va&vb))
        else:result['reasons'].append('Too few spatially distributed training inliers')
    else:result['reasons'].append('Insufficient separated train/validation/audit correspondences')
    for name,field in fields.items():
        g=geometry(field)
        result['models'].append(dict(name=name,geometry=g,
            validation=errors(field,rows,'validation'),audit=errors(field,rows,'audit'),
            safe=bool(g['folding_pixels']==0 and g['max_displacement_px']<=60 and g['stretch_min']>=.65 and g['stretch_max']<=1.5)))
    baseline=result['models'][0];selected=baseline
    # Validation selects the model. Audit is accessed only after selection, with no fallback fitting.
    for m in result['models'][1:]:
        old=selected['validation'];new=m['validation']
        if m['safe'] and old and new and new['median_px']<old['median_px']-.5 and new['p90_px']<=old['p90_px']+.5:selected=m
    proposed=selected['name'];result['proposed']=proposed
    if proposed!='baseline':
        old=baseline['audit'];new=selected['audit']
        passed=bool(new['median_px']<old['median_px']-.5 and new['p90_px']<=old['p90_px']+.5)
        result['status']='provisional_improvement' if passed else 'audit_failed'
        if passed:result['selected']=proposed
        else:result['reasons'].append('Reserved audit points did not confirm improvement; baseline retained')
    elif len(fields)>1:
        result['status']='no_safe_validated_gain';result['reasons'].append('No candidate passed geometry and model-selection checks')
    for name in set([result['selected'],proposed]):
        field=fields[name];q=GRID+field.reshape(-1,2)
        warped=sample(a,q).reshape(512,512)
        mask=sample(va.astype(float),q,0).reshape(512,512)>.5;warped[~mask]=0
        overlay(warped,b).save(folder/('after.png' if name==result['selected'] else 'rejected_proposal.png'))
    np.savez_compressed(folder/'residual_inverse_map.npz',displacement_xy=fields[result['selected']],
        target_to_manual_aligned=True,approved=False)
    # BigWarp-compatible automatic suggestions; deliberately inactive, never human labels.
    with (folder/'automatic_landmarks_inactive.csv').open('w',newline='') as f:
        writer=csv.writer(f)
        for i,r in enumerate(rows):writer.writerow([f'AUTO_{r["split"]}_{i:03d}','false',*r['moving'],*r['target']])
    landmarks=before.copy();draw=ImageDraw.Draw(landmarks)
    for r in rows:
        x,y=r['target'];color={'train':'yellow','validation':'lime','audit':'magenta','buffer':'gray'}[r['split']]
        draw.ellipse((x-3,y-3,x+3,y+3),outline=color,width=2);draw.line([tuple(r['target']),tuple(r['moving'])],fill=color,width=1)
    landmarks.save(folder/'matches.png')
    result['inverse_map_contract']='output target pixel p samples manual-aligned moving at p + displacement_xy[y,x]. Compose with inverse saved moving_to_target_native for native source sampling. Not a production montage transform.'
    write(folder/'result.json',result)
    for path,h in cnv_hashes.items():assert sha(path)==h
    print(group,counts,result['status'],result['selected'],flush=True)
    return result

def main(out):
    if out.exists():raise ValueError('Fresh output required')
    manifest=read(BASE/'manifest.json')
    for p,h in manifest['source_hashes'].items():assert sha(p)==h,f'Stale pilot source: {p}'
    out.mkdir(parents=True);results=[]
    for group in manifest['groups']:results.append(run_pair(group['group'],out))
    for p,h in manifest['source_hashes'].items():assert sha(p)==h,f'Source changed: {p}'
    write(out/'results.json',results)
    write(out/'VERIFIED.json',dict(source_hashes_unchanged=True,source_hashes=manifest['source_hashes'],
        code_sha256=sha(__file__),all_eight_completed=len(results)==8,production_modified=False,
        scope='One pair per eye, eight eyes; pairwise feasibility, not full montage correction',
        geometry_limits='Exploratory review gates: displacement <=60 px; local singular values .65 to 1.5; no folds. Not biological validation.'))
    html=['<!doctype html><meta charset="utf-8"><title>Automatic warp pilot</title><style>body{font:16px system-ui;margin:24px;background:#182027;color:#eee}img{width:min(46vw,650px)}button{padding:8px}section{border-top:1px solid #789;margin-top:30px}a{color:#8df}</style><h1>Automatic residual-warp pilot</h1><p>Eight pairs from your saved manual placements. Red: moving; cyan: target. Drafts only; original montages untouched. This is pairwise feasibility, not a corrected full montage.</p><p><a href="REPORT.md">Results and Fiji review instructions</a></p>']
    for r in results:
        g=r['group'];html.append(f'<section><h2>{g}: {r["status"]} ({r["selected"]})</h2><p>Before (left) / proposed output (right). <a href="{g}/matches.png">Automatic matches</a> · <a href="{g}/result.json">Measurements</a></p><img src="{g}/before.png"><img src="{g}/after.png"></section>')
    (out/'index.html').write_text('\n'.join(html),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
