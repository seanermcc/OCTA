"""Physical distances to actual pixel outlines; thickness is never resampled."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import map_coordinates

def rigid(matrix):
    a=np.asarray(matrix,float)
    if a.shape!=(3,3) or not np.allclose(a[2],[0,0,1]) or not np.allclose(a[:2,:2].T@a[:2,:2],np.eye(2),atol=1e-6) or not np.isclose(np.linalg.det(a[:2,:2]),1):
        raise ValueError('Alignment must be rigid, physical-scale-preserving, and reflection-free')
    return a

def transform(points,matrix):
    return np.asarray(points)@matrix[:2,:2].T+matrix[:2,2]

def grid(shape,spacing):
    yy,xx=np.indices(shape)
    return np.stack((xx*spacing[1],yy*spacing[0]),axis=-1)

def sample_mask(mask,spacing,points,matrix=None):
    if matrix is not None: points=transform(points,np.linalg.inv(rigid(matrix)))
    x=np.floor(points[...,0]/spacing[1]+.5).astype(int); y=np.floor(points[...,1]/spacing[0]+.5).astype(int)
    valid=(x>=0)&(y>=0)&(x<mask.shape[1])&(y<mask.shape[0])
    return valid & mask[np.clip(y,0,mask.shape[0]-1),np.clip(x,0,mask.shape[1]-1)]

def boundary_segments(mask,spacing):
    """Exact edges of the union of occupied pixel rectangles, at half pixels."""
    sy,sx=spacing; pad=np.pad(mask,1)
    segments=[]
    for dy,dx,offsets in [(-1,0,(-.5,-.5,.5,-.5)),(1,0,(-.5,.5,.5,.5)),
                         (0,-1,(-.5,-.5,-.5,.5)),(0,1,(.5,-.5,.5,.5))]:
        ys,xs=np.nonzero(mask & ~pad[1+dy:1+dy+mask.shape[0],1+dx:1+dx+mask.shape[1]])
        x1,y1,x2,y2=offsets
        segments.append(np.stack([np.column_stack(((xs+x1)*sx,(ys+y1)*sy)),
                                  np.column_stack(((xs+x2)*sx,(ys+y2)*sy))],axis=1))
    return np.concatenate(segments)

class Footprint:
    def __init__(self,mask,spacing,matrix=None,complete=None):
        if not mask.any(): raise ValueError('Empty footprint')
        self.mask=mask; self.spacing=np.asarray(spacing,float)
        if min(self.spacing)<=0 or not np.isfinite(self.spacing).all(): raise ValueError('Invalid physical scale')
        self.matrix=rigid(np.eye(3) if matrix is None else matrix)
        self.segments=transform(boundary_segments(mask,spacing),self.matrix)
        self.mid=self.segments.mean(axis=1); self.tree=cKDTree(self.mid)
        self.area=float(mask.sum()*np.prod(spacing)); self.diameter=2*np.sqrt(self.area/np.pi)
        y,x=np.nonzero(mask); self.centroid=transform(np.array([x.mean()*spacing[1],y.mean()*spacing[0]]),self.matrix)
        self.complete=bool(complete if complete is not None else not(mask[[0,-1]].any() or mask[:,[0,-1]].any()))

    def inside(self,points):
        # nearest sampling with half-pixel FOV boundaries
        p=transform(points,np.linalg.inv(self.matrix))
        x=np.floor(p[...,0]/self.spacing[1]+.5).astype(int); y=np.floor(p[...,1]/self.spacing[0]+.5).astype(int)
        valid=(x>=0)&(y>=0)&(x<self.mask.shape[1])&(y<self.mask.shape[0])
        return valid & self.mask[np.clip(y,0,self.mask.shape[0]-1),np.clip(x,0,self.mask.shape[1]-1)]

    def distance(self,points):
        shape=points.shape[:-1]; p=points.reshape(-1,2); result=np.empty(len(p))
        # Segments have only two possible lengths. Query all midpoints within
        # the nearest midpoint distance plus the maximum half length: exact,
        # unlike a fixed number of nearest segments on anisotropic grids.
        half=float(np.max(np.linalg.norm(self.segments[:,1]-self.segments[:,0],axis=1))/2)
        for start in range(0,len(p),50000):
            q=p[start:start+50000]; dm,idx=self.tree.query(q)
            best=dm.copy()
            # Usually the nearest midpoint segment suffices; only candidates
            # whose midpoint can beat its distance are examined.
            candidates=self.tree.query_ball_point(q,dm+half)
            lengths=np.fromiter(map(len,candidates),int,len(q)); owner=np.repeat(np.arange(len(q)),lengths)
            ids=np.concatenate(candidates).astype(int)
            a=self.segments[ids,0]; v=self.segments[ids,1]-a
            u=np.clip(np.sum((q[owner]-a)*v,axis=1)/np.sum(v*v,axis=1),0,1)
            ds=np.linalg.norm(q[owner]-a-u[:,None]*v,axis=1)
            best[:]=np.inf; np.minimum.at(best,owner,ds)
            result[start:start+len(q)]=best
        result=result.reshape(shape); result[self.inside(points)]=0
        return result

def bins(distance,inside,edges):
    """Interior=0; (0,e1), [e1,e2), ..., [e5,e6], outside=-1."""
    out=np.searchsorted(np.asarray(edges)[1:],distance,side='right')+1
    out[distance==edges[-1]]=len(edges)-1
    out[(distance>edges[-1])|~np.isfinite(distance)]=-1
    out[inside]=0
    return out.astype('int8')

def full_band_areas(footprint,edges,spacing):
    lo=footprint.segments.min(axis=(0,1))-edges[-1]-max(spacing)
    hi=footprint.segments.max(axis=(0,1))+edges[-1]+max(spacing)
    xs=np.arange(np.floor(lo[0]/spacing[1]),np.ceil(hi[0]/spacing[1])+1)*spacing[1]
    ys=np.arange(np.floor(lo[1]/spacing[0]),np.ceil(hi[1]/spacing[0])+1)*spacing[0]
    counts=np.zeros(len(edges),np.int64)
    for y in np.array_split(ys,max(1,int(np.ceil(len(xs)*len(ys)/80000)))):
        xx,yy=np.meshgrid(xs,y); points=np.stack((xx,yy),axis=-1)
        b=bins(footprint.distance(points),footprint.inside(points),edges)
        counts+=np.bincount(b[b>=0],minlength=len(edges))
    return counts*np.prod(spacing)

def regions(footprints,shape,spacing,onh,edges_for):
    points=grid(shape,spacing)
    distances=np.stack([f.distance(points) for f in footprints])
    interiors=np.stack([f.inside(points) for f in footprints]); any_inside=interiors.any(axis=0)
    # Deterministic ownership at equal distance; exact ties are separately recorded.
    nearest=distances.argmin(axis=0)
    ties=np.isclose(distances,distances.min(axis=0),rtol=0,atol=1e-8).sum(axis=0)>1
    result=[]
    for i,f in enumerate(footprints):
        edges=np.asarray(edges_for(f)); raw=bins(distances[i],interiors[i],edges)
        owned=(nearest==i)&~any_inside&~onh
        keep=(raw==0)&~onh | (raw>0)&owned
        assigned=np.where(keep,raw,-1)
        areas=full_band_areas(f,edges,spacing)
        diagnostics=[]
        for band in range(7):
            wanted=raw==band; available=assigned==band; other=wanted&any_inside&~interiors[i]
            diagnostics.append(dict(band=band,expected_area_um2=float(areas[band]),
                fov_area_um2=float(wanted.sum()*np.prod(spacing)),
                available_area_um2=float(available.sum()*np.prod(spacing)),
                other_lesion_area_um2=float(other.sum()*np.prod(spacing)),
                onh_lost_area_um2=float((wanted&onh).sum()*np.prod(spacing)),
                shared_area_um2=float((wanted&~any_inside&~onh&(nearest!=i)).sum()*np.prod(spacing)),
                tied_area_um2=float((wanted&ties&~any_inside).sum()*np.prod(spacing))))
        result.append((assigned,distances[i],diagnostics))
    return result

def recover_outline(footprints,spacing):
    """Union verified same-session repeat masks; completeness needs observed exterior."""
    from scipy.ndimage import binary_dilation
    lo=np.min([f.segments.min(axis=(0,1)) for f in footprints],axis=0)-2*max(spacing)
    hi=np.max([f.segments.max(axis=(0,1)) for f in footprints],axis=0)+2*max(spacing)
    origin=np.floor(lo/np.asarray(spacing)[::-1])*np.asarray(spacing)[::-1]
    shape=tuple((np.ceil((hi-origin)/np.asarray(spacing)[::-1]).astype(int)+1)[::-1])
    points=grid(shape,spacing)+origin
    union=np.zeros(shape,bool); covered=union.copy()
    for f in footprints:
        union|=f.inside(points)
        q=transform(points,np.linalg.inv(f.matrix))
        covered|=(q[...,0]>=-.5*f.spacing[1])&(q[...,0]<(f.mask.shape[1]-.5)*f.spacing[1])&(
                  q[...,1]>=-.5*f.spacing[0])&(q[...,1]<(f.mask.shape[0]-.5)*f.spacing[0])
    complete=not (binary_dilation(union)&~covered).any()
    matrix=np.eye(3); matrix[:2,2]=origin
    return Footprint(union,spacing,matrix,complete=complete)
