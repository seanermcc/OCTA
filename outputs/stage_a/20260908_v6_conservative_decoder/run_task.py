"""Development-only reads and new-experiment-only writes, including tests."""
import json
import os
from pathlib import Path
import re
import runpy
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'code')); sys.dont_write_bytecode=True
DATA=HERE.parent/'20260908_v2'
manifest=json.loads((DATA/'manifest.json').read_text())
cache=json.loads((DATA/'cache_manifest.json').read_text())
def norm(p): return os.path.normcase(os.path.abspath(p))
blocked=set()
for r in manifest['records']:
    if r['animal'] in {'TS247','TS283','TS328'}:
        blocked.update(norm(p) for p in (r['label']['path'],r['targets'],cache['entries'][r['key']]['file']['path']))
def audit(event,args):
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)): return
    p=os.fsdecode(args[0])
    if norm(p) in blocked or re.search(r'(?:TS|T)(?:247|283|328)(?!\d)',p,re.I) or 'repeatability' in p.lower():
        raise PermissionError('Locked data read blocked: '+p)
    mode,flags=args[1:3]
    writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
    if writing and not norm(p).startswith(norm(HERE)+os.sep): raise PermissionError('Writes restricted to new experiment: '+p)
sys.addaudithook(audit)
kind,target,*rest=sys.argv[1:]
if kind=='tests':
    import stage_a.common as common
    out,jsonwrite=common.output_dir,common.write_json
    def redirect(p):
        p=Path(p)
        return HERE/'checks'/p.relative_to(DATA) if p.is_relative_to(DATA) else p
    common.output_dir=lambda p:out(redirect(p))
    common.write_json=lambda p,o:jsonwrite(redirect(p),o)
elif kind!='module': raise ValueError(kind)
sys.argv=[target]+rest
runpy.run_module(target,run_name='__main__')
