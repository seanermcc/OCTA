# Diagnostic figure review

Four generated diagnostic figures were inspected for readability and whether missing measurements and policy differences were visible:

- TS165_OD_2025-04-29_WT_s01_111827: WT example.
- TS336_OD_2026-06-16_D42_s05_134542: CNV example.
- TS336_OD_2026-06-09_D35_s05_155756: selected for low retinal/vitreous CNR and high low-signal coverage.
- TS267_OS_2025-03-19_D28_s03_103903: selected for high adjacent-B-scan discontinuity.

Labels and panels were readable. Empty strict total-thickness maps explicitly state that the reporting policy supplies no finite measurements. Preliminary maps expose gaps instead of filling missing values. The low-signal example shows problematic predicted curves and high entropy; automatic shadow detection does not capture every low-signal region. The discontinuity example shows substantial axial variation and restricted preliminary coverage. These observations support keeping acquisition metrics, model support, spatial irregularity and human review separate.

This was a check of diagnostic presentation, not a segmentation accuracy study or human rating exercise. No labels, ratings, thresholds or model outputs were changed.
