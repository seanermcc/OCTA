"""Standalone scientific review figures; no annotations written."""
from .common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from eight_surface.config import SURFACE_NAMES

def run():
    for sid in SCANS:
        out=ROUND/'volumes'/sid;d=npz(out/'measurements.npz');g=npz(out/'geometry.npz');a=npz(out/'diagnostics.npz')
        folder=ROUND/'figures'/sid;folder.mkdir(parents=True,exist_ok=True)
        for k,name in enumerate(SURFACE_NAMES):
            path=folder/f'{name}.png'
            if path.exists() and path.stat().st_mtime_ns>=(out/'measurements.npz').stat().st_mtime_ns:continue
            panels=[(d['raw_position_branch'][:,k],'Neural depth / px',None,None),
                (np.where(np.isfinite(d['reported_positions'][:,k]),1,np.where(np.isfinite(d['uncertain_estimates'][:,k]),.5,0)),'Solid 1 / dashed 0.5 / withheld 0',0,1),
                (d['entropy'][:,k],'Normalized depth entropy',0,1),(a['spike_um'][:,k],'Local spike / µm',0,40),
                (g['local_cnr'],'Local signal CNR',0,10),(a['onh_distance_um'],'ONH distance or edge proxy / µm',0,1500)]
            fig,axes=plt.subplots(2,3,figsize=(12,8),layout='constrained')
            for ax,(data,title,lo,hi) in zip(axes.flat,panels):
                im=ax.imshow(data,origin='upper',vmin=lo,vmax=hi,cmap='viridis');ax.set_title(title,fontsize=10);ax.set_xlabel('Native A-line');ax.set_ylabel('Native B-scan');fig.colorbar(im,ax=ax,shrink=.75)
                if g['cnv'].any():ax.contour(g['cnv'],levels=[.5],colors='magenta',linewidths=.4)
            fig.suptitle(f'{sid} / {name}\nV2 round_000 · working policy, unchanged weights · diagnostics are not accuracy labels',fontsize=11)
            fig.savefig(path,dpi=110);plt.close(fig)
        images=np.load(read(out/'prepared.json')['images'],mmap_mode='r');offset=int(g['label_offset'])
        fig,axes=plt.subplots(3,1,figsize=(13,9),layout='constrained')
        for ax,b in zip(axes,[128,256,384]):
            image=images[b];lo,hi=np.percentile(image,[2,99.5]);ax.imshow(image,cmap='gray',vmin=lo,vmax=hi,aspect='auto')
            for k in range(8):
                ax.plot(d['reported_positions'][b,k]-offset,lw=.9,label=SURFACE_NAMES[k]);ax.plot(d['uncertain_estimates'][b,k]-offset,'--',lw=.8,color='#ffb45c')
            ax.set_title(f'B-scan {b}: solid working measurements / amber candidate proposals');ax.set_xlim(0,511);ax.set_ylim(image.shape[0],0);ax.set_ylabel('Crop depth / px')
        axes[-1].set_xlabel('Native A-line');axes[0].legend(loc='upper right',ncol=4,fontsize=7);fig.suptitle(sid)
        fig.savefig(folder/'bscans.png',dpi=125);plt.close(fig)
        print('Figures',sid,flush=True)

if __name__=='__main__':run()
