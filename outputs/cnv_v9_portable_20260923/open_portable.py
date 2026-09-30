"""Inspect portable snapshots with the current v9 editor; never write annotations."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from types import SimpleNamespace

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'outputs/octa-auto_cnv_v9/final_correction'
PORTABLE = Path('E:/octa')
DATA = PORTABLE / 'For_Segmentation'
MANIFEST = PORTABLE / 'code/PORTABLE_CACHE.json'
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE))
import common
common.HERE = HERE
import loader
import viewer

manifest = common.read(MANIFEST)
verified = set()


def checked(relative, full=True):
    path = (PORTABLE / 'code' / relative[6:]) if relative.startswith('@code/') else DATA / relative
    expected = manifest['files'][relative]
    if path.stat().st_size != expected['bytes']:
        raise ValueError('Cache size mismatch: ' + str(path))
    stamp = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
    if full and stamp not in verified:
        if common.sha(path) != expected['sha256']:
            raise ValueError('Cache SHA-256 mismatch: ' + str(path))
        verified.add(stamp)
    return path


def acquisition_queue():
    queue = []
    for sid, entry in manifest['scans'].items():
        directory = entry['directory']
        meta = common.read(checked(directory + '/prepared.json'))
        context = common.read(checked(entry['context_metadata']))
        with np.load(checked(entry['context']), allow_pickle=False) as z:
            if z['cnv'].shape != (512, 512):
                raise ValueError('CNV grid mismatch: ' + sid)
        with np.load(checked(directory + '/geometry.npz'), allow_pickle=False) as z:
            lo, hi = map(int, z['retina_band'])
            offset = int(z['label_offset'])
            if offset != (1024 - hi if bool(z['vitreous_high']) else lo):
                raise ValueError('Canonical crop mismatch: ' + sid)
        images = np.load(checked(directory + '/images.npy', full=False), mmap_mode='r')
        if list(images.shape) != entry['image_shape'] or images.shape != (512, hi - lo, 512):
            raise ValueError('Volume grid mismatch: ' + sid)
        if meta['scan_id'] != sid or meta['source']['path'] != entry['source_identity']:
            raise ValueError('Acquisition identity mismatch: ' + sid)
        a = dict(meta['acquisition'])
        a.update(scan_id=sid, source_identity=entry['source_identity'], native_shape=[512, 512],
                 directory=directory, context=entry['context'], context_metadata=entry['context_metadata'],
                 source_status=context['sources']['cnv']['status'],
                 eligibility_day_basis='actual days' if a.get('days_post_laser') else 'nominal day',
                 preview_role='Portable final-v9 snapshot; inspection only',
                 metadata_note='Structural OCT cache; OCTA channel is not included.',
                 review_notes=context['status'] + '\nSource: ' + context['sources']['cnv']['path'])
        if a.get('days_post_laser'):
            a['day_label'] = 'D' + str(a['days_post_laser'])
        queue.append(a)
    return queue


QUEUE = acquisition_queue()
original_read = viewer.read
viewer.read = lambda p: {'acquisitions': QUEUE} if Path(p) == HERE / 'queue/queue.json' else original_read(p)


def load_portable(a):
    d = a['directory']
    images = np.load(checked(d + '/images.npy'), mmap_mode='r')
    with np.load(checked(d + '/geometry.npz'), allow_pickle=False) as z:
        offset = int(z['label_offset'])
    # Cached arrays already have their recorded canonical orientation; do not flip again.
    projection = images.mean(axis=1)
    if not np.isfinite(projection).all():
        raise ValueError('Nonfinite structural projection: ' + a['scan_id'])
    return SimpleNamespace(acquisition=a, images=images, structural=projection,
                           octa=np.zeros((512, 512), np.float32),
                           metadata={'canonical_crop_offset': offset})


viewer.Cache = lambda: loader.Cache(loader=load_portable)


def seed_snapshot(store):
    a = store.acquisition
    with np.load(checked(a['context']), allow_pickle=False) as z:
        mask = z['cnv'].astype(bool)
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    pending = 'pending' in a['source_status']
    store.state['regions'] = [dict(id=f'snapshot-{i}', state='draft' if pending else 'kept',
                                   runs=common.encode(labels == i), origin={'kind': 'portable_snapshot'})
                              for i in range(1, n + 1)]
    store.state['absence'] = 'confirmed negative' in a['source_status']
    store.saved_signature = common.digest(store.state)
    return n


viewer.seed_gui_drafts = seed_snapshot


class PortableWindow(viewer.Window):
    def __init__(self, start=None):
        super().__init__(start=start)
        self.setWindowTitle(f'CNV v9 · {len(QUEUE)} portable cached acquisitions · Inspect')
        self.resize(1500, 960)
        allowed = {'Previous', 'Next', 'Return to fixed queue', 'Fit views', 'Inspect'}
        for bar in self.findChildren(viewer.W.QToolBar):
            for action in bar.actions():
                if action.text() and action.text() not in allowed:
                    action.setEnabled(False)
        for widget in (self.confirm_button, self.absence, self.prediction, self.historical,
                       self.reviewer, self.diameter):
            widget.setEnabled(False)
        self.confirm_button.setText('Saved snapshot · inspection only')
        self.context_note.setText('Inspect saved final-v9 masks. Click OCT to select a B-scan; scroll to zoom, middle-drag to pan. Source masks and review decisions remain unchanged.')
        self.octa.parentWidget().setTitle('OCTA unavailable in this portable cache')
        self.octa.parentWidget().hide()
        self.review_notes.setMaximumHeight(65)
        for label in self.findChildren(viewer.W.QLabel):
            if label.text() == 'Final assessment flags and source notes (preserved)':
                label.setText('Saved CNV status and provenance')

    def save(self):
        return True

    def mode(self, mode):
        super().mode('inspect')

    def update_progress(self):
        self.progress_label.setText(f'Portable cached acquisitions: {len(QUEUE)} · Sample {self.index + 1} / {len(QUEUE)}')
        self.coverage.setText('Source snapshot: 59 confirmed positive · 1 confirmed negative · 2 correction pending. All 512 B-scans available per sample.')

    def refresh(self):
        super().refresh()
        if self.scan:
            self.status.setText(self.scan.acquisition['source_status'] + '\nViewing saved snapshot; no new confirmation.')

    def loaded(self, scan):
        super().loaded(scan)
        self.statusBar().showMessage('Ready · Saved CNV snapshot over native structural OCT · Inspection only')
        common.atomic(HERE / 'runtime/ready.json', dict(scan_id=scan.acquisition['scan_id'],
                      samples=len(QUEUE), image_shape=list(scan.images.shape), annotations_written=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--verify-ui', action='store_true')
    p.add_argument('--scan')
    args = p.parse_args()
    from collections import Counter
    report = dict(samples=len(QUEUE), statuses=dict(Counter(a['source_status'] for a in QUEUE)),
                  masks_and_metadata_sha256='verified for all samples', image_headers='verified for all samples',
                  image_sha256='verified on loading each sample', source_editor=str(SOURCE),
                  source_viewer_sha256=common.sha(SOURCE / 'viewer.py'), annotations_written=False)
    common.atomic(HERE / 'runtime/inventory.json', report)
    print(json.dumps(report, indent=2), flush=True)
    if args.check:
        return 0
    app = viewer.W.QApplication([])
    viewer.configure_app(app)
    window = PortableWindow(args.scan)
    if args.verify_ui:
        def validate():
            try:
                for row in (0, 256, 511):
                    window.navigate(row, 256)
                    assert window.row == row and window.scan.images[row].shape[1] == 512
                union = np.zeros((512, 512), bool)
                for r in window.store.state['regions']:
                    union |= common.decode(r['runs'])
                with np.load(DATA / window.scan.acquisition['context'], allow_pickle=False) as z:
                    assert np.array_equal(union, z['cnv'])
                window.navigate(256, 256)
                def finish():
                    window.grab().save(str(HERE / 'runtime/preview.png'))
                    common.atomic(HERE / 'runtime/ui_verified.json', dict(scan_id=window.scan.acquisition['scan_id'],
                                  bscan_endpoints=True, exact_snapshot_mask=True, queue_count=window.choice.count(),
                                  annotations_written=bool(list((HERE / 'review/regions').glob('*.json')))))
                    window.close()
                    app.quit()
                viewer.Q.QTimer.singleShot(500, finish)
            except Exception:
                import traceback
                traceback.print_exc()
                app.exit(1)
        window.ready.connect(validate)
        viewer.Q.QTimer.singleShot(120000, lambda: app.exit(2))
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
