# Explicit review rounds

Run these commands from this folder. `V2_COMMAND.cmd` activates the `octa` environment and selects the isolated v2 implementation. CPU/Qt and GPU stages run as separate processes. Every checkpoint/data snapshot records its provenance. Neither review clicks nor closing the GUI starts training.

## Current release

`round_000` uses the frozen v1 position and state weights with v2 working/reporting policies. There is **no learned improvement claim**. All ten volumes contain 512 native B-scans. Current feedback lives in `reviewer`; human labels elsewhere are read-only.

The initial audit `datasets/release_feedback_audit` contains one prior v1 review with 26 exact stroke columns and negative reliability evidence. It has no positive reliability examples. `round_001/training_status.json` records that the provider was preserved. The older `initial_feedback` snapshot is retained as an intermediate audit; use `release_feedback_audit` for the release.

## After a short review session

1. Freeze a **new** named snapshot. Existing snapshots are immutable.

   ```bat
   V2_COMMAND.cmd -m octa_seg_v2.snapshot feedback_001
   ```

2. Train the reliability/traceability branch with position weights frozen. Repeating the identical command resumes its checkpoint. The initial minimum requires affirmative and negative reliability evidence from at least two distinct new reviewed B-scans each. If support is insufficient, no weights change.

   ```bat
   V2_COMMAND.cmd -m octa_seg_v2.train datasets\feedback_001 round_001 --steps 300
   ```

3. Once training succeeds, infer all ten volumes on the GPU, then export and assess in a separate CPU process.

   ```bat
   V2_COMMAND.cmd -m octa_seg_v2.next_round infer round_001 --positions frozen
   V2_COMMAND.cmd -m octa_seg_v2.next_round export round_001 --positions frozen
   OPEN_OCTA_SEG_V2.cmd --round round_001\variants\frozen
   ```

   `variants/frozen/COMPLETE.json` seals this candidate output. The default launcher continues to open round_000 until a later provider is deliberately chosen. The comparison checkbox shows round_000 against the candidate. Review `reports/assessment_comparison.csv`, `round_mechanical_comparison.csv`, and `assessment_status.json` before judging improvement. Mechanical coverage retention does not establish correct-boundary retention.

## Optional position sensitivity experiments

Only run these when new exact corrections or explicit unchanged-coordinate approvals exist. Both experiments preserve the frozen-position alternative. Manual-only and manual-plus-approved results have separate checkpoint/output folders.

```bat
V2_COMMAND.cmd -m octa_seg_v2.train datasets\feedback_001 round_001 --steps 300 --positions manual
V2_COMMAND.cmd -m octa_seg_v2.next_round infer round_001 --positions manual
V2_COMMAND.cmd -m octa_seg_v2.next_round export round_001 --positions manual

V2_COMMAND.cmd -m octa_seg_v2.train datasets\feedback_001 round_001 --steps 300 --positions approved
V2_COMMAND.cmd -m octa_seg_v2.next_round infer round_001 --positions approved
V2_COMMAND.cmd -m octa_seg_v2.next_round export round_001 --positions approved
```

The state model samples animals uniformly, then reviewed B-scans/regions, and balances loss by boundary, head, and affirmative/negative class. Strip width does not determine how often a region is sampled. Original audited v1 examples supply replay; new feedback replaces overlapping original B-scans. Candidate positions and automatic tapers are not inferred as human evidence. The state branch cannot send gradients to positions.

Random assessment B-scans are withheld wholesale from new fitting and replay. This does **not** undo earlier checkpoint exposure. The current models descend from all-label models: resulting assessments are development/workflow comparisons, not animal-excluded generalization estimates. `checkpoint_ancestry.json` derives seen status from eligible position records and the actual parent checkpoint. No new probability calibration is claimed. Position fine-tuning changes the state model's input features, so its reporting behavior also requires reassessment.

## Reproduce verification

```bat
V2_COMMAND.cmd -m unittest octa_seg_v2.test_contract -v
V2_COMMAND.cmd -m octa_seg_v2.verify_gui
V2_COMMAND.cmd -m octa_seg_v2.verify_neural
V2_COMMAND.cmd -m octa_seg_v2.verify --native
```

Qt mutation checks use an explicitly synthetic fixture under `tests/gui_runs`, never a real human annotation. Real-volume GUI checks are read-only. Native alignment checks compare B-scans 0, 256 and 511 from one bulk source-band read per volume with the saved canonical image cache. Closed rounds must be verified rather than overwritten; create a new round for changed policies or weights.

## Limits of the delivered training workflow

The no-training support gate and neural loss masking have been exercised. Training on a new real v2 feedback round, its position sensitivities, and its held-out assessment await user review evidence. No new training run, positional improvement, calibration success, or promotion is implied by the availability of these commands.
