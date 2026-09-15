from common import *
from eight_surface.cnv_labels import load_label
from scipy import ndimage as ndi
for p in sorted((ROOT/'outputs/cnv_labels').glob('*TS267*')):
 r=load_label(p); lab,n=ndi.label(r['cnv_mask']); sizes=np.bincount(lab.ravel())[1:]
 print(p.name,'reviewed',r['reviewed_targets'][0],'pixels',r['cnv_mask'].sum(),'components',sizes.tolist())
