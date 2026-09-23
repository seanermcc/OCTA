"""Standalone localhost read-only truth/prediction viewer. Notes use browser storage."""
from common import *
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from functools import lru_cache
import io,base64
from PIL import Image

def png(arr):
    stream=io.BytesIO();Image.fromarray(arr).save(stream,format='PNG');return stream.getvalue()
def gray(arr):
    lo,hi=np.percentile(arr,[1,99]);return np.clip((arr-lo)/max(hi-lo,.001)*255,0,255).astype('uint8')
def b64(a):return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()

@lru_cache(maxsize=2)
def case_data(sid):
    cache=HERE/'cache'/sid;d=npz(cache/'enface.npz');v6=npz(cache/'v6.npz');m1=npz(HERE/'predictions/model1'/(sid+'.npz'));m2=npz(HERE/'predictions/model2'/(sid+'.npz'))
    truth=HERE/'data/targets'/(sid+'.npz');reference=npz(truth) if truth.exists() else None
    v6score=next((v6[k] for k in ('score','probability','probabilities','prob') if k in v6),None)
    if v6score is None:raise ValueError('Frozen v6 raw score field missing: '+str(list(v6)))
    data=dict(structural=b64(gray(d['optical'][0])),octa=b64(gray(d['optical'][1])),v6=b64(v6['mask'].astype('uint8')),v6score=b64(np.round(v6score*255).astype('uint8')),m1=b64(m1['raw_mask'].astype('uint8')),m1filtered=b64(m1['filtered_mask'].astype('uint8')),m1score=b64(np.round(m1['score']*255).astype('uint8')),suppressed=b64(m1['removal_reason']),m2=b64(m2['raw_mask'].astype('uint8')),m2score=b64(np.round(m2['score']*255).astype('uint8')),manual=b64(reference['target'].astype('uint8')) if reference else None,ignored=b64(reference['ignored'].astype('uint8')) if reference else None,reviewed=b64(reference['known'].astype('uint8')) if reference else None)
    return data

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            url=urlparse(self.path);query=parse_qs(url.query);cases=read(HERE/'data/preview.json')['cases'];ids={c['scan_id'] for c in cases}
            if url.path=='/':return self.send(200,(HERE/'viewer.html').read_bytes(),'text/html; charset=utf-8')
            if url.path=='/api/manifest':return self.json(dict(release='octa-auto_cnv_v8',preview_sha256=sha(HERE/'data/preview.json'),cases=cases,results=read(HERE/'reports/comparison.json')))
            if url.path=='/api/case':
                sid=query['sid'][0]
                if sid not in ids:return self.send(404,b'Unknown frozen case')
                return self.json(case_data(sid))
            if url.path=='/api/bscan':
                sid=query['sid'][0];row=int(query['row'][0])
                if sid not in ids or not 0<=row<512:return self.send(400,b'Invalid native coordinates')
                volume=np.load(HERE/'cache'/sid/'structural.npy',mmap_mode='r');arr=volume[row]
                return self.send(200,png(gray(arr)),'image/png')
            return self.send(404,b'Not found')
        except Exception as e:return self.send(500,str(e).encode())
    def do_POST(self):self.send(405,b'Read-only server. Comparison notes are browser-local and exportable.')
    def json(self,d):self.send(200,json.dumps(d,default=json_type).encode(),'application/json')
    def send(self,status,body,kind='text/plain'):
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass
if __name__=='__main__':
    import argparse,webbrowser
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8768);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    try:server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    except OSError:
        import urllib.request
        with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/manifest',timeout=3) as response:existing=json.load(response)
        if existing.get('release')!='octa-auto_cnv_v8' or existing.get('preview_sha256')!=sha(HERE/'data/preview.json'):raise RuntimeError('Port belongs to a different service; use --port')
        if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{args.port}')
        print(f'Existing v8 comparison: http://127.0.0.1:{args.port}',flush=True);sys.exit(0)
    if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{args.port}')
    print(f'V8 comparison: http://127.0.0.1:{args.port}',flush=True);server.serve_forever()
