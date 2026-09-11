# Metric dictionary — frozen octa-seg_v1 batch

These are descriptive metrics for preliminary review. No thresholds are fitted, no composite quality score is calculated, and no scan is excluded for a low metric. All CSVs use UTF-8. Blank numeric cells mean unavailable, not zero.

## Coordinates and units

Source HDF5 arrays are B-scan × A-line × depth. Every native B-scan and A-line is retained. The expected grid is 512 × 512 × 1024. Raw model positions, reported positions and contextual estimates are **full canonical depth pixels**, with vitreous at depth zero. Images are canonical depth crops. Subtract `label_offset` for a plotted crop coordinate; for reversed disk orientation the offset is `1024-retina_hi`. Axial conversion is 1.12 µm/px. Lateral sampling is approximately 1460/512 µm. No spatial resampling, inter-acquisition registration or longitudinal registration is applied to model outputs. Native single-B-scan preprocessing is the frozen neural model's policy; the three-B-scan average is used only for the existing shadow stage.

## Denominators and field conventions

- `native_n`: all B-scan/A-line locations (262,144 per boundary or layer). Scan-level model fractions additionally average all eight boundaries.
- `excluded_n`: union of frozen image-exclusion/rejected-row reasons and current explicit human image exclusions/rejected rows. Boundary invisibility is not itself a whole-image exclusion.
- Boundary `eligible_n`: native grid minus image exclusions. Layer `eligible_n`: additionally excludes the automatic shadow mask. Endpoint denials and unreliability cause missing measurements, not a smaller spatial denominator.
- `finite_native_n` counts all finite values on the native grid; `finite_eligible_n` counts finite values inside the stated mask. `coverage_native_pct=100*finite_native_n/native_n`; `coverage_eligible_pct=100*finite_eligible_n/eligible_n`. Zero denominator produces a blank percentage.
- Statistics always use **eligible finite** values unless a `native` prefix explicitly requests all native finite values. `n` is the number actually summarized, not the denominator before missingness. Missing values are never filled, smoothed or interpolated for statistics.
- `mean`, `median`, `sd`, `iqr`, `mad`, `p01`, `p05`, `p25`, `p75`, `p95`, `p99`, `max` are arithmetic mean, median, population standard deviation (ddof=0), P75−P25, unscaled median absolute deviation from the median, named percentiles, and maximum. Percentiles use NumPy's default linear interpolation. All are blank when n=0. SD=0 for one sample. More variation is neither automatically worse quality nor measurement uncertainty.
- `aline_abs_jump_*`: absolute difference between immediately adjacent native A-lines, summarized only when both endpoints are eligible and finite. `bscan_abs_jump_*` similarly uses adjacent native B-scans at the same A-line, without registration or bridging gaps. `*_eligible_adjacent_pairs` counts pairs eligible before checking finiteness; `*_abs_jump_n` counts finite eligible pairs. Jumps are in µm for positions and thickness. Large values indicate greater local irregularity, possibly anatomy, pathology, motion or model error.
- `raw_um_*`, `reported_um_*`, `context_um_*` apply these coverage/distribution/jump definitions to the separate raw, reported and contextual positions. Depth position distributions are not layer thickness or quality scores.
- `segmentation_*`, `preliminary_*`, `preliminary_include_unreliable_*` apply the same definitions to layer measurements under their separately named policies.

## Boundary assessment, support and geometry

`native_reported_pct`, `native_uncertain_pct`, `native_not_traceable_pct` count model states 1, 3 and 2 over the complete native grid. `eligible_*` uses the non-excluded grid. These three percentages sum to 100 for nonempty denominators. They are model assessments after the existing human guards, **not confirmed human visibility or calibrated correctness probabilities**. Reported-position finite coverage is independently measured. A contextual estimate is stored only for state 3, separately from reported positions.

`model_traceability_native_*` and `model_reliability_native_*` summarize the two model sigmoid outputs over all native finite values. `*_eligible_*` uses the non-excluded mask. Units are dimensionless [0,1]. Larger indicates greater model-assessed evidence; probability of correct position is not calibrated. `entropy_native_*` / `entropy_eligible_*` summarize positional-distribution entropy divided by log(native depth), dimensionless; larger indicates a broader model distribution, not validated positional error.

For each of `raw_`, `reported_`, and `context_`, and each `native_` / `eligible_` scope:

- `finite_n`: finite positions in scope.
- `out_of_crop_n/pct`: finite positions below crop offset or above offset+crop-height−1; percent denominator is finite positions. Full-depth raw positions outside the review crop are counted even when valid in the original depth range.
- `crossing_n`: locations where this boundary crosses or equals **any** other finite boundary in anatomical order, including a nonadjacent boundary across missing ones. A location is counted once per affected boundary, regardless of how many pairwise crossings it contains.
- `crossing_comparable_n`: finite locations with at least one other finite boundary. `crossing_pct` divides crossing_n by this count. Isolated context values without a second finite contextual boundary are not crossing-testable.
- `invalid_geometry_n`: union of nonfinite, out-of-crop and crossing locations. This is a descriptive union, not an additional masking rule. Nonfinite positions are reported separately by the coverage fields; do not interpret withholding as a geometric error.

`human_visibility_yes_n/no_n/unknown_n` and analogous reliability fields come from explicit saved annotation states through the existing provenance adapter. They are native counts, never inferred from model state or generic acceptance. Their sum equals the native grid. Legacy whole-boundary judgments can apply to an entire B-scan; `human_judgments.csv` records whether local provenance exists. Labels are read only and fingerprinted. Neither edits nor acceptance are imported as scan-quality ratings.

`reason_<code>_native_n` counts the unchanged v1 operational reasons: 1 learned evidence passed (experimental), 2 learned not-traceable, 3 below evidence thresholds, 4 vessel-derived unreliable default, 5 explicit human not-traceable, 6 explicit human unreliable, 7 excluded image, 8 rejected B-scan, 9 insufficient boundary calibration support, 10 nonfinite/outside-full-image/adjacent crossing, 11 positive human state plus passed image check. Counts describe missingness mechanisms; code 4 is often based on an unreviewed automatic proposal.

## Thickness policies and limitations

`segmentation_policy`: unchanged `octa-seg_v1` reported endpoints only. Adjacent/composite endpoint difference ×1.12; negative differences and automatic shadow columns are NaN. The original policy permits zero differences; no new rule is imposed. These maps are in `primary_thickness_um` with B-scan × layer × A-line axes.

`preliminary_policy`: the actual octa-thick engine constant `pilot-use-available-exclude-explicit-unreliable-v2`. The **v2 in this existing policy name is not octa-seg_v2**. Its default mode uses available saved model/context/human positions, rejects frozen not-traceable/image exclusions and all pairwise crossings, requires positive thickness, excludes shadows and explicit human unreliability, and preserves established correction precedence. The optional `include_unreliable` mode is exported separately and is not the default. `preliminary_explicit_unreliable_n` counts finite optional-mode measurements touching an explicitly unreliable endpoint. Default and optional policies use the same layer definition and spatial eligibility denominator. Missingness can arise from denied, nonfinite, out-of-crop, crossing or explicitly unreliable endpoints and shadows; native endpoint reason/source arrays are preserved in the thickness exports for exact point-level inspection.

RNFL, GCL, IPL, INL, OPL, photoreceptor composite, RPE band and total are available layer definitions; reported coverage may be zero. `INNER_RETINA` is a v1 segmentation composite not present in the existing viewer, and its viewer statistics are explicitly unavailable. Isolated ONL, ELM, IS, OS, BM and IPL sublaminae are not separately resolved. ELM/BM entries flag unavailable independent landmarks, not inferred layer thicknesses. No published anatomy is substituted for missing measurements.

Layer missingness counts are deliberately nonexclusive: `shadow_native_n` and `image_excluded_native_n` are native spatial counts; `segmentation_missing_top_eligible_n` / `segmentation_missing_bottom_eligible_n` count missing reported endpoints on the non-shadow, non-excluded grid; `segmentation_negative_delta_eligible_n` counts negative finite endpoint differences there. Analogous `preliminary_missing_*_eligible_n` counts missing endpoints after the existing engine's policy. A sample with both endpoints missing appears in both counts; do not add these as a partition.

## Independent acquisition QC

Calculated by the existing `scan_quality.measure_one` workflow, using raw volume intensity, not model positions. The runner supplies its already-read raw volume through an in-memory I/O adapter. The crop/band matches the longitudinal preparation policy. All acquisition fields are over the native grid; boundary and layer eligibility masks do not retrospectively alter the acquisition measurements.

| Fields | Definition and units | Direction and limitation |
|---|---|---|
| `retina_lo`, `retina_hi`, `noise_window_side` | Disk depth crop [lo,hi), and side of vitreous window | Geometry metadata, not scores |
| `noise_floor` | Median intensity of the vitreous window | Native processed-intensity units; background level |
| `noise_sigma_mad` | 1.4826 × median absolute deviation of all vitreous intensities | Native intensity units; greater noise spread |
| `retina_vitreous_contrast` | Native-location retinal P75 minus local vitreous median, then median across locations | Native intensity units; larger generally stronger signal |
| `retina_cnr` | Contrast divided by max(vitreous scaled MAD, 1e−6) | Dimensionless; larger generally stronger signal; band selection matters |
| `low_signal_frac` | Fraction of native locations with local contrast below 3 × max(vitreous scaled MAD,1e−6) | [0,1]; larger means less signal coverage; existing fixed threshold |
| `adjacent_bscan_corr_median` | Median correlation of neighboring robustly standardized structural en-face rows | [−1,1]; larger greater lateral-pattern continuity |
| `bscan_discontinuity_p95` | P95 of 1−adjacent correlation | Dimensionless; larger greater discontinuity |
| `brightness_stripe_power_frac` | Fraction of non-DC residual row-brightness Fourier power at ≥1/16 cycles/B-scan after removing 17-row moving average | [0,1]; larger higher-frequency striping; amplitude can still be small |
| `brightness_stripe_mad` | Scaled MAD of row-brightness residual | Native intensity units; larger stripe amplitude |
| `axial_centroid_jump_median_px`, `axial_centroid_jump_p95_px` | Absolute adjacent jumps of intensity-weighted retinal-band depth centroid | Depth pixels; larger abrupt axial motion/anatomical change |
| `axial_centroid_residual_p95_px` | P95 absolute centroid residual from 17-row moving average | Depth pixels; larger high-frequency displacement |
| `axial_centroid_stripe_power_frac` | Same high-frequency power calculation on centroid | [0,1]; larger relative axial stripe power |
| `shadow_native_pct`, `shadow_eligible_pct` | Existing automatic shadow proxy; full native grid / non-excluded grid denominators | Percent; larger missing/shadow coverage, not confirmed human vessel footprint |
| `repeat_group_n`, `repeat_peer_n` | Available completed acquisitions / other acquisitions in same animal, eye, date | Counts; provisional until all scans finish |
| `repeat_corr_median`, `repeat_corr_best` | Median/best translation-registered structural fingerprint correlation against peers | [−1,1]; larger agreement, may reflect overlap rather than quality |
| `repeat_comparable` | Existing workflow: best correlation ≥0.30 | Necessary gate; not proof all peers overlap |
| `repeat_disagreement` | 1−median peer correlation, only when comparable | Larger disagreement; non-comparable is blank, not poor |
| `repeat_best_peer` | Scan identity of best-correlated peer | Metadata |
| `repeat_registration_shift_px` | Magnitude of best-peer translation | **128×128 fingerprint pixels**, not native-grid pixels; no change to model coordinates |

Noise window: up to 48 pixels on the longer outside-band side, keeping a four-pixel edge/band margin. Structural en-face is retinal P75. Raw centroid uses median A-line depth profile, subtracting its P10 and clipping negative weights. Repeat fingerprints preserve broad structure, robustly standardize, clip to ±6 and block-average to 128×128. Registration is translation-only, bounded to 24 fingerprint pixels per axis. Repeated scans may sample different retinal positions. The comparability gate uses the best peer, while disagreement uses all scored peers, exactly as the existing workflow; this limits interpretation of mixed-overlap groups.

`animal`, `eye`, `scan_no`, `session_date`, `acq_time`, `day_label`, `days_post_laser`, `source`, `status`, `error`, `elapsed_s`, `model_version`, `analysis_policy`, `completed` are identity, actual/nominal timepoint, source, execution and policy metadata. `days_post_laser` takes precedence where available. `model_*_native_pct` scan columns average the corresponding boundary states across all eight boundaries. `human_quality_rating` stays blank in the model table; explicit ratings live separately.

## Regions, annotations and overlap

`region_layer_qc.csv` uses the same statistics by policy and region. `eligible_nonexcluded` is the non-excluded image grid; `automatic_shadow` is the automatic shadow footprint; `cnv_footprint` is the saved outline; `vessel_footprint` may be a saved draft/reviewed mask or an automatic proposal, as `region_provenance` states. `human_region_<id>_<category>` uses explicitly saved region categories. `other_eligible_outside_footprints` is the complement of available CNV, vessel and shadow footprints and is **not a human normal-retina label**.

Each regional layer denominator intersects the region with non-excluded and non-shadow eligibility. Thus automatic-shadow regions have zero eligible thickness samples, intentionally. Regions can overlap and must not be summed as disjoint partitions. `cnv_vessel_overlap_n` is the overlapping footprint count inside that region before shadow masking. Absent annotations mean annotation unavailable, not confirmed absence. Automatic proposals never become human annotations. The existing reviewed/draft vessel status is retained; saved masks may contain partly reviewed automatic content.

In the regional layer table, `native_*` columns retain the full-scan baseline for comparison, while `eligible_*`, `n` and all distribution/jump statistics refer to the indicated region after its masking. Use eligible columns for between-region comparisons; the repeated native baseline is not a within-region denominator.

`region_qc.csv` retains signal and support within shadowed regions: `nonexcluded_region_n` is the region after image exclusions but before shadow removal; `shadow_n/pct`, `low_signal_pct`, `local_cnr_*` and `model_reported_pct` / `model_uncertain_pct` / `model_not_traceable_pct` use that denominator. Model percentages average the eight boundaries within the region. `local_cnr_*` uses the same raw per-location contrast-to-noise definition as the acquisition workflow. This table permits shadow-region signal assessment even when thickness is entirely unavailable there.

## Human scan ratings and associations

`qualitative_ratings.csv` is a separate human-entry table: `rating` accepts Good / Usable / Poor / Unsure; `comments`, `rater`, `rated_at`, `provenance` preserve context. Blank means unrated. Generic segmentation acceptance, regional Good/Bad/Unsure strip ratings and numeric rankings are not compatible whole-scan ratings. Do not promote them automatically.

The comparison uses Poor=0, Usable=1, Good=2 for descriptive Spearman association; Unsure is plotted separately and excluded from ordering. Individual metrics remain separate. Animal-cluster bootstrap intervals resample whole animals with all of their rated acquisitions to reflect repeated acquisitions; sparse categories/few animals are flagged. No A-line pseudoreplication, threshold fitting, automatic exclusion or composite score is performed. Associations are exploratory and do not validate segmentation accuracy.
