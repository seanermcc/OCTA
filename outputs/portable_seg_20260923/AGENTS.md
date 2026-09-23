# Project conventions — OCT-A tree shrew CNV pipeline

Read `README.md` for status and `PIPELINE.md` for how each stage works. This
file holds the things that are easy to get wrong and expensive to get wrong.

## Hard facts

- Input is `*_processedVolumes.mat` (MATLAB v7.3 = HDF5, read with `h5py`).
  **Never** attempt to reconstruct from `.RAW` — that is spectral OCT
  reconstruction and lives in the lab's MATLAB code, not here.
- h5py reports the volume as `(B-scan, A-line, depth)`. MATLAB wrote it as
  `[depth, A-line, B-scan]`. Do not transpose a 2 GB array; slice instead.
- **Canonical orientation is vitreous at depth 0.** Files on disk are the other
  way round. Always call `prepare_bscan(..., vitreous_at_high_index)` and derive
  that flag with `detect_orientation(profile)` — the `vitreous_at_high_index`
  field stored inside older `.npz` samples was written by a buggy version and is
  wrong for at least the first WT export.
- Axial 1.12 µm/px. Lateral ~1460 µm across 512 A-lines. The `X500um` in
  filenames is galvo drive amplitude, not retinal extent.
- Animal identity is the number only (`TS241`). Sex letters conflict between
  sessions for the same animal.
- Folder day labels are nominal. Use `days_post_laser` from the index when real
  laser dates are available.

## Layer anatomy — the error that is easy to re-introduce

In tree shrew the **GCL is a distinct dark band** (~10–12 µm) between a thick
bright RNFL and a thick IPL. The first dark band below the RNFL is the GCL,
**not the INL**. An earlier prior set assumed otherwise and stacked every inner
surface one landmark too shallow; TOTAL still matched, so it looked fine.
Layer thicknesses come from `code/octa/reference.py` (eNeuro 2024, tree shrew
only). See the `octa-layer-segmentation` skill.

## Settings that were chosen by measurement — don't change casually

- `bscan_avg = 3` — still shipped, but **re-measured on four scans 2026-08-28
  and the original justification did not reproduce.** Both controls improve
  with more averaging (TOTAL −15 to −18% from N=1 to N=7); both CNV scans get
  *worse* (+60%, +111%), and only in TOTAL — the ILM→BM span, where lesions
  live. The +3.4 µm RNFL bias appears on none of the four. Treat N=3 as a safe
  middle, not a measured optimum; N may belong per-scan rather than global.
  Re-derive before the full batch. See README "Segmentation settings".
- `refine_slow_axis(..., attract=0.05)` — **not higher.** Above ~0.4 it becomes a
  median filter and erases CNV lesions.
- Anchors are ILM and the RPE-complex peak. Not Bruch's membrane.
- `RELATIVE_PRIORS` comes from `reference.py`, not from a fit to one scan —
  **except `RNFL_GCL` and `GCL_IPL`**, refit from real hand corrections
  (2026-08-27) and verified to cut distance-to-ground-truth by ~75-80% with
  the real pipeline. Re-verified on 19 corrections (2026-08-28) and converged.
  See the comment above `RELATIVE_PRIORS` in `segment.py` before changing
  either of those two numbers again, and don't copy the same treatment to the
  other four surfaces `refit` reports — their corrections are mostly noise
  (measured).
- **Do not refit `IPL_INL`, however large `refit`'s delta for it looks.** That
  delta is a *relative position* and moves with where ILM and RPE land;
  measured directly, the automatic `IPL_INL` is already 0.7 µm from where
  humans drew it. Tested and rejected 2026-08-28. Two questions, again:
  "is the prior in the right place" is not "is the surface in the right place".
- **The IPL reading thick against the paper is not a bug to fix.** After the
  refit, RNFL reads 11-16 µm thinner and IPL 8-17 µm thicker than the
  published table — but RNFL + GCL + IPL is conserved to within ~3 µm, so the
  boundary moved, not the tissue. The paper's RNFL is axon *bundle height*,
  which a per-A-line surface reads ~27% lower. Which convention to report is
  Xiaorong's call, not a prior to tune.
- Inner-surface search windows scale with the distance to neighbouring priors,
  not with the ILM→RPE span. With closely packed surfaces and layers as thin as
  the GCL, a fixed window lets two surfaces land on the same edge and report a
  zero-thickness layer as a confident measurement.
- The cascade is **10 surfaces** (`CASCADE_VERSION` in `segment.py`). The IPL
  sublaminae were removed: prior-driven in every scan checked, never
  image-driven. `reference._STACK` still contains them — that is the published
  anatomy and is how the stack reaches the right depth for IPL/INL — so
  removing them changed no other prior.

## Two different questions about a surface

`local_confidence` says whether the **image** or the **prior** placed a surface;
`reference.plausible_range` says whether the answer is **anatomically sensible**.
A third question — could a human *see* the boundary at all — is answered only by
the per-surface "not visible" flag in `label_gui.py`. An invisible boundary has
no correct answer to learn, which is not the same as the automatic answer being
wrong, and neither is the same as it being right.
Plausible-but-unsupported is the dangerous combination — it is smooth, ordered,
sensible-looking, and carries no information. Run `code\qc_vs_reference.py`,
which reports both. Do not use `surface_confidence` as a quality score: it is a
whole-column comparison and is correctly negative for every banded surface,
the ILM included.

## Scan-quality metrics — do not revive `quality_confidence`

`outputs/quality_scores.csv` used whole-column `surface_confidence` and
`quality_scores_v2.csv` replaced it with `local_confidence`. The files contain
the same 314 scans, but their rankings agree only moderately (Pearson 0.237,
Spearman 0.550; bottom-15 overlap 5, top-15 overlap 2). V1 is not a quality
metric. V2 is a useful *segmentation-support* proxy, but it is not acquisition
quality and was computed from one unaveraged B-scan rather than the real volume
pipeline. Never use either as a good/bad scan label.

Independent acquisition QC lives in `code/scan_quality.py` and
`outputs/scan_quality_metrics.csv`: retinal/vitreous CNR and low-signal
coverage; raw adjacent-B-scan continuity and stripe power; and registered
same-session repeat agreement. Keep the axes separate until GUI review
calibrates them. Repeat disagreement is valid only when `repeat_comparable` is
true; scans may sample different retinal locations. Full definitions and the
v1/v2 comparison are in `outputs/QUALITY_METRICS_NOTE.md`.

## Conventions

- Nothing writes to `OCTA_RawData\` or `MATLAB Code\`. Outputs go to
  `octa\outputs\`.
- Human labels are ground truth and are written only by `label_gui.py`, via
  `octa/labels.py`. Never write a label file by hand or from a script, and
  never treat an un-edited surface in one as evidence — `surface_edited`,
  `surface_displaced`, `surface_visible` and `region_excluded` distinguish what
  a human actually drew, what the ordering constraint shoved, what nobody
  looked at, and what the image itself couldn't support for any surface.
- An `accepted` verdict is not automatically trustworthy: the per-B-scan timer
  cannot distinguish a genuine look from a reflex click. `review_surfaces.py
  refit` reports accepted/corrected time separately and warns when an accepted
  median looks too fast — read that warning before trusting accepted labels as
  ground truth.
- Shadowed A-lines are NaN in thickness maps, never interpolated.
- Every new quality claim needs a measurement, not an impression. When a metric
  looks too good, check for a confound first — the vessel-contamination scare
  turned out to be shared spatial trend in both maps.
- Report layers we cannot measure reliably as unreliable rather than dropping
  them silently. All layers matter to this project (per Xiaorong).

## Environment

```
conda activate octa      # python 3.11, h5py, numpy, scipy, scikit-image, matplotlib, pandas
```

`python code\check_env.py` diagnoses import problems. h5py failing to import on
Windows is usually a broken conda/pip mix, not a missing package.

**Activate the env — do not call `D:\Anaconda\envs\octa\python.exe` directly.**
Without activation `Library\bin` is off PATH, MKL fails to delay-load, and
`numpy.dot` plus all of matplotlib crash the interpreter with exit code
`0xC06D007F` and no Python traceback. It looks like a corrupted install; it is
a missing activation.
