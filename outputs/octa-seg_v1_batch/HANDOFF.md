# Completed batch — 2026-09-11 07:00 local

FINAL_VERIFIED.json confirms successful final integrity and cohort checks for all 314 acquisitions, with 26 verified reuses, no failed scans and 16 unavailable acquisitions. Diagnostic review is recorded in verification/visual_review.md. No processing or audit remains pending. The historical execution notes below are retained for provenance; their running PIDs are obsolete.

# Active batch execution and continuation

The user's entire request is in REQUEST.md. All **314 acquisitions have per-scan QC completion markers**. Final cohort integrity verification is running; this is not yet a completed delivery. Do not claim final completion until FINAL_VERIFIED.json exists.

Historical recovery update, 2026-09-11 05:12 local: supervisor 41560 exited during table assembly; its 312-scan snapshot is stale. Final audit recovery Python PID 39844, started 04:53, remains active and its CPU time is increasing. Its log is logs/final_audit_recovery.log (hash verification is quiet). Do not launch another audit or supervisor while it runs. See verification/aggregation_recovery.md for the repaired table snapshot race and verification/visual_review.md for completed inspection of four diagnostic examples. After audit success, refresh script provenance and supervisor/status records, review REPORT.md, pause the heartbeat and deliver.

## Running system

`RUN_ALL.cmd` activates the octa environment and runs `code/supervise.py`. A detached hidden process was started on 2026-09-10. `supervisor.json` holds the live Python PID; `logs/supervisor_stdout.log` and `logs/supervisor_stderr.log` hold durable output. Two CPU lanes overlap preparation/export/QC with one exclusive GPU lane. Per-scan and supervisor locks prevent duplicate writers and duplicate supervisors. `runtime/<scan>.json` records each child worker and parent PID. `stage_timings/` records finished stage durations. The initial sequential/auxiliary parent schedulers were replaced; their already-running inference children were allowed to finish safely. Use only the supervisor going forward.

Scheduled continuation: Codex heartbeat `finish-frozen-octa-seg-v1-batch`, every 15 minutes, attached to this task. Check progress quietly; investigate real stalls/failures; notify verified completion or required user action. Pause the heartbeat after final delivery.

## Inventory

330 indexed acquisitions. 316 processed files on disk reconcile to **314 distinct acquisitions + 2 byte-identical duplicate files**, verified by full-file SHA-256. `duplicate_files.json` records both paths and full hashes. 16 acquisitions lack processed volumes (15 have RAW; 1 has no RAW). No reconstruction is attempted. All repeats, eyes and visits are included. `manifest.json` stores native shapes and source fingerprints; source fingerprints use size/mtime and three 1-MiB SHA-256 samples, with that limitation disclosed. Checkpoints and dependency files use full-file SHA-256.

## Processing contract

Only frozen octa-seg_v1 `position.pt` and `states.pt` under ALL_LABELLED are used. Single native-B-scan full-depth preprocessing is `stage_a.geometry.preprocess` (bscan_avg=1 for the neural model). The three-B-scan average belongs only to the unchanged shadow stage. Preparation matches the longitudinal v1 pipeline, including the six pilot shadow inputs and existing crop choices. No octa-seg_v2 reporting module is imported. The existing vessel shape-gate method and the octa-thick policy happen to have v2 in their own names; these are not segmentation-model versions.

Sources are bulk-read with ProcessedVolume; orientation is freshly detected. Every native cropped image is compared to the original full-depth model preprocessing during fresh inference. Reuse is limited to raw neural arrays from prior complete v1 outputs, after verifying source, native grid, all crop images, geometry masks and checkpoint fingerprints. New v1 operational decisions/context estimates are always rebuilt. The helper `code/verify_longitudinal_match.py` processes one known longitudinal scan and asserts exact equality of all important arrays; its result belongs in `verification/longitudinal_v1_exact_match.json`.

Human annotations are read, never created or edited. Existing frozen/live guards and current octa-thick correction precedence are preserved. Model states, human visibility, acquisition quality, spatial irregularity and preliminary thickness policy are separate. No quality score or quality-based exclusions are introduced.

## Completion and recovery

Per-volume `complete.json` means segmentation exported; only `qc_complete.json` (schema_version=2) means that volume has passed QC, engine checks and artifact verification. `counts.json` and tables are regenerated under an aggregate lock. The supervisor retries failures once, then continues to final review; unresolved failures require investigation, not relabeling as complete. The final cohort audit checks every source/input/artifact hash, 314 scan rows, 2,512 boundary rows, 5,338 layer rows (including explicitly unavailable definitions), state percentages, visibility denominators, thickness finite counts and the viewer selection.

`COMPLETE.json` means all per-scan QC markers exist. **FINAL_VERIFIED.json is the final cohort-audit success marker.** Do not give final completion until it exists and the report/figures are reviewed. `code/final_audit.py` produces it. Supervisor exceptions appear in stderr, and a dead PID with incomplete markers requires recovery. Check for active workers before declaring a stall: a stage may spend minutes bulk-reading the disk or creating shadows without intermediate text.

The first two prepared image fingerprints initially differed only in Windows mmap-close mtime, after the mmap had been fingerprinted while still open. Full-file hashes proved identical contents. `repair_image_timestamp.py` repairs only identical-content timestamps and records the evidence; preparation now closes the mapping before fingerprinting. No source, model, position or mask was changed. Early QC outputs are automatically upgraded to schema 2 by the supervisor.

Current original repo `git status` includes many preexisting user changes. This task edits only this batch directory and the authorized `outputs/octa-thick_v1/octa-thick_batch_v1.cmd`. Do not change or revert other files. Do not edit any human labels.

## Commands (Anaconda Prompt)

```bat
conda activate octa
cd /d G:\OCT_TreeShrew\octa
call outputs\octa-seg_v1_batch\RUN_ALL.cmd
```

This safely refuses to launch another supervisor if one is running. For a detached recovery launch, use PowerShell Start-Process with WindowStyle Hidden and redirect stdout/stderr inside this batch's logs. Do not overwrite a currently active log.

Open completed volumes:

```bat
call outputs\octa-thick_v1\octa-thick_batch_v1.cmd
```

Rebuild tables and human-rating comparisons:

```bat
call outputs\octa-seg_v1_batch\BATCH.cmd aggregate
```

Run final audit after all QC is complete:

```bat
python outputs\octa-seg_v1_batch\code\final_audit.py
```

No compatible whole-scan ratings were found. `qualitative_ratings.csv` has 314 blank rating rows, with Good / Usable / Poor / Unsure choices documented. Existing pilot Good/Bad/Unsure labels concern strips and are not converted. `ratings.py` produces separate metric distributions and Spearman correlations, with animal-cluster bootstrap intervals and sparse-rating warnings, when ratings are supplied.

Current update 2026-09-11 05:42 local: first recovery audit completed every hash check, then failed an incorrect expected-layer-count assertion (18 instead of 17). Corrected to exact scan/layer name coverage. Full rerun active, Python PID 12812, exec session 73406, log logs/final_audit_recovery_2.log, with per-scan progress. Do not duplicate it. Final expected layer rows: 5338. Counts now correctly show 314 complete, 26 reused, 0 failed, 16 unavailable. FINAL_VERIFIED.json is still required before delivery.
