"""Local final-CNV assessment. The only mutable records are new assessment flags."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import threading
import uuid

HERE=Path(__file__).resolve().parent

def read(p): return json.loads(Path(p).read_text(encoding='utf8'))

def atomic(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('w',encoding='utf8') as f:
        json.dump(obj,f,indent=2,allow_nan=False); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,p)

class Conflict(ValueError): pass

class AssessmentStore:
    def __init__(self, data, directory):
        self.cases={r['scan_id']:r for r in data['cases']}
        self.directory=Path(directory); self.lock=threading.RLock()
    def head(self,sid):
        if sid not in self.cases: raise ValueError('Unknown sample')
        path=self.directory/'decisions'/(sid+'.json')
        if path.exists():
            d=read(path)
            if d['token'] != self.cases[sid]['token']: raise Conflict('Displayed CNV selection changed. Reconcile the previous assessment before continuing.')
            return d
        return dict(scan_id=sid,token=self.cases[sid]['token'],revision=0,status='unassessed',notes='')
    def all(self):
        with self.lock: return {sid:self.head(sid) for sid in self.cases}
    def save(self,payload):
        if set(payload)!={'scan_id','token','expected_revision','status','notes'}: raise ValueError('Invalid fields')
        sid=payload['scan_id']
        if not isinstance(sid,str) or sid not in self.cases: raise ValueError('Unknown sample')
        if payload['status'] not in ('unassessed','good','review'): raise ValueError('Invalid assessment')
        if not isinstance(payload['notes'],str) or len(payload['notes'])>4000: raise ValueError('Notes must be at most 4000 characters')
        if type(payload['expected_revision']) is not int: raise ValueError('Invalid revision')
        with self.lock:
            old=self.head(sid)
            if old['revision']!=payload['expected_revision'] or old['token']!=payload['token']: raise Conflict('Assessment changed in another tab. Reload before saving.')
            if old['status']==payload['status'] and old['notes']==payload['notes']: return old
            r=dict(scan_id=sid,token=old['token'],revision=old['revision']+1,status=payload['status'],notes=payload['notes'],updated_at=datetime.now(timezone.utc).isoformat(),source=self.cases[sid]['source'],mask_sha256=self.cases[sid]['mask_sha256'],human_action='explicit final CNV assessment in browser',previous_revision_sha256=hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest())
            hp=self.directory/'history'/sid/(str(r['revision']).zfill(6)+'.json')
            if hp.exists(): raise Conflict('An interrupted save needs reconciliation before another revision can be written.')
            atomic(hp,r); atomic(self.directory/'decisions'/(sid+'.json'),r)
            return r

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(HERE/'gallery'),**kwargs)
    def respond(self,data,status=200):
        body=json.dumps(data,allow_nan=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        p=urlparse(self.path).path
        try:
            if p=='/health': return self.respond(dict(app='cnv-final-assessment',root=str(HERE),pid=os.getpid()))
            if p in ('/assessments','/export'):
                records=STORE.all()
                if p=='/export':
                    return self.respond(dict(schema='cnv-final-assessment-export-v1',records=records,flagged=[DATA_BY_ID[s] for s,r in records.items() if r['status']=='review'],separate_prior_queue=DATA['excluded']))
                return self.respond(records)
            return super().do_GET()
        except Conflict as exc: self.respond(dict(error=str(exc)),409)
    def do_POST(self):
        try:
            if self.path!='/assessments': self.send_error(404); return
            if self.headers.get('Origin') not in (None,'http://'+self.headers.get('Host','')): self.send_error(403); return
            if self.headers.get('Content-Type','').split(';')[0]!='application/json': self.send_error(415); return
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<20000: raise ValueError('Invalid request size')
            self.respond(STORE.save(json.loads(self.rfile.read(size))))
        except Conflict as exc: self.respond(dict(error=str(exc)),409)
        except (ValueError,KeyError,TypeError) as exc: self.respond(dict(error=str(exc)),400)
        except Exception: self.respond(dict(error='Save failed. Keep this page open and retry after checking the server.'),500)
    def log_message(self,*args): pass

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8805); parser.add_argument('--assessment-dir',type=Path,default=HERE/'assessment')
    args=parser.parse_args(); DATA=read(HERE/'gallery/data.json'); DATA_BY_ID={r['scan_id']:r for r in DATA['cases']}; STORE=AssessmentStore(DATA,args.assessment_dir)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print('Final CNV assessment: http://127.0.0.1:'+str(args.port),flush=True); server.serve_forever()
