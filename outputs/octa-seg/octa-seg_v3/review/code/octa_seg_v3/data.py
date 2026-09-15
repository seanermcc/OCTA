"""Read-only frozen-volume loading and bounded background look-ahead caching."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import threading
import time
import numpy as np
from .common import ROOT, OUT, V1, V2, BATCH, read, fingerprint, available_memory
from .policy import baseline
from octa_seg_v1.decisions import thickness
from eight_surface.config import SURFACE_NAMES, LAYER_DEFS
from cnv_review_v1.data import load_enface

THICKNESS_NAMES = [x[0] for x in LAYER_DEFS] + ['INNER_RETINA']
THICKNESS_LABELS = {'TOTAL': 'Full retina · ILM → outer RPE',
                    'PHOTORECEPTOR': 'Photoreceptor composite',
                    'INNER_RETINA': 'Inner retina · ILM → IPL/INL'}


def local_path(value):
    path = Path(value)
    if path.exists():
        return path
    parts = str(value).replace('\\', '/').split('/')
    if 'octa' in parts:
        candidate = ROOT.joinpath(*parts[parts.index('octa') + 1:])
        if candidate.exists():
            return candidate
    if 'OCTA_RawData' in parts:
        candidate = ROOT.parent.joinpath(*parts[parts.index('OCTA_RawData'):])
        if candidate.exists():
            return candidate
    raise FileNotFoundError(value)


def discover():
    """The ten v2 providers take priority; completed cohort caches supply the rest."""
    result = {}
    for folder in (BATCH / 'volumes', V2 / 'round_000/volumes'):
        if not folder.exists():
            continue
        for path in sorted(folder.iterdir()):
            if all((path / name).is_file() for name in ('prepared.json', 'measurements.npz', 'geometry.npz')):
                result[path.name] = dict(scan_id=path.name, directory=str(path.resolve()))
    return [result[key] for key in sorted(result)]


@dataclass
class Volume:
    entry: dict
    images: np.ndarray
    data: dict
    geometry: dict
    base: dict
    thickness: np.ndarray
    structural: np.ndarray
    scan: object
    overlays: tuple
    model_id: str
    provenance: dict
    seconds: float
    bytes: int
    image_mode: str


def load_volume(entry, image_budget=1024**3):
    started = time.perf_counter()
    path = Path(entry['directory'])
    prep = read(path / 'prepared.json')
    if prep['scan_id'] != entry['scan_id']:
        raise ValueError('Provider scan identity mismatch')
    with np.load(path / 'measurements.npz', allow_pickle=False) as z:
        data = {key: z[key] for key in ('raw_position_branch', 'probabilities', 'entropy',
                'vessel', 'shadow', 'label_offset', 'surface_names')}
    if list(data['surface_names']) != SURFACE_NAMES:
        raise ValueError('Provider does not use the current eight-boundary anatomy')
    with np.load(path / 'geometry.npz', allow_pickle=False) as z:
        geometry = {key: z[key] for key in z.files}
    image_path = local_path(prep['images'])
    mapped = np.load(image_path, mmap_mode='r', allow_pickle=False)
    if mapped.ndim != 3 or mapped.shape[0] != 512 or mapped.shape[2] != 512:
        raise ValueError('Expected cached canonical images [512, depth, 512]')
    if data['raw_position_branch'].shape != (512, 8, 512) or data['probabilities'].shape != (512, 8, 2, 512):
        raise ValueError('Frozen prediction/native image grid mismatch')
    if int(data['label_offset']) != int(geometry['label_offset']):
        raise ValueError('Provider and geometry disagree on canonical crop offset')
    # These caches were canonicalized with freshly detected source orientation.
    # Never flip them using a historical sample's orientation flag.
    if not (prep.get('orientation_fresh') or 'canonical' in str(prep.get('orientation', '')) or
            'fresh' in str(prep.get('orientation', ''))):
        raise ValueError('Cached image orientation provenance is missing')
    if mapped.nbytes <= image_budget:
        images = np.array(mapped, copy=True)
        image_mode = 'RAM'
    else:
        images = mapped
        image_mode = 'memory mapped (RAM limit)'
    calibration = read(V1 / 'calibration/deployment_vessels.json')['thresholds']
    shape = data['raw_position_branch'].shape
    base = {key: np.empty(shape, dtype=dtype) for key, dtype in
            [('reported_positions', np.float32), ('uncertain_estimates', np.float32),
             ('state', np.uint8), ('reason', np.uint8)]}
    offset = int(data['label_offset'])
    for row in range(512):
        b = baseline(data['raw_position_branch'][row], data['probabilities'][row], calibration,
                     data['vessel'][row], offset, images.shape[1])
        for key in base:
            base[key][row] = b[key]
    maps = thickness(base['reported_positions'], data['shadow'])
    structural = np.mean(images, axis=1, dtype=np.float32)
    source = local_path(prep['source']['path'])
    scan = SimpleNamespace(scan_id=entry['scan_id'], source_volume=source, native_shape=(512, 512),
                           retina_band=tuple(map(int, geometry['retina_band'])),
                           surface_names=tuple(SURFACE_NAMES), px_um=1.12, shadow=data['shadow'],
                           structural_bscan=lambda row: images[row])
    proposal_dir = V2 / 'proposals'
    if not (proposal_dir / f'{scan.scan_id}_proposal.npz').exists():
        proposal_dir = BATCH / 'proposals'
    overlays = load_enface(scan, ROOT / 'outputs/cnv_labels', proposal_dir)
    provider_hash = fingerprint(path / 'measurements.npz')
    model_id = 'v3-baseline-v2-policy-1:' + provider_hash + ':' + fingerprint(V1 / 'calibration/deployment_vessels.json')
    provenance = dict(provider=str(path), provider_sha256=provider_hash, image_path=str(image_path),
                      image_shape=list(images.shape), crop_offset=offset,
                      source_volume=str(source), source_fingerprint=prep['source'],
                      orientation='existing canonical cache; original fresh detection retained',
                      model_id=model_id, human_guards_loaded=False,
                      note='Frozen raw predictions + v2 working policy; no other reviewer curves loaded.')
    arrays = [images, maps, structural, *data.values(), *base.values(), *geometry.values()]
    for array in arrays:
        if isinstance(array, np.ndarray):
            array.setflags(write=False)
    nbytes = sum(a.nbytes for a in arrays if isinstance(a, np.ndarray) and not isinstance(a, np.memmap))
    return Volume(entry, images, data, geometry, base, maps, structural, scan, overlays,
                  model_id, provenance, time.perf_counter() - started, nbytes, image_mode)


class VolumeCache:
    """Current + next two volumes; one reader prevents competing disk decompressions."""
    def __init__(self, entries, max_bytes=None, loader=load_volume):
        self.entries = {x['scan_id']: x for x in entries}
        self.max_bytes = max_bytes or min(3 * 1024**3, max(256 * 1024**2, available_memory() // 4))
        self.loader = loader
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='octa-v3-read-cache')
        self.lock = threading.RLock()
        self.cache = OrderedDict()
        self.pending = {}
        self.current = None
        self.hits = 0
        self.misses = 0
        self.closed = False

    def _load(self, sid):
        value = self.loader(self.entries[sid], image_budget=max(0, self.max_bytes // 3 - 100 * 1024**2))
        with self.lock:
            if self.closed:
                return value
            self.cache[sid] = value
            self.cache.move_to_end(sid)
            while len(self.cache) > 3 or sum(v.bytes for v in self.cache.values()) > self.max_bytes:
                candidates = [key for key in self.cache if key != self.current and key != sid]
                if not candidates:
                    break
                self.cache.pop(candidates[0])
        return value

    def request(self, sid, foreground=False):
        with self.lock:
            if foreground:
                self.current = sid
                for key, future in list(self.pending.items()):
                    if key != sid and not future.running():
                        if future.cancel() or future.done():
                            self.pending.pop(key, None)
            if sid in self.cache:
                self.hits += 1
                self.cache.move_to_end(sid)
                return self.cache[sid], None
            future = self.pending.get(sid)
            if future is None or future.cancelled() or (future.done() and future.exception() is not None):
                self.misses += 1
                future = self.executor.submit(self._load, sid)
                self.pending[sid] = future
            return None, future

    def prefetch(self, ids):
        for sid in ids[:2]:
            self.request(sid)

    def status(self):
        with self.lock:
            # Drop completed futures so they do not retain evicted volume arrays.
            for key, future in list(self.pending.items()):
                if future.done():
                    self.pending.pop(key, None)
            return dict(ready=list(self.cache), loading=[k for k, f in self.pending.items() if not f.done()],
                        bytes=sum(v.bytes for v in self.cache.values()), budget=self.max_bytes,
                        hits=self.hits, misses=self.misses)

    def close(self):
        with self.lock:
            self.closed = True
            self.cache.clear()
            self.pending.clear()
        self.executor.shutdown(wait=False, cancel_futures=True)
