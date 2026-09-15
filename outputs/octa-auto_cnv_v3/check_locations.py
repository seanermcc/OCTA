from common import *
from scipy import ndimage as ndi
from algorithm import grow
for day in ('D7','D28'):
 v=next(v for v in selected() if v['day_label']==day and v['eye']=='OD')
 a=npz(ROOT/'outputs/octa-auto_cnv_v2/scans'/v['scan_id']/'maps.npz');c=npz(HERE/'development'/f'{v["scan_id"]}.npz')
 labs,n=ndi.label(a['manual_cnv'],np.ones((3,3)))
 for i in range(1,n+1):
  mask=labs==i; y,x=np.nonzero(mask); print(day,'manual',i,'center',round(y.mean()),round(x.mean()),'hit',bool((mask&grow(c['core'],75)).any()))
 print('screened',[(round(r['row']),round(r['col']),r['pixels'],r['screen_reasons']) for r in json.loads(str(c['screened_records_json'])) if r['pixels']>=250])
