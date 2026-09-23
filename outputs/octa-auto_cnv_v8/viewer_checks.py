"""Exercise every frozen case and full-depth navigation via the read-only HTTP API."""
from common import *
import urllib.request,urllib.error,io
from PIL import Image
def run(port=8768):
    base=f'http://127.0.0.1:{port}'
    def get(path):
        with urllib.request.urlopen(base+path,timeout=60) as r:return r.read()
    m=json.loads(get('/api/manifest'));assert len(m['cases'])==30
    checks=[]
    for c in m['cases']:
        sid=c['scan_id'];d=json.loads(get('/api/case?sid='+sid))
        import base64
        for key in ('structural','octa','v6','v6score','m1','m1filtered','m1score','suppressed','m2','m2score'):
            assert len(base64.b64decode(d[key]))==512*512,(sid,key)
        assert bool(d['manual'])==c['training_exposure']
        for row in (0,256,511):
            im=Image.open(io.BytesIO(get(f'/api/bscan?sid={sid}&row={row}')))
            assert im.size==(512,1024)
        checks.append(dict(scan_id=sid,overlays=True,rows=[0,256,511],native_bscan_size=[512,1024]))
    try:
        urllib.request.urlopen(urllib.request.Request(base+'/api/case',data=b'{}',method='POST'))
        raise AssertionError('Server allowed mutation')
    except urllib.error.HTTPError as e:assert e.code==405
    write(HERE/'verification/viewer_checks.json',dict(passed=True,http_cases=checks,post_rejected=True,browser_visual_qa='recorded separately in screenshots and browser_qa.json'))
    progress('Viewer API verified on all 30 cases and 90 native B-scans')
if __name__=='__main__':run()
