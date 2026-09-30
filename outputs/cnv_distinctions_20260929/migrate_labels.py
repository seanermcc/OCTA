"""Requested category migration, delegated to the GUI's authoritative journal writer.

No human coordinates, layer labels, review timers or old events are edited.
Run without --apply for a read-only preflight of every targeted journal.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import numpy as np

ROOT = Path('D:/Projects/octa')
sys.path[:0] = [str(ROOT/'outputs/octa-seg/octa-seg_v3/review/code'),
               str(ROOT/'outputs/octa-seg/octa-seg_v2/code'), str(ROOT/'code')]
from octa_seg_v3 import common as C, lesions as L
from octa_seg_v3.feedback import resolve, STATE_KEYS, state_digest
from octa_seg_v3.label_gui import Journal, QtCore

DRIVE = Path('F:/octa')
ARCHIVE = DRIVE/'archived/cnv_gui_before_20260929/annotations'
REVIEWERS = [DRIVE/'reviewers/lead', DRIVE/'reviewers/shichu', DRIVE/'For_Segmentation/Reviews/reviewers/lead']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    providers = {p.parent.name: p.parent for group in ('Reviewed_Samples', 'More_Samples')
                 for p in (DRIVE/'For_Segmentation'/group).glob('*/prepared.json')}
    records = []
    locks = []
    for reviewer in REVIEWERS:
        lock = QtCore.QLockFile(str(reviewer/'reviewer_session.lock'))
        lock.setStaleLockTime(30000)
        if not lock.tryLock(0):
            raise RuntimeError(f'Close the reviewer before migration: {reviewer}')
        locks.append(lock)
        for path in sorted((reviewer/'journals').glob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8'))
            backup = ARCHIVE/path.relative_to(DRIVE)
            if backup.exists():
                data = json.loads(backup.read_text(encoding='utf-8'))
            assert data['reviewer_id'] == reviewer.name
            records.append((path, data, sha(backup) if backup.exists() else sha(path)))
    records.sort(key=lambda r: (r[1]['scan_id'], str(r[0])))
    prepared = []
    previous_sid = None
    for path, data, before_sha in records:
        sid = data['scan_id']
        if sid != previous_sid:
            provider = providers[sid]
            prep = json.loads((provider/'prepared.json').read_text())
            assert prep['scan_id'] == sid
            assert prep.get('orientation_fresh') or 'canonical' in str(prep.get('orientation', ''))
            with np.load(provider/'measurements.npz', allow_pickle=False) as z:
                baseline = z['raw_position_branch']; offset = int(z['label_offset'])
                boundary_names = z['surface_names'].tolist()
            shape = np.load(provider/'images.npy', mmap_mode='r').shape
            provider_sha = sha(provider/'measurements.npz')
            previous_sid = sid
        assert data['source']['provider_sha256'] == provider_sha
        assert data['source']['source_fingerprint']['sha256'] == prep['source']['sha256']
        assert data['source']['image_shape'] == list(shape)
        assert data['source']['crop_offset'] == offset
        assert data.get('boundary_names', boundary_names) == boundary_names
        raw = baseline[data['bscan']].copy()
        events = data['events'][:data['cursor']]
        before = resolve(events, raw, offset, shape[1])
        kind = L.LEGACY_MAPPING[data['reviewer_id']]
        after = resolve(events + [dict(action=L.MIGRATION_ACTION, reviewer_id=data['reviewer_id'],
                        destination=kind, from_definition=L.LEGACY_VERSION, lesion_definition=L.DEFINITION_VERSION,
                        legacy_region_runs=L.runs(before['lesions']['cnv_region']))], raw, offset, shape[1])
        assert state_digest(before) == state_digest(after)
        assert before['confirmation'] == after['confirmation']
        assert np.array_equal(before['approved'], after['approved'])
        assert np.array_equal(before['lesions']['cnv_region'], after['lesions'][kind])
        assert not after['lesions']['cnv_full' if kind == 'cnv_core' else 'cnv_core'].any()
        prepared.append((path, data, before_sha, raw, offset, shape[1], before))
    print(f'Preflight passed: {len(prepared)} journals, original providers and all layer states verified.', flush=True)
    if not args.apply:
        return
    report = []
    original_out = C.OUT
    for path, data, before_sha, raw, offset, depth, before in prepared:
        current = json.loads(path.read_text(encoding='utf-8'))
        already = bool(current['events'] and current['events'][-1]['action'] == L.MIGRATION_ACTION)
        if already:
            assert current['events'][:-1] == data['events'][:data['cursor']]
            assert current['cursor'] == len(current['events'])
        elif sha(path) != before_sha:
            raise RuntimeError(f'Journal changed after preflight: {path}')
        backup = ARCHIVE/path.relative_to(DRIVE)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(path, backup)
        assert sha(backup) == before_sha
        # Explicitly select the requested reviewer store for the existing GUI writer.
        # This process exits after migration; no application storage config changes.
        C.OUT = path.parent.parent
        journal = Journal(path, {k: data[k] for k in ('reviewer_id', 'scan_id', 'bscan', 'model_id')})
        changed = journal.migrate_cnv(raw, offset, depth)
        stored = json.loads(path.read_text())
        empty = not data['events'][:data['cursor']]
        assert changed or already or empty
        assert (stored['events'] == data['events'] if empty else stored['events'][:-1] == data['events'][:data['cursor']])
        assert stored['active_seconds'] == data['active_seconds']
        after = resolve(stored['events'][:stored['cursor']], raw, offset, depth)
        assert state_digest(before) == state_digest(after)
        assert np.array_equal(before['approved'], after['approved'])
        for key in ('cnv_edge', 'cnv_edge_state', 'cnv_edge_unreliable', 'hyper_ref'):
            assert np.array_equal(before['lesions'][key], after['lesions'][key], equal_nan=True)
        report.append(dict(path=str(path), archive=str(backup), before_sha256=before_sha, after_sha256=sha(path),
                           reviewer=data['reviewer_id'], destination=L.LEGACY_MAPPING[data['reviewer_id']],
                           columns=int(before['lesions']['cnv_region'].sum()), geometry_unchanged=True,
                           old_events_unchanged=True, new_category_not_confirmed=True,
                           status='empty_journal_unchanged' if empty else 'migrated'))
        print(f'Migrated {len(report)}/{len(prepared)} {data["reviewer_id"]}: {path.name}', flush=True)
    C.OUT = original_out
    result = dict(records=report, native_macos_execution_tested=False, labels_writer='octa_seg_v3.label_gui.Journal.migrate_cnv')
    for destination in (ROOT/'outputs/cnv_distinctions_20260929/MIGRATION_REPORT.json', DRIVE/'CNV_DISTINCTIONS_MIGRATION.json'):
        destination.write_text(json.dumps(result, indent=2), encoding='utf-8')
    for lock in locks:
        lock.unlock()


if __name__ == '__main__':
    main()
