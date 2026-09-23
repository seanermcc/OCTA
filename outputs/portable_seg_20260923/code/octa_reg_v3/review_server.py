"""Loopback reviewer; human montage decisions never overwrite registration inputs."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import threading
from urllib.parse import urlsplit

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / 'outputs/octa-reg_v3'
LOCK = threading.Lock()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fingerprint(data):
    baseline = [data['summary']['group'], data['summary']['canvas_origin'],
                [(s['scan_id'], s['tier'], s.get('matrix_to_onh_pixels')) for s in data['scans']]]
    return hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()


def rigid(m):
    if not isinstance(m, list) or len(m) != 3 or any(not isinstance(r, list) or len(r) != 3 for r in m):
        return False
    if any(type(v) not in (float, int) or not math.isfinite(v) for r in m for v in r):
        return False
    a,b,x = m[0]; c,d,y = m[1]
    return (max(abs(m[2][i]-[0,0,1][i]) for i in range(3)) < 1e-8
            and max(abs(a*a+c*c-1), abs(b*b+d*d-1), abs(a*b+c*d), abs(a*d-b*c-1)) < 1e-6
            and max(abs(x), abs(y)) < 100000)


def validate(data, body):
    if body.get('base_fingerprint') != fingerprint(data):
        raise ValueError('Automatic placements changed. Reload before reviewing.')
    fields = body.get('fields')
    if not isinstance(fields, dict):
        raise ValueError('Invalid fields')
    scans = {s['scan_id']: s for s in data['scans']}
    decisions = body.get('decisions', {})
    if not isinstance(decisions, dict): raise ValueError('Invalid review decisions')
    for sid, decision in decisions.items():
        if sid not in scans or not isinstance(decision, dict) or set(decision) != {'tier','notes'}:
            raise ValueError('Unknown scan or invalid decision')
        if decision['tier'] not in ('supported','uncertain','excluded'):
            raise ValueError('Invalid review category')
        if scans[sid]['tier']=='excluded' and decision['tier']!='excluded':
            raise ValueError('Original source exclusions remain locked')
        if not isinstance(decision['notes'], str) or len(decision['notes'])>8000:
            raise ValueError('Notes must be text, up to 8000 characters')
        if decision['tier']=='supported' and not scans[sid].get('matrix_to_onh_pixels') and sid not in fields:
            raise ValueError('Place an unlocalized field before marking it supported')
    for sid, f in fields.items():
        if sid not in scans or scans[sid]['tier'] == 'excluded':
            raise ValueError('Unknown or explicitly excluded field')
        if not isinstance(f, dict) or set(f) != {'matrix_to_onh_pixels', 'status'}:
            raise ValueError('Invalid field record')
        if f['status'] not in ('draft', 'confirmed') or not rigid(f['matrix_to_onh_pixels']):
            raise ValueError('Expected a finite rigid placement and explicit review status')
    if type(body.get('montage_confirmed')) is not bool:
        raise ValueError('Invalid montage decision')
    origin = body.get('onh_override')
    if origin is not None and (not isinstance(origin, list) or len(origin) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) >= 100000 for v in origin)):
        raise ValueError('Expected a finite ONH center in the original coordinate frame')
    if body['montage_confirmed'] and any(decisions.get(s['scan_id'],{}).get('tier',s['tier']) == 'supported' and
            not s.get('matrix_to_onh_pixels') and s['scan_id'] not in fields for s in data['scans']):
        raise ValueError('Localize every supported field before confirming the whole montage')


def current(folder, data):
    path = folder/'human_review.json'
    if path.exists():
        result = load(path)
        if result['base_fingerprint'] != fingerprint(data):
            raise ValueError('Saved review belongs to different automatic placements; preserve it and reconcile first.')
        result.setdefault('onh_override', None)
        result.setdefault('decisions', {})
        result['supports_manual_onh'] = True
        result['supports_review_categories'] = True
        return result
    inherited = data.get('inherited_review')
    if inherited:
        result=dict(schema='octa-reg-v3-inherited-review-1', group=data['summary']['group'],
                    base_fingerprint=fingerprint(data),revision=0,fields={},decisions={},
                    montage_confirmed=inherited['montage_confirmed'],onh_override=None,
                    supports_manual_onh=True,supports_review_categories=True,
                    inherited_from=dict(source=inherited['source'],revision=inherited['revision']))
        for row in inherited['records']:
            sid=row['scan_id'];m=row['matrix_to_current_origin_pixels']
            if m is not None:result['fields'][sid]=dict(matrix_to_onh_pixels=m,status='confirmed' if row['placement_confirmed'] else 'draft')
            if row['review_tier']!='unlocalized':result['decisions'][sid]=dict(tier=row['review_tier'],notes=row['notes'])
        return result
    return dict(schema='octa-reg-v3-human-review-1', group=data['summary']['group'],
                base_fingerprint=fingerprint(data), revision=0, fields={}, montage_confirmed=False,
                onh_override=None, supports_manual_onh=True, decisions={}, supports_review_categories=True)


def effective_poses(data, fields, origin, decisions=None):
    """Rebase coordinates only; render positions and pairwise registration stay fixed."""
    result = {}
    for s in data['scans']:
        if (decisions or {}).get(s['scan_id'],{}).get('tier',s['tier']) == 'excluded': continue
        m = fields.get(s['scan_id'], {}).get('matrix_to_onh_pixels', s.get('matrix_to_onh_pixels'))
        if m is not None:
            m = copy.deepcopy(m)
            m[0][2] -= (origin or [0,0])[0]; m[1][2] -= (origin or [0,0])[1]
            result[s['scan_id']] = m
    return result


def analysis_records(data, review):
    decisions=review.get('decisions',{}); fields=review['fields']
    poses=effective_poses(data,fields,review.get('onh_override'),decisions)
    records=[]
    for s in data['scans']:
        decision=decisions.get(s['scan_id'],{}); tier=decision.get('tier',s['tier'])
        records.append(dict(scan_id=s['scan_id'],automatic_tier=s['tier'],review_tier=tier,
            tier_source='manual' if decision else 'automatic',notes=decision.get('notes',''),
            placement_confirmed=fields.get(s['scan_id'],{}).get('status')=='confirmed' and tier!='excluded',
            eligible_for_primary_analysis=review['montage_confirmed'] and tier=='supported' and s['scan_id'] in poses,
            matrix_to_current_origin_pixels=poses.get(s['scan_id'])))
    return records


def analysis_inputs(folder, include_flagged=False, require_confirmed=True):
    """Future analysis entry point: fail on unfinished reviews; exclude flagged by default."""
    folder=Path(folder); data=load(folder/'montage.json'); review=current(folder,data)
    if require_confirmed and not review['montage_confirmed']:
        raise ValueError('Montage review is not confirmed')
    rows=analysis_records(data,review)
    allowed={'supported','uncertain','unlocalized'} if include_flagged else {'supported'}
    return dict(group=data['summary']['group'],review_revision=review['revision'],
        montage_confirmed=review['montage_confirmed'],onh_override=review.get('onh_override'),
        records=[r for r in rows if r['review_tier'] in allowed and r['matrix_to_current_origin_pixels'] is not None])


def save(folder, data, body):
    prior = current(folder, data)
    if body.get('revision') != prior['revision']:
        raise ValueError('Another tab saved a newer review. Export your draft, then reload.')
    body=copy.deepcopy(body)
    body.setdefault('decisions',prior.get('decisions',{}))
    validate(data, body)
    now = datetime.now(timezone.utc).isoformat()
    origin = body.get('onh_override', prior.get('onh_override'))
    result = dict(schema='octa-reg-v3-human-review-1', group=data['summary']['group'],
                  base_fingerprint=fingerprint(data), revision=prior['revision']+1,
                  fields=copy.deepcopy(body['fields']), montage_confirmed=body['montage_confirmed'], saved_at=now,
                  onh_override=copy.deepcopy(origin), supports_manual_onh=True,
                  decisions=copy.deepcopy(body['decisions']), supports_review_categories=True,
                  onh_origin_kind='manual_onh' if origin is not None else data['summary'].get('origin_kind','unresolved'),
                  effective_matrices_to_onh_pixels=effective_poses(data, body['fields'], origin, body['decisions']),
                  coordinate_system='native pixels relative to unchanged automatic ONH/reference origin',
                  automatic_registration_sha256=hashlib.sha256((folder/'montage.json').read_bytes()).hexdigest())
    result['analysis_records']=analysis_records(data,result)
    if data.get('inherited_review'):
        result['inherited_from']={k:data['inherited_review'][k] for k in ('source','revision')}
    result['analysis_policy']='Use analysis_inputs: confirmed montage required, supported only by default; flagged opt-in; excluded never included.'
    # Immutable revisions make undo/reconfirmation auditable. Only this UI's review records are written.
    history = folder/'review_history'; history.mkdir(exist_ok=True)
    encoded = json.dumps(result, indent=2, allow_nan=False)
    with (history/f'{result["revision"]:06d}.json').open('x', encoding='utf-8') as f:
        f.write(encoded)
    temp = folder/'human_review.json.tmp'
    temp.write_text(encoded, encoding='utf-8'); os.replace(temp, folder/'human_review.json')
    return result


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        self.root = Path(directory).resolve()
        super().__init__(*args, directory=str(self.root), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def reply(self, code, payload):
        raw = json.dumps(payload).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def api_folder(self):
        match = re.fullmatch(r'/api/review/(TS\d+_(?:OD|OS))', urlsplit(self.path).path)
        if not match: raise ValueError('Unknown review route')
        folder = (self.root/match[1]).resolve()
        if folder.parent != self.root or not (folder/'montage.json').is_file():
            raise ValueError('Unknown montage')
        return folder

    def do_GET(self):
        if self.path in ('/api/health','/health'): return self.reply(200, {'service': 'octa-reg-v3-review', 'supports_manual_onh': True, 'root':str(self.root), 'pid':os.getpid()})
        if self.path.startswith('/api/'):
            try:
                folder = self.api_folder()
                with LOCK: result = current(folder, load(folder/'montage.json'))
                self.reply(200, result)
            except (ValueError, OSError) as e: self.reply(409, {'error': str(e)})
        else: super().do_GET()

    def do_POST(self):
        # Same-origin JSON only. No CORS, arbitrary paths, or non-loopback listeners.
        origin = self.headers.get('Origin')
        if origin != f'http://{self.headers.get("Host")}' or urlsplit(origin).hostname not in ('127.0.0.1', 'localhost'):
            return self.reply(403, {'error': 'Same-origin local review only'})
        if self.headers.get('Content-Type') != 'application/json':
            return self.reply(415, {'error': 'Expected JSON'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size < 1000000: raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(size))
            folder = self.api_folder()
            with LOCK: result = save(folder, load(folder/'montage.json'), body)
            self.reply(200, result)
        except (ValueError, OSError, TypeError, KeyError) as e:
            self.reply(409, {'error': str(e)})


def main():
    from functools import partial
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--port', type=int, default=8774)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=args.directory))
    print(f'Reviewer: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__': main()
