---
name: octa-layer-segmentation
description: >
  Segment, validate, and hand-correct retinal layer surfaces in the tree shrew
  vis-OCT / OCT-A CNV dataset, scoring every layer against the published eNeuro
  2024 tree shrew reference values. Use this whenever the work touches retinal
  layer boundaries, layer thickness, ILM/RNFL/GCL/IPL/INL/OPL/ONL/ELM/IS-OS/RPE/BM
  surfaces, IPL sublaminae (S1/S2/S3, retired), thickness maps, the labelling
  GUI, segmentation QC, "does
  this segmentation look right", suspicious or implausible layer thicknesses,
  low-quality or low-signal B-scans, manual correction or labelling of surfaces,
  refitting segmentation priors, or running/resuming the batch over the 314
  processed scans. Also use it before changing anything in octa/segment.py,
  octa/volume.py, octa/surfaces.py or octa/reference.py, because several
  settings there were chosen by measurement and silently degrade if altered.
---

# Tree shrew OCT layer segmentation

This skill covers the segmentation half of the OCT-A tree shrew CNV pipeline:
finding layer surfaces, deciding whether to believe them, correcting the ones
that are wrong, and feeding those corrections back.

Read `../../../PIPELINE.md` for how each stage works and `../../../CLAUDE.md`
for project-wide rules. This file covers what is specific to layers.

## Before anything else

```bash
conda activate octa
```

Running `D:\Anaconda\envs\octa\python.exe` directly without activating fails in
a confusing way: `Library\bin` is missing from PATH, MKL fails to delay-load,
and `numpy.dot` plus **all** of matplotlib crash the interpreter outright with
exit code `0xC06D007F` and no Python traceback. It looks like a broken
environment. It is not — it is a missing activation.

## The workflow

```
segment  ->  qc_vs_reference  ->  review pack  ->  human correction  ->  refit
```

Each step has a script in `code/`. Run them from `code/`.

### 1. Segment

```bash
python batch_segment.py --dry-run          # see what would run
python batch_segment.py --limit 2          # smoke-test on real scans
python batch_segment.py                    # the real run, ~3-5 h, disk-bound
```

Resumable — a scan with existing output is skipped unless `--overwrite`.

### 2. Score against the published values

```bash
python qc_vs_reference.py --sample ../outputs/samples/slab_TS165_WT.npz
python qc_vs_reference.py --npz ../outputs/segmented/<scan>.npz
python qc_vs_reference.py --all --out ../outputs/qc_reference_scores.csv
python qc_vs_reference.py --show-priors    # the reference table and priors
```

This prints two tables, and **the second one is the one that catches real
problems**. See "Reading the two verdicts" below.

### 3. Build a review pack, correct it, refit

```bash
python review_surfaces.py pack --npz ../outputs/segment_v2/<scan>.npz --n 12
python review_surfaces.py pack --all ../outputs/segment_v2 --n 6   # a queue
python label_gui.py ../outputs/review            # correct them (Qt window)
python review_surfaces.py refit --labels ../outputs/labels
```

`pack` does one bulk read per scan and keeps only the B-scans worth a human's
time, ranked on four things that do not substitute for one another —
unsupported surfaces, implausible layers, shadow fraction, and disagreement
with neighbouring B-scans — **combined by rank within the scan**, not by adding
the raw numbers. Added raw they barely discriminated (0.63–0.83 across a whole
pack, controls included); ranked, the same scan spreads 0.15–0.94. Picks are
forced `--min-sep` apart, or the "worst" B-scans come out as one contiguous run
and cost eight times as much to label for almost the same information. A few
median-ranked **controls** are packed too and are not optional: a correction set
drawn only from failures teaches a refit that the retina looks like its own
worst cases.

`label_gui.py` needs a desktop session (PySide6). `pack` and `refit` are
headless. Correction is freehand-drag on the active surface; the offset is
tapered to zero beyond the ends of the stroke, so a correction joins the
untouched automatic surface instead of leaving discontinuities no DP surface
could produce.

The GUI records three things separately, and conflating them is how a training
set gets quietly poisoned:

| | means |
|---|---|
| `surface_edited` | a human drew this surface — **the only evidence** |
| `surface_displaced` | ordering shoved it to make room for someone else's edit |
| `surface_visible` | the human could actually see this boundary here |
| `region_excluded` | per-A-line, not per-surface: the image itself is unusable in this column range, for every surface at once (right-drag to mark, ctrl+right-drag to clear, `e` to clear all) |

`surface_visible` and `region_excluded` answer different questions and are easy
to conflate. A boundary can be invisible while the image around it is fine
(mark `surface_visible=False` on that one surface); a stretch of the image can
be unusable regardless of which boundary you're looking for — a shadow, an
edge artefact — in which case mark the region instead of walking through every
surface individually.

It also times each B-scan (only while the window has focus). That number is
what decides whether a learned model is reachable, and it should be measured
before anyone commits to a labelling budget.

The old matplotlib editor (`review_surfaces.py edit`) is gone — two editors
means two label formats to keep in step, and the less-used one drifts.

## Reading the two verdicts

`qc_vs_reference.py` answers two independent questions, and conflating them is
how this project previously shipped a wrong result that looked right.

**Plausible?** Median layer thickness against the eNeuro 2024 tree shrew table.
Catches a mislabelled cascade.

**Supported?** `local_confidence` — how much better the chosen depth was than
its immediate neighbourhood, as a robust z-score. Catches a surface the prior
placed and the image never confirmed.

| | Supported | Unsupported |
|---|---|---|
| **Plausible** | a result | **the dangerous case** |
| **Implausible** | a real anomaly (lesion? bad scan?) | broken, and honest about it |

Plausible-but-unsupported is dangerous because it is invisible. A surface
pinned by its prior is smooth, correctly ordered, and sits at an anatomically
sensible depth — because a prior put it there. Plotting it over a
contrast-stretched B-scan will not reveal anything wrong. This already happened
once here, which is why the confidence number now travels with the surfaces
instead of being computed and dropped.

When a layer is unsupported, report it as unreliable. Do not quietly drop it —
all layers matter to this project (per Xiaorong).

A third question is not answered by either verdict: **could a human see the
boundary at all?** An invisible boundary has no correct answer to learn, which
is a different statement from the automatic answer being wrong. Only the
per-surface "not visible" flag in `label_gui.py` records it.

Current state (10-surface cascade, TS241 D0, pre-refit numbers): ILM, IPL_INL,
INL_OPL, OPL_ONL, ELM, ISOS, RPE and BM are image-driven; **RNFL_GCL and
GCL_IPL are mixed**, at 40–42% prior-driven A-lines. Those two were the
weakest boundaries in the cascade, which is exactly why they were the first
target for hand correction and the first (and so far only) surfaces refit from
real human ground truth — see `CASCADE_VERSION` "4-10surf" in `segment.py`.
Re-run `qc_vs_reference.py` on a fresh segmentation to see the post-refit
numbers; the ones above predate it.

**IPL_S1S2 and IPL_S2S3 have been removed** from the cascade — they were
prior-driven in all 15 scans checked, never once image-driven, because our SNR
does not resolve the IPL sublaminae the paper resolves with speckle-reduced
SR-B-scans. They remain in `reference._STACK` (published anatomy, and how the
stack reaches the correct IPL/INL depth), so removing them changed no other
prior. See `RETIRED_SURFACES` in `segment.py` to restore them.

## Tree shrew layer anatomy — the thing that was got wrong

Read `references/reference-values.md` for the full published table with
provenance and the arithmetic cross-checks.

The short version, because it is easy to re-introduce this error: in tree shrew
the **GCL is a distinct dark band** about 10-12 µm thick, sitting between a
thick bright RNFL and a thick IPL. The first dark band below the RNFL is
therefore the GCL, **not the INL**.

An earlier version of the priors made exactly that mistake and stacked every
inner surface one landmark too shallow. The symptom was subtle: TOTAL thickness
still matched the published value, because the error was purely in how the
inner retina was subdivided. What gave it away was an "IS" layer 47 µm thick,
which is not anatomically possible.

Depths below the ILM, from stacking the published peripheral thicknesses, with
the landmarks measured independently in our own ILM-flattened profiles:

| Boundary | Published depth | Our measured landmark |
|---|---|---|
| RNFL/GCL (GCL dark band starts) | 59 µm | trough at 59.4 µm |
| INL dark band centre | 128 µm | trough at 125.4 µm |
| OPL bright band centre | 150 µm | peak at 146.7 µm |
| ONL dark band centre | 165 µm | trough at 166.9 µm |
| RPE complex | ~200 µm | peak at 197.1 µm |

If a change makes these stop agreeing, the change is wrong.

## Settings chosen by measurement — do not change casually

These are in `octa/segment.py`, `octa/volume.py` and `batch_segment.py`. Each
has a failure mode that only shows up in aggregate, so an experiment that
"looks fine on one B-scan" is not evidence.

- `bscan_avg = 3`. Larger reduces RNFL noise but biases it +3.4 µm and makes
  ONL/INL worse.
- `attract = 0.05`. Above ~0.4 slow-axis refinement degenerates into a median
  filter along the slow axis and **erases CNV lesions** — a lesion is precisely
  a localised departure from its neighbours.
- Anchors are the ILM and the RPE-complex peak, not Bruch's membrane. BM
  vanishes under large vessel shadows and is clipped at the bottom of the
  recorded range in some B-scans.
- `RELATIVE_PRIORS` comes from `octa/reference.py`, not from a fit to one scan.
- Search windows are tied to the distance to neighbouring priors
  (`NEIGHBOUR_FRAC`), not to a fixed fraction of the span. With twelve surfaces
  and layers as thin as the GCL, a fixed window lets two surfaces land on the
  same edge; `enforce_order` then stacks them 1 px apart and a zero-thickness
  layer is reported as a confident measurement.

## Traps specific to this data

**Orientation.** Always derive it with `detect_orientation(profile)`. The
`vitreous_at_high_index` field stored in older `.npz` samples was written by a
buggy version and is wrong for at least the first WT export. Canonical
orientation is vitreous at depth 0; files on disk are the other way round.

**Bulk reads only.** HDF5 chunks span the whole B-scan axis, so reading one
B-scan decompresses the same chunks as reading the entire volume. A per-B-scan
loop measured ~1,500× slower than one bulk read (78 min vs 13 s). This is why
`review_surfaces.py pack` exists.

**`surface_confidence` vs `local_confidence`.** `surface_confidence` compares
against the whole column and is routinely *negative* for every banded surface
including the ILM — correctly, since the choroid is a stronger dark→bright edge
than the RNFL. It is not a quality score. Use `local_confidence`.

**`BAD_COST`** in `octa/surfaces.py` is `+1e12`, a sentinel for "inadmissible"
in a minimisation. It was called `NEG_INF`, which inverts the meaning of every
comparison it appears in if taken at face value.

**Shadowed A-lines are NaN**, never interpolated, in thickness maps. A vessel
shadow means the evidence was absent and the map should say so.

**Central vs peripheral.** The paper measures at 500 µm (central) and 1,200 µm
(peripheral) from the ONH. Our field is ~1460 µm and the ONH is outside it in
many scans, so we usually cannot say which regime a scan is in.
`plausible_range()` therefore accepts the union of both. Do not pick one regime
unless the eccentricity is actually known.

**RNFL is measured differently by the paper.** The published 81.7 / 62.8 µm is
*axon bundle height*, measured at the bundles. Tree shrew RNFL is organised
into discrete vertically elongated bundles, so a per-A-line mean sits below
that and varies a lot laterally. A low mean RNFL is anatomy, not a failure —
`plausible_range` widens the RNFL lower bound for this reason.

## Refitting priors from human corrections

`review_surfaces.py refit` only pools **`corrected`-verdict files**, and only
the specific surfaces `surface_edited` marks as touched within them — never
`accepted` (nothing was drawn; it's the automatic output echoed back) and
never a surface a `corrected` file happened not to touch. Both are the same
"only trust what was actually drawn on" principle, applied at the file level
and the surface level. Getting either wrong is not hypothetical: the first
real batch of labels had 14 rushed `accepted` files diluting 10 genuine
corrections so thoroughly that `RNFL_GCL`'s measured delta from published went
from -0.068 (isolated correctly) to -0.001 (blended in) — invisible.

Having enough edits is not the same as the edits meaning anything, either.
`--min-edits` gates on *count*; it says nothing about whether what's being
corrected is a consistent offset or per-A-line noise a scalar prior can never
capture. Check both — `refit`'s own delta column is the count check; decompose
bias vs. residual (median-per-B-scan offset vs. what's left after removing it)
for the second. On 2026-08-27's 10 corrections, `RNFL_GCL`/`GCL_IPL` were
78-84% consistent offset; `IPL_INL`/`INL_OPL`/`OPL_ONL`/`ELM` were 19-33% —
mostly noise. Only the first two were applied.

Applying a refit to `RELATIVE_PRIORS` is a deliberate manual edit, not
automatic, and **verify it with the real pipeline before trusting it** — a
single-B-scan `segment_bscan()` comparison omits `bscan_avg` and slow-axis
refinement, which is not what a human actually corrected against. On the same
10 corrections, distance-to-ground-truth for `RNFL_GCL`/`GCL_IPL` dropped
~75-80% with the full pipeline (`octa/segment.py`'s comment on
`RELATIVE_PRIORS` has the numbers) — but applying *all six* of `refit`'s
reported surfaces, not just the two with a real signal, made the derived IPL
layer measurably worse against the paper (GCL_IPL moved, IPL_INL barely did,
so the gap between them widened). Check the layer built from any surface you
refit, not just the surface itself.

`refit` also reports the **measured cost of review**, split by verdict because
blending them has the identical contamination problem: accepted-B-scan time
cannot distinguish a real look from a reflex click. Quote the `corrected`
median, not a blend, and note the `n` it's based on.

## The intended next step: a learned boundary cost

Not a U-Net, at least not first. `build_costs()` → `SURFACE_COST` →
`banded_dp` already isolates the only hand-tuned part of the cascade — the
per-pixel cost images. Replacing those with a learned per-pixel boundary score,
while keeping the ordering constraints, neighbour-scaled windows, slow-axis
refinement and `local_confidence` untouched, trains on tens of labelled B-scans
rather than hundreds and stays interpretable.

Train only on surfaces marked `surface_edited`. Never on `surface_displaced`
ones (the ordering constraint moved those, not a human) and never on untouched
surfaces (that is the prior being fed back as evidence for itself). Validate
against held-out human labels, never against the classical output.

`sklearn` is **not** currently in the `octa` environment; it will need
installing before this starts.

## When adding a quality claim

Every new quality claim needs a measurement, not an impression. When a metric
looks too good, check for a confound first — the vessel-contamination scare
turned out to be shared spatial trend in both maps, not contamination.
