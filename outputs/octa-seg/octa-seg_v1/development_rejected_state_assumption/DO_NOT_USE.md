# Rejected prerelease state-head attempt — not octa-seg_v1 release models

This attempt inferred affirmative reliability from an eligible manual position.
That was too strong: the saved reliability judgment can still be unknown. Its
state heads, state predictions, calibration and evaluation are invalid for the
requested semantics and are retained only as development history.

The release dataset uses explicit saved state judgments only. The final heads
were retrained from scratch, and final state predictions/calibration/evaluation
were regenerated. No human annotation file was changed.

Completed position models and image/position features were retained because
their targets did not change. The per-record before/after byte-hash proof is in
`../data/state_semantics_correction.json`. The manifest here is historical and
references working cache paths that were subsequently corrected; the separate
`derived_state_targets` arrays record the superseded target planes.

Use only the checkpoints in `../models`, the dataset in `../data`, and the
reports linked by `../START_HERE.md`. Future learned revisions belong in v2.
