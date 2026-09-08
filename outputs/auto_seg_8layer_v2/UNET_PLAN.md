# Multi-task U-Net for eight-boundary segmentation — implementation plan

Written 2026-09-02. Supersedes the scalar-prior cascade in
`code/auto_seg_8layer_v2/` for the inner boundaries. Nothing here changes the
GUI, the label format, or `code/eight_surface/`.

## Why the current cascade is being replaced, in one table

Measured on the 53 corrected labels, with the ILM and PR_RPE anchors *handed to
the algorithm for free*:

| | `RNFL_GCL` | `GCL_IPL` | `IPL_INL` | `INL_OPL` | `OPL_ONL` |
|---|---|---|---|---|---|
| Half-width needed to contain 95% of human answers | 40.5 px | 37.4 px | 23.9 px | 16.5 px | 12.8 px |
| Half-width the code uses | 4.9 | 4.9 | 12.2 | 6.4 | 6.4 |
| Human answer falls outside the search window | 75% | 73% | 25% | 33% | 28% |

The dynamic program cannot select an answer that is not in its candidate set,
so on three A-lines in four it returns the prior, lightly perturbed. Widening
the windows does not help on its own: the GCL is ~12 px thick, so at the width
the anatomy demands the inner surfaces overlap and nothing separates them —
the five hand-designed edge filters are shared across all eight boundaries and
encode "there is an edge here", not "this is GCL/IPL rather than IPL/INL".

**The priors are load-bearing because the evidence is not discriminative.** The
fix is to make the evidence discriminative, then delete the priors and windows.

## Architecture

One small U-Net encoder, two heads, then a decoder that enforces anatomy.

```
B-scan (flattened, 2 channels)
        |
   U-Net encoder/decoder      ~2-4 M params, base 32, 4 down / 4 up
        |
   +----+----+
   |         |
region head  boundary head
9 classes    8 channels, per-column softmax over depth
   |         |
   +----+----+
        |
  ordering-constrained DP  (existing code, priors and windows removed)
        |
  8 ordered surfaces + per-column uncertainty
```

**Region head** — 9 classes: vitreous, RNFL, GCL, IPL, INL, OPL, photoreceptor,
RPE, sub-RPE. Every pixel is a training target, so the 53 B-scans supply
~11.4 M supervised pixels instead of ~27 k boundary points. This is where the
sample efficiency comes from.

**Boundary head** — 8 channels, softmax **down each A-line** rather than over
the whole image. That makes each column a proper probability distribution over
depth, which gives three things at once: a sub-pixel position via soft-argmax,
a calibrated uncertainty via the distribution's entropy, and a natural cost for
the DP via its negative log.

**Decoder** — the existing ordering-constrained DP, fed `−log p` from the
boundary head instead of `build_costs()`, with `RELATIVE_PRIORS` and the
neighbour-scaled windows deleted. Only the non-crossing minimum-gap constraint
and the lateral smoothness step remain. Optionally add the region head's
transition log-probabilities as a second cost term.

The slow-axis refinement (`attract=0.05`) is **retested, not assumed**. It
exists to stabilise a weak cost image; with a strong learned cost it may be
unnecessary or harmful, and CLAUDE.md is explicit that this parameter erases
CNV shape when raised.

## Data preparation

1. **Canonical orientation** via the existing `prepare_bscan` /
   `detect_orientation`. Never trust the `vitreous_at_high_index` field stored
   in old `.npz` samples.
2. **Per-B-scan intensity normalisation** to the 1st–99.5th percentile range.
3. **Flattening.** Tilt and curvature are the dominant nuisance variable — the
   retina sweeps 150 → 660 px across a single B-scan in some volumes.
   Each A-line is shifted so the posterior tissue edge sits at a fixed row, and
   the image is cropped to a fixed height around it.
   - The shift comes from `tissue_bounds`' posterior edge, **not** the ILM,
     because the ILM is the surface currently known to fail (see
     `REPORT.md`). The edge is median-smoothed before use so a local glitch
     cannot tear the image.
   - The shift array is stored and inverted before any output is compared to a
     human label or written to disk. All reported numbers are in original
     image coordinates.
   - The **un-flattened** image is passed as a second input channel, so the
     model can recover if the flattening is locally wrong.
4. **Targets**, built from the human boundaries only:
   - region map: fill between consecutive human boundary rows per A-line;
   - boundary maps: a Gaussian band, σ ≈ 2 px, centred on the human row.
5. **Masking — this is what keeps the model honest.**
   - A-lines with `region_excluded` contribute no loss anywhere.
   - A boundary channel is supervised only where the human drew it *and*
     marked it visible *and* left it reliable.
   - A region is supervised only where **both** its bounding surfaces are
     valid.
   - The 21 `rejected` B-scans are excluded from supervision entirely. They
     are retained as unlabelled data for possible semi-supervised use later.

An invisible boundary has no correct answer to learn. Supervising one would
teach the model to invent a line exactly where the human said none exists,
which is the failure mode this whole project has been trying to avoid.

## Splits

Whole animals, never B-scans. Round 1 covers TS165, TS169, TS241, TS247,
TS250, TS267; finishing the remaining 16 packs is expected to add TS283,
TS305, TS325, TS328 and TS336, for ~11 animals.

With animal counts this small a single held-out split is too noisy, so use
**leave-two-animals-out cross-validation** and report the spread across folds,
not just the mean. Volumes from one animal never straddle a fold, and neither
do same-session repeats.

## Losses

| term | purpose |
|---|---|
| masked cross-entropy on the region map | dense supervision |
| Dice or inverse-frequency class weights | the GCL is ~12 px thick and will otherwise be ignored |
| masked per-column cross-entropy on boundary maps | sharp, well-localised boundaries |
| masked L1 between soft-argmax depth and the human row | directly optimises the metric we report, in pixels |
| monotonicity hinge on the soft-argmax depths | penalises crossings before the DP has to repair them |

Augmentation: horizontal flip, small elastic and affine warps, gamma and
brightness jitter, speckle noise, and **synthetic shadow columns** — shadows
are the single most common real corruption and the model must learn to abstain
in them rather than interpolate.

## Decoding and abstention

Soft-argmax gives sub-pixel depth; the per-column distribution's entropy gives
uncertainty. Calibrate an entropy threshold on validation folds so that flagged
columns capture most of the large errors, then emit **NaN** there rather than a
confident wrong line. Shadowed A-lines stay NaN and are never interpolated.

This replaces `local_confidence` as the "image or prior?" signal, and it is a
better one: a scalar prior no longer exists to fall back on.

## Evaluation protocol

Primary metric: median and 90th-percentile absolute boundary distance in µm,
per surface, on held-out animals, restricted to A-lines the human did not
exclude and surfaces the human drew. Reported alongside:

- the same numbers for the current v2 cascade, on identical B-scans;
- **the human repeatability floor** from the blind second round;
- layer thickness error, since two boundaries can both move and leave the
  layer correct;
- gross-miss rate (> 25 µm);
- the fraction of columns where the model abstains.

Broken out by WT/control, remote CNV retina, and lesion rim/core once the
lesion annotations exist. A model that improves the average while degrading
lesion cores is not an improvement for this project.

## Sequencing

**Phase 0 — labelling (yours, in progress).**
Finish the remaining 16 review packs, and complete the 10-B-scan blind round
already queued in `outputs/auto_seg_8layer_v2/repeatability/packs`.

**Phase 1 — data pipeline and harness (mine, can start immediately).**
Flattening with round-trip verification on all 53 existing labels, target and
mask construction, animal-level fold definition, and the evaluation harness
wired to the v2 baseline and the repeatability floor. None of this depends on
the new labels, and all of it is testable against what exists today.

**Phase 2 — model and training.** Once Phase 0 lands. Install `torch` with
CUDA for the RTX 3060 Ti.

**Phase 3 — decoder integration and evaluation.** Swap the learned cost into
the DP, retest the slow-axis refinement rather than inheriting it, and report
against both baselines.

## Risks, and what is done about each

| risk | mitigation |
|---|---|
| ~110 B-scans is still a small training set | small model, heavy augmentation, strong weight decay, cross-validation instead of one split |
| Overfitting to a few animals | leave-two-animals-out; report per-animal, not just pooled |
| Flattening anchor fails and corrupts the input | anchor-free posterior edge, median-smoothed, round-trip verified on all 53 before training; raw image kept as a second channel |
| GCL is ~12 px and gets ignored | class weighting / Dice |
| Model looks good on average, fails on lesions | lesion-stratified reporting; never train on CNV alone; keep WT and remote retina in every batch |
| A confident, smooth, wrong line — the failure this project keeps hitting | explicit abstention with a calibrated threshold, and NaN rather than interpolation |

## Pre-committed calls — revisit after Phase 1

Made without the user present (they were asleep), so surfacing them explicitly
rather than letting them pass silently:

1. **Training tensors are built from 3-B-scan averages, not the unaveraged
   review-pack images.** The packs store single raw B-scans for GUI display;
   inference runs on `average_bscans(imgs, bscan_avg=3)`. Training on
   unaveraged inputs and running on averaged ones would be exactly the
   train/inference mismatch CLAUDE.md warns about for the v2 quality score.
   This requires one pass over each source `.mat` volume rather than reusing
   the review packs directly — check that pass actually ran on all 53 labelled
   B-scans and didn't silently fall back to pack images anywhere.
2. **Flattening uses integer per-A-line shifts, not interpolated/subpixel
   ones.** An integer shift makes the round-trip (`shift` then `unshift`)
   exactly lossless, which is what the round-trip self-test checks. Confirm
   the self-test actually exercised this — an interpolated shift would still
   "round-trip" approximately and could hide a bug.
3. **Animal folds are a function over whatever animals are present, not a
   frozen file.** `leave_two_animals_out(animal_ids)` should regenerate folds
   from the current label set rather than reading a fixed list, so the 5
   animals expected from the remaining 16 packs (TS283, TS305, TS325, TS328,
   TS336) are absorbed automatically. Confirm this actually happened after
   Phase 0 finished, rather than the harness still enumerating the original 6.

## Expected outcome, stated honestly

At ~110 labelled B-scans: roughly 1–2 px on ILM, PR_RPE and RPE, and 3–6 px on
the weak inner boundaries — a 3–5× improvement on the current cascade, with
line shapes that follow the image rather than the prior.

"Almost exactly like the manual" means reaching the human repeatability floor,
which the blind round is about to measure. Getting the inner boundaries there
will most likely need ~150–300 labelled B-scans. The route to that is active
learning: train, run on unlabelled volumes, and have the GUI serve the
highest-uncertainty B-scans first, so each hour of labelling buys the most
accuracy. That loop is not part of this plan, but this plan is built so it can
be switched on without rework.
