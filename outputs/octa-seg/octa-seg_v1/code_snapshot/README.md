# OCT-A tree shrew CNV analysis pipeline

**octa-seg_v1 (2026-09-10):** the versioned boundary family now includes separate
traceability/reliability learning, per-boundary withholding, and isolated
contextual estimates. Its learned reporting states fail animal-excluded
validation, so this is an **experimental review workflow**, not a validated
measurement model. See [START_HERE](outputs/octa-seg/octa-seg_v1/START_HERE.md)
for the four complete volumes, 30-example CNV review queue, evidence audit,
calibration, and limitations. Open the queue using
`outputs\octa-seg\octa-seg_v1\OPEN_OCTA_SEG_V1.cmd`. Future feedback is stored
separately for v2; generic acceptance does not approve uncertain estimates.

Automated retinal layer segmentation and thickness mapping for the tree shrew
CNV (AMD model) OCT-A dataset.

**Major-vessel pilot (2026-09-09):** a classical contrast-and-shape baseline
produced six experimental en-face proposals, using two new vessel brush masks
from TS165 for development. It recovers major trunks but still confuses image
seams and lesion artifacts with vessels; it is not ready for unattended use.
Human labels are unchanged. See the
[six-scan comparison and labeling recommendation](outputs/vasculature_baseline/20260909_major_vessels/START_HERE.md).
The follow-up [continuous-band shape gate](outputs/vasculature_baseline/20260909_major_vessels_shape_gate/START_HERE.md)
removes small/compact regions on those same six proposals. It improves precision
with a small recall tradeoff; long image seams and some elongated artifacts remain.
The [32-scan editing queue](outputs/vasculature_baseline/20260909_queue32/START_HERE.md)
is now prepared for GUI correction: automatic masks preload where no vessel work
has been saved, and existing manual masks and drafts take priority. At preparation,
three vessel masks were already saved and 29 scans needed review. Open
`python code/open_enface_vessels.py` after activating `octa` to resume at the first
unfinished vessel mask.

## Repository scope

This repository contains the analysis code, pipeline documentation, and text
reports. Raw OCT/OCT-A volumes, derived arrays, figures, model checkpoints, and
human annotation files are intentionally excluded because they are large and
may contain study data. The pipeline expects the source dataset to be available
locally; paths shown below describe the lab workstation layout and can be
changed through the scripts' command-line arguments.

**Current inner-retina status (2026-09-09): the user authorized the full labeled
cohort, including the formerly reserved animals. The new development dataset has
102 corrected B-scans from nine animals and uses manual positions only; the layer
segmentation skill and published thickness values are not ground truth. The
eight-head architecture is retained, with four inner boundaries reported.
Nine animal-excluded models and a separate all-label inference model are complete.
Four complete volumes and 36 new review candidates are saved; all 33 implementation
checks passed. Open the [image-first guide](outputs/stage_a/20260909_full_labeled_cohort/START_HERE.md)
or the [full-cohort run report](outputs/stage_a/20260909_full_labeled_cohort/RUN_REPORT.md).
The earlier [seven-animal Tier 1 report](outputs/stage_a/20260909_inner_retina_tier1/RUN_REPORT.md)
remains a historical checkpoint. No untouched final-test estimate is claimed in
the new run. The strict no-regression criterion failed, so these remain experimental
outputs; the full 314-scan batch has not been run.**

> **The five existing files in `outputs\segmented\` are stale.** They were
> written with the old 9-surface cascade, whose inner-retina labels are wrong by
> one landmark, and with `attract` silently 0.0 rather than the 0.05 their own
> metadata records. Re-run `batch_segment.py --overwrite`. `qc_vs_reference.py`
> refuses to score them rather than printing confident numbers for the wrong
> layers.
>
> **`outputs\segment_v3\` holds the current output** — six scans re-run on
> 2026-08-28 with the refit priors (`CASCADE_VERSION` "4-10surf"): the three
> chosen for figures (TS267 D0 s02, TS267 D56 s01, TS305 D49 s03) and the three
> hand-labelled scans used to verify the priors. `outputs\figures\v3\` has the
> figures, `before_after_vs_paper.csv` the layer-by-layer comparison.
>
> **The 15 files in `outputs\segment_v2\` are also stale, more mildly.** They
> were segmented before `RNFL_GCL`/`GCL_IPL` were refit from real hand
> corrections (`CASCADE_VERSION` "3-10surf" -> "4-10surf"). They still carry
> the correct 10 surfaces and are still scoreable — this is not the same kind
> of wrong as the 9-surface files above — but `RNFL_GCL`/`GCL_IPL` in them sit
> at the old, now-measured-worse position (median 16 um from where a human
> actually drew them, vs ~4 um after the refit). Re-run `batch_segment.py
> --overwrite` on these 15 to pick up the improvement; see
> `octa/segment.py`'s comment on `RELATIVE_PRIORS` for the measurement.

---

## Where everything lives

```
G:\OCT_TreeShrew\
├── OCTA_RawData\            330 acquisitions, 3 years of imaging (READ ONLY)
│   └── <session>\<scan>_Processed\*_processedVolumes.mat   <- our input
├── MATLAB Code\             the lab's original pipeline (READ ONLY, see below)
└── octa\                    THIS PROJECT
    ├── README.md            this file
    ├── PIPELINE.md          what each stage does and how it does it
    ├── code\                the Python package and scripts
    └── outputs\             indexes, samples, figures, results
```

Nothing here writes to `OCTA_RawData` or `MATLAB Code`. Every output goes to
`octa\outputs\`.

---

## The one thing to understand first

**We are not reprocessing your raw data, and we can't.**

Turning a 10 GiB `.RAW` file into a usable volume is spectral OCT reconstruction —
λ→k resampling, dispersion compensation, 24-band STFT, GPU FFT, then registering
and averaging three volume repeats. That is what the lab's MATLAB code does, and
it has already been run on 314 of your 330 acquisitions over the past three
years. That is why the index says only 15 are "unprocessed" even though you never
ran a batch: **you didn't process them, the lab already had.**

Our pipeline starts one step later. It reads the `*_processedVolumes.mat` files
that MATLAB already produced (1,176 GB of them) and does the layer segmentation
and analysis that the existing code never did.

The 15 unprocessed acquisitions can't be analysed until someone runs the MATLAB
reconstruction on them:

| Session | Scans | Note |
|---|---|---|
| `26.06.30 TS336M CNV D49` | 5 | never processed |
| `26.07.28 TS336M CNV D56` | 5 | never processed |
| `25.04.16 TS267F CNV D56\New folder` | 3 | never processed |
| `25.08.07 TS305M CNV D35` | 1 | never processed |
| `24.10.17 TS247F before/after laser` | 1 | never processed |
| `24.10.17 TS247F before/after laser` | 1 | RAW deleted — unrecoverable |

---

## Dataset summary (from `outputs\scan_index.csv`, 330 rows)

| | |
|---|---|
| Acquisitions | 330 |
| With `processedVolumes.mat` (analysable) | **314** |
| Not yet reconstructed | 15 |
| RAW deleted | 1 |
| Hiding in subfolders (`analysis\`, `New folder\`, `Reanalysis\`, …) | 103 |
| Total `processedVolumes.mat` on disk | 1,176 GB |
| Animals | TS165 (WT), TS169, TS241, TS247, TS250, TS267, TS283, TS305, TS325, TS328, TS336 |

Every acquisition is 512 A-lines × 512 B-scans × 1024 depth pixels, a nominal
500 µm galvo drive corresponding to ~1460 µm on the retina, and ~1.12 µm per
depth pixel in tissue.

---

## What has been established so far

**The existing MATLAB segmentation is not usable for this project.**
`layers_refined_auto.mat` contains 4 surfaces, but only ILM and the NFL/GCL
boundary are actually refined; surfaces 3 and 4 sit within ~10 px of the first
two instead of ~200 px deeper where IS/OS should be. Even the RNFL result has
ILM and NFL/GCL crossing each other in a substantial fraction of A-lines.

**The layer landmarks the data supports** (measured, not assumed — from
ILM-flattened profiles in three separated vessel-free windows, all agreeing):
ILM at 0 µm, a strong trough at ~59 µm, a bump at ~95 µm, a dark band centred
~125 µm, a bump at ~147 µm, a trough at ~167 µm, then the photoreceptor/RPE
complex peaking at ~197 µm. The inner retina is one broad bright band with **no
visible RNFL/GCL step** in an averaged profile.

**The landmarks are now labelled, and the old labelling was wrong.** Stacking the
published eNeuro 2024 tree shrew thicknesses from the ILM predicts the GCL dark
band at 59 µm, the INL at 128 µm, the OPL at 150 µm and the ONL at 165 µm — four
independent agreements with the measured landmarks to within ~4 µm. The trough at
59 µm is the **GCL**, which in this species is a distinct dark band; the previous
priors read it as the INL and stacked everything below it one landmark too
shallow. That is why RNFL (34.7 µm) and GCL+IPL (28 µm) came out at roughly half
the published values while TOTAL still matched, and why the old cascade reported
a 47 µm "IS" layer.

**Measured against the paper after the fix** (TS165 WT slab, median µm, paper
peripheral in brackets): RNFL 59.4 [62.8], GCL 10.1 [10.1], IPL 41.4 [45.7],
INL 32.5 [34], ONL 22.4 [19], TOTAL 210.6 [229.8]. Every layer with a published
value is in range.

**The IPL sublaminae S1/S2/S3 are no longer segmented.** They came out
prior-driven rather than image-driven in all 15 scans checked (40–42%
prior-driven A-lines, the two weakest boundaries in the cascade, never once
scoring `image` support) — our SNR does not resolve them the way the paper's
speckle-reduced SR-B-scans do. The cascade is now **ten surfaces**. Removing
them left every other prior bit-identical, because `reference._STACK` still
stacks S1+S2+S3 to reach the IPL/INL depth. It did widen IPL/INL's search
window, which nearly doubled that surface's `local_confidence` (0.99 → 1.79)
while moving IPL and INL further from the published values — supported up,
plausible down. Human labelling is what should settle that, not another prior.

**Segmentation settings, chosen by measurement:**
- B-scan averaging **N = 3** (larger N reduces RNFL noise but biases it +3.4 µm and makes ONL/INL worse)
  - **Re-measured 2026-08-28 on four scans — unchanged, but the justification
    no longer reproduces, and the answer splits by scan type.** The original
    sweep was run only on a WT scan. TOTAL jitter from N=1 to N=7:

    | scan | N=1 | N=7 | best | change |
    |---|---|---|---|---|
    | `TS241_OD_2024-08-14_D0_s02` (control) | 1.43 | 1.18 | N=6 | −18% |
    | `TS267_OD_2025-02-19_D0_s02` (control, motion) | 7.52 | 6.39 | N=3 | −15% |
    | `TS267_OD_2025-04-16_D56_s01` (3 lesions) | 1.86 | 3.93 | N=1 | **+111%** |
    | `TS305_OD_2025-08-21_D49_s03` (2 lesions) | 2.17 | 3.47 | N=1 | **+60%** |

    Both controls improve with averaging; both CNV scans degrade, and only in
    TOTAL — the ILM→BM span, which is where a lesion lives. In GCL+IPL, which
    the lesions barely reach, every scan improves, but the CNV scans improve
    4-12x less (−3 to −5% vs −27 to −36%). The +3.4 µm RNFL bias does not
    appear on any of the four (bias within ±1 px at every N). So N=3 is
    currently a safe middle rather than a measured optimum, and **N may belong
    per-scan rather than global.** Re-derive properly before the 314-scan
    batch; do not edit casually. Sweeps in `outputs\sweep_<scan_id>.csv`,
    figures in `outputs\figures\v3\`.
- Slow-axis refinement **on**, soft attraction weight **0.05**
- Anchors: ILM and the RPE-complex peak, not Bruch's membrane

**Precision achieved** (WT scan, thickness jitter, RMS µm): TOTAL 3.33,
RNFL 1.99, GCL+IPL 2.88, INL 3.88, OPL 3.87, ONL 3.35.

**The vessel negative control passes.** After removing shared large-scale spatial
trend, correlation between every layer's thickness and vessel attenuation is
≤ 0.08. (The raw correlation of −0.5 was a confound, not contamination.)

**The CNV case holds.** On TS267F D98, where the lab marked three laser lesions,
the surfaces track through the disrupted regions without collapsing; total
thickness spans 87–335 µm versus a WT median of 208 µm.

---

## Quick start

```
conda create -n octa -c conda-forge python=3.11 h5py numpy scipy scikit-image matplotlib pandas
conda activate octa
cd /d G:\OCT_TreeShrew\octa\code
```

| Task | Command |
|---|---|
| Score a scan against the paper | `python qc_vs_reference.py --sample "<slab>.npz"` |
| Show the reference table + priors | `python qc_vs_reference.py --show-priors` |
| Build a human-review pack | `python review_surfaces.py pack --npz "<segmented>.npz" --n 12` |
| Build packs for a whole folder | `python review_surfaces.py pack --all ..\outputs\segment_v2 --n 6` |
| Correct surfaces by hand | `python label_gui.py ..\outputs\review` |
| En-face masks + linked surface review | `python eight_surface\cnv_gui.py ..\outputs\eight_surface\segmented` |
| Refit priors from corrections | `python review_surfaces.py refit --labels ..\outputs\labels` |
| Rebuild the index | `python index_scans.py --root "G:\OCT_TreeShrew\OCTA_RawData" --out "..\outputs\scan_index.csv"` |
| Pull a working sample | `python export_sample.py --volumes "<...processedVolumes.mat>" --slab --aline-stride 2 --out "..\outputs\samples\<name>.npz"` |
| Inspect a .npz | `python peek_npz.py "<file>.npz" --figures` |
| Re-run the averaging sweep | `python sweep_bscan_avg.py --seg "<segmented>.npz" --n-bscans 320 --out "..\outputs\sweep.csv" --plot "..\outputs\figures\sweep.png"` |
| Rebuild the presentation figures | `python make_figures.py --seg "<segmented>.npz" --before "<older>.npz" --out-dir "..\outputs\figures\v3"` |
| Compare two cascades against the paper | `python compare_versions.py --before ..\outputs\segment_v2 --after ..\outputs\segment_v3` |
| Check the environment | `python check_env.py` |

See `PIPELINE.md` for what each stage does and why.

---

## What is not built yet

1. **Batch runner** over all 314 scans (~3–5 hours, disk-bound).
2. ~~**Quality scoring** at A-line / B-scan / scan level.~~ **Independent scan
   QC implemented 2026-08-31:** signal/contrast, raw slow-axis continuity, and
   same-session repeat agreement are in `code/scan_quality.py` and
   `outputs/scan_quality_metrics.csv`. Thresholds and a combined grouping are
   intentionally deferred until the next GUI review calibrates the metrics
   against human `good / usable / reject` labels.
3. **Thickness-map query tools** — pick a point or ROI on the en-face, get layer
   thicknesses.
4. **ONH detection, eccentricity mapping, area-centralis axis.** Requires
   montaging, since the ONH is outside the ~1460 µm field in many scans.
5. **CNV lesion detection** from the layer maps.
6. **Learned segmenter** trained on human corrections of the hard cases.

## Open questions

- INL and ONL reference values are read off eNeuro 2024 Figure 3C, not stated in
  its text. They pass an arithmetic cross-check (see `code/octa/reference.py`)
  but are flagged `confirmed=False`. Worth confirming with Xiaorong.
- OPL, IS, OS and RPE-BM have no published tree shrew value at all; the priors
  for those are our own, from the residual of the paper's arithmetic.
- Whether the IPL sublaminae are recoverable at all in our data with heavier
  A-line averaging, as the paper does (250 A-lines, ~545 µm). They are out of
  the cascade until there is evidence either way; the GUI's per-surface
  "not visible" flag is how that evidence gets collected.
- ~~**IPL_INL almost certainly needs its own refit.**~~ **Answered 2026-08-28:
  it does not.** With 15 corrections touching it, the automatic `IPL_INL` sits
  0.7 µm from the hand-drawn surface — already right. The derived IPL layer
  does come out thicker against the paper, but that is `GCL_IPL` moving, not
  `IPL_INL` being misplaced, and against human labels the IPL layer *improved*
  (13.0 → 9.3 µm). See the `RELATIVE_PRIORS` comment in `octa/segment.py`.
- **`ELM` is now the most-wrong surface with human evidence behind it** — 5.9
  µm from hand-drawn truth, unchanged by the refit, and the only surface whose
  corrections all pull the same way (100% sign agreement, n=16). Its *prior* is
  already right (refit residual -0.001): the image pulls it deeper and the
  human pulls it back, so this is a cost-function or search-window problem, not
  a prior. Next thing to look at.

**RNFL_GCL and GCL_IPL priors refit from real hand corrections (2026-08-27) —
resolved, applied.** The first two surfaces with actual human ground truth
behind them rather than only the paper and a plausibility check. Verified with
the real pipeline on the two real scans with corrections plus the WT dev slab:
distance from the automatic output to the hand-drawn truth dropped from 16.3 to
3.4 µm (RNFL_GCL) and 16.2 to 4.4 µm (GCL_IPL) — roughly a 75-80% reduction.
The other four surfaces `refit` reports were **not** applied (see
`octa/segment.py`'s comment on `RELATIVE_PRIORS` for why, and the IPL_INL note
above for the trade-off this exposed). Existing outputs predate this and are
flagged stale above.

**Re-verified on 19 corrections (2026-08-28) — confirmed, nothing changed.**
With nearly twice the labels, `refit`'s residual for the two applied priors is
+0.004 and +0.011: they have converged. Distance to hand-drawn truth over 14
corrected B-scans in 5 scans, `segment_v2` → `segment_v3`: RNFL_GCL 17.5 → 6.3
µm, GCL_IPL 16.0 → 8.0 µm, and the derived layers RNFL 24.6 → 7.3, IPL 13.0 →
9.3. **The IPL_INL refit flagged above as the next target was tested and
rejected**: `refit`'s -0.024 delta for it is a relative-position artefact, and
measured directly the automatic IPL_INL already sits 0.7 µm from where humans
drew it. Re-deriving the whole stack from the human RNFL instead of the
paper's was tested too and is no better overall. See the `RELATIVE_PRIORS`
comment for both measurements.

**Against the paper, the same change reads as a regression, and that is
expected.** Over the six re-segmented scans, mean distance to the published
value went 4.4 → 6.8 µm: RNFL 11-16 µm thinner, IPL 8-17 µm thicker, GCL
slightly better, everything below IPL_INL bit-identical. RNFL + GCL + IPL is
conserved to within ~3 µm in every scan, so this moves the RNFL/GCL boundary
rather than the tissue — which is what the paper's axon-*bundle*-height RNFL
convention predicts (a per-A-line surface reads ~27% lower). **Open question
for Xiaorong: which convention should this project report?** It is not a prior
to tune — the humans and the paper agree on the total.
- Real laser-induction dates for TS169, TS250, TS305, TS336 (`outputs\laser_dates.csv`).
  Folder day labels drift from true elapsed time by up to 41 days for TS325.
- Confirm the 1460 µm lateral field figure inherited from `meansureOnBscan.m`.
