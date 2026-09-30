"""Serve only the generated comparison on loopback; never serves the repository."""
import argparse
import functools
import http.server
import json
import re
import urllib.request
import webbrowser
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--directory', default=str(Path(__file__).resolve().parents[2]/'outputs/reviewer_comparison'))
parser.add_argument('--port', type=int, default=8818)
parser.add_argument('--open', action='store_true')
args=parser.parse_args()
folder=Path(args.directory).resolve()
if not (folder/'index.html').is_file():
    raise SystemExit('Run REFRESH_COMPARISON.cmd first.')
url=f'http://127.0.0.1:{args.port}/'
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        # Only explicit viewer exports, with no caller-controlled directories.
        name=self.path.removeprefix('/export/')
        origin=self.headers.get('Origin')
        allowed_origin=f'http://127.0.0.1:{args.port}'
        if (not self.path.startswith('/export/') or
            not re.fullmatch(r'TS[A-Za-z0-9_-]+\.(png|csv)',name) or
            self.headers.get('X-OCTA-Export')!='1' or origin not in (None,allowed_origin)):
            self.send_error(403);return
        try:
            length=int(self.headers.get('Content-Length','0'))
        except ValueError:
            self.send_error(400);return
        if not 0<length<25*1024*1024:
            self.send_error(413);return
        content=self.rfile.read(length)
        if (name.endswith('.png') and not content.startswith(b'\x89PNG\r\n\x1a\n')) or (name.endswith('.csv') and b'scan_id,bscan,scope,boundary,a_line' not in content[:100]):
            self.send_error(400);return
        export=folder/'exports';export.mkdir(exist_ok=True)
        destination=export/name
        destination.write_bytes(content)
        payload=json.dumps(dict(url='exports/'+name,path=str(destination))).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload)

    def do_GET(self):
        if self.path == '/comparison-health':
            payload=json.dumps(dict(app='octa-reviewer-comparison',directory=str(folder))).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload)
        else:
            super().do_GET()
    def end_headers(self):
        self.send_header('Cache-Control','no-cache')
        super().end_headers()
    def list_directory(self, path):
        self.send_error(403)

try:
    server=http.server.ThreadingHTTPServer(('127.0.0.1',args.port),functools.partial(Handler,directory=str(folder)))
except OSError:
    with urllib.request.urlopen(url+'comparison-health',timeout=2) as response:
        health=json.load(response)
    if health != dict(app='octa-reviewer-comparison',directory=str(folder)):
        raise SystemExit('Port belongs to another application; choose --port.')
    if args.open:webbrowser.open(url)
else:
    if args.open:webbrowser.open(url)
    print(url,flush=True)
    server.serve_forever()
