# Revision-2 automated eight-boundary segmentation

Generated 2026-09-02. Code in `code/auto_seg_8layer_v2/`, outputs in this
folder. Nothing in `code/eight_surface/` was modified: the GUI, the review
packs, the human labels and the original eight-boundary batch are untouched.

## What was asked and what was done

The automatic eight-boundary cascade was recalibrated against the 16 completed
review packs and then re-run on the **16 review-queue volumes that have no
human labels**, so the delivered segmentation is not a fit to its own training
data. Twenty example figures are spread across the acquisition QC score.

Training evidence: 74 saved decisions in 16 packs — 53 `corrected`, 21
`rejected`. Only the 53 corrected ones are evidence, and within them only
boundaries a human actually drew, marked visible, left reliable, and outside
right-drag exclusions. The 21 rejected B-scans and the 15.1% of A-lines marked
excluded are used nowhere. There were **no** `accepted`-without-edit labels, so
the reflex-click concern in CLAUDE.md does not arise here; median active review
time on the corrected B-scans was 84.8 s.

## Finding 1 — the `PR_RPE` anchor failed on a third of reviewed B-scans

The shipped rule takes the brightest dynamic-programming path in
`[ILM + 60, n_depth]`. In tree shrew the RNFL/IPL plateau is broad and
laterally consistent, while the RPE complex is bright on some A-lines and
attenuated on others, so the cheapest continuous bright path can run through
the **inner** retina and take every deeper surface with it.

Measured on the 53 corrected B-scans, comparing each automatic line with the
human line the same person drew over it:

| | median | 95th percentile | fraction shifted > 20 px |
|---|---|---|---|
| ILM correction | 0.0 px | 6.4 px | 2 / 53 |
| `PR_RPE` correction | −5.8 px | +193.4 px | **17 / 53 (32%)** |

The failures are one-sided: the automatic line sits 160–215 px too shallow.
They occur in 6 of the 16 reviewed volumes, and are not confined to CNV eyes.

**Fix.** The human `PR_RPE` sits at 0.759–0.924 of the ILM-to-posterior-tissue
depth on all 53 B-scans, lesions included. The search is now bracketed to
`[ILM + 0.60·d, ILM + 1.02·d]`, where `d` is the robust ILM-to-posterior-edge
depth already computed by `tissue_bounds` and previously discarded. Where the
posterior edge is unusable the code reverts to the old rule and records a note
on the volume. This is a bracket, not a smoothing term: `attract` stays at 0.05
and no averaging changed, so localized CNV shape is not touched.

## Finding 2 — two inner priors were wrong, three only looked wrong

The eight-boundary config inherited `RNFL_GCL = 0.2390` and
`GCL_IPL = 0.2799` from the ten-surface cascade. Under this contract they place
both surfaces one landmark too shallow — the same class of error the project
already hit once, and against the same reference table.

Human-drawn layer thickness versus the shipped automatic output, on the same
53 B-scans, against eNeuro 2024 tree shrew (central / peripheral):

| Layer | Human | Shipped automatic | Paper |
|---|---|---|---|
| RNFL | 90.0 µm | 56.0 | 81.7 / 62.8 |
| **GCL** | **13.2** | 9.0 | **12.5 / 10.1** |
| IPL | 56.9 | 76.2 | 50.0 / 45.7 |
| **INL** | **35.6** | 32.5 | **34.0 / 34.0** |
| OPL | 16.7 | 14.6 | — |
| PHOTORECEPTOR | 30.9 | 43.7 | — |
| RPE | 21.2 | 14.6 | — |
| TOTAL | 265.2 | 245.3 | 250.7 / 229.8 |

GCL and INL landing independently on the published values is the check that
matters: if the human stack were shifted as a whole, both would not agree. The
automatic GCL is too thin and its IPL absorbs the difference, which is the
signature of `RNFL_GCL` and `GCL_IPL` sitting too shallow.

`review.py refit` reports large relative-position deltas for `IPL_INL`,
`INL_OPL` and `OPL_ONL` as well. **Most of that is the anchor failure, not the
prior.** Asking the other question — how far is the automatic surface from the
human line, in micrometres, on B-scans where the anchor did not fail:

| surface | all 53 B-scans | good-anchor 36 only |
|---|---|---|
| ILM | 0.2 µm | 0.4 µm |
| `RNFL_GCL` | 42.4 | **30.5** |
| `GCL_IPL` | 46.2 | **34.1** |
| `IPL_INL` | 10.3 | 3.0 |
| `INL_OPL` | 8.5 | 4.4 |
| `OPL_ONL` | 10.1 | 4.5 |
| `PR_RPE` | 10.7 | 9.3 |
| `RPE` | 4.9 | 2.7 |

This is the distinction CLAUDE.md records, and it holds: on good-anchor
B-scans only `RNFL_GCL` and `GCL_IPL` are genuinely misplaced.

**So both candidate prior sets were run through the real pipeline** — 3-B-scan
averaging and `attract = 0.05` slow-axis refinement, not a single unaveraged
B-scan — and scored against the human labels. Results below.

## Measured result

Distance from the human line, in micrometres, over all 53 corrected B-scans.
Baseline is the shipped cascade's own stored `auto_surfaces`, so both columns
come from the same real pipeline.

| surface | baseline median | v2 median | baseline p90 | v2 p90 | baseline > 25 µm | v2 > 25 µm |
|---|---|---|---|---|---|---|
| ILM | 0.2 | 0.2 | 6.9 | 6.9 | — | 0.04 |
| `RNFL_GCL` | 42.4 | **9.0** | 114.7 | **26.7** | — | 0.15 |
| `GCL_IPL` | 46.2 | **10.1** | 125.3 | **27.8** | — | 0.17 |
| `IPL_INL` | 10.3 | **4.2** | 158.0 | **10.5** | 0.35 | **0.02** |
| `INL_OPL` | 8.5 | **5.6** | 172.9 | **9.2** | 0.30 | **0.00** |
| `OPL_ONL` | 10.1 | **4.7** | 191.3 | **7.8** | 0.35 | **0.00** |
| `PR_RPE` | 10.7 | **9.5** | 199.3 | **16.8** | 0.33 | **0.00** |
| `RPE` | 4.9 | **2.9** | 193.2 | **7.6** | 0.34 | **0.00** |

Refitting all five inner priors beat refitting only two on exactly the three
surfaces in dispute (`IPL_INL` p90 36.9 → 10.5 µm; `OPL_ONL` 20.3 → 7.8), so
all five were adopted — on the measurement, not on the relative-prior delta.
Both variants are in `qc/variant_comparison.json`.

### Adopted priors

| surface | shipped | revision 2 | leave-one-animal-out spread |
|---|---|---|---|
| `RNFL_GCL` | 0.2390 | **0.3695** | 0.021 |
| `GCL_IPL` | 0.2799 | **0.4256** | 0.011 |
| `IPL_INL` | 0.5799 | **0.6625** | 0.007 |
| `INL_OPL` | 0.7460 | **0.8018** | 0.006 |
| `OPL_ONL` | 0.8046 | **0.8748** | 0.007 |

Refitting with any one of the six animals removed moves each prior by at most
0.021 of the ILM-to-`PR_RPE` span — far less than the 0.056–0.146 corrections
themselves. These are dataset-wide constants, not one animal's anatomy.

### The priors are not overfitted

The table above is measured on the same 53 B-scans the priors were fitted from.
Refitting each fold without one animal and scoring only that animal's B-scans
(`qc/leave_one_animal_out.json`) changes almost nothing:

| surface | in-sample | leave-one-animal-out |
|---|---|---|
| `RNFL_GCL` | 9.0 µm | 10.3 |
| `GCL_IPL` | 10.1 | 11.3 |
| `IPL_INL` | 4.2 | 4.2 |
| `INL_OPL` | 5.6 | 5.6 |
| `OPL_ONL` | 4.7 | 5.1 |
| `PR_RPE` | 9.5 | 9.5 |
| `RPE` | 2.9 | 2.9 |

The outer anchor has no fitted parameter, so it needs no fold.

## Held-out result: the 16 volumes nobody labelled

The delivered segmentation is in `segmented/` — 16 volumes, 8192 B-scans, no
failures. The outer-anchor bracket applied on all but 2 B-scans; those two fell
back to the old rule and are recorded in that volume's notes.

There is no human ground truth here, so the only available checks are
anatomical. Median over volumes of each volume's median layer thickness
(`qc/heldout_vs_reference.csv`):

| Layer | shipped | v2 | hand-labelled | paper C/P | d(hand) shipped → v2 |
|---|---|---|---|---|---|
| RNFL | 51.5 | 84.0 | 90.0 | 81.7 / 62.8 | 38.5 → **6.0** |
| GCL | 10.1 | 12.9 | 13.2 | 12.5 / 10.1 | 3.1 → **0.3** |
| IPL | 61.6 | 48.8 | 56.9 | 50.0 / 45.7 | 4.7 → 8.2 |
| INL | 37.0 | 38.1 | 35.6 | 34.0 / 34.0 | 1.4 → 2.5 |
| TOTAL | 230.7 | 245.3 | 265.2 | 250.7 / 229.8 | 34.5 → **19.9** |

Volumes with every checked layer inside the published plausible range: shipped
9/16, v2 **14/16**.

Two caveats. The hand column comes from the *labelled* volumes, so this is a
comparison of central tendencies between two different sets of eyes, not a
paired measurement — the labelled per-B-scan table above is the rigorous one.
And `plausible_range` is a nonsense screen, not an accuracy measure: it spans
10–128 µm for RNFL.

## The 20 examples

`figures/qc_examples/` plus `figures/qc_examples_contact_sheet.png` and
`figures/qc_examples/examples_manifest.csv`.

The 16 held-out volumes do not span the dataset-wide acquisition QC range: 11
sit below the 5th percentile, 4 near the 50th, 1 near the 90th. Deciles are
therefore taken **within the held-out set** (one volume per decile, spanning
qc_score 7.58 to 50.11), and every figure is annotated with its dataset-wide
percentile as well. Two B-scans per decile: the volume's median and its worst
by segmentation support, so each pair shows a typical case and that volume's
hardest one.

## What is still wrong — read this before using the output

### A pre-existing ILM failure, which this revision exposes rather than causes

On the lowest-QC held-out volumes the ILM drifts up into the vitreous over
broad stretches of A-lines. In `TS267_OS_2025-03-19_D28_s03_103903` b0333 it
reaches 16 px where the true ILM is ~145. It is clearly visible in the decile-1
and decile-20 examples.

The ILM code is **unchanged** in this revision, and the two cascades' ILM
arrays are bit-identical on all 16 volumes, so this defect is pre-existing.
But it did not show up before and it does now, for a specific reason: with
`RNFL_GCL` sitting ~31 µm deeper, a drifting ILM now produces an *implausibly*
thick RNFL instead of a merely too-thick one.

| | shipped | v2 |
|---|---|---|
| A-lines with RNFL outside 10.1–127.7 µm | 0.2% | **6.4%** |
| held-out volumes with > 1% such A-lines | 1 / 16 | 8 / 16 |

The shipped cascade avoided the upper bound mainly by placing RNFL_GCL far too
shallow — its median RNFL of 51.5 µm is below the published peripheral value
and 38 µm below the hand labels — so this is not evidence that the old priors
were better. It is evidence that **the ILM is now the limiting surface.**

It also propagates: the new outer bracket is ILM-relative, so on a B-scan where
the ILM is wrong the `PR_RPE` bracket rides on a wrong reference. The bracket
could be made ILM-independent — measured against the human labels,
`tissue_bounds`' posterior edge sits 20–58 px below the human `PR_RPE`, which
is enough to bracket it without using the ILM at all. That is untested and is
the first thing to try.

**Recommended next step: fix the ILM before running the remaining volumes.**

### Residual error on the two refitted inner surfaces

`RNFL_GCL` and `GCL_IPL` still miss by more than 25 µm on roughly one B-scan in
six, with p90 near 27–28 µm. A scalar relative prior cannot fix this: the tree
shrew RNFL is organised into discrete bundles, so its lower boundary genuinely
moves A-line to A-line. These are the cases for the learned boundary-cost model
in the plan document, and the highest-value B-scans to send back to the GUI.

### The RNFL convention question is still open

The hand labels read RNFL at 90.0 µm against a published axon-bundle height of
81.7 µm central, while CLAUDE.md records that a per-A-line surface should read
*lower* than bundle height. `RNFL + GCL + IPL` is 160.1 µm by hand against
144.2 published, and v2 gives 145.7 on the held-out volumes — so the boundary
convention, not the tissue, is what differs. Calibrating to the hand labels was
the right default, but it means the reported RNFL/IPL split inherits whichever
convention the labelling used. That is Xiaorong's call, not a prior to tune.

### Not done

The GUI was not touched, as requested. No labels were written. The remaining 16
review packs were not segmented with this revision, and neither were the other
282 indexed scans.
