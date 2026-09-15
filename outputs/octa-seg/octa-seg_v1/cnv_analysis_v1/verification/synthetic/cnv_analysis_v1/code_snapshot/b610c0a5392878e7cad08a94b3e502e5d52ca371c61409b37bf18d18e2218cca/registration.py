"""Rigid vessel/structure registration with separate proposals and human edits."""
import numpy as np
from scipy.ndimage import binary_dilation, map_coordinates
from skimage.feature import ORB, match_descriptors
from skimage.measure import ransac
from skimage.transform import EuclideanTransform
from .geometry import grid, transform, rigid, Footprint

def normalized(image):
    a=np.asarray(image,float); good=np.isfinite(a)
    if not good.any(): return np.zeros_like(a)
    lo,hi=np.percentile(a[good],[2,98])
    return np.clip((np.nan_to_num(a,nan=lo)-lo)/max(hi-lo,1e-6),0,1)

def warp_image(image,spacing,target_shape,target_spacing,matrix):
    p=transform(grid(target_shape,target_spacing),np.linalg.inv(rigid(matrix)))
    return map_coordinates(image,[p[...,1]/spacing[0],p[...,0]/spacing[1]],
                           order=1,mode='constant',cval=np.nan,prefilter=False)

def propose(moving,fixed,sm,sf,exclude_m,exclude_f,settings):
    base=dict(state='failed',matrix=None,uncertainty_um=None,method='ORB/rigid RANSAC',
              diagnostics={},reason='insufficient independent feature matches')
    images=[normalized(moving),normalized(fixed)]; feats=[]
    for image,spacing,ex in zip(images,(sm,sf),(exclude_m,exclude_f)):
        orb=ORB(n_keypoints=1600,fast_threshold=.05)
        try: orb.detect_and_extract(image)
        except RuntimeError: return base
        rc=np.round(orb.keypoints).astype(int)
        keep=~binary_dilation(ex,iterations=4)[rc[:,0],rc[:,1]]
        feats.append((orb.keypoints[keep,::-1]*np.asarray(spacing)[::-1],orb.descriptors[keep]))
    if min(len(f[0]) for f in feats)<8: return base
    matches=match_descriptors(feats[0][1],feats[1][1],cross_check=True,max_ratio=.8)
    if len(matches)<8: return base
    src=feats[0][0][matches[:,0]]; dst=feats[1][0][matches[:,1]]
    try:
        model,inliers=ransac((src,dst),EuclideanTransform,min_samples=3,
            residual_threshold=settings['max_residual_um'],max_trials=1000,random_state=417)
    except TypeError:  # newer scikit-image renamed random_state to rng
        model,inliers=ransac((src,dst),EuclideanTransform,min_samples=3,
            residual_threshold=settings['max_residual_um'],max_trials=1000,rng=417)
    if model is None or inliers is None or inliers.sum()<3: return base
    mat=rigid(model.params); warped=warp_image(images[0],sm,fixed.shape,sf,mat)
    bad=warp_image(exclude_m.astype(float),sm,fixed.shape,sf,mat)
    valid=np.isfinite(warped)&~exclude_f&(bad<.01)
    overlap=float(valid.sum()/max(1,(~exclude_f).sum()))
    corr=float(np.corrcoef(warped[valid],images[1][valid])[0,1]) if valid.sum()>30 else 0.
    if not np.isfinite(corr): corr=0.
    residual=float(np.sqrt(np.mean(model.residuals(src[inliers],dst[inliers])**2)))
    angle=float(np.degrees(model.rotation))
    diag=dict(matches=len(matches),inliers=int(inliers.sum()),inlier_fraction=float(inliers.mean()),
              rms_um=residual,overlap=overlap,correlation=corr,rotation_deg=angle)
    passed=(diag['inliers']>=settings['min_inliers'] and diag['inlier_fraction']>=settings['min_inlier_fraction']
            and overlap>=settings['min_overlap'] and corr>=settings['min_correlation']
            and residual<=settings['max_residual_um'] and abs(angle)<=settings['max_rotation_deg'])
    # Image metrics establish a candidate, not verified same-tissue identity.
    # This explicit review gate prevents a repeating vessel pattern from silently
    # joining distinct retinal fields or trajectories.
    return dict(state='proposed' if passed else 'failed',matrix=mat.tolist(),uncertainty_um=residual,
                method='ORB/rigid RANSAC',diagnostics=diag,
                reason='alignment review required' if passed else 'registration diagnostics failed',
                matched_source_um=src[inliers].tolist(),matched_target_um=dst[inliers].tolist())

def fit_onh(mask,edge,spacing):
    """Circle fit with angular-support and residual guards for partial ONH edges."""
    from scipy.ndimage import binary_erosion
    boundary=(edge if edge.any() else mask&~binary_erosion(mask)).copy()
    # The acquisition frame is not a visible anatomical ONH edge.
    boundary[[0,-1]]=False; boundary[:,[0,-1]]=False
    y,x=np.nonzero(boundary)
    unavailable=dict(state='unavailable',center_um=None,uncertainty_um=None,method='visible ONH edge fit')
    if len(x)<12: return unavailable
    p=np.column_stack((x*spacing[1],y*spacing[0])); a=np.column_stack((2*p,np.ones(len(p))))
    if np.linalg.cond(a)>1e8: return unavailable
    fit=np.linalg.lstsq(a,np.sum(p*p,axis=1),rcond=None)[0]; center=fit[:2]
    radius=np.sqrt(max(0,fit[2]+center@center)); residual=float(np.sqrt(np.mean((np.linalg.norm(p-center,axis=1)-radius)**2)))
    angles=np.sort(np.mod(np.arctan2(p[:,1]-center[1],p[:,0]-center[0]),2*np.pi))
    arc=2*np.pi-np.max(np.diff(np.r_[angles,angles[0]+2*np.pi]))
    if radius<20 or radius>1500 or arc<np.pi/2 or residual>max(15,.12*radius): return unavailable
    uncertainty=float(max(max(spacing),residual)/max(np.sin(arc/2),.2))
    return dict(state='localized',center_um=center.tolist(),uncertainty_um=uncertainty,
                radius_um=float(radius),arc_degrees=float(np.degrees(arc)),residual_um=residual,
                method='visible ONH edge fit')

def branch_convergence(lines):
    """Independent vessel-branch axes, in physical coordinates; no CNV/thickness input.

    Editable alignment can supply vessel branches when the ONH is off-image.
    At least three independently traced branches and well-conditioned directions
    are required; inconsistent intersections remain unavailable.
    """
    a=[]; b=[]
    for line in lines:
        p=np.asarray(line,float)
        if p.ndim!=2 or p.shape[1]!=2 or len(p)<2: raise ValueError('Invalid vessel branch')
        center=p.mean(axis=0); _,_,vh=np.linalg.svd(p-center,full_matrices=False)
        direction=vh[0]; normal=np.array([-direction[1],direction[0]])
        a.append(normal); b.append(normal@center)
    if len(a)<3: return dict(state='unavailable',center_um=None,uncertainty_um=None,method='vessel branch convergence')
    a=np.array(a); b=np.array(b)
    if np.linalg.cond(a)>5: return dict(state='unavailable',center_um=None,uncertainty_um=None,method='vessel branch convergence')
    center=np.linalg.lstsq(a,b,rcond=None)[0]
    uncertainty=float(max(10,np.sqrt(np.mean((a@center-b)**2))*np.linalg.cond(a)))
    return dict(state='proposed' if uncertainty<100 else 'unavailable',center_um=center.tolist(),
                uncertainty_um=uncertainty,method='vessel branch convergence')

def vessel_onh_proposal(vessel,spacing):
    """Independent vessel geometry only; proposals require localization review."""
    from skimage.morphology import skeletonize
    from scipy.ndimage import convolve,label
    skeleton=skeletonize(vessel)
    degree=convolve(skeleton.astype(int),np.ones((3,3),int),mode='constant')-skeleton
    segments,n=label(skeleton&~binary_dilation(skeleton&(degree>2)),structure=np.ones((3,3)))
    lines=[]; centers=[]
    for k in range(1,n+1):
        y,x=np.nonzero(segments==k)
        if len(x)<20: continue
        p=np.column_stack((x*spacing[1],y*spacing[0])); center=p.mean(axis=0)
        _,singular,vh=np.linalg.svd(p-center,full_matrices=False)
        if singular[0]<1e-6 or singular[1]/singular[0]>.25: continue
        if centers and min(np.linalg.norm(center-c) for c in centers)<100: continue
        projected=(p-center)@vh[0]
        if np.ptp(projected)<80: continue
        lines.append([list(center+projected.min()*vh[0]),list(center+projected.max()*vh[0])]); centers.append(center)
    result=branch_convergence(lines); result['vessel_branch_axes_um']=lines
    result['reason']='Independent vessel geometry proposal; localization review required'
    return result

def match_lesions(source,target,max_distance_um=100):
    """Return unambiguous footprint matches; preserve splits/mergers as ambiguity."""
    scores=np.zeros((len(source),len(target)))
    for i,a in enumerate(source):
        y,x=np.nonzero(a.mask); p=transform(np.column_stack((x*a.spacing[1],y*a.spacing[0])),a.matrix)
        for j,b in enumerate(target):
            if np.linalg.norm(a.centroid-b.centroid)>max(max_distance_um,.5*max(a.diameter,b.diameter)): continue
            intersection=b.inside(p).sum()*np.prod(a.spacing)
            scores[i,j]=intersection/max(a.area+b.area-intersection,1e-6)
    hits=scores>=.15; result=[]
    for i in range(len(source)):
        js=np.flatnonzero(hits[i])
        if not len(js): result.append(dict(source=i,target=None,state='unmatched',iou=0.))
        elif len(js)>1: result.append(dict(source=i,target=None,state='ambiguous_split_or_merge',iou=float(scores[i].max())))
        else:
            j=int(js[0]); state='matched' if hits[:,j].sum()==1 else 'ambiguous_split_or_merge'
            result.append(dict(source=i,target=j if state=='matched' else None,state=state,iou=float(scores[i,j])))
    return result
