# Frozen octa-seg_v1 acquisition batch

Status: complete. Preliminary automatic results for review; no new validation or accuracy claim.

Expected available: 314; completed and QC verified: 314; verified raw-neural reuse within completed scans: 26; failed: 0; unavailable: 16; pending: 0.

Every available repeat, eye and visit is included. See `reconciliation.json`, `acquisitions.csv`, `unavailable_acquisitions.csv` and `failures.csv`. Completion requires both segmentation and QC markers. Unavailable RAW is never reconstructed here.

## Results

- `scan_qc.csv`: acquisition axes and separate model coverage; repeat disagreement is interpretable only when repeat_comparable is true. Repeat groups include the complete cohort; interpret mixed-overlap groups with the limitations below.
- `boundary_qc.csv`: one row per acquisition/boundary, model probabilities and entropy, native and eligible coverage, geometry and adjacent jumps.
- `layer_qc.csv`: one row per acquisition/layer; separate segmentation and unchanged octa-thick policies, plus explicitly unavailable layers.
- `region_layer_qc.csv`: region-stratified statistics, with provenance and overlap counts.
- `volumes/<scan>/SUMMARY.md`, `diagnostic.png`, `boundary_states.png`: per-scan review.
- `qualitative_ratings.csv`: human Good / Usable / Poor / Unsure ratings and comments; blank until explicitly rated.
- `METRIC_DICTIONARY.md`: definitions, denominators, masking, interpretation and limitations.
- `thick/exports/`: native-grid thickness exports from the actual engine; `thick/volumes.json`: completed-volume selection.

## Verification and limitations

Each QC completion marker records input/artifact hashes and checks. Full native image grids are compared during inference; fresh orientation and canonical crop offsets are retained. The actual octa-thick engine loads every completed volume, verifies shadow masking and point/map units, and exports both existing modes. Model checkpoints and dependency files are fingerprinted. Source identity uses file size, mtime and three 1-MiB SHA-256 samples, not a full-source cryptographic digest.

The experimental model's traceability/reliability values are model assessments, not calibrated correctness or human visibility. Human visibility is separately counted. SD/IQR/MAD measure spatial variation, which may include genuine CNV pathology. Vessel proposals and automatic shadows are not human annotations. Footprint groups may overlap; “other” is their complement, not confirmed normal retina. No combined quality score or quality-based exclusions are introduced. Isolated ONL and unresolved sublayers remain explicitly unavailable.

## Anaconda Prompt commands

Open all 314 completed volumes:
```bat
conda activate octa
cd /d G:\OCT_TreeShrew\octa
call outputs\octa-thick_v1\octa-thick_batch_v1.cmd
```

Resume all remaining stages, retrying failures:
```bat
conda activate octa
cd /d G:\OCT_TreeShrew\octa
call outputs\octa-seg_v1_batch\RUN_ALL.cmd
```

Rebuild tables and compare subsequently supplied human ratings:
```bat
call outputs\octa-seg_v1_batch\BATCH.cmd aggregate
```

Final cohort audit passed. See FINAL_VERIFIED.json and verification/final_scan_audit.csv.

Exact longitudinal v1 array matching passed. Read [material limitations](LIMITATIONS.md), including the frozen ILM withholding behavior and why strict segmentation RNFL/total differ from preliminary viewer measurements.

Verified table counts: 314 scan rows, 2,512 boundary rows and 5,338 layer rows (17 definitions per scan, including eight explicitly unavailable definitions). Representative WT, CNV, low-signal and discontinuous acquisitions were inspected for diagnostic readability; see [figure review](verification/visual_review.md). Human scan ratings remain blank and ready for input. Recovery details are recorded in [aggregation recovery](verification/aggregation_recovery.md).
