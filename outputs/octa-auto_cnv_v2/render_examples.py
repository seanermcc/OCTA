from common import *
from pilot import figure
for v in selected():
 p=HERE/'scans'/v['scan_id']; figure(v['scan_id'],npz(p/'maps.npz'),p/'overview.png')
print('Regenerated 17 overview figures')
