# Stage A eligibility audit — 2026-09-08

The completed first-round queue contains **160 decisions in 32 volumes across 11 animals: 101 corrected and 59 rejected**. All decisions were readable and matched the standard queue. There are no missing decisions. The source index still contains 314 processed acquisitions.

After the conservative Stage A policy, **89 B-scans in 23 volumes across nine animals contain eligible evidence**, totaling **172,308 boundary-column targets**. These are correlated positions, not 172,308 independent examples or verified locally drawn strokes.

## Eligibility and provenance policy

Only corrected decisions contribute supervision. A surface must have explicit edited, visible and reliable flags, with no displacement flag. A column must be inside the reviewed image and outside human exclusions, the frozen classical shadow mask, and the Stage A CNV exclusion. Missing flags are errors rather than permissive defaults. Accepted and rejected decisions supply no boundary or region targets.

The exclusion around a positive reviewed footprint is **250 µm**, measured in the native two-dimensional en-face grid using the footprint's B-scan and A-line spacing. A column is eligible only when its pixel-center distance to the nearest positive footprint pixel is **strictly greater than 250 µm**. The saved signed distance is negative inside a footprint. This discretized, Euclidean convention is a provisional conservative candidate from the staged specification; it is not evidence that remote tissue has no biological CNV effects. Sensitivity experiments belong in development data and require a new dataset version. For empty or unavailable footprints the distance array is NaN and the explicit scope status determines eligibility.

The active anatomy remains `5-8surf-pr`: ILM, RNFL_GCL, GCL_IPL, IPL_INL, INL_OPL, OPL_ONL, PR_RPE and RPE. PR_RPE retains the existing RPE-complex peak convention. RPE retains the outer endpoint convention. The seven closed bands and TOTAL are all retained; PHOTORECEPTOR is a composite band. No endpoint was reinterpreted as anatomical BM, and no retired boundary was restored.

**Legacy limitation:** edited/visible/reliable/displaced are surface-wide flags. An edited surface is eligible under this documented legacy policy across its remaining usable columns, but this does not establish local drawing or inspection history. No stroke footprint was inferred from label-minus-auto differences. The GUI source shows that later ordering can mark previously edited surfaces as displaced, and that the active surface clears its displacement flag; local effects within that active stroke cannot be reconstructed. Every displacement-flagged surface is excluded conservatively. A future local-provenance audit could further narrow this pool.

The provenance audit inspected the label serializer and stroke/order update logic and verified all 160 review images against newly prepared source pixels. The saved decisions have no `surface_visible=False` flags at all. This dataset therefore supplies no credible local visibility-negative training set, and no local visibility head is trained. The aggregate exclusion flags mark 36,352 boundary-column positions as displaced and 10,240 as unreliable; flags overlap and must not be summed as unique exclusions.

Seventeen corrected records had otherwise-eligible saved rows outside the displayed review image. The 628 affected boundary-column targets receive an explicit `outside_review_image` reason. A wider input cannot establish what was visible to the reviewer outside that image, so those targets stay excluded. The full native-depth cache avoids any additional training crop losses.

Regions require two eligible adjacent endpoints and nonnegative separation. No open-ended vitreous or sub-RPE region is supervised. Rejected images remain in decision/coverage manifests; a rejection is not interpreted as eight invisible boundaries. ONH-edge annotations remain open traces, not exclusion-area masks.

## Biological scope

The 32 volumes have **28 reviewed footprints: 19 positive, nine empty**, with four missing. Missing/unreviewed footprints do not establish negativity. Nominal D0 and review-selection `is_control` flags do not establish pre-laser status. Explicit `before laser` metadata and the documented TS165 WT acquisition establish control status. Exact `days_post_laser` is retained when available; positive nominal CNV dates establish post-laser context only, not an exact elapsed interval.

| Eligible scope | B-scans with some evidence |
|---|---:|
| WT or explicit pre-laser, reviewed negative footprint | 5 |
| Reviewed footprint-negative post-laser tissue | 16 |
| Remote tissue in positive scans, beyond 250 µm | 66 |
| Reviewed footprint-negative, timing unknown | 2 |

The two timing-unknown negative examples remain distinguishable from healthy controls. Post-laser footprint negativity likewise does not prove healthy tissue. The four unavailable footprints are listed in `integrity_and_environment.json`; their corrected records supply no Stage A targets unless independent control metadata establishes eligibility. None was silently reclassified from its review role or nominal day.

## Coverage and partitions

| Animal | Corrected | Eligible B-scans | Partition |
|---|---:|---:|---|
| TS165 | 3 | 3 | train |
| TS169 | 3 | 3 | validation |
| TS241 | 7 | 7 | train |
| TS247 | 26 | 23 | locked test |
| TS250 | 4 | 4 | train |
| TS267 | 37 | 31 | train |
| TS283 | 7 | 4 | locked test |
| TS305 | 3 | 3 | train |
| TS325 | 11 | 11 | validation |
| TS328 | 0 | 0 | locked test, rejection evidence only |
| TS336 | 0 | 0 | validation, rejection evidence only |

| Surface | Eligible boundary-column targets |
|---|---:|
| ILM | 15,860 |
| RNFL_GCL | 24,736 |
| GCL_IPL | 22,615 |
| IPL_INL | 22,375 |
| INL_OPL | 21,592 |
| OPL_ONL | 21,487 |
| PR_RPE | 22,166 |
| RPE | 21,477 |

There are 39 eligible B-scans in the existing low acquisition-QC selection group, 25 medium and 25 high. `coverage_by_animal_surface_qc.csv` reports the full animal × surface × QC × biological/scope breakdown, including zero-evidence entries. `animal_coverage.csv` supplies a compact animal-by-surface table. The historical QC groups are descriptive review strata, not calibrated good/bad labels. The manifest preserves independent CNR, low-signal, continuity, stripe and repeat axes separately; repeat disagreement is interpretable only with `repeat_comparable`. The retired whole-column quality-confidence metric is never used for inclusion, weighting or evaluation.

The coverage-only split was frozen before fitting: **48 train, 14 validation and 27 test eligible B-scans**. Every surface has evidence in each split. All eyes, sessions, dates, repeats and neighboring B-scans inherit the animal's partition. Future blind repeatability pairs must map back to the original animal; no repeatability directory or pair data was read here.

The five training animals include TS165, the only WT animal, and TS267, the largest contributor. Validation uses high-QC negative tissue from TS169 and low/medium-QC tissue from TS325. Test reserves broad QC coverage from TS247 plus TS283, and rejected-only TS328. Only two animals in each held-out partition have corrected evidence. TS247 and TS267 contribute 54 of the 89 eligible B-scans; animal-balanced training sampling and animal-macro reporting prevent image count alone from setting the headline result. There is **no independent WT generalization estimate** in this design.

## Frozen artifacts and geometry

`manifest.json` contains joined source metadata and independent QC, explicit reason counts, source/label/pack/footprint fingerprints, and pointers to versioned target and scope arrays. The per-column `reason_bits` arrays preserve overlapping exclusion reasons. `partitions.json` freezes animal assignments and coverage; loaders validate dataset and partition identities.

`historical_cohort.json` separately freezes the original **53-B-scan benchmark**, identified by the historical baseline error table, and preserves its historical score rows verbatim. It records current September 8 label hashes separately. September 2 label hashes were not captured, so historical label revisions cannot retrospectively be certified. The completed 101-correction cohort is not required to reproduce that historical summary. No historical test-animal predictions were recomputed for debugging.

All 160 decisions now have new N=1, single-channel, full-native-depth caches. Orientation was redetected from each freshly read source volume profile. For every B-scan, the corresponding canonical crop matched its review-pack image exactly. Eligible targets are contained in the native image. Training/inference use the same dB conversion, full-image percentile normalization, and clipping; no flattening, spatial resampling or additional crop is used. The canonical label offset and disk-depth inverse are explicit.

Human labels, packs and footprint files have full SHA-256 fingerprints. Large source MAT files use size/mtime plus three sampled 1 MiB blocks, explicitly **not a full-file content hash**; every consumed native B-scan array and generated cache has a full content hash. Cache identity includes source, label, geometry, orientation and preprocessing. Existing old caches were preserved. Final integrity checks verified all 160 labels, 32 packs and 28 footprints unchanged.

The `octa-layer-segmentation` skill informed supervision, shadow handling, orientation and anatomy safeguards. The user's current eight-boundary U-Net and N=1 instructions take precedence over historical ten-surface/learned-cost/N=3 advice in that skill and older documents.
