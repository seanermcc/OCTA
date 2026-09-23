"""Read-only diagnostic of native images and latest saved v2 placements."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from skimage.feature import SIFT, match_descriptors
from skimage.exposure import equalize_adapthist
from skimage.measure import ransac
from skimage.transform import SimilarityTransform, AffineTransform, EuclideanTransform
from scipy import ndimage as ndi

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
paths=sorted((ROOT/'outputs/octa-reg_v1/prepared').glob('TS165_OD*.npz'))
review=json.loads((ROOT/'outputs/octa-reg_v2/all_samples/TS165_OD/human_review.json').read_text())
images=[];features=[];poses=[]
fig,axes=plt.subplots(2,5,figsize=(20,8.5))
for i,p in enumerate(paths):
    z=np.load(p);im=z['enface'].copy();lo,hi=np.nanpercentile(im,[2,98]);im=np.clip((im-lo)/(hi-lo),0,1)
    images.append(im)
    poses.append(np.array(review['fields'][p.stem]['matrix_to_onh_pixels']))
    axes.flat[i].imshow(im,cmap='gray',vmin=0,vmax=1)
    axes.flat[i].set_title(f'Scan {i+1} | native 512 x 512');axes.flat[i].axis('off')
    detector=SIFT(upsampling=2,c_dog=.004)
    detector.detect_and_extract(equalize_adapthist(im,clip_limit=.02))
    features.append((detector.keypoints[:,::-1].astype(float),detector.descriptors))
fig.suptitle('TS165 OD — identical native pixel scale; independent 2–98% contrast stretch',fontsize=18)
fig.tight_layout();fig.savefig(OUT/'native_contact_sheet.png',dpi=130);plt.close(fig)
records=[]
for a,b in [(a,b) for a in range(10) for b in range(a+1,10) if a>=6 or b>=6]:
    pa,da=features[a];pb,db=features[b]
    matches=match_descriptors(da,db,max_ratio=.85,cross_check=True)
    src=pa[matches[:,0]];dst=pb[matches[:,1]]
    if len(matches)<5:continue
    manual=np.linalg.inv(poses[b])@poses[a]
    record=dict(a=a+1,b=b+1,matches=len(matches),manual=manual.tolist(),fits={})
    for cls in (EuclideanTransform,SimilarityTransform,AffineTransform):
        model,ok=ransac((src,dst),cls,min_samples=3,residual_threshold=4,max_trials=4000,rng=165)
        if not model:continue
        residual=model.residuals(src[ok],dst[ok]);sing=np.linalg.svd(model.params[:2,:2],compute_uv=False)
        record['fits'][cls.__name__]=dict(matrix=model.params.tolist(),inliers=int(ok.sum()),scale_singular_values=sing.tolist(),median_error=float(np.median(residual)),span=np.ptp(src[ok],axis=0).tolist(),source=src[ok].tolist(),target=dst[ok].tolist())
    records.append(record)
    print(a+1,b+1,[(k,v['inliers'],np.round(v['scale_singular_values'],3).tolist()) for k,v in record['fits'].items()],flush=True)
(OUT/'pair_fits.json').write_text(json.dumps(dict(review_revision=review['revision'],scans=[p.stem for p in paths],pairs=records),indent=2))
