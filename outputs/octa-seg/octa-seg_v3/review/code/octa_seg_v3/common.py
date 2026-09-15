from pathlib import Path
import hashlib
import json
import os
import re
import uuid

OUT = Path(__file__).resolve().parents[2]
V3 = OUT.parent
ROOT = next((p for p in OUT.parents if (p / 'PIPELINE.md').is_file() and (p / 'code/octa/labels.py').is_file()), None)
if ROOT is None or OUT.name != 'review' or V3.name != 'octa-seg_v3':
    raise RuntimeError('Review must be installed at <project>/outputs/octa-seg/octa-seg_v3/review.')
V2 = V3.parent / 'octa-seg_v2'
V1 = V3.parent / 'octa-seg_v1'
BATCH = ROOT / 'outputs/octa-seg_v1_batch'
CATEGORIES = {'cnv': 'CNV', 'onh': 'ONH', 'artifact': 'Shadow / low signal / artifact',
              'clear': 'Clearly readable tissue'}
ROLES = {'development': 'Development', 'assessment': 'Reserved assessment', 'practice': 'Practice'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def writable(path):
    path = Path(path).resolve()
    if not path.is_relative_to(OUT):
        raise ValueError('All v3 outputs must stay inside octa-seg_v3')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write(path, value):
    path = writable(path)
    content = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def fingerprint(path):
    path = Path(path)
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def reviewer_id(value):
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,39}', value) or value in {'con', 'prn', 'aux', 'nul'}:
        raise ValueError('Use 1–40 letters, numbers, underscores or hyphens for your reviewer ID.')
    if re.fullmatch(r'(com|lpt)[0-9]', value):
        raise ValueError('That name is reserved by Windows.')
    return value


def available_memory():
    """Read RAM without WMI permissions or an additional dependency."""
    import ctypes
    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ('total', 'available', 'total_page', 'available_page', 'total_virtual', 'available_virtual', 'extended')]
    if os.name == 'nt':
        state = MemoryStatus()
        state.length = ctypes.sizeof(state)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            return state.available
    return 4 * 1024**3
