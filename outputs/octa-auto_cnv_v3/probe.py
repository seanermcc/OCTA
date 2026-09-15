from common import *
from algorithm import detect
from scipy import ndimage as ndi
for v in selected():
 a=npz(ROOT/'outputs/octa-auto_cnv_v2/scans'/v['scan_id']/'maps.npz');c,r=detect(a)
 labels,n=ndi.label(a['manual_cnv'],np.ones((3,3))); hits=sum(bool((__import__('algorithm').grow(c['core'],75)&(labels==i)).any()) for i in range(1,n+1))
 print(v['scan_id'],len(r),'hits',hits,'/',n,'points',[(round(z['row']),round(z['col']),round(z['circularity'],2),round(z['score'],2)) for z in r],flush=True)
 save_npz(HERE/'development'/f'{v["scan_id"]}.npz',**c)
 write(HERE/'development'/f'{v["scan_id"]}.json',r)
