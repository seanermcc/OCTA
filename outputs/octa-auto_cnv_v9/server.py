"""Local gallery and explicit human review decisions; frozen model assets stay read-only."""
from common import *
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from PIL import Image
import io,threading,webbrowser,argparse
from media import gray
from review_store import ReviewStore,ReviewConflict
STATIC_ROOT=HERE/'gallery'
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kw):super().__init__(*args,directory=str(STATIC_ROOT),**kw)
 def json_response(self,value,status=200):
  payload=json.dumps(value,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(payload)
 def do_POST(self):
  try:
   url=urlparse(self.path)
   if url.path!='/reviews':self.send_error(404);return
   origin=self.headers.get('Origin')
   if origin and origin!=f"http://{self.headers.get('Host')}":self.send_error(403);return
   if self.headers.get('Content-Type','').split(';')[0]!='application/json':self.send_error(415);return
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=32768:raise ValueError('Invalid review request size')
   payload=json.loads(self.rfile.read(size));sid=payload.pop('scan_id')
   self.json_response(REVIEWS.save(sid,payload))
  except ReviewConflict as exc:self.json_response(dict(error=str(exc)),409)
  except (ValueError,KeyError,TypeError) as exc:self.json_response(dict(error=str(exc)),400)
  except Exception:self.json_response(dict(error='Review could not be saved; reload to check the saved state before retrying'),500)
 def do_GET(self):
  url=urlparse(self.path)
  if url.path=='/health':
   self.json_response(dict(app='octa-cnv-v9-gallery',root=str(HERE),pid=os.getpid(),review_api=1));return
  if url.path in ('/reviews','/reviews/export','/reviews/model2-queue'):
   try:self.json_response(REVIEWS.queue() if url.path.endswith('model2-queue') else REVIEWS.all())
   except ReviewConflict as exc:self.json_response(dict(error=str(exc)),409)
   return
  if url.path=='/bscan':
   try:
    args=parse_qs(url.query);sid=args['scan'][0];row=int(args['row'][0])
    if sid not in MEDIA or not 0<=row<=511:raise ValueError('Unknown scan/row')
    r=MEDIA[sid];fp=r['images'];st=Path(fp['path']).stat()
    if st.st_size!=fp['bytes'] or st.st_mtime_ns!=fp['mtime_ns']:raise ValueError('Native provider changed; reverify before viewing')
    data=np.load(fp['path'],mmap_mode='r');img=Image.fromarray(gray(data[row],r['bscan_display_limits']));buf=io.BytesIO();img.save(buf,format='PNG');payload=buf.getvalue();self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(payload)));self.send_header('Cache-Control','private, max-age=3600');self.end_headers();self.wfile.write(payload)
   except Exception as e:self.send_error(400,str(e))
   return
  # Static server is confined to gallery; no annotation or raw-volume HTTP endpoint.
  return super().do_GET()
 def log_message(self,*args):pass
def main():
 global MEDIA,STATIC_ROOT,REVIEWS
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8799);parser.add_argument('--open',action='store_true');parser.add_argument('--fixture',action='store_true');args=parser.parse_args()
 if args.fixture:STATIC_ROOT=HERE/'verification/ui_fixture'
 MEDIA={r['scan_id']:r for r in read(STATIC_ROOT/'media_manifest.json')['records']}
 REVIEWS=ReviewStore(STATIC_ROOT,HERE/'verification/ui_fixture_reviews' if args.fixture else HERE/'manual_review')
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
 if args.open:threading.Timer(.6,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
 print(f'CNV v9 gallery: http://127.0.0.1:{args.port}',flush=True);server.serve_forever()
if __name__=='__main__':main()
