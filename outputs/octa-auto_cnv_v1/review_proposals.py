"""Reuse the existing region editor; automatic seeds are unclassified, isolated."""
import argparse
from types import SimpleNamespace
from common import *
from cnv_review_v1 import gui
from cnv_review_v1.data import Region, RegionStore, SurfaceIndex
from eight_surface.config import SURFACE_NAMES
from scipy import ndimage as ndi


class ProposalLoader(gui.Loader):
    def run(self):
        try:
            sid = self.path.stem
            a = npz(HERE/'scans'/sid/'maps.npz')
            meta = json.loads(str(a['metadata_json']))
            out = volume_path(sid)
            d = npz(out/'measurements.npz'); g = npz(out/'geometry.npz')
            images = np.load(out/'images.npy', mmap_mode='r')
            # Second panel is explicitly a thickness deficit, not fabricated OCTA.
            deficit_display = np.nan_to_num(a['deficit_percent'], nan=-30.)
            scan = SimpleNamespace(scan_id=sid, source_volume=Path(meta['visit']['source']),
                    native_shape=(512, 512), surface_names=tuple(SURFACE_NAMES), px_um=1.12,
                    retina_band=tuple(g['retina_band']), shadow=g['shadow'],
                    surfaces=d['raw_position_branch']-int(g['label_offset']),
                    structural_bscan=lambda row: images[row], structural_enface=a['enface'],
                    octa_enface=deficit_display, days_post_laser='', day_label=meta['visit']['day_label'],
                    vitreous_at_high_index=bool(g['vitreous_high']), segmentation_path=out/'measurements.npz')
            seed = HERE/'proposals'/f'{sid}.npz'
            proposal = npz(seed)['proposal_mask']
            store = RegionStore(HERE/'review/regions', scan, proposal, str(seed))
            if not store.path.exists():
                # Group disconnected measurable islands by nearest core for editing;
                # the original proposal pixels are unchanged and gaps stay gaps.
                core_labels, count = ndi.label(a['core'], np.ones((3, 3)))
                store.regions = []
                if count:
                    indices = ndi.distance_transform_edt(~a['core'], return_distances=False, return_indices=True)
                    groups = core_labels[tuple(indices)]
                    for k in range(1, count+1):
                        mask = proposal & (groups == k)
                        store.regions.append(Region(f'auto-{k}', mask,
                            origin='octa-auto_cnv_v1 unreviewed proposal; disconnected islands grouped by nearest core for editing, not anatomical borders'))
                store.saved_signature = store.signature()  # opening alone cannot save a label
            index = SurfaceIndex([HERE/'review/surface_labels', *read(LONG/'v2/launch_config.json')['manual_sources']])
            index.refresh(scan)
            automatic = dict(name='Saved neural boundaries (experimental)', path=str(out/'measurements.npz'))
            vessel = meta['audit']['preparation']['footprints']
            enface = (a['manual_cnv'], a['vessel'], g['onh'], g['onh_edge'], vessel, '')
            self.loaded.emit((scan, scan.surfaces, np.full_like(scan.surfaces, np.nan), automatic, enface, index, store))
        except Exception as exc:
            self.failed.emit(f'{type(exc).__name__}: {exc}')


def create_window(sid=None):
    gui.Loader = ProposalLoader
    config = dict(output=str(HERE/'review'), segmentations=str(HERE/'proposals'),
                  enface_labels=str(ROOT/'outputs/cnv_labels'), proposals=str(LONG/'v2/proposals'),
                  manual_sources=read(LONG/'v2/launch_config.json')['manual_sources'], auto_sources=[], region_sources=[])
    paths = [HERE/'proposals'/f"{r['scan_id']}.npz" for r in selected() if (HERE/'proposals'/f"{r['scan_id']}.npz").exists()]
    index = next((i for i, p in enumerate(paths) if p.stem == sid), 0)
    window = gui.MainWindow(config, paths=paths, start_index=index)
    window.setWindowTitle('octa-auto_cnv_v1 · Edit or reject automatic proposals · isolated human review')
    window.sources_bar.hide()  # source swapping is outside this fixed pilot
    window.octa.parentWidget().setTitle('Signed thinning context (gray; missing shown dark)')
    window.structural.parentWidget().setTitle('Structural OCT · automatic regions need review')
    return window


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--scan'); parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    app = gui.QtWidgets.QApplication([]); gui.configure_app(app)
    window = create_window(args.scan)
    if args.capture:
        def capture():
            window.grab().save(str(destination(HERE/'verification/reviewer.png')))
            assert not window.store.dirty
            write(HERE/'verification/reviewer_open.json', dict(scan=window.scan.scan_id, regions=len(window.store.regions),
                   unclassified=all(r.category == 'Unclassified' for r in window.store.regions), labels_written=window.store.path.exists()))
            app.quit()
        window.ready.connect(lambda: gui.QtCore.QTimer.singleShot(800, capture))
    window.show()
    return app.exec()

if __name__ == '__main__':
    raise SystemExit(main())
