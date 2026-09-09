# How the pipeline works, stage by stage

Each stage below says **what** it does, **how** it does it, and **why that way** —
the "why" matters most, because several of these choices were made after a
simpler approach failed on this specific dataset.

Conventions that hold everywhere:

| | |
|---|---|
| Canonical orientation | depth index 0 = vitreous, increasing into tissue |
| As stored on disk | the opposite — the acquisition pipeline saves vitreous at HIGH index |
| Axial scale | 1.12 µm per pixel in tissue (1550 µm / 1.35 over 1024 px) |
| Lateral scale | ~1460 µm across 512 A-lines (~2.85 µm/A-line) |
| Volume in `.mat` | MATLAB `[depth, A-line, B-scan]`; h5py reports it reversed as `(B-scan, A-line, depth)` |

---

## Stage 1 — Inventory (`index_scans.py`)

**What.** One CSV row per acquisition, keyed by (animal, eye, day), recording
which products exist and flagging anything ambiguous.

**How.** Walks `OCTA_RawData` recursively to depth 3, collecting `.RAW` files and
`*_Processed` directories, then parses the names.

Naming is three years of drift, so the parser is deliberately forgiving in
matching and strict in reporting:

- `T241F`, `TS241`, `TS241F` → all canonicalise to **TS241**. Identity is the
  number alone, because sex letters conflict between sessions for the same
  animal (TS305 appears as both `TS305M` and `TS305F`).
- `-R1`, `-R01`, and `R1` with no separator → eye OD, scan 1.
- Session folders naming two animals (`26.03.03 TS250 CNVD7 TS325 CNV D98`) are
  split by finding every animal token and reading the timepoint fragment that
  follows it.
- `6mo` → day 180, `LASER DAY` and `before laser` → day 0.
- `TS36` is aliased to TS336 — the RAW files inside that folder say `TS336M`.

**Why recursion matters.** 103 of 330 acquisitions live one or two levels down
in hand-made folders (`analysis\`, `New folder\`, `Reanalysis\`, `TS328 re\`).
An earlier top-level-only version silently missed all of them and reported 229
acquisitions instead of 330.

**Timepoints.** Folder day labels are *nominal*. Given real laser dates via
`--laser-dates`, the index adds an exact `days_post_laser` computed from session
dates, plus the drift. TS267's labels are near-exact; TS325's "D119" is really
+160 days.

---

## Stage 2 — Extract a working subset (`export_sample.py`)

**What.** Pulls a manageable slice out of one 4 GiB `processedVolumes.mat`.

**How.** Opens the v7.3 `.mat` with `h5py` (v7.3 *is* HDF5) and slices lazily, so
a single B-scan costs 4 MB rather than loading 2 GB. Finds the retina band
automatically and crops depth to it.

Two modes:
- default — 32 consecutive B-scans plus 24 spread across the volume (~85 MB)
- `--slab` — **every** B-scan at half the A-line sampling (~190 MB)

**Why `--slab` exists.** Anything that varies along the slow axis — B-scan
averaging, 3D regularisation — cannot be studied on 32 consecutive B-scans,
which span only 91 µm. Real retinal structure varies over hundreds of µm. The
first averaging sweep was run on the 32-scan block and its conclusions were not
trustworthy for that reason.

**Retina-band detection.** Threshold the mean depth profile relative to the span
between its 10th and 99.5th percentiles, close gaps shorter than 90 px, take the
longest run, pad. The gap-closing is essential: in tree shrew vis-OCT the ONL is
dark enough to fall below any threshold that also excludes the vitreous, which
splits the tissue band in two, and a naive "longest run" then returns only the
inner retina.

**Orientation detection.** Decided by which side of the tissue carries the
*longer* low-intensity run — not by comparing mean intensity either side. The
first few depth pixels sit at the zero-delay edge and are darker than the
vitreous, so a mean comparison is decided by an 8-pixel sliver and returns the
wrong answer. (It did, for the first WT export.)

---

## Stage 3 — Surface finding (`octa/surfaces.py`)

**What.** Given a cost image `[depth, A-line]`, find the single depth per A-line
that minimises total cost, subject to a limit on how far the surface may move
between neighbouring A-lines.

**How.** Dynamic programming across A-lines. `dp_surface(cost, max_step, lo, hi)`.
A confidence value per A-line records how much better the chosen depth was than
the best alternative outside a margin — near zero means the smoothness prior
decided it, not the image.

**Why the bounds are soft.** `lo`/`hi` are enforced as a steep linear penalty,
not a hard mask. A hard mask can make the problem *infeasible*: if the band
shifts by more than `max_step` between adjacent A-lines — which happens wherever
a vessel shadow disturbs the initial guess — no admissible path exists, every
candidate accumulates the same saturating penalty, and the traceback returns
noise pinned to row 0. That failure was silent and produced plausible-looking
garbage.

**Cost images.** Gradient costs favour a dark→bright or bright→dark transition;
intensity costs favour bright or dark pixels. Smoothing is edge-replicated, not
zero-padded — zero padding darkens the first and last rows, manufactures a huge
boundary gradient, and the DP snaps every surface onto row 0.

---

## Stage 4 — The layer cascade (`octa/segment.py`)

**What.** Ten surfaces per B-scan: ILM, RNFL/GCL, GCL/IPL, IPL/INL, INL/OPL,
OPL/ONL, ELM, IS/OS, RPE, BM. `CASCADE_VERSION` in `octa/segment.py` records
this set; every output carries it.

GCL/IPL was added once the layer labels were pinned to published tree shrew
values (`octa/reference.py`) — in this species the GCL is a distinct dark band,
and failing to separate it from the IPL was the bug that put every inner
surface one landmark too shallow.

**The two IPL sublamina boundaries (IPL S1/S2, IPL S2/S3) have been removed.**
They are real anatomy and the paper resolves them, but not in our data: across
all 15 scans checked they landed in `mixed` support every single time and never
in `image`, averaging 40–42% prior-driven A-lines — the two least-supported
boundaries in the cascade. The paper resolves them on speckle-reduced
SR-B-scans, which we do not have. What they produced was smooth, correctly
ordered, anatomically sensible surfaces carrying no information: the
plausible-but-unsupported case this project has been burned by before.

Removing them moves no other prior. `reference._STACK` still contains
S1 + S2 + S3, which is how the stack arrives at the correct depth for IPL/INL,
so the remaining priors are bit-identical to what they were with twelve
surfaces (verified). It does widen one search window — IPL/INL's nearest prior
neighbours are now GCL/IPL and INL/OPL rather than the two sublaminae, so its
half-width roughly doubles, to just under the `MAX_HALFWIDTH_FRAC` cap. On the
TS165 WT slab that let IPL/INL settle 1 px shallower and **nearly doubled its
`local_confidence`, 0.99 → 1.79** — it locks onto a real edge once it is not
boxed in. The cost is on the other axis: IPL 40.3 → 37.0 µm and INL 33.6 → 37.0
against the paper's 45.7 and 34.0. Supported went up, plausible went down. That
is a question for human labelling to settle, not for another prior.

To restore them: add the names back to `SURFACE_NAMES` and `INNER_SURFACES` and
restore their `SURFACE_COST` entries. The priors are already there.

**How.** Strongest features first, each one bounding the next:

1. **ILM** — first dark→bright transition, searched in a band around the coarse
   tissue leading edge.
2. **RPE-complex peak** — the brightest thing below the inner retina. A ~10 dB
   bump, the largest feature in any A-line.
3. **Vessel shadows** — A-lines whose ILM→RPE energy is a robust-z outlier.
   The RPE anchor is interpolated across them before anything else uses it.
4. **BM** — first strong bright→dark below the RPE peak.
5. **IS/OS** — dark→bright rise just inner to the RPE peak.
6. **Inner surfaces** — each in a window around a prior placed at a *published*
   fraction of the ILM→RPE distance. The window half-width is 40% of the
   distance to the nearer neighbouring prior, not a fixed ±7% of the span:
   with closely packed surfaces and layers as thin as the GCL (~9 px), a fixed
   window overlaps its neighbours and two surfaces can land on the same edge.
   `enforce_order` then stacks them 1 px apart, and a zero-thickness layer gets
   reported as a confident measurement.
7. **Ordering enforced** — cumulative maximum from the vitreous side.

**Why the priors are published rather than fitted.** They used to come from
landmarks fitted to one wild-type scan with the anatomy unconfirmed, and the
labelling was wrong: the first dark band below the RNFL is the GCL in tree
shrew, not the INL. Every inner surface was one landmark too shallow. TOTAL
still matched, because the error was purely in how the inner retina was
subdivided — which is exactly why it survived so long.

**Why anchor on the RPE peak rather than Bruch's.** BM was the first choice and
it failed: it vanishes entirely under large vessel shadows, and in some B-scans
it sits at the very bottom of the recorded depth range where the choroid is
clipped.

**Why a cascade rather than one joint optimisation.** The outer surfaces carry
far more contrast than the inner ones. Finding them first turns the weak inner
problem into a well-conditioned one and makes surface crossing impossible — the
failure mode that makes the existing `layers_refined_auto.mat` unusable.

---

## Stage 5 — 3D regularisation (`octa/volume.py`)

**What.** Makes surfaces consistent *between* B-scans, not just within one.

**How.** Two separate mechanisms:

**B-scan averaging** (`bscan_avg=3`) raises SNR before surfaces are found.
Averaging happens in dB, which is correct here: speckle is multiplicative in
linear amplitude, therefore additive in dB, so a plain mean is the right
estimator. Even window widths are taken one slice further back than forward —
using `n//2` on each side silently makes width 4 identical to width 5.

**Slow-axis refinement** (`attract=0.05`) smooths each surface map along the
B-scan axis to form a prior, then re-finds every surface under a soft linear
pull toward it. Surfaces are re-found from the vitreous inward, each bounded by
the one already refined above it.

**Why soft, not a window.** The first version used a hard ±6 px window and made
RNFL *worse* — inside a narrow window the search flips between two nearly equal
minima from slice to slice, adding jitter instead of removing it. A linear pull
leaves one optimum that moves smoothly. Switching improved every layer at once
(TOTAL 5.48 → 3.33 µm jitter, RNFL 2.56 → 1.99).

**Why the weight is 0.05 and not higher.** Above ~0.4 the image stops overriding
the prior entirely and this degenerates into a median filter along the slow
axis — which looks excellent on a healthy retina and **erases a CNV lesion**,
since a lesion is precisely a localised departure from its neighbours. At 0.05
the image still overrules the prior in ~8% of A-lines.

---

## Stage 6 — Thickness maps

**What.** Eight layer thicknesses as en-face images, `[B-scan, A-line]`, in µm.

**How.** Differences between consecutive surfaces × 1.12 µm. Shadowed A-lines
are set to **NaN, not interpolated** — a vessel shadow means the evidence was
absent, and the map should say so rather than invent a plausible number.

**The vessel negative control.** A retinal vessel is not a layer-thickness
feature, so thickness should be uncorrelated with vessel attenuation. Testing
this requires removing shared large-scale spatial trend from *both* maps first:
retinal thickness and vessel calibre both vary smoothly across the field, and
the raw correlation (≈ −0.5) is dominated by that shared structure rather than by
any contamination. Detrended, every layer comes in at |r| ≤ 0.08.

---

## Stage 7 — Independent scan quality (`scan_quality.py`)

**What.** Three acquisition-quality axes for every processed scan, deliberately
separate from segmentation confidence: retinal signal/contrast, raw slow-axis
continuity, and registered agreement with same-session repeats.

**How.** The script reads the previously detected retinal band plus a vitreous
noise window. Signal is retinal P75 minus vitreous median, with a robust CNR
and low-signal coverage. Continuity uses adjacent structural-en-face B-scan
correlation, discontinuity P95, and high-frequency stripe power. Repeat
agreement translation-registers compact structural fingerprints within
(animal, eye, session-date) groups.

**Why separate axes.** Signal loss, motion, and poor repeatability are different
failure modes and need not move together. No combined score or threshold is
claimed before comparison with human scan-level labels. Repeat disagreement is
only valid when `repeat_comparable=True`; same-session acquisitions can sample
different retinal locations, and non-overlap is not poor quality. Definitions
and the retired v1/v2 `quality_confidence` history are in
`outputs/QUALITY_METRICS_NOTE.md`.

---

## Stage 8 — Human review (`review_surfaces.py`, `label_gui.py`)

**What.** Turn the automatic output into ground truth for the B-scans where it
cannot be trusted, and measure how much that costs.

```
pack  ->  correct in the GUI  ->  refit
```

**`review_surfaces.py pack`** does one bulk read per scan and keeps only the
B-scans worth a human's time, ranked on four things that do not substitute for
one another: unsupported surfaces (`local_confidence` below floor), implausible
layer thicknesses, shadow fraction, and disagreement with neighbouring B-scans
along the slow axis.

The four are combined **by rank within the scan**, not by adding the raw
numbers. Added raw they barely discriminated — the first pack built that way
spread 0.63 to 0.83 across its ten picks, controls included, which is far too
narrow to claim the worst were meaningfully worse. Each component saturates in
its own range, so the sum was dominated by whichever had the widest spread.
Ranked, the same scan spreads 0.15 to 0.94.

Picks are also forced at least `--min-sep` B-scans apart. The score varies
smoothly along the slow axis, so without that the eight "worst" B-scans came
out as a contiguous run (392–415 on TS241 D0) — eight times the labelling cost
for almost the same information. A few median-ranked **controls** are packed
too, and are not optional: a correction set drawn only from failures teaches a
refit that the retina looks like its own worst cases.

**`label_gui.py`** is a PySide6 window. Freehand-drag redraws the active
surface; the correction is spliced in exactly where it was drawn and its
*offset* is faded to zero over `taper` A-lines beyond the ends, so it joins the
untouched automatic surface smoothly instead of leaving two discontinuities no
DP surface could produce. A-lines the image did not support are painted in
warning colour on the active surface — that is the part worth attention.

Three things it records that the old matplotlib editor did not:

- **Whether a surface was visible at all.** Marking a boundary *not visible* is
  not the same as correcting it, and neither is the same as accepting it. An
  invisible boundary has no correct answer to learn. This is the measurement
  that should have settled the IPL-sublaminae question.
- **Edited vs displaced.** Correcting one surface can shove another, because
  ordering only ever pushes deeper surfaces out. A shoved surface differs from
  the automatic result without anyone having drawn it, and training on it would
  be training on a side effect. The two are recorded separately.
- **Time on task**, banked only while the window has focus. Nobody yet knows
  whether a B-scan takes 30 s or 5 min, and that number decides whether a
  learned model is reachable at all.

**`review_surfaces.py refit`** re-estimates the relative-depth priors, and
trusts a surface only if a human *actually drew on it* at least `--min-edits`
times — not merely reviewed it. `refit` pools only `corrected`-verdict files,
and even within one, only the surfaces that file's `surface_edited` marks as
touched. An `accepted` verdict is deliberately excluded from this, not merely
down-weighted: the per-B-scan timer cannot tell a genuine look from a reflex
click, and the first real batch of labels had 14 accepted files at a median 0s
review time diluting 10 genuine corrections into invisibility (`RNFL_GCL`'s
delta from published measured as -0.001 blended, -0.068 once isolated). Read
the accepted/corrected time split `refit` prints, not just its top-line
numbers.

`refit_all` and `refit_trusted` are reported separately because *count* of
edits isn't the whole story either — a surface can be corrected often and
still not be systematically mislocated, if what's being corrected is per-B-scan
noise rather than a consistent offset. `RNFL_GCL` and `GCL_IPL` (2026-08-27,
10 corrections) had 78-84% of their correction as a consistent offset;
`IPL_INL`/`INL_OPL`/`OPL_ONL`/`ELM` had only 19-33%. Applying a refit to
`RELATIVE_PRIORS` is a deliberate manual edit, and "enough edits to trust a
number" and "the number is mostly signal, not noise" are different checks —
`refit`'s `--min-edits` gate is only the first of the two.

---

## Stage A — learned inner-retina experiments and manual review

The current implementation and measurements are in
[`outputs/stage_a/20260909_inner_retina_tier1/RUN_REPORT.md`](outputs/stage_a/20260909_inner_retina_tier1/RUN_REPORT.md).
Only manually edited, visible, reliable, non-displaced boundaries supply
segmentation ground truth. Published thickness tables are not ground truth.
The frozen legacy labels identify edited surfaces but do not locate individual
strokes; the report preserves that limitation.

`stage_a_inner_retina.py` and `stage_a_compare.py --scope inner-retina` report
ILM, RNFL_GCL, GCL_IPL, IPL_INL and RNFL/GCL/IPL/INNER_RETINA. The delivered
eight-head model is retained after the equal-budget four-head experiment.
All experiments leave the locked final-test animals untouched.

`stage_a_decoder.py` compares the original expected-depth estimator, independent
smooth paths followed by minimum-gap isotonic projection, and a joint PyMaxflow
minimum cut. Gap bounds come from training animals' manually supported adjacent
surfaces. Both constrained methods eliminate crossings and reduce large errors,
with small median tradeoffs in individual animal/sensitivity rows. The cheap
ordered-path method is an experimental review aid; neither constrained method
passes the strict no-regression criterion. The original scientific baseline is
preserved. These modules are outside `stage_a/` to preserve checkpoint resume
identity.

`stage_a_inner_cv.py` trains animal-disjoint models with separate training,
calibration, and evaluation roles. `stage_a_inner_calibrate.py` measures
transferred entropy thresholds with per-animal coverage/error curves. These are
development cross-validation results, not final-test or deployment guarantees.

`stage_a_inner_queue.py` runs full-volume inference and ranks B-scans using
withheld fraction and a longest flagged-run proxy. Gross error itself is
unknowable without manual reference. The queue reuses the existing eight-surface
pack writer and excludes previously reviewed B-scans. It writes packs, never
labels. Shadowed and withheld thicknesses remain NaN; outer quantities outside
the inner-retina experiment are explicitly unreliable. Acquisition QC remains
separate from this review priority.

## Not yet built

**ONH, eccentricity, area centralis.** Needs montaging — the ONH is outside the
~1460 µm field in many scans.

**Lesion detection.** A CNV lesion is local RPE elevation with outer-retinal
disruption, which should be a distinctive signature in a thickness map.

**Classical learned boundary cost.** An unimplemented alternative to Stage A.
`build_costs()` → `SURFACE_COST` → `banded_dp` already isolates the one
part of the cascade that is hand-tuned: the per-pixel cost images. Replacing
those with a learned per-pixel boundary score, while keeping the ordering
constraints, neighbour-scaled search windows, slow-axis refinement and
`local_confidence` exactly as they are, is data-efficient enough to train on
tens of labelled B-scans rather than hundreds, and stays interpretable.

Gated on Stage 8 producing labels and, more importantly, on the measured cost
per B-scan that Stage 8 records. Validate against held-out **human** labels,
never against the classical output, and only on surfaces marked `edited` —
never on `displaced` ones or on surfaces nobody touched.
