"""Reuse the existing region editor; automatic seeds are unclassified, isolated."""
import argparse
from types import SimpleNamespace
from common import *
from cnv_review_v1 import gui
from cnv_review_v1.data import Region, SurfaceIndex
from review_store import ReviewStore
from eight_surface.config import SURFACE_NAMES
from scipy import ndimage as ndi


class ProposalLoader(gui.Loader):
    def run(self):
        try:
            sid = self.path.stem
            a = npz(HERE/'scans'/sid/'maps.npz')
            meta = json.loads(str(a['metadata_json']))
            out = volume_path(sid)
            for name in ('geometry.npz','measurements.npz'):
                source=out/name
                if meta['audit']['input_hashes'][str(source)] != sha(source):
                    raise RuntimeError('Upstream volume changed; rerun the v2 pilot before combining maps with linked B-scans.')
            d = npz(out/'measurements.npz'); g = npz(out/'geometry.npz')
            images = np.load(out/'images.npy', mmap_mode='r')
            # Second panel is explicitly a thickness deficit, not fabricated OCTA.
            deficit_display = np.nan_to_num(a['deficit_percent'], nan=-30.)
            scan = SimpleNamespace(scan_id=sid, source_volume=Path(meta['visit']['source']),
                    native_shape=(512, 512), surface_names=tuple(SURFACE_NAMES), px_um=1.12,
                    retina_band=tuple(g['retina_band']), shadow=g['shadow'],
                    surfaces=d['raw_position_branch']-int(g['label_offset']),
                    structural_bscan=lambda row: images[row], structural_enface=a['enface'], maps=a, metadata=meta,
                    octa_enface=deficit_display, days_post_laser='', day_label=meta['visit']['day_label'],
                    vitreous_at_high_index=bool(g['vitreous_high']), segmentation_path=out/'measurements.npz')
            seed = HERE/'proposals'/f'{sid}.npz'
            proposal = npz(seed)['proposal_mask']
            store = ReviewStore(HERE/'review/regions', scan, proposal, str(seed))
            config=read(LONG/'v2/launch_config.json')
            index = SurfaceIndex([HERE/'review/surface_labels', Path(config['output'])/'surface_labels', *config['manual_sources']])
            index.refresh(scan)
            automatic = dict(name='Saved neural boundaries (experimental)', path=str(out/'measurements.npz'))
            vessel = meta['audit']['preparation']['footprints']
            enface = (a['manual_cnv'], a['vessel'], g['onh'], g['onh_edge'], vessel, '')
            self.loaded.emit((scan, scan.surfaces, np.full_like(scan.surfaces, np.nan), automatic, enface, index, store))
        except Exception as exc:
            self.failed.emit(f'{type(exc).__name__}: {exc}')




