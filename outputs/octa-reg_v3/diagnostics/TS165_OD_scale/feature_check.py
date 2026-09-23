from pathlib import Path
import json
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent;root=P.parents[3]
r=json.loads((P/'pair_fits.json').read_text())
fig,axes=plt.subplots(2,2,figsize=(12,12))
for row,(a,b) in enumerate([(7,8),(8,9)]):
    fit=next(x for x in r['pairs'] if x['a']==a and x['b']==b)['fits']['SimilarityTransform']
    for col,(n,key) in enumerate([(a,'source'),(b,'target')]):
        im=np.array(Image.open(root/f'outputs/octa-reg_v3/TS165_OD/assets/{n-1:03}.png'))
        ax=axes[row,col];ax.imshow(im,cmap='gray');ax.set_title(f'Scan {n}, SIFT candidate scale {fit["scale_singular_values"][0]:.3f}')
        for i,(x,y) in enumerate(fit[key]):ax.plot(x,y,'r+');ax.text(x+3,y,str(i),color='red',fontsize=14)
        ax.grid(alpha=.15)
fig.tight_layout();fig.savefig(P/'feature_check.png',dpi=120)
