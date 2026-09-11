"""Physical geometry; image x right, y down. No thickness-driven registration."""
import warnings
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import ConvexHull, distance
from skimage.morphology import skeletonize
from skimage.feature import ORB, match_descriptors
from skimage.measure import ransac
from skimage.transform import EuclideanTransform


def xy_grid(shape, spacing):
    y, x = np.indices(shape)
    return np.stack((x * spacing[1], y * spacing[0]), axis=-1)


def apply(points, matrix):
    return np.asarray(points) @ matrix[:2, :2].T + matrix[:2, 2]


def feret(mask, spacing):
    """Maximum span of the union of physical pixel cells (not equivalent area)."""
    yx = np.argwhere(mask & ~ndi.binary_erosion(mask))
    if not len(yx): return 0.
    xy = yx[:, ::-1] * np.asarray(spacing)[::-1]
    corners = np.concatenate([xy + np.array([dx*spacing[1], dy*spacing[0]])
                              for dx, dy in [(-.5,-.5),(-.5,.5),(.5,-.5),(.5,.5)]])
    hull = corners[ConvexHull(corners).vertices]
    return float(distance.pdist(hull).max())


def dilate_um(mask, clearance, spacing):
    if not mask.any(): return mask.copy()
    # Conservative rasterization: a selected cell may intersect the continuous buffer.
    # Excess is bounded by a pixel diagonal; never under-buffer an edge.
    return ndi.distance_transform_edt(~mask, sampling=spacing) <= clearance + .5*np.hypot(*spacing)


def lesion_buffer(mask, spacing, factor=1.):
    labels, n = ndi.label(mask); result = np.zeros_like(mask); records = []
    for k in range(1, n+1):
        m = labels == k; d = feret(m, spacing)
        buffered = dilate_um(m, factor*d, spacing); result |= buffered
        y, x = np.nonzero(m)
        records.append(dict(component=k, diameter_um=d, clearance_um=factor*d,
                            area_um2=float(m.sum()*np.prod(spacing)),
                            truncated=bool(m[0].any() or m[-1].any() or m[:,0].any() or m[:,-1].any()),
                            bscan_min=int(y.min()), bscan_max=int(y.max()),
                            bscan_link=int(np.median(y)), aline_link=int(np.median(x))))
    return result, records


def vessel_buffer(mask, spacing, factor=.5):
    if not mask.any(): return mask.copy()
    skel = skeletonize(mask)
    radius = ndi.distance_transform_edt(mask, sampling=spacing)
    _, near = ndi.distance_transform_edt(~skel, sampling=spacing, return_indices=True)
    local_radius = radius[tuple(near)]
    outside = ndi.distance_transform_edt(~mask, sampling=spacing)
    return mask | (outside <= factor*2*local_radius + .5*np.hypot(*spacing))


def _circle(points):
    origin = points.mean(axis=0); p = points-origin
    a = np.column_stack([2*p, np.ones(len(p))])
    sol = np.linalg.lstsq(a, np.sum(p*p, axis=1), rcond=None)[0]
    center = sol[:2]+origin
    radius = np.sqrt(max(0, sol[2]+np.sum(sol[:2]**2)))
    return center, radius


def fit_onh(mask, edge, spacing, cfg):
    boundary = edge.copy() if edge.any() else mask & ~ndi.binary_erosion(mask)
    # Image borders from a clipped filled disc are not anatomical edges.
    boundary[[0,-1],:] = False; boundary[:,[0,-1]] = False
    points = np.argwhere(boundary)[:, ::-1] * np.asarray(spacing)[::-1]
    failure = dict(resolved=False, method="visible edge", reason="insufficient visible arc")
    if len(points) < 12: return failure
    center, r = _circle(points)
    angles = np.sort(np.mod(np.arctan2(*(points-center)[:, ::-1].T), 2*np.pi))
    span = np.degrees(2*np.pi-np.diff(np.r_[angles, angles[0]+2*np.pi]).max())
    residual = float(np.sqrt(np.mean((np.linalg.norm(points-center,axis=1)-r)**2)))
    # Bootstrap spatial arc blocks, not individual adjacent boundary pixels.
    blocks = np.floor(np.mod(np.arctan2((points-center)[:,1], (points-center)[:,0]),2*np.pi)/(np.pi/12)).astype(int)
    groups = [points[blocks == b] for b in np.unique(blocks)]
    rng = np.random.default_rng(cfg["seed"]); centers=[]
    for _ in range(cfg["bootstrap_samples"]):
        sample = np.concatenate([groups[i] for i in rng.integers(len(groups),size=len(groups))])
        if len(np.unique(sample, axis=0)) >= 3: centers.append(_circle(sample)[0])
    uncertainty = float(np.percentile(np.linalg.norm(np.asarray(centers)-center, axis=1),95)) if centers else 1e9
    resolved = (span >= cfg["onh_min_arc_deg"] and residual <= cfg["onh_max_residual_um"]
                and uncertainty <= cfg["onh_max_uncertainty_um"] and r > 2*max(spacing))
    return dict(resolved=bool(resolved), method="visible edge", center_um=center.tolist(),
                diameter_um=float(2*r), residual_um=residual, arc_deg=float(span),
                uncertainty_um=uncertainty, branches=0,
                reason="adequate visible arc" if resolved else "short arc, poor circle fit, or uncertain center")


def branches(mask, spacing, cfg):
    skel = skeletonize(mask)
    neighbors = ndi.convolve(skel.astype(int), np.ones((3,3),int))-skel
    junction = skel & (neighbors > 2)
    parts, n = ndi.label(skel & ~ndi.binary_dilation(junction), structure=np.ones((3,3)))
    records=[]
    for k in range(1,n+1):
        pts = np.argwhere(parts==k)[:, ::-1] * np.asarray(spacing)[::-1]
        if len(pts)<8: continue
        mean=pts.mean(axis=0); _,s,v=np.linalg.svd(pts-mean, full_matrices=False)
        length=np.ptp((pts-mean) @ v[0]); curve=float(s[1]/max(s[0],1e-12))
        if length < cfg["branch_min_length_um"]: continue
        records.append(dict(point=mean.tolist(), direction=v[0].tolist(), length_um=float(length),
                            curvature_ratio=curve, accepted=curve<=cfg["branch_max_curvature_ratio"]))
    return records, junction


def convergence(records, cfg):
    good=[r for r in records if r["accepted"]]
    failure=dict(resolved=False, method="vessel convergence", branches=len(good), reason="insufficient independent straight branches")
    if len(good)<cfg["convergence_min_branches"]: return failure
    p=np.array([r["point"] for r in good]); v=np.array([r["direction"] for r in good])
    normals=np.stack([-v[:,1],v[:,0]],axis=1)
    def solve(idx):
        a=normals[idx]; b=np.sum(a*p[idx],axis=1)
        if np.linalg.cond(a.T@a)>cfg["convergence_max_condition"]: return None
        return np.linalg.lstsq(a,b,rcond=None)[0]
    center=solve(np.arange(len(good)))
    if center is None: return dict(failure,reason="parallel or ill-conditioned branches")
    residuals=np.abs(np.sum(normals*(center-p),axis=1))
    rng=np.random.default_rng(cfg["seed"]); boot=[]
    for _ in range(cfg["bootstrap_samples"]):
        c=solve(rng.integers(len(good),size=len(good)))
        if c is not None: boot.append(c)
    uncertainty=float(np.percentile(np.linalg.norm(np.array(boot)-center,axis=1),95)) if boot else 1e9
    rms=float(np.sqrt(np.mean(residuals**2)))
    ok=(len(boot)>=cfg["bootstrap_samples"]//2 and uncertainty<=cfg["onh_max_uncertainty_um"]
        and rms<=cfg["onh_max_residual_um"])
    return dict(resolved=bool(ok),method="vessel convergence",branches=len(good),center_um=center.tolist(),
                diameter_um=None,uncertainty_um=uncertainty,residual_um=rms,
                branch_agreement_um=residuals.tolist(),condition=float(np.linalg.cond(normals.T@normals)),
                reason="branch agreement passed" if ok else "inconsistent or uncertain convergence")


def features(enface, vessel, blocked, spacing):
    valid=np.isfinite(enface)&~blocked
    if valid.sum()<100: return dict(points=np.empty((0,2)),descriptors=np.empty((0,256),bool),branches=np.empty((0,2)))
    lo,hi=np.percentile(enface[valid],[2,98]); image=np.clip((enface-lo)/max(hi-lo,1e-6),0,1)
    image[~valid]=0
    # ORB sees structural reflectance; retain only descriptors anchored near vessels.
    detector=ORB(n_keypoints=1200,fast_threshold=.04)
    try: detector.detect_and_extract(image)
    except (RuntimeError,ValueError): return dict(points=np.empty((0,2)),descriptors=np.empty((0,256),bool),branches=np.empty((0,2)))
    rc=np.round(detector.keypoints).astype(int)
    # Entire descriptor footprint must avoid masked lesions/artifacts (31px patch).
    safe=~ndi.binary_dilation(blocked,iterations=20)
    near=ndi.distance_transform_edt(~vessel,sampling=spacing)<35
    take=safe[tuple(rc.T)]&near[tuple(rc.T)]
    sk=skeletonize(vessel); junction=sk & (ndi.convolve(sk.astype(int),np.ones((3,3)))-sk>2)
    lab,n=ndi.label(ndi.binary_dilation(junction,iterations=2))
    pts=np.array(ndi.center_of_mass(junction,lab,range(1,n+1))).reshape(-1,2)
    return dict(points=detector.keypoints[take,::-1]*np.asarray(spacing)[::-1],
                descriptors=detector.descriptors[take],branches=pts[:,::-1]*np.asarray(spacing)[::-1])


def sample_native(array, target_xy, spacing):
    """Nearest native observation; no interpolation across invalid/excluded tissue."""
    x=np.rint(target_xy[...,0]/spacing[1]).astype(int); y=np.rint(target_xy[...,1]/spacing[0]).astype(int)
    valid=(y>=0)&(y<array.shape[-2])&(x>=0)&(x<array.shape[-1])
    yc=np.clip(y,0,array.shape[-2]-1); xc=np.clip(x,0,array.shape[-1]-1)
    out=array[...,yc,xc].astype(float); out[...,~valid]=np.nan
    return out,valid


def register(a,b,fa,fb,cfg):
    """Return physical rigid A->B only after structural AND independent branch checks."""
    from scipy.spatial import cKDTree
    fail=dict(verified=False,reason="insufficient vessel-anchored structural matches")
    if min(len(fa["points"]),len(fb["points"]))<cfg["registration_min_matches"]: return fail
    matches=match_descriptors(fa["descriptors"],fb["descriptors"],cross_check=True,max_ratio=.75)
    if len(matches)<cfg["registration_min_matches"]: return fail
    pa=fa["points"][matches[:,0]]; pb=fb["points"][matches[:,1]]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model,inliers=ransac((pa,pb),EuclideanTransform,min_samples=3,
                            residual_threshold=cfg["registration_residual_um"],max_trials=1500,rng=cfg["seed"])
    if model is None or inliers.sum()<cfg["registration_min_matches"]: return fail
    matrix=model.params; residual=float(np.sqrt(np.mean(model.residuals(pa[inliers],pb[inliers])**2)))
    moved=apply(xy_grid(a["enface"].shape,a["spacing"]),matrix)
    ben,inbounds=sample_native(b["enface"],moved,b["spacing"])
    bmask,_=sample_native(b["registration_blocked"],moved,b["spacing"])
    bv,_=sample_native(b["vessel"],moved,b["spacing"])
    valid=inbounds&~a["registration_blocked"]&(bmask==0)&np.isfinite(ben)
    overlap=float(valid.sum()/max(1,(~a["registration_blocked"]).sum()))
    av=a["vessel"]&valid; bv=(bv==1)&valid
    dice=float(2*(av&bv).sum()/max(1,av.sum()+bv.sum()))
    corr=float(np.corrcoef(a["enface"][valid],ben[valid])[0,1]) if valid.sum()>10 else 0.
    if not np.isfinite(corr): corr=0.
    branch_n=0; branch_rms=None
    if len(fa["branches"]) and len(fb["branches"]):
        dist,idx=cKDTree(fb["branches"]).query(apply(fa["branches"],matrix))
        take=dist<cfg["registration_residual_um"]*2
        branch_n=len(np.unique(idx[take]))
        if take.any(): branch_rms=float(np.sqrt(np.mean(dist[take]**2)))
    verified=(overlap>=cfg["registration_min_overlap"] and dice>=cfg["registration_min_vessel_dice"]
              and corr>=cfg["registration_min_structural_correlation"]
              and branch_n>=cfg["registration_min_branch_matches"])
    return dict(verified=bool(verified),matrix=matrix.tolist(),residual_um=residual,
                inliers=int(inliers.sum()),matches=len(matches),overlap_fraction=overlap,
                vessel_dice=dice,structural_correlation=corr,branch_matches=branch_n,
                branch_residual_um=branch_rms,
                reason="vessel-supported rigid match" if verified else "overlap, structure, or branch checks failed")
