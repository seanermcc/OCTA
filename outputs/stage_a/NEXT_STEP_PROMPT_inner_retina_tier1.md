# Next step — inner-retina scope reduction, a constrained decoder, and a calibrated abstain queue

Written 2026-09-08 as the execution prompt for three changes agreed after a
review of the Stage A v4 results. Each phase below has its own stopping point
and its own report. **They may be run as three separate conversations**; if so,
run them in order, because phase 2 measures against the baseline phase 1
freezes, and phase 3 needs phase 2's decoder to be settled.

---

## Why this step

The scientific target is **RNFL, GCL and IPL thickness**. Those three layers are
bounded by exactly four surfaces — `ILM`, `RNFL_GCL`, `GCL_IPL`, `IPL_INL` — and
everything the pipeline currently does to find the other four is either
irrelevant to that target or actively coupling it to the part of the image a CNV
destroys.

Three measurements motivate the three phases. All were made on the 101
`corrected` labels in `outputs/eight_surface/labels/` (27 volumes, 9 animals) on
2026-09-08, and all should be reproduced by phase 1 before anything is built on
them:

1. **The prior is better conditioned on the inner band.** Predicting a surface
   as a fixed fraction of `ILM → PR_RPE` needs a ±41.8 px half-window to cover
   95% of human `RNFL_GCL` answers (±40.1 for `GCL_IPL`). As a fraction of
   `ILM → IPL_INL` it needs ±30.1 px and ±25.8 px. Real, free, and not
   sufficient on its own.

2. **No scalar hand-off can rescue the classical cascade.** Given an *oracle*
   per-B-scan offset — a human supplying the perfect constant for every single
   B-scan — `RNFL_GCL` p95 only falls to 17.8 px (~20 µm), and `GCL_IPL` to
   15.2 px. Per-volume offset: 24.5 / 22.6 px. The residual is lateral structure
   *within* one B-scan (axon bundles). This is why the answer is a better cost
   image and a better decoder, not a better prior.

3. **There is almost no lesion ground truth.** Only **7** corrected B-scans
   cross a drawn CNV footprint, ~170 lesion columns in total. Nothing in this
   prompt may claim a within-lesion result.

Against that, the v4 long run
(`outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/`) is already good on
the four target surfaces — median / p95 / gross(>25 µm):

| Surface | median µm | p95 µm | gross |
|---|---|---|---|
| ILM | 1.57 | 33.88 | 0.0572 |
| RNFL_GCL | 2.59 | 36.14 | 0.0566 |
| GCL_IPL | 2.07 | 14.76 | 0.0437 |
| IPL_INL | 2.74 | 85.26 | 0.1020 |

**So the U-Net is not being replaced.** Phase 1 narrows what is reported, phase 2
adds the constraint the model provably lacks, and phase 3 turns the existing
uncertainty signal into a workflow. If any phase makes the table above worse,
that phase failed and is reported as having failed.

## Read first

- `AGENTS.md`, `CLAUDE.md`, and the `octa-layer-segmentation` skill.
- `outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/REPORT_TABLES.md` —
  the numbers this work must not regress.
- `outputs/stage_a/20260908_v2/dev_seed20260908/RUN_REPORT.md` §3 (the resume
  bug), §5 (where it fails), §9 (commands).
- `outputs/stage_a/20260908_v3_readability/RUN_REPORT.md` §6 — the entropy
  evidence phase 3 must calibrate.
- `code/eight_surface/README.md` — label format, provenance, and the four
  judgements the GUI keeps apart.
- `outputs/EIGHT_SURFACE_GUI_QC_AND_CNV_PLAN.md` §"How automated segmentation
  can be retrained".

## Environment

```
conda activate octa
```

Verified present in the env on 2026-09-08: `torch 2.8.0+cu126`, `numpy`,
`scipy`, `scikit-image`, `pandas`, `h5py`. **`PyMaxflow` is NOT installed, and
neither is `scikit-learn`.**

> **Installing into this env is the documented way to break it.** `CLAUDE.md`
> records that a broken conda/pip mix on Windows makes `h5py` fail to import,
> and that missing activation crashes `numpy.dot` and matplotlib with
> `0xC06D007F` and no traceback. Before installing PyMaxflow, note the current
> package state; after installing, immediately run `python code\check_env.py`
> and confirm `h5py`, `numpy.dot` and a matplotlib figure still work. If
> anything breaks, roll the install back and use the pure-NumPy fallback in
> phase 2 step 3 instead. Do not "fix" a broken env by reinstalling packages
> on top of it.

---

# Phase 1 — reduce the scope to four surfaces

This phase changes **what is reported and evaluated**, plus one classical
baseline setting. It does not retrain anything.

Three sub-items with genuinely different costs and different claims. Do not
conflate them; a cold reading of the brief could easily merge 1a and 1c into
"retrain with four heads", which is not what 1a says.

### 1a. Inner-retina evaluation scope — free, no retraining

Add an inner-retina reporting mode to the evaluation and comparison path that
scores only `ILM`, `RNFL_GCL`, `GCL_IPL`, `IPL_INL` and the three bands `RNFL`,
`GCL`, `IPL`, plus `INNER_RETINA` (= `ILM → IPL_INL`) as the new TOTAL analogue.

The existing 8-head checkpoint is used unchanged; only the surfaces you read out
of it change. Re-emit the v4 tables in this scope so there is a frozen
inner-retina baseline every later phase is measured against.

Include, in the same table: per-animal rows (TS169 and TS325 separately), and
the with/without-`TS325_OD_2026-05-26_6mo_s01_112940_b0510` sensitivity. That
one B-scan has 148 contiguous failing columns and dominates the pooled tails;
`sensitivity_without_b0510.csv` already exists as a template.

### 1b. Renormalize the classical priors to the inner band — classical only

**This applies to the classical cascade in `code/auto_seg_8layer_v2/`, which is
the baseline, not to the U-Net.** The 41.8 → 30.1 px measurement in "Why this
step" is a statement about a *scalar positional prior*, and the U-Net has none.

Refit `RNFL_GCL` and `GCL_IPL` as fractions of `ILM → IPL_INL` instead of
`ILM → PR_RPE`, and drop the `PR_RPE` outer anchor from the inner-retina path
entirely. Score the result through the real pipeline with
`auto_seg_8layer_v2/eval_variants.py`, including `--loao` for the
animal-held-out number, exactly as `project_octa_eight_surface_v2_cascade`
requires. Adopt only on that measurement.

Two standing constraints from `CLAUDE.md` still hold and are not up for
revision here: `refine_slow_axis(attract=0.05)`, not higher; and **do not refit
`IPL_INL`** however large a `refit` delta looks — that was tested and rejected
on 2026-08-28, and again in revision 2 the direct measurement said the
automatic `IPL_INL` was already ~0.7 µm from the human answer.

Expect this to help and not to be enough. If the inner-band renormalization
does *not* reproduce a spread reduction close to 41.8 → 30.1 px, stop and report
that, because it means the label subset being used differs from the one measured
here.

### 1c. Four-head retraining — an experiment, not a foregone conclusion

Train a 4-boundary variant (`model.boundary = Conv2d(base, 4, 1)`, region head
reduced to the 3 inner bands) on the same frozen split and compare against 1a.

The hypothesis is that concentrating 101 corrected B-scans on 4 surfaces beats
spreading them over 8. The competing hypothesis — that the outer surfaces are
*useful auxiliary supervision* that regularizes the shared encoder — is equally
plausible and is what the measurement decides. Report both directions honestly.
If 8 heads wins, keep 8 heads and report only 4; that is a perfectly good
outcome and 1a already delivers it.

### Phase 1 acceptance

- The three measurements in "Why this step" reproduced, with the script kept.
- A frozen inner-retina baseline table, per-animal, with the b0510 sensitivity.
- A `--loao` number for 1b.
- An explicit statement of whether 1c won, lost, or was inconclusive.

---

# Phase 2 — a decoder with inter-surface constraints

### The defect being fixed

`stage_a/model.py::decode()` takes a **softmax over depth per column and returns
its expected value**. Nothing couples the four surfaces to each other. The
consequence is already measured and recorded: every one of 512 B-scans in a real
WT volume contains crossing columns, median 14.9%, and crossing is the single
largest withholding reason — above shadow.

Note carefully what a soft-argmax does on a bimodal column: it returns a depth
*between* the two modes, where there is no boundary at all. A constrained
decoder does not merely tidy up crossings; it changes the estimator.

### 2a. Where the code goes — read this before creating a file

`train.code_identity()` hashes **every `.py` in `code/stage_a/`**, and the resume
guard rejects a checkpoint whose hash moved. This is why `stage_a_compare.py`,
`stage_a_review.py` and `stage_a_readability.py` live *outside* that directory
on purpose.

**Put the decoder outside too** — `code/stage_a_decoder.py` — so the delivered
v4 checkpoint stays resumable. If it genuinely must live inside `stage_a/`,
that is a deliberate decision to break resume on an existing checkpoint and it
needs to be raised first, not discovered afterwards.

### 2b. Derive the constraints from the labels, do not invent them

For each adjacent pair, measure the layer thickness distribution across the 101
corrected B-scans and take a wide interval (e.g. 1st/99th percentile, then
widened by a stated margin). Record the numbers and how they were derived.

Sanity anchors, not substitutes for the measurement: `reference.py` (eNeuro
2024, tree shrew) puts the GCL at ~10–12 µm ≈ 9–11 px at 1.12 µm/px. The GCL
being a **thin dark band between a thick bright RNFL and a thick IPL** is the
error `CLAUDE.md` warns is easy to re-introduce — if the fitted minimum GCL
separation comes out near zero, that is the bug reappearing, not a loose
anatomical bound.

Also carry over the existing axial step limit between adjacent A-lines
(`max_step=2` in the current DP).

### 2c. Build three decoders and measure all three

The point is to find out whether a global optimum earns its complexity, so the
graph cut must be measured against a cheap control, not just against the status
quo.

1. **Baseline** — the current soft-argmax, unchanged.
2. **Cheap control** — per-surface argmax/DP, then project each column onto the
   ordered cone (isotonic regression / pool-adjacent-violators along the surface
   index, with the minimum separations as offsets). ~20 lines, no new dependency.
3. **Graph cut** — Li / Wu / Chen / Sonka optimal surface segmentation, all four
   surfaces solved simultaneously as one min-cut, costs `−log softmax(logits)`,
   hard min/max separation between adjacent surfaces. `PyMaxflow` if the install
   is clean; otherwise report that phase 2c-3 is blocked on the dependency
   rather than hand-rolling a max-flow.

A 4-surface joint DP is O(D⁴) and is not the fallback. Do not build a
sequential DP with feasibility filtering and describe it as a global optimum —
it is not one.

### 2d. What to report

- **Crossing rate before and after.** Decoders 2 and 3 should be exactly 0 by
  construction; if not, the constraint is not actually being enforced.
- **Boundary error on the four surfaces, per animal, with b0510 sensitivity.**
  Crossing rate going to zero while error rises means the constraint is
  hiding the failure, not fixing it.
- **The columns that changed.** How many columns moved, by how much, and
  whether the movers were the high-entropy ones. If the decoder mostly moves
  confident columns, something is wrong.
- The honest coverage caveat on any three-way comparison: stored classical v2
  has **no predictions for any TS169 B-scan**, so v2 comparisons are TS325-only
  and cover 11 of 14 eligible B-scans.

### Phase 2 acceptance

Crossing eliminated **and** the phase 1 inner-retina error table not regressed.
A decoder that zeroes crossings while degrading `RNFL_GCL`/`GCL_IPL` median
error is a negative result and is reported as one.

---

# Phase 3 — a calibrated abstain-and-route queue

### What exists and what is wrong with it

Entropy predicts gross error at AUROC 0.92–1.00 per surface, and at ~90%
retained column coverage the retained p95 is 7.4 µm. That is a usable
abstention signal.

The defect is stated in `project_octa_stage_a_first_training_run`: **the
threshold was measured on the same two animals that selected the checkpoint.**
Any coverage number quoted from it is uncalibrated. Entropy also orders error
*magnitude* poorly (Spearman 0.14–0.53) even while separating gross from
non-gross well — so it is a triage signal, never a quality score, and must not
be reported as one. `CLAUDE.md` already forbids reviving `quality_confidence`
for the same reason.

### 3a. Calibrate on held-out animals

Only 9 animals carry labels; 2 are in validation and the final-test partition is
**locked** (`inference.py::test_guard`). **Do not unlock it for this.**

Use leave-one-animal-out over the available labelled animals and report a
coverage/error curve with per-animal spread, not a single number. State plainly
what LOAO over 9 animals can and cannot support. If the per-animal spread is
wide enough that no single threshold is defensible, that is the finding — report
it and recommend a per-volume adaptive rule instead of forcing a global
constant.

### 3b. Build the queue

A script that runs inference over a set of volumes, computes per-B-scan retained
fraction and longest gross run, and emits a review queue ordered by how much
human time each B-scan is likely to be worth.

Reuse the existing pack machinery (`eight_surface/review.py pack`) so the output
opens in the existing GUI. **Write packs, never labels.** `label_gui.py` via
`eight_surface/labels.py` is the only writer of human labels — `CLAUDE.md` is
unconditional on this, and a queue builder that writes a label file has
corrupted ground truth, not saved time.

Keep the queue's ordering signal separate from the acquisition-QC axes in
`outputs/scan_quality_metrics.csv`. They answer different questions and
`outputs/QUALITY_METRICS_NOTE.md` says to keep them apart until GUI review
calibrates them.

### 3c. Report honestly

Shadowed A-lines stay NaN and are never interpolated. Layers that cannot be
measured reliably are reported as unreliable, not dropped — all layers matter to
this project, per Xiaorong. An abstained column is missing evidence, not a
measurement of zero.

### Phase 3 acceptance

A LOAO coverage/error curve with per-animal spread; a working queue builder that
writes packs only; and a written statement of what coverage number may be quoted
and on what evidence.

---

## Standing constraints for all three phases

- Nothing writes to `OCTA_RawData\` or `MATLAB Code\`. Outputs go to
  `octa\outputs\`.
- Never write or modify a human label file from a script.
- Hold out **whole animals**, never random B-scans from the same volume.
- Every quality claim needs a measurement. When a metric looks too good, look
  for the confound first.
- Do not quote a pooled p95 without the b0510 sensitivity beside it.
- No CNV-core claim. 7 B-scans and ~170 lesion columns cannot support one, and
  the lesion work in the Tier 3 brainstorm is explicitly out of scope here.

## Out of scope

Sparse-B-scan lesion propagation, longitudinal same-animal priors, the
per-boundary GBM cost model, attenuation-coefficient contrast, OCTA plexus
cues (blocked by `OCTA_MOTION_CONTRAST_AND_VASCULAR_ANALYSIS_NOTE.md` §"Rules
for current CNV work" item 3), architecture sweeps, and any approach to the
locked test animals.
