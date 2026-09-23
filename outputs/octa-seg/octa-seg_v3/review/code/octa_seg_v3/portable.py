"""Explicit, sealed cache-only packages; never fall back to the source computer."""
from functools import lru_cache
from pathlib import Path
import numpy as np
from .common import ROOT, read, fingerprint


def enabled():
    return (ROOT / 'PORTABLE_CACHE.json').is_file()


@lru_cache(maxsize=1)
def manifest():
    value = read(ROOT / 'PORTABLE_CACHE.json')
    if value.get('format') != 'octa-portable-cache-1':
        raise ValueError('Unsupported portable cache format')
    return value


def key(value):
    text = str(value).replace('\\', '/').lower()
    # Newly saved reviews may name a relocated package (different drive/root).
    # All cache assets retain their project-relative outputs/ identity.
    if '/outputs/' in text:
        return 'outputs/' + text.split('/outputs/', 1)[1]
    return text.split('/octa/', 1)[-1] if '/octa/' in text else text


def inside(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Portable path leaves the package')
    return path


def local_path(value):
    path = Path(value).resolve()
    if path.is_relative_to(ROOT.resolve()) and path.exists():
        return path
    relative = manifest()['aliases'].get(key(value))
    if relative is not None:
        path = inside(relative)
        if path.exists():
            return path
    raise FileNotFoundError('File is not in the portable package: ' + str(value))


def entries():
    return [dict(scan_id=sid, directory=str(inside(rec['directory'])))
            for sid, rec in sorted(manifest()['scans'].items())]


@lru_cache(maxsize=128)
def _verify(relative, size, mtime):
    path = inside(relative)
    if fingerprint(path) != manifest()['files'][relative]['sha256']:
        raise ValueError('Portable cache changed or is incomplete: ' + relative)


def verify(relative):
    path = inside(relative)
    stat = path.stat()
    _verify(relative, stat.st_size, stat.st_mtime_ns)


def validate_scan(sid, path, prep):
    rec = manifest()['scans'][sid]
    if path.resolve() != inside(rec['directory']):
        raise ValueError('Portable provider does not match the frozen scan')
    for relative in rec['required_files']:
        verify(relative)
    if prep['source'] != rec['source_fingerprint']:
        raise ValueError('Portable source provenance mismatch')
    # This is the original source identity, not a file to open. No fake MAT file.
    return Path(rec['source_identity'])


def overlays(sid):
    rec = manifest()['scans'][sid]
    verify(rec['context'])
    verify(rec['context_metadata'])
    meta = read(inside(rec['context_metadata']))
    with np.load(inside(rec['context']), allow_pickle=False) as arrays:
        masks = [np.array(arrays[name], copy=True) for name in ('cnv', 'vessel', 'onh', 'edge')]
    return (*masks, meta, '')


def signature(sid):
    rec = manifest()['scans'][sid]
    return tuple((str(inside(rel)), inside(rel).stat().st_mtime_ns, inside(rel).stat().st_size)
                 for rel in (rec['context'], rec['context_metadata']))
