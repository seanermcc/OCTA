from pathlib import Path
import json
import numpy as np
from scipy.ndimage import map_coordinates
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
paths=sorted((ROOT/'outputs/octa-reg_v1/prepared').glob('TS165_OD*.npz'))
review=json.loads((ROOT/'outputs/octa-reg_v2/all_samples/TS165_OD/human_review.json').read_text())
images=[];poses=[]
for p in paths:
    z=np.load(p);im=z['enface'];lo,hi=np.nanpercentile(im,[2,98]);images.append(np.clip((im-lo)/(hi-lo),0,1))
    poses.append(np.array(review['fields'][p.stem]['matrix_to_onh_pixels']))
grid=np.indices((512,512))[::-1].reshape(2,-1).T
fig,axes=plt.subplots(6,3,figsize=(12,24))
for row,(a,b) in enumerate([(4,7),(5,7),(3,8),(1,9),(2,9),(8,9)]):
    transform=np.linalg.inv(poses[a-1])@poses[b-1]
    q=grid@transform[:2,:2].T+transform[:2,2]
    warped=map_coordinates(images[a-1],q[:,::-1].T,order=1,cval=np.nan).reshape(512,512)
    for col,(im,label) in enumerate([(warped,f'Scan {a}, placed into scan {b} coordinates'),(images[b-1],f'Scan {b}, native')]):
        axes[row,col].imshow(im,cmap='gray',vmin=0,vmax=1);axes[row,col].set_title(label)
    rgb=np.zeros((512,512,3));rgb[:,:,0]=1-np.nan_to_num(warped,nan=1);rgb[:,:,1]=rgb[:,:,2]=1-images[b-1]
    axes[row,2].imshow(rgb);axes[row,2].set_title(f'Dark structures: red={a}, cyan={b}')
    for ax in axes[row]:ax.set_xticks([0,128,256,384,511]);ax.set_yticks([0,128,256,384,511])
fig.suptitle(f'Saved manual placements (v2 revision {review["revision"]}); no scaling',fontsize=16)
fig.tight_layout();fig.savefig(OUT/'manual_overlap_comparison.png',dpi=100)
