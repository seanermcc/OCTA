from common import *
from urllib.request import urlopen
from PIL import Image
from media import gray
import io
cases=read(HERE/'data/selection.json')['acquisitions'];records={r['scan_id']:r for r in read(HERE/'gallery/media_manifest.json')['records']};tested=[]
for a in cases:
 sid=a['scan_id'];r=records[sid];native=np.load(r['images']['path'],mmap_mode='r')
 for row in (0,511):
  with urlopen(f'http://127.0.0.1:8799/bscan?scan={sid}&row={row}') as response:got=np.array(Image.open(io.BytesIO(response.read())))
  assert np.array_equal(got,gray(native[row],r['bscan_display_limits']))
 tested.append(sid)
write(HERE/'verification/HTTP_NATIVE_ROWS_QA.json',dict(passed=True,acquisitions=len(tested),native_rows=[0,511],lossless_png_values_match_native_display_transform=True,scans=tested))
print('HTTP edge B-scans verified for all',len(tested),'acquisitions')
