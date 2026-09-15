"""Local-only reviewer: observations and time, no writes to source annotations."""
from common import *
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from io import BytesIO
import argparse
import threading
import webbrowser
from PIL import Image

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(HERE),**kwargs)
    def do_GET(self):
        uri=urlparse(self.path)
        if uri.path=='/bscan':
            try:
                args=parse_qs(uri.query);sid=args['scan'][0];row=int(args['row'][0]);x=int(args.get('x',['256'])[0])
                allowed={r['scan_id'] for r in read(HERE/'data/manifest.json')['scans']}
                if sid not in allowed or not 0<=row<512 or not 0<=x<512:raise ValueError('Unknown scan/row/column')
                images=np.load(volume_path(sid)/'images.npy',mmap_mode='r');a=images[row]
                lo,hi=np.percentile(a,[2,98]);v=(np.clip((a-lo)/max(hi-lo,1e-6),0,1)*255).astype('uint8')
                from PIL import ImageDraw
                shown=Image.fromarray(v).convert('RGB');draw=ImageDraw.Draw(shown);draw.line((x,0,x,v.shape[0]-1),fill=(255,196,71),width=1)
                out=BytesIO();shown.save(out,format='PNG');raw=out.getvalue()
                self.send_response(200);self.send_header('Content-Type','image/png');self.end_headers();self.wfile.write(raw)
            except Exception as e:self.send_error(400,str(e))
        else:super().do_GET()
    def do_POST(self):
        if self.path!='/review-event':self.send_error(404);return
        # Only this local page may submit review observations; source annotation writers are never imported.
        origin=self.headers.get('Origin','')
        if origin and origin!=f'http://127.0.0.1:{self.server.server_port}':self.send_error(403);return
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<16000:raise ValueError('Invalid payload')
            d=json.loads(self.rfile.read(length));valid={q['id'] for q in read(HERE/'review/queue.json')}
            if d['item_id'] not in valid:raise ValueError('Unknown queue item')
            if d['depth_needed'] not in ('yes','no','unclear'):raise ValueError('Choose a depth assessment')
            if d['model'] not in ('A','B','C','v3','comparison'):raise ValueError('Unknown review arm')
            for key in ('additions','removals','corrections','acceptances'):
                if not isinstance(d[key],int) or not 0<=d[key]<=10000:raise ValueError('Invalid action count')
            seconds=float(d['active_seconds'])
            if not 0<=seconds<=86400:raise ValueError('Invalid elapsed time')
            result=dict(item_id=d['item_id'],model=d['model'],additions=d['additions'],removals=d['removals'],
                corrections=d['corrections'],acceptances=d['acceptances'],active_seconds=seconds,depth_needed=d['depth_needed'],
                notes=str(d.get('notes',''))[:4000],reviewer=str(d.get('reviewer',''))[:200],saved_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
                kind='human-entered review observations; not lesion label geometry',timing='browser visible and focused after Start review; user can pause')
            with self.server.write_lock:
                with dest(HERE/'review/human_observations.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result)+'\n')
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"saved":true}')
        except Exception as e:self.send_error(400,str(e))
    def log_message(self,*args):pass

def run():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8766);p.add_argument('--no-open',action='store_true');args=p.parse_args()
    try:server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    except OSError:server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.write_lock=threading.Lock()
    url=f'http://127.0.0.1:{server.server_port}/review.html'
    print('Review page: '+url,flush=True)
    if not args.no_open:webbrowser.open(url)
    server.serve_forever()

if __name__=='__main__':run()
