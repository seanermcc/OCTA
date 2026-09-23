"""Export frozen, role-separated training targets; never fit a model or write labels."""
import argparse
import time
import numpy as np
from .common import OUT, read, write, fingerprint, reviewer_id
from .saved import index
from .data import load_volume, local_path
from .feedback import training_targets
from .context_policy import VERSION as CONTEXT_POLICY, vessel_columns


def export(reviewer, role, include_shadow_overrides=True):
    reviewer = reviewer_id(reviewer)
    group_mode = 'include' if include_shadow_overrides else 'exclude'
    destination = OUT / 'training_exports' / (time.strftime('%Y%m%d_%H%M%S') + '_' + reviewer + '_' + role + '_shadow_' + group_mode)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = dict(format='octa-reviewed-targets-3', reviewer=reviewer, data_role=role,
        created_at=time.time(), context_policy=CONTEXT_POLICY, shadow_override_group=group_mode,
        model_training_performed=False, records=[], skipped=[])
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
            volume = load_volume(dict(scan_id=record['scan_id'], directory=str(local_path(record['source']['provider']))), image_budget=0)
            from .providers import context_overlays
            from .common import V2, BATCH
            proposal = V2 / 'proposals'
            if not (proposal / f'{volume.scan.scan_id}_proposal.npz').exists():
                proposal = BATCH / 'proposals'
            volume.overlays = context_overlays(volume, proposal)
        if volume.model_id != record['model_id']:
            raise ValueError('Saved source changed; export stopped: ' + entry['path'])
        row = record['bscan']
        target = training_targets(record, volume.data['raw_position_branch'][row], int(volume.data['label_offset']),
            volume.images.shape[1], volume.data['shadow'][row], role=role, vessel=vessel_columns(volume, row),
            include_shadow_overrides=include_shadow_overrides)
        if not target['eligible']:
            manifest['skipped'].append(dict(path=entry['path'], reason='different frozen data role'))
            continue
        name = f'{record["scan_id"]}_b{row:04d}.npz'
        np.savez_compressed(destination/name, **{k:v for k,v in target.items() if isinstance(v,np.ndarray)})
        manifest['records'].append(dict(file=name, sha256=fingerprint(destination/name), journal=entry['path'],
            journal_sha256=fingerprint(entry['path']), reviewer_id=record['reviewer_id'], scan_id=record['scan_id'], bscan=row,
            boundary_names=volume.scan.surface_names, source=record['source'], confirmation=target['review_status'],
            geometry_revision=target['confirmation_event'].get('geometry_revision'),
            review_policy=target['confirmation_event'].get('review_policy'),
            acknowledged_warnings=target['confirmation_event'].get('acknowledged_warnings', {}),
            context_policy=CONTEXT_POLICY, vessel_context=volume.overlays[4],
            shadow_override_columns=int(target['shadow_override_columns'].sum()),
            shadow_override_source_names=list(volume.scan.surface_names) + ['CNV edge'],
            native_geometry=target['confirmation_event']['native_geometry'],
            lesion_eligible=target['lesion_eligible'], lesion_definition=target['lesion_definition'],
            lesion_definitions=target['confirmation_event'].get('lesion_definitions'),
            approved_positions=int(target['approved_position'].sum())))
    write(destination/'COMPLETE.json', manifest)
    return destination


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reviewer',required=True)
    parser.add_argument('--role',choices=('development','assessment'),required=True)
    parser.add_argument('--shadow-overrides', choices=('include', 'exclude'), default='include',
                        help='Include or exclude the manual-shadow-override cohort from all training supervision.')
    args=parser.parse_args()
    print(export(args.reviewer,args.role,args.shadow_overrides == 'include'))

if __name__=='__main__': main()
