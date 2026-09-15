"""Recorded execution adapter: preserve frozen outputs and never open test data."""
import json
import os
from pathlib import Path
import re
import runpy
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'code'))
DATA = HERE.parent / '20260908_v2'
OLD3 = HERE.parent / '20260908_v3_readability'
manifest = json.loads((DATA / 'manifest.json').read_text())
cache = json.loads((DATA / 'cache_manifest.json').read_text())
locked = {'TS247', 'TS283', 'TS328'}

def norm(p):
    return os.path.normcase(os.path.abspath(p))

blocked = set()
for r in manifest['records']:
    if r['animal'] in locked:
        for p in [r['label']['path'], r['targets'], cache['entries'][r['key']]['file']['path']]:
            blocked.add(norm(p))
for sid, src in manifest['sources'].items():
    if any(a in sid for a in locked):
        for key in ('source', 'segmentation', 'pack', 'scope_hash', 'footprint'):
            if src[key]:
                blocked.add(norm(src[key]['path']))

def forbidden(p):
    return norm(p) in blocked or bool(re.search(r'(?:TS|T)(?:247|283|328)(?!\d)', str(p), re.I)) or 'repeatability' in str(p).lower()

def audit(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    p = os.fsdecode(args[0])
    if forbidden(p):
        raise PermissionError('Locked animal/repeatability file access blocked: ' + p)
    mode, flags = args[1], args[2]
    writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    if writing and any(norm(p).startswith(norm(root) + os.sep) for root in (DATA, OLD3)):
        raise PermissionError('Frozen output write blocked: ' + p)

sys.addaudithook(audit)
kind, target, *rest = sys.argv[1:]
if kind in ('report', 'tests'):
    import stage_a.common as common
    destination = HERE / 'checks' / target
    destination.mkdir(parents=True, exist_ok=True)
    original_output = common.output_dir
    original_json, original_csv, original_verify = common.write_json, common.write_csv, common.verify
    def redirect(p):
        p = Path(p).resolve()
        return destination / p.relative_to(DATA) if p.is_relative_to(DATA) else p
    common.output_dir = lambda p: original_output(redirect(p))
    common.write_json = lambda p, obj: original_json(redirect(p), obj)
    common.write_csv = lambda p, rows: original_csv(redirect(p), rows)
    if kind == 'report':
        skipped, verified = [], []
        def scoped_verify(fp):
            if forbidden(fp['path']):
                skipped.append(fp['path'])
            else:
                original_verify(fp)
                verified.append(fp['path'])
        common.verify = scoped_verify
        runpy.run_path(str(ROOT / 'code/stage_a_report.py'), run_name='__main__')
        original_json(destination / 'verification_scope.json', dict(
            verified_files=len(verified), skipped_locked_files=len(skipped),
            full_cohort_counts_source='frozen manifest metadata; locked file contents not verified',
            locked_animal_data_read=False, repeatability_data_read=False))
    else:
        sys.argv = ['stage_a.test_stage_a']
        runpy.run_module('stage_a.test_stage_a', run_name='__main__')
elif kind == 'module':
    sys.argv = [target] + rest
    runpy.run_module(target, run_name='__main__')
elif kind == 'script':
    sys.argv = [target] + rest
    runpy.run_path(str(ROOT / target), run_name='__main__')
else:
    raise ValueError(kind)
