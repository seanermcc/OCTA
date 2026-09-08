# Revision-2 automated eight-boundary segmentation

Isolated from `code/eight_surface/`. Nothing here modifies the GUI, the review
packs, the human labels, or the original eight-boundary batch outputs. All
results are written to `outputs/auto_seg_8layer_v2/`.

Calibrated on the 53 human-corrected B-scans in the 16 completed review packs;
run on the **16 review-queue volumes that have no human labels**, so the
reported behaviour is not a fit to its own training set.

## What changed, and why

Two changes, both forced by a measurement against the human labels. Everything
else — ILM cost and search, the RPE outer edge, neighbour-scaled inner search
windows, shadow handling, `attract=0.05`, `bscan_avg=3`, local confidence — is
byte-for-byte the shipped behaviour.

### 1. `PR_RPE` is bracketed from the posterior tissue edge

The shipped rule takes the brightest DP path in `[ILM + 60, n_depth]`. In tree
shrew the RNFL/IPL plateau is broad and laterally consistent, while the RPE
complex is bright on some A-lines and attenuated on others, so the cheapest
continuous bright path can run through the **inner** retina. Measured on the 53
corrected B-scans, that happened on **17 of them (32%)**, with the automatic
line 160–215 px too shallow, dragging every surface below it with it.

The human `PR_RPE` sits at 0.759–0.924 of the ILM-to-last-tissue depth on all
53 B-scans, lesions included. The search is therefore restricted to
`[ILM + 0.60·d, ILM + 1.02·d]` where `d` is the robust ILM-to-posterior-edge
depth from `tissue_bounds`. Where that edge is not usable the code falls back
to the original rule and says so in the volume notes.

### 2. `RNFL_GCL` and `GCL_IPL` priors refit — and only those two

The eight-boundary config inherited `RNFL_GCL=0.2390` and `GCL_IPL=0.2799` from
the ten-surface cascade. Under this contract they place both surfaces one
landmark too shallow. See `outputs/auto_seg_8layer_v2/REPORT.md` for the
measurements.

`review.py refit` also reports large relative-position deltas for `IPL_INL`,
`INL_OPL` and `OPL_ONL`. **Those are artefacts of the anchor failures above.**
Measured directly on B-scans where the anchor did not fail, the shipped
automatic lines were already 3.0, 4.4 and 4.5 µm from the human ones. This is
the distinction CLAUDE.md records: "is the prior in the right place" is not "is
the surface in the right place". The two candidate prior sets were run through
the real pipeline and compared; see `qc/variant_comparison.json`.

## Files

| File | Purpose |
|---|---|
| `segment_v2.py` | Per-B-scan cascade with the outer anchor |
| `volume_v2.py` | Volume driver; reuses the validated slow-axis refinement |
| `fit_priors.py` | Fits inner priors from human labels, with leave-one-animal-out |
| `eval_variants.py` | Scores candidate settings against the human labels through the real pipeline |
| `batch_v2.py` | Batch runner; `--held-out` selects the 16 unlabelled volumes |
| `export_examples.py` | QC tables and the 20 acquisition-QC-spread example figures |
| `check_labels.py` | Renders human labels beside the automatic lines |
| `priors_v2.json` | Fitted priors and their per-surface evidence |

## Order of operations

From `code`, with `conda activate octa`:

```powershell
python auto_seg_8layer_v2/fit_priors.py --out auto_seg_8layer_v2/priors_v2.json
python auto_seg_8layer_v2/eval_variants.py
python auto_seg_8layer_v2/batch_v2.py --held-out
python auto_seg_8layer_v2/export_examples.py
```

## What this is not

This is calibration plus one anchor fix, not a learned segmenter. It does not
touch the GUI, does not write labels, and does not claim the remaining error is
acceptable — `RNFL_GCL` and `GCL_IPL` still miss by more than 25 µm on roughly
one B-scan in six, and `IPL_INL` on about one in four. Those are the cases the
learned boundary-cost model in the plan document is meant to address, and they
are exactly the B-scans worth sending back to the GUI.
