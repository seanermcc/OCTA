# Eight-boundary GUI, QC review, and CNV analysis plan

Updated: 2026-09-02

Implementation update: the linked structural/OCTA en-face footprint editor,
versioned independent CNV/ONH-edge label format, and core/rim/nearby/remote
review-pack builder are now implemented in `code/eight_surface/cnv_gui.py`,
`cnv_labels.py`, and `cnv_review.py`. CNV is a freehand, automatically closed
and lightly smoothed footprint; the ONH annotation is a separate open edge
trace, suitable for an ONH entering through the field boundary. Structural and
OCTA brightness/contrast controls are display-only. The editor intentionally
has no RPE-elevation or thickness advisory panel. No biological CNV masks have
been created automatically; annotation remains a human action.

## Current checkpoint

- The eight-boundary review queue contains **32 volume packs**.
- Manual review is complete for the first **16 of 32 packs**.
- Those 16 packs produced **74 saved B-scan decisions**.
- The other 16 packs currently have no saved labels.
- Closing the GUI committed the final active decision; the count increased from
  67 labels in 15 packs to 74 labels in 16 packs.
- No prior refit, learned-model training, or lesion-mask training has been run
  from this checkpoint.

## Where the outputs and GUI are

| Item | Location | Meaning |
|---|---|---|
| Human labels | `outputs/eight_surface/labels/` | The important manual output: one compressed NPZ per reviewed B-scan. These records contain the corrected and automatic boundaries, verdict, edited/displaced/visible/reliable flags, excluded A-lines, timing, and provenance. |
| Review packs | `outputs/eight_surface/review/` | The 32 GUI input packs. These are a review queue, not human ground truth. |
| Automatic eight-boundary volumes | `outputs/eight_surface/segmented/` | Automatic segmentations used to construct the packs. |
| Pre-manual comparison images | `outputs/pre-images_8layer_Gui/` | One matched pre-manual image per pack plus `pre_manual_manifest.csv`. |
| QC-selected volume list | `outputs/eight_surface/qc_review_groups.csv` | The 32 volumes and their low/medium/high QC strata. |
| Independent QC measurements | `outputs/scan_quality_metrics.csv` | Separate signal, slow-axis continuity, and repeat-agreement measurements. |
| Ranked QC review table | `outputs/scan_quality_ranked.csv` | Exploratory 0-100 review-ordering score derived from the separate QC axes. It is not a validated biological or clinical quality label. |
| QC workbooks and previews | `outputs/scan_quality_20260831/` | Human-readable workbooks, definitions, and verification previews. |
| New GUI | `code/eight_surface/label_gui.py` | The current eight-boundary manual correction program. |
| GUI/workflow instructions | `code/eight_surface/README.md` | Launch command, controls, output meanings, and post-review steps. |

Run the GUI from `code/` after activating the `octa` environment:

```powershell
python eight_surface/label_gui.py ..\outputs\eight_surface\review
```

It resumes at the next undecided B-scan. Matched post-manual figures have not
yet been generated; when wanted, the existing command is:

```powershell
python eight_surface/prepost_images.py post
```

## What changed in the new GUI

This workflow is intentionally isolated from the old ten-surface GUI and old
labels. It draws eight boundaries:

1. `ILM`
2. `RNFL_GCL`
3. `GCL_IPL`
4. `IPL_INL`
5. `INL_OPL`
6. `OPL_ONL`
7. `PR_RPE` — the former RPE-complex peak
8. `RPE` — the outer RPE edge, formerly used as the BM endpoint

ELM and IS/OS are no longer forced as separately measurable boundaries. The
band from `OPL_ONL` to `PR_RPE` is reported as a combined `PHOTORECEPTOR`
layer. This avoids pretending the current images reliably resolve every outer
retinal sub-boundary.

The GUI records distinct decisions that must remain distinct during analysis
or training:

- A drawn boundary (`surface_edited`) is direct human evidence.
- A boundary moved only by the ordering constraint (`surface_displaced`) is
  not a human label.
- A boundary marked not visible (`surface_visible=False`) has no defensible
  target at that location.
- An unchecked boundary (`surface_reliable=False`) remains visible for context
  but is excluded from analysis; its adjacent thickness band or bands become
  unreliable/NaN.
- A right-drag exclusion (`region_excluded`) marks an A-line range unusable for
  every boundary, such as a severe shadow or edge artefact.
- Accepted, corrected, and rejected verdicts, active review time, stroke count,
  control status, source pack, and label time are stored with every decision.

The new version also resumes at the next undecided B-scan, preserves rejections
across restarts, skips rejected images during ordinary navigation, and fixes a
pack-switch timing bug that could briefly expose an invalid B-scan index.

## What the new QC check does

The old `quality_confidence` rankings are retired as acquisition-quality
labels. The first used whole-column surface confidence; the second used local
segmentation support from one B-scan. Neither measured acquisition quality.

The independent QC pass now keeps three failure axes separate:

1. **Signal/contrast:** retinal signal relative to a vitreous noise window,
   robust CNR, and low-signal coverage.
2. **Slow-axis continuity:** adjacent raw B-scan agreement, discontinuity, and
   stripe/motion behaviour.
3. **Repeat agreement:** registered similarity between same-session repeats,
   used only when the repeats have enough structural overlap to be comparable.

For review ordering, an exploratory 0-100 score combines equal-weight
within-dataset ranks. Missing repeat information is declared and the score uses
the two observed axes; it is not silently imputed. The 32-volume manual-review
sample contains 16 lowest-scoring volumes, 8 near the 50th percentile, and 8
near the 90th percentile. The packs contain a 96:32:32 low:medium:high B-scan
mix, including median-ranked within-volume controls so the correction set does
not contain failures only.

## Interpretation of the example CNV

The circled region shows a focal outer-retinal/RPE-complex abnormality with
substantial distortion and attenuation below it. Several normal-retina
assumptions become unsafe there: a nominal boundary may be displaced by real
lesion anatomy, may attach to a different bright edge, or may not be visible at
all. A smooth, anatomically ordinary line through the lesion can therefore be
a prior-driven error rather than a measurement.

This should not automatically be treated as generic low image quality. The
lesion is biologically meaningful, while the deep shadow beneath it is missing
evidence. The appropriate annotation can differ by boundary: redraw a visible
displaced boundary, mark a genuinely absent/indistinguishable boundary not
visible and unreliable, and exclude only the A-line ranges where the image is
unusable for every boundary.

Two existing settings should not be increased to make these scans look
smoother. Slow-axis attraction above about 0.4 erases localized CNV shape; the
validated value is 0.05. More B-scan averaging also worsened TOTAL segmentation
on both measured CNV examples, so any lesion-specific averaging change must be
tested against human-corrected lesion B-scans rather than chosen visually.

## Recommended lesion labelling and analysis

En-face CNV labelling is useful, but it answers a different question from
surface correction. A footprint says where the lesion is in the lateral plane;
it does not specify where each retinal boundary lies in depth.

A practical annotation design is:

1. Draw a CNV footprint on registered en-face structural and OCTA views. Avoid
   defining it from a thickness map alone, because that would make the lesion
   label depend on the segmentation being evaluated.
2. Mark representative cross-sections through lesion core, edge, and nearby
   unaffected retina. Correct visible surfaces there and explicitly flag
   invisible or unreliable ones.
3. Preserve three spatial zones: lesion core, a perilesional rim/annulus, and
   matched remote retina from the same volume. This makes nearby-tissue effects
   testable instead of mixing them into one volume average.
4. Register longitudinal en-face views for the same animal and eye, then track
   lesion footprint, height/volume, OCTA flow area, and layer changes in the
   same core/rim/remote coordinates.
5. Treat repeated scans and time points as repeated observations from the same
   animal, not independent samples.

Useful lesion-centred measurements include RPE/PR-RPE elevation and
irregularity, photoreceptor-band disruption or loss, lesion height and volume,
core and annular layer thickness, and OCTA flow area/density. Deep attenuation
and shadow coverage should accompany these values as missing-evidence metrics.
If CNV creates tissue that cannot be represented by the normal layer stack, add
explicit lesion top/base or lesion-compartment annotations rather than forcing
a normal anatomical boundary through it.

## How automated segmentation can be retrained

There are three different operations, and they should not be called the same
thing.

### 1. Refit scalar position priors

The existing `review.py refit` step can adjust the relative locations of the
five weak inner boundaries. It consumes only corrected boundaries that were
actually drawn, visible, left reliable, and outside excluded A-lines. It must
not learn from accepted untouched lines, displaced-only lines, invisible
boundaries, rejected B-scans, or excluded regions.

This is calibration, not a learned image segmenter. A prior should change only
when corrections show a consistent offset across B-scans. Large noisy
per-A-line corrections are evidence that a scalar prior cannot solve the
problem. In particular, the existing project measurements say not to refit
`IPL_INL` merely because its relative-prior delta looks large.

### 2. Learn boundary-cost images, then retain the current constraints

This is the best next model for the current label volume. Train a small
pixel-wise image model to predict a probability/cost map for each boundary,
then pass those costs into the existing dynamic-programming surface finder.
Keep the anatomical ordering constraints, neighbour-scaled search windows,
shadow handling, slow-axis refinement, and local-confidence reporting.

Training targets should come only from genuinely human-drawn, visible,
reliable regions. Validation should hold out entire animals (and ideally
sessions), not random B-scans from the same volume, to prevent near-duplicate
leakage. Report boundary distance separately inside CNV core, at the lesion
rim, in remote retina, and in WT/control tissue.

### 3. Move to a CNN/U-Net or vision transformer when enough labels exist

A full image-to-boundary model has a higher ceiling but needs substantially
more diverse ground truth. It can predict eight boundary heatmaps, uncertainty,
and optionally a lesion mask. A 2.5-D model using neighbouring B-scans can use
3-D context without the memory cost of a full-volume model. Its outputs should
still be projected to ordered non-crossing surfaces and should preserve an
explicit abstain/unreliable state.

### Do not train on CNV scans only

A CNV-only model would learn the lesion distribution but lose its normal
anatomical reference and may hallucinate lesions or distort intact retina.
Prefer one of these designs:

- a single model trained with balanced WT, remote CNV retina, lesion rim, and
  lesion core sampling;
- a shared encoder with separate normal-boundary, lesion-boundary, and lesion-
  mask heads; or
- a normal model plus a lesion-aware specialist selected by an independently
  trained lesion detector.

Oversample lesion pixels or use lesion-weighted loss, but retain normal and
perilesional examples in every training round. Use active learning to send the
largest model-human disagreements and highest-uncertainty regions back to the
GUI.

## Where an LLM fits

A language model is not the right core engine for dense OCT segmentation. The
output is eight precise depth coordinates for every A-line, which is a vision
and numerical-optimization problem. A multimodal model adapted to do this would
in practice be a vision segmentation model, not an ordinary text LLM.

An LLM can still be useful around the segmenter: summarize QC and correction
patterns, retrieve similar past failures, propose active-learning cases,
standardize free-text lesion notes, generate audit reports, and orchestrate
the deterministic training/evaluation pipeline. It should not invent missing
boundaries or replace stored masks, reliability flags, and measured confidence.

## Suggested order of work after all 32 packs

1. Finish and audit all 32 packs; generate the matched post-manual images.
2. Summarize verdicts, edited surfaces, visibility/reliability flags, review
   time, and CNV/WT/core/rim coverage.
3. Create en-face lesion footprints and cross-sectional lesion-core/rim labels
   as a separate annotation product linked by scan ID and coordinates.
4. Freeze animal-level training/validation/test splits before fitting anything.
5. Measure the scalar prior refit, but apply only consistent, independently
   validated offsets.
6. Train the learned boundary-cost model first and compare it with the current
   classical costs on held-out human labels.
7. Add lesion-aware sampling or a lesion head only if the held-out lesion-core
   errors show a real benefit without degrading WT and remote retina.
8. Consider a larger U-Net/vision-transformer model only after the label count,
   time cost, and failure analysis justify it.
