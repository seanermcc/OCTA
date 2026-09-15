"""Export frozen, role-separated training targets; never fit a model or write labels."""
import argparse
import time
import numpy as np
from .common import OUT, read, write, fingerprint, reviewer_id
from .saved import index
from .data import load_volume
from .feedback import training_targets


def export(reviewer, role):
    reviewer = reviewer_id(reviewer)
    destination = OUT / 'training_exports' / (time.strftime('%Y%m%d_%H%M%S') + '_' + reviewer + '_' + role)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = dict(format='octa-reviewed-targets-1', reviewer=reviewer, data_role=role,
        created_at=time.time(), model_training_performed=False, records=[], skipped=[])
    volume = None
    for entry in index(reviewer):
        if entry['status'] != 'Confirmed' or entry['legacy']:
            manifest['skipped'].append(dict(path=entry['path'], reason=entry['status']))
            continue
        record = read(entry['path'])
        if not record.get('training_eligible') or record['scan_id'].startswith('SYNTHETIC'):
            manifest['skipped'].append(dict(path=entry['path'], reason='test/ineligible record'))
            continue
        if volume is None or volume.model_id != record['model_id'] or volume.scan.scan_id != record['scan_id']:
            volume = load_volume(dict(scan_id=record['scan_id'], directory=record['source']['provider']), image_budget=0)
        if volume.model_id != record['model_id']:
            raise ValueError('Saved source changed; export stopped: ' + entry['path'])
        row = record['bscan']
        target = training_targets(record, volume.data['raw_position_branch'][row], int(volume.data['label_offset']),
            volume.images.shape[1], volume.data['shadow'][row], role=role)
        if not target['eligible']:
            manifest['skipped'].append(dict(path=entry['path'], reason='different frozen data role'))
            continue
        name = f'{record["scan_id"]}_b{row:04d}.npz'
        np.savez_compressed(destination/name, **{k:v for k,v in target.items() if isinstance(v,np.ndarray)})
        manifest['records'].append(dict(file=name, sha256=fingerprint(destination/name), journal=entry['path'],
            journal_sha256=fingerprint(entry['path']), reviewer_id=record['reviewer_id'], scan_id=record['scan_id'], bscan=row,
            boundary_names=volume.scan.surface_names, source=record['source'], confirmation=target['review_status'],
            geometry_revision=record['events'][record['cursor']-1].get('geometry_revision'),
            approved_positions=int(target['approved_position'].sum())))
    write(destination/'COMPLETE.json', manifest)
    return destination


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reviewer',required=True)
    parser.add_argument('--role',choices=('development','assessment'),required=True)
    args=parser.parse_args()
    print(export(args.reviewer,args.role))

if __name__=='__main__': main()
