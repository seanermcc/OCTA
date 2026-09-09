# Experimental whole-column readability and ordered decoding

This is an opt-in development package, separate from `stage_a` so its additions
do not change the original trainer's checkpoint/resume code identity. No normal
layer thickness prior, GUI change, label-format change, or deployment threshold
is introduced. Boundary and thickness references are the frozen manual labels.

The completed run is in
`outputs/stage_a/20260908_v5_readability_ordered/`. Start with its `RUN_REPORT.md`.
It is a failed promotion candidate: useful coverage is lost and catastrophic
ordered predictions remain. The weak legacy positive targets are not certified
local visibility labels; strict local-positive supervision has zero examples.

`readability.py` constructs unknown-masked readability targets and attaches a
64,641-parameter context head to the unchanged epoch-124 boundary model.
`load_readability_model(head_checkpoint, device)` verifies and restores both
components. Its forward result is `(boundary_logits, region_logits,
readability_logits)`. Sigmoid readability is an uncalibrated score. No gate is
enabled automatically. Only the new head receives gradients.

`ordered.py` accepts `[8, native_depth, A-line]` logits in canonical coordinates.
It uses an exact ordered dynamic program for each column, followed by one
forward/backward coordinate-descent sweep with measured, bounded continuity
penalties. It does not claim a globally optimal two-dimensional solution.
Caller-provided scope, shadow and optional readability masks split the problem
into independent intervals. Infeasible or posterior-unsupported columns carry
explicit reason bits. Only `retained_rows` are measurements: rejected values are
NaN. The existing thickness function checks both endpoints and their order.

The dated execution guard blocks final-test/repeatability reads and restricts
writes to the new experiment. Activate the `octa` conda environment, set
`PYTHONPATH=code`, and use the recorded `reproduce.ps1` commands. Existing
completed prepare/train/evaluate artifacts are protected against accidental
rerun; a fresh experiment requires a new output root and its own frozen plan.

Modules:

- `experiment`: annotation audit, exact baseline reproduction, training, integrity.
- `evaluate`: fixed component comparisons, coverage grid, measurements and reasons.
- `paired`: exact common-support comparisons and recovered-crossing failures.
- `review`: standalone plotting process, avoiding a local OpenMP runtime conflict.
- `report`: report tables from completed CSV/JSON results.
- `test_readability_ordered`: synthetic target, gradient, geometry and NaN checks.

Run tests with the dated guard and
`tests stage_a_readability_ordered.test_readability_ordered`. The original
`tests stage_a.test_stage_a` suite is redirected to this experiment's check folder.
No test creates a human-label file.
