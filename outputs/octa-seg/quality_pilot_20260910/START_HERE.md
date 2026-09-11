# Six-volume frozen-v1 quality pilot

All six complete 512-B-scan exports use the same v1 weights, thresholds and candidate rules. The original four neural predictions were reused; reporting and candidates were recomputed before human overrides. No model was trained.

Open **OPEN_QUALITY_REVIEW.cmd** for 24 suggested vertical strips (about 15–30 minutes). Choose Good / Bad / Unsure and drag across the B-scan. Bad is the default. Metrics and sampling reasons remain hidden until that strip is rated. Free browsing works normally. Ratings are separate from boundary annotations.

## Separate evidence axes

| Scan | CNR | Low signal % | Solid % | Dashed % | Entropy P95 | Displayed jump >20 µm % | Displayed spike >20 µm % | Original user review |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| TS165_OS_2025-04-29_WT_s02_121711 | 10.40 | 7.04 | 52.12 | 0.12 | 0.733 | 0.03 | 0.00 | Decent; some solid segments appear to deserve dashed uncertainty. |
| TS247_OD_2024-11-06_D21_s03_104157 | 19.44 | 0.43 | 62.99 | 0.17 | 0.617 | 0.02 | 0.00 | Great—almost perfect, particularly with good signal. |
| TS283_OD_2025-01-29_D7_s02_123712 | 6.27 | 9.00 | 60.05 | 0.45 | 0.908 | 0.01 | 0.00 | Really solid; a few stray/misplaced labels near the ONH. |
| TS325_OD_2026-05-26_6mo_s01_112940 | 5.48 | 21.48 | 59.06 | 0.28 | 0.729 | 0.02 | 0.00 | OK, but needs more uncertain guesses through difficult stretches. |
| TS328_OD_2026-04-09_beforelaser_s01_130813 | 22.75 | 0.26 | 69.16 | 0.48 | 0.698 | 0.03 | 0.00 | Not yet reviewed |
| TS336_OD_2026-05-22_D21_s05_114507 | 20.02 | 0.19 | 65.82 | 0.10 | 0.723 | 0.02 | 0.00 | Not yet reviewed |

## Definitions and limitations

- Acquisition axes come from scan_quality_metrics.csv: raw retinal/vitreous contrast, CNR, low signal, motion and stripes. Repeat disagreement is omitted unless repeat_comparable is true. They are not segmentation scores.
- Entropy is Shannon entropy of the native depth softmax divided by log(depth); median and P95 are retained. Low entropy can accompany a confidently misplaced line. State-head scores are not established calibrated probabilities.
- Adjacent jump is absolute depth change within a finite stretch, assigned to the right A-line. Its denominator is eligible adjacent pairs. Spike is absolute deviation from the nine-A-line median, padded with the endpoint inside each finite stretch; its denominator is finite positions. Neither calculation bridges gaps or changes a surface. Warnings use >20 µm, with identical >10 and >40 sensitivity summaries.
- Solid and dashed curves are evaluated separately. Withheld/no-candidate geometry statistics refer only to raw diagnostic proposals, never displayed continuations. The displayed aggregate pools solid and dashed eligible locations without bridging between them.
- Thickness tables report population SD, median, mean, IQR, coverage and local roughness. Primary thickness is the unchanged v1 definition. Diagnostic thickness uses raw finite in-image positions, rejects crossing/intermediate-invalid boundaries, and masks shadows. RNFL/TOTAL/INNER_RETINA primary coverage is zero because v1 withholds ILM. TOTAL ends at the eight-surface outer RPE edge.
- ONH distances use native Euclidean lateral spacing (~1460/512 µm). TS165 distances are to its annotated mask, zero inside. TS283 uses a partial-edge proxy. All other distances remain unknown.
- Context table cells jointly separate local signal CNR (<3, 3–10, ≥10), vessel footprint, CNV outline, and ONH distance (0–250, 250–500, 500–1000, ≥1000 µm; -1 unknown). Outside a mask is not confirmed absence. Missing vessel/CNV annotations remain unknown context; footprint provenance is in each prepared.json. Automatic vessel proposals are not human annotations.
- CNV outlines and acquisition motion/stripe measurements provide context for deformations; warnings never assign an automatic wrong label. Distribution differences, smoothness and matching averages cannot establish correctness.

## Files

- reports/volumes.csv: acquisition, model behavior and preserved full-volume feedback in separate columns.
- reports/boundaries.csv: every boundary × solid/dashed/withheld/raw, with state scores, entropy and 10/20/40 µm warnings.
- reports/thickness.csv and thickness_contexts.csv: primary and diagnostic thickness distributions, including invalid/crossing fractions and coverage.
- reports/onh_warnings.csv, reports/strips.csv, maps/<scan>/<boundary>.png and volumes/<scan>/diagnostics.npz: native maps and spatial summaries.
- volumes/<scan>/measurements.npz and review_packs: complete automatic exports. The four frozen source volumes and all existing human labels remain intact.
- reviewer/quality_reviews: GUI-only Good/Bad/Unsure records with model identity, undo and clear history. No position targets, visibility marks, or exclusions are made by these ratings.

## Assessment and next decision

Regional human judgments are pending. Run UPDATE_RATING_COMPARISON.cmd after review to compare entropy, jumps and spikes with Good/Bad, retaining Unsure and separating random from targeted samples. No regional failure rate or metric accuracy can yet be estimated.

Continue the focused review workflow if unseen acquisitions remain comparable by human assessment. If positions are good but solid/dashed choices are poor, prioritize reporting/candidates. Investigate training/preprocessing before architecture if major positional failures occur in good signal. Prioritize obscuration handling if failures cluster in low signal. This pilot does not independently establish unseen-animal generalization: these animals contributed other acquisitions to the labeled development cohort.

Evaluation follows the task-specific uncertainty principle in [ValUES (ICLR 2024)](https://proceedings.iclr.cc/paper_files/paper/2024/hash/1548d98b62d3a4382a31ba77d89186cd-Abstract-Conference.html); warning performance must be checked against independent human judgments rather than assumed from entropy.

## Additional results

[Thickness comparison](reports/THICKNESS_COMPARISON.md), [regional assessment](reports/HUMAN_ASSESSMENT.md), and [verification](reports/verification.json).

The two new acquisitions have CNR 22.75 (TS328) and 20.02 (TS336), with low-signal coverage below 0.3%. Their diagnostic total-thickness medians, 252.5 and 246.9 µm, fall within the original-four median range (207.1–253.7 µm). TS328’s diagnostic photoreceptor median is higher (33.7 µm versus 25.9–29.4 µm); this is a finding to inspect, not an established error.

**Context limitation:** neither new acquisition has a saved vessel, CNV or ONH mask. Its zero vessel input is the existing missing-mask behavior, so higher solid coverage cannot be interpreted as better quality: vessel-derived withholding is absent. The unknown-context rows cannot support fully matched vessel/CNV/ONH comparisons. No missing anatomy was estimated.

The solid/dashed spike fractions rounded to 0.00% above are not proof of correctness. Full-precision fractions and maximum magnitudes are in the tables. The optional white dotted ILM is a raw diagnostic overlay; it is excluded from the solid/dashed aggregate and remains covered by the raw per-boundary diagnostics.
