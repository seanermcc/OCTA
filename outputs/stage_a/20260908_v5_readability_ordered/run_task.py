"""Execution guard: development reads only; writes only into this experiment."""
import json
import os
from pathlib import Path
import re
import runpy
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'code'))
sys.dont_write_bytecode = True
DATA = HERE.parent / '20260908_v2'
manifest = json.loads((DATA / 'manifest.json').read_text())
cache = json.loads((DATA / 'cache_manifest.json').read_text())

def norm(path):
    return os.path.normcase(os.path.abspath(path))

blocked = set()
for record in manifest['records']:
    if record['animal'] in {'TS247', 'TS283', 'TS328'}:
        for path in (record['label']['path'], record['targets'], cache['entries'][record['key']]['file']['path']):
            blocked.add(norm(path))

def audit(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    path = os.fsdecode(args[0])
    if norm(path) in blocked or re.search(r'(?:TS|T)(?:247|283|328)(?!\d)', path, re.I) or 'repeatability' in path.lower():
        raise PermissionError('Locked data access: ' + path)
    mode, flags = args[1:3]
    writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    if writing and not norm(path).startswith(norm(HERE) + os.sep):
        raise PermissionError('Writes restricted to new experiment: ' + path)

sys.addaudithook(audit)
kind, target, *rest = sys.argv[1:]
if kind == 'tests':
    import stage_a.common as common
    original = common.output_dir
    common.output_dir = lambda p: original(HERE / 'checks' / Path(p).relative_to(DATA)) if Path(p).is_relative_to(DATA) else original(p)
    original_json = common.write_json
    common.write_json = lambda p, o: original_json(HERE / 'checks' / Path(p).relative_to(DATA), o) if Path(p).is_relative_to(DATA) else original_json(p, o)
    sys.argv = [target] + rest
    runpy.run_module(target, run_name='__main__')
elif kind == 'module':
    sys.argv = [target] + rest
    runpy.run_module(target, run_name='__main__')
else:
    raise ValueError(kind)
