"""Matched structural dark-band widths; these are not anatomical vessel diameters."""
from pathlib import Path
import json
import numpy as np
from scipy.ndimage import map_coordinates,gaussian_filter1d
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent;root=P.parents[3]
paths=sorted((root/'outputs/octa-reg_v1/prepared').glob('TS165_OD*.npz'))
ims=[np.load(p)['enface'].copy() for p in paths]
fits=json.loads((P/'refined_fits.json').read_text())
offsets=np.arange(-55,55.01,.25)
def measure(im,center,normal):
    tangent=np.array([-normal[1],normal[0]])
    coords=center[None,None,:]+offsets[:,None,None]*normal+np.arange(-3,4)[None,:,None]*tangent
    profile=map_coordinates(im,coords.reshape(-1,2)[:,::-1].T,order=1,cval=np.nan).reshape(len(offsets),7).mean(axis=1)
    if not np.isfinite(profile).all():raise ValueError('Profile crosses native image boundary')
    profile=gaussian_filter1d(profile,4)
    left=np.median(profile[:60]);right=np.median(profile[-60:]);baseline=np.linspace(left,right,len(profile));depth=baseline-profile
    central=abs(offsets)<45;peak=np.max(depth[central]);norm=depth/peak
    # Outer half-depth crossings enclosing the central dark vessel and its reflex.
    cross=np.where(norm>=.5)[0]
    l,r=cross[0],cross[-1]
    lx=np.interp(.5,norm[l-1:l+1],offsets[l-1:l+1]);rx=np.interp(.5,norm[r:r+2][::-1],offsets[r:r+2][::-1])
    return float(rx-lx),norm,[float(lx),float(rx)]
records=[]
for a,b,centers,normal in [(1,9,[[177,115],[195,160],[280,255],[308,292]],np.array([.83,-.56])),
                           (8,9,[[177,115],[195,160],[280,255],[308,292]],np.array([.83,-.56])),
                           (7,8,[[333,100],[348,135],[411,215],[440,250]],np.array([.83,-.56])),
                           (4,7,[[190,50],[203,105],[216,160],[222,185]],np.array([.975,-.22]))]:
    fit=next(r for r in fits if r['a']==a and r['b']==b);m=np.array(fit['matrix']);inv=np.linalg.inv(m)
    n=normal/np.linalg.norm(normal);n_a=inv[:2,:2]@n;n_a/=np.linalg.norm(n_a)
    fig,axes=plt.subplots(2,3,figsize=(14,9));fig.suptitle('TS165 OD: same trunk segments, native pixel widths')
    for ax,scan in zip(axes[0,:2],[a,b]):
        im=ims[scan-1];lo,hi=np.percentile(im,[2,98]);ax.imshow(im,cmap='gray',vmin=lo,vmax=hi);ax.set_title(f'Scan {scan}: native 512 x 512')
    for i,c in enumerate(centers):
        c=np.array(c);ca=c@inv[:2,:2].T+inv[:2,2]
        try:wa,pa,edgea=measure(ims[a-1],ca,n_a);wb,pb,edgeb=measure(ims[b-1],c,n)
        except ValueError:
            print('Skip boundary profile',a,b,i+1,flush=True);continue
        records.append(dict(a=a,b=b,site=i+1,source_center=ca.tolist(),target_center=c.tolist(),source_width_px=wa,target_width_px=wb,ratio=wb/wa))
        for ax,cc,nn in [(axes[0,0],ca,n_a),(axes[0,1],c,n)]:
            seg=cc+np.array([[-35],[35]])*nn;ax.plot(*seg.T,color=f'C{i}',lw=1.5);ax.text(*cc,str(i+1),color=f'C{i}',fontsize=12)
        ax=[axes[0,2],*axes[1]][i];ax.plot(offsets,pa,label=f'Scan {a}: {wa:.1f}px');ax.plot(offsets,pb,label=f'Scan {b}: {wb:.1f}px');ax.axhline(.5,color='gray',ls=':');ax.set_xlim(-40,40);ax.set_ylim(-.3,1.3);ax.set_title(f'Matched site {i+1}');ax.set_xlabel('Native pixels across vessel');ax.set_ylabel('Normalized dark-band depth');ax.legend(fontsize=9)
    fig.tight_layout();fig.savefig(P/f'width_profiles_{a}_{b}.png',dpi=140)
(P/'width_measurements.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records,indent=2))
