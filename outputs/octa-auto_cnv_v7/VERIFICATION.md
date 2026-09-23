# Software verification — v7

Verified 2026-09-18T03:04:41.132340+00:00. This record means application verification, **not** completion of 30 human reviews. No model was trained.

**20 contract tests passed**, plus real Qt tests on four animals and an actual Windows launcher capture. V7 human labels: **0 positive / 0 no-CNV**.

## Evidence

- `verification/contract_tests.txt` / `.json`: deterministic queue, strict day handling including missing numeric values, native run bounds, duplicate acquisitions, visit cycling/exhaustion, full reserve, empty/unresolved regions, whole-field background, explicit absence/conflicts, ignored overlaps, edit invalidation, undo/redo, stale writers and simulated atomic save failure. Thirty-two synthetic confirmed acquisitions test the target and continuation beyond it; multiple regions/revisions do not inflate counts.
- `verification/real_gui.json`: real native providers; actual Qt mouse painting/closed-loop fill, erase, Keep/Unsure/Remove, save/reopen, absence/add/undo, first/last rows and columns, disconnected intervals, multiple states, zoom preservation, optional context visibility and stable cursor. Synthetic gestures are stored only in `verification/gui/`.
- `verification/launcher.png`: captured from the actual `OPEN_OCTA_AUTO_CNV_V7.cmd` using the native Windows Qt platform. The process exited successfully. Normal launch uses the same path without `--capture`.
- `verification/final_context_checks.json`: final optional-overlay guards validate the native identity/grid, original prediction hash and checkpoint identity, and historical hashes.

| Acquisition | Final verified load (s) | B-scan array | Projection error (dB) |
|---|---:|---|---:|
| TS169_OD_2025-01-14_D35_s05_113034 | 10.2 | [512, 426, 512] | 0.0 |
| TS267_OD_2025-03-05_D14_s01_104048 | 17.33 | [512, 458, 512] | 0.0 |
| TS336_OD_2026-07-28_D56_s01_143412 | 13.69 | [512, 502, 512] | 0.0 |
| TS241_OS_2024-09-04_D21_s01_104822 | 15.86 | [512, 546, 512] | 0.0 |

All four structural B-scan volume projections reproduced the frozen structural en-face values exactly. Canonical orientation/crop and source hashes were checked. TS267 D14 has historical review evidence; TS169, TS241 and the tested TS336 acquisition were unreviewed in the inventoried footprint sources.
The initial TS336 recovery took 116.84 s. It read the processed volume once, freshly detected orientation, called prepare_bscan, reproduced the v6 native-array hash, and wrote a v7-only cache. Subsequent cached loading is shown above. There are ten such newer providers; only needed acquisitions are recovered. Other cold loads depend on disk/cache state and prefetch contention.

## Screenshot review

An initial offscreen capture displayed missing-font boxes. Loading the Segoe UI font file explicitly corrected it. Final screenshots were inspected for readable controls, optical alignment, region colors and translucent B-scan intervals. The two synthetic images visibly identify themselves as software tests; they are not biological annotations.

![Native launcher](verification/launcher.png)

![Real TS267 historical-review acquisition](verification/real_TS267.png)

![Synthetic multiple intervals on a real structural scan](verification/synthetic_multiple_intervals.png)

## Preservation and storage

358 scoped legacy files (445,639,335 bytes) had identical full-file SHA-256 before/after real GUI use. Scope: v1–v6 code/guides/launchers, v6 checkpoints, original CNV files, current/historical region records, and six-model predictions/provenance for the four tested acquisitions. See preservation_before.json and preservation_result.json. This does not claim fresh full hashes of all 1,944 predictions or all giant processed volumes.
The fresh queue inventory sampled every one of the 332 processed files, checked source identities against validated providers and retained the prior full hashes for eight duplicate copies with current stat/sample checks. Zero new unindexed acquisitions were found. Existing v6 whole-cohort validation is provenance, not a new v7 full-cohort inference or native-load test.
Opening real cases and toggling references created zero human annotation files. Browsing/session logs remain separate from decisions. Every synthetic test is confined to verification storage and excluded from real progress.

## Limits and handoff

Real loading was exercised on four animals, not every acquisition. All queue candidates have available provenance-linked sources/providers, but a future missing/changed input produces a recoverable load error, never a negative label. Synthetic testing verifies software semantics, not biological segmentation accuracy. Optional thickness views and automatic reference copying are deliberately absent. Review quality and actual model benefit require the next human collection/training round.
Start with START_HERE.md; use MODEL_AND_LABEL_HISTORY.md and TRAINING_PLAN.md for the next dataset freeze. No upstream code, model, original labels, RAW data or MATLAB code was altered.