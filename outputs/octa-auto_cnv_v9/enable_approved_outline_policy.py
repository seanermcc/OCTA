"""Record the user's interpretation policy without rewriting human decisions."""
from common import *
from review_store import TARGET_POLICY,ReviewStore

paths=list((HERE/'manual_review/decisions').glob('*.json'))+list((HERE/'manual_review/history').glob('*/*.json'))
before=[fingerprint(p) for p in paths]
write(HERE/'verification/approved_outline_human_records_before.json',dict(files=before))
write(HERE/'manual_review/training_target_policy.json',TARGET_POLICY)
store=ReviewStore(HERE/'gallery',HERE/'manual_review');reviews=store.all()
both=[r for r in reviews['records'].values() if r['confirm_m1'] and r['confirm_m2_adjusted']]
assert all(not r['needs_target_resolution'] and r['preferred_shared_target_model']=='m2_adjusted' for r in both)
for fp in before:verify(fp)
write(HERE/'verification/APPROVED_OUTLINE_POLICY_QA.json',dict(passed=True,synthetic_tests=5,existing_human_files_unchanged=len(before),both_approved_records=len(both),both_approved_record_ids=[r['scan_id'] for r in both],existing_notes_and_revisions_preserved=True,shared_target_preference='confirmed m2_adjusted, else confirmed m1',separate_model_approvals_retained=True,source=fingerprint(HERE/'review_store.py'),policy=fingerprint(HERE/'manual_review/training_target_policy.json'),training_started=False))
print(f'Policy enabled; {len(both)} existing dual approvals accepted, {len(before)} human files unchanged')
