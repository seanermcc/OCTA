from common import *
sid='TS267_OD_2025-03-05_D14_s01_104048'
a=npz(HERE/'scans'/sid/'maps.npz'); y,x=230,85
print('POINT', {k:str(a[k][y,x]) for k in ['core','candidate_labels','geometry_any','background_supported','automatic_thickness_um','structural_context']})
for j,(u,v) in enumerate(a['geometry_pairs']):
 if a['geometry_crossing'][y,j,x]:print('CROSSING',a['surface_names'][u],a['surface_names'][v],a['automatic_surfaces_crop_px'][y,[u,v],x])
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
images=np.load(volume_path(sid)/'images.npy',mmap_mode='r')
fig,axs=plt.subplots(3,1,figsize=(12,9),layout='constrained')
for ax,row in zip(axs,[227,230,233]):
 im=images[row];lo,hi=np.percentile(im,[2,99]);ax.imshow(im,cmap='gray',vmin=lo,vmax=hi,aspect='auto')
 for j,name in enumerate(a['surface_names']):ax.plot(a['automatic_surfaces_crop_px'][row,j],lw=1,label=name)
 ax.axvline(x,color='white',ls=':');ax.set_xlim(45,130);ax.set_ylim(360,0);ax.set_title(f'Native B-scan {row}; all eight raw neural boundaries; A-line 85 dotted')
axs[0].legend(ncol=4,fontsize=8);axs[-1].set_xlabel('Native A-line')
fig.savefig(destination(HERE/'verification/D14_linked_bscans.png'),dpi=140)
