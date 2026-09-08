# OCT scan quality metrics — definitions and v1/v2 history

## The old `quality_confidence` files

`quality_scores.csv` and `quality_scores_v2.csv` contain the same 314 scans in
the same order. `shadow_frac`, `retina_lo`, and `retina_hi` are identical. The
substantive difference is `quality_confidence`:

| file | implementation | range | interpretation |
|---|---|---:|---|
| `quality_scores.csv` | old whole-column `surface_confidence` | -0.9015 to -0.3569 | not a scan-quality score |
| `quality_scores_v2.csv` | replacement `local_confidence` | 1.0286 to 8.8012 | local image support for automatic surfaces |

The two rankings agree only moderately (Pearson r = 0.237; Spearman r = 0.550).
Only 5 of the bottom 15 and 2 of the top 15 scans overlap. The old metric is
correctly negative for banded surfaces because a stronger unrelated edge often
exists elsewhere in the A-line. The v2 metric asks the useful segmentation
question — image-driven or prior-driven? — but still does **not** measure
acquisition quality. It came from a fast one-B-scan proxy rather than the real
volume pipeline and its high outlier predates the current edge/MAD guards.

Do not use either CSV to label scans good or bad. Keep `local_confidence` as a
per-surface segmentation-support measurement alongside anatomical plausibility.

## Independent acquisition QC added 2026-08-31

`code/scan_quality.py` measures three separate axes without using automatic
retinal surfaces and writes `outputs/scan_quality_metrics.csv`:

1. **Signal/contrast** — retinal-band upper-quartile intensity above a vitreous
   noise window, its robust contrast-to-noise ratio, and the fraction of spatial
   positions below three vitreous MADs.
2. **Raw slow-axis continuity** — median adjacent-B-scan structural correlation,
   the 95th percentile discontinuity, and high-frequency slow-axis stripe power.
3. **Repeat agreement** — translation-registered structural-en-face correlation
   to other scans from the same animal, eye, and session. Agreement is reported
   as QC only when the best pair has enough structural overlap
   (`repeat_comparable=True`). Non-overlap is not called poor quality.

These values deliberately remain separate. There is no combined score or
good/bad threshold until they are compared with image review. The next GUI pass
should show the three axes, sample their high/middle/low and discordant cases,
and collect a human scan-level `good / usable / reject` verdict plus reason.
Those labels can then calibrate a grouping rule and reveal which measurements
actually predict usability for this dataset.

## Exploratory rank score added 2026-09-01

At the user's request, `code/rank_scan_quality.py` now creates a transparent
0–100 **QC score** in `outputs/scan_quality_ranked.csv`. It is the equal-weight
mean of three within-dataset percentile ranks (higher = better):

1. `rank_signal`: CNR (high good) and low-signal coverage (low good);
2. `rank_continuity`: adjacent-B-scan discontinuity, axial centroid residual,
   and brightness stripe amplitude (all low good);
3. `rank_repeat`: registered repeat correlation (high good).

Scans without a comparable repeat average the two observed axes and declare
that explicitly in `qc_score_component_n=2`; they are not silently assigned a
made-up repeat rank. This is a practical review-ordering score, not a validated
clinical/biological quality label. The selected 1st, 50th, and 99th percentile
examples are in `outputs/scan_quality_examples.csv` and
`outputs/qc_score_examples/` (five evenly spaced raw B-scans per scan).
