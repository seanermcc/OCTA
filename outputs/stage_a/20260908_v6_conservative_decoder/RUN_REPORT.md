**Stage A: three conservative decoder checkpoints — 2026-09-08**

C2 is the most useful of the new review checkpoints: large retained errors disappear, while 80.5% of eligible manual surface positions remain. It does not meet all prespecified development criteria. C3 lowers leakage further but discards another 4,209 supported positions without removing the remaining 19-column ILM failure. Keep C2 for inspection and move to local visibility annotation; no version is promoted to production.

| Method | Supported retained / 34,809 | Coverage | Leak / 17,096 | Median / p95 (um) | Gross >25 um | Worst run |
| --- | --- | --- | --- | --- | --- | --- |
| Epoch 124 existing | 33090 | 95.1% | 3159 / 18.5% | 2.10 / 9.41 | 658 | 44 |
| Previous learned + ordered | 26121 | 75.0% | 616 / 3.6% | 2.08 / 7.84 | 153 | 13 |
| Previous simple gate | 26099 | 75.0% | 646 / 3.8% | 1.93 / 7.39 | 79 | 19 |
| Previous simple + ordered | 25503 | 73.3% | 504 / 2.9% | 2.05 / 7.50 | 42 | 27 |
| C1 bounded / partial | 31757 | 91.2% | 2206 / 12.9% | 2.15 / 7.76 | 41 | 19 |
| C2 tighter signal | 28019 | 80.5% | 816 / 4.8% | 2.08 / 7.46 | 19 | 19 |
| C3 strict signal | 23810 | 68.4% | 266 / 1.6% | 2.00 / 7.24 | 19 | 19 |

Coverage uses 34,809 eligible manual boundary positions in 14 B-scans from TS169 and TS325. Leakage uses 8 × 2,137 explicitly human-excluded columns across all 38 validation decisions. The 24 other validation decisions contribute withholding diagnostics, not boundary-accuracy targets. Errors are conditional on retention; missing values do not count as correct. The 2,782 readable proxy columns are weak reviewed positives, not calibrated local visibility labels. Columns within a B-scan are correlated; these are descriptive development results, not independent-sample confidence estimates.

The epoch-124 boundary model and cached native predictions are unchanged: zero training updates. C1 retains the original scope, shadow, missing-value and crossing rejections; nothing rejected by those protections is recovered. It evaluates uncertainty separately for each boundary, restricts candidates to supported posterior rows within 3 pixels of the original expectation, orders every retained surface pair, and withholds abrupt jumps and short fragments. C2 inherits all C1 rejections, narrows movement to 2 pixels, and adds the prior entropy-plus-signal gate at its training 98th percentile. C3 inherits C2, uses 1.5 pixels and the 95th-percentile gate, and requires longer intervals. These are three saved configurations, not three trained neural networks.

Continuity limits come from eligible manually segmented training curves: C1 uses max(6 pixels, twice the training 99.9th-percentile adjacent slope) for each boundary. C2 and C3 reduce these limits to 75% and 50% respectively, with floors of 4 and 3 pixels. Minimum retained lengths are 6, 8 and 16 columns. Entropy caps are training manual-position quantiles 99.5%, 99% and 98.5%. The posterior candidate cost is at most log(20) below its own peak. One-pixel ordering is geometric; no published thickness priors or classical boundary locations are ground truth. Steep unsupported intervals are withheld rather than flattened. These limits can also remove genuine steep anatomy.

Each disconnected interval is decoded independently with bounded neighbor penalties. Removals trigger re-solving so rejected positions no longer influence neighbors. Retained masks only shrink between checkpoints. Measurement arrays contain NaN gaps; thickness requires both endpoints to be retained, finite and ordered. Validated thickness arrays remain entirely NaN. Raw predictions, overlapping reason bits, configuration fingerprints and source snapshots accompany every checkpoint.

**What the images establish**

D98: the previous combined method retained 390/1,592 supported positions (24.5%). C1 retains 1,414 (88.8%); C2 retains 1,091 (68.5%); C3 retains 873 (54.8%). The added coverage reveals a real unresolved disagreement with manual ILM at zero-based columns 232–250: 19 retained errors above 25 um, up to 39.2 um. This is a smooth, low-entropy error, so increasingly strict jump and signal filters do not identify it. The manual reference remains the scoring target.

b0510: C1 removes most false upper plateaus but retains nine gross GCL/IPL errors, reaching 506.7 um. C2 and C3 withhold all 4,096 possible boundary positions. Their boundary accuracy on this image is unavailable, not perfect. This is successful abstention from a catastrophic output, not recovered segmentation. RPE has no eligible manual target here; TOTAL and RPE thickness therefore cannot certify this example.

Readable controls: the TS169 b0164 image retains 98.4%, 97.4% and 96.7% through C1/C2/C3. The TS325 D42 b0023 image retains 97.9%, 83.9% and 73.7%. The latter loss is substantial and is a reason to collect local visibility instead of applying a stricter whole-column gate.

[D98 comparison](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/figures/D98_comparison.png) · [b0510 comparison](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/figures/b0510_comparison.png) · [Readable control](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/figures/readable_control.png) · [Accuracy–coverage curves](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/figures/accuracy_coverage.png)

**Withholding helps; relocating the curves does not improve mean accuracy**

| Checkpoint | Identical supported positions | Raw MAE (um) | Decoded MAE (um) | Raw / decoded gross |
| --- | --- | --- | --- | --- |
| c1_bounded_partial | 31757 | 2.842 | 2.897 | 40 / 41 |
| c2_tighter_signal | 28019 | 2.569 | 2.631 | 18 / 19 |
| c3_strict_signal | 23810 | 2.487 | 2.548 | 18 / 19 |

On exactly the same retained positions, decoding slightly worsens mean error by about 0.06 um. The principal gain is withholding bad positions, not more accurate boundary placement. No future model-training claim should be based on these decoder results. The fixed prior threshold grid is compared descriptively in approximate_matched_coverage.csv; matches are approximate, and their coverage differences are stated. No new validation threshold search was used.

**Animal and quality results**

| Checkpoint | Animal | Supported retained / eligible | Coverage | p95 (um) | Leakage |
| --- | --- | --- | --- | --- | --- |
| C1 bounded / partial | TS169 | 7354 / 7508 | 97.9% | 8.76 | 9.1% |
| C1 bounded / partial | TS325 | 24403 / 27301 | 89.4% | 7.35 | 14.2% |
| C1 bounded / partial | TS336 | 0 / 0 | unavailable | unavailable | unavailable |
| C2 tighter signal | TS169 | 7274 / 7508 | 96.9% | 8.62 | 4.8% |
| C2 tighter signal | TS325 | 20745 / 27301 | 76.0% | 6.85 | 4.8% |
| C2 tighter signal | TS336 | 0 / 0 | unavailable | unavailable | unavailable |
| C3 strict signal | TS169 | 7048 / 7508 | 93.9% | 8.62 | 3.5% |
| C3 strict signal | TS325 | 16762 / 27301 | 61.4% | 6.50 | 0.9% |
| C3 strict signal | TS336 | 0 / 0 | unavailable | unavailable | unavailable |

TS336 has no eligible manual boundary positions and no explicit whole-column exclusions in this validation set. Its accuracy and unreadability leakage are unavailable; retained unknown positions are not evidence of correctness.

| C2 quality stratum | Supported retained / eligible | Coverage | p95 (um) | Gross |
| --- | --- | --- | --- | --- |
| high | 7274 / 7508 | 96.9% | 8.62 | 0 |
| low | 17303 / 23064 | 75.0% | 6.42 | 0 |
| medium | 3442 / 4237 | 81.2% | 8.29 | 19 |

**Every layer remains reported**

These are experimental thickness errors against eligible manual endpoint pairs, not checks against published layer thicknesses. A low median does not clear a local gross failure. No layer is silently omitted.

| Layer | C2 retained / eligible | C2 median / p95 (um) | C2 gross | C3 coverage | C3 p95 (um) |
| --- | --- | --- | --- | --- | --- |
| GCL | 3611 / 4580 | 2.33 / 7.73 | 0 | 68.1% | 7.87 |
| INL | 3519 / 4580 | 3.80 / 11.81 | 5 | 64.3% | 10.96 |
| IPL | 3524 / 4580 | 3.01 / 9.22 | 2 | 65.3% | 9.13 |
| OPL | 3619 / 4580 | 3.43 / 9.90 | 0 | 66.6% | 9.90 |
| PHOTORECEPTOR | 3564 / 4580 | 2.96 / 8.83 | 0 | 64.1% | 8.47 |
| RNFL | 2660 / 3517 | 2.47 / 8.53 | 17 | 63.1% | 8.24 |
| RPE | 3472 / 3812 | 2.21 / 10.08 | 0 | 77.1% | 11.20 |
| TOTAL | 2564 / 2782 | 2.24 / 5.92 | 18 | 79.8% | 5.61 |

The checkpoint folders also contain all eight boundary tables, thickness results by animal/quality/biology/scope, per-B-scan worst runs, useful labelled tissue lost, overlapping exclusion reasons and individual measurement views. Existing legacy labels have surface-wide edit evidence rather than exact stroke provenance; the frozen eligibility approximation is preserved for comparison and does not establish per-column local visibility.

**Stopping decision and next productive work**

All three configurations fail at least one criterion frozen before C1. C2 meets pooled coverage, leakage, gross fraction, maximum error and crossing criteria, but fails corrected-animal coverage, readable-control coverage and maximum contiguous gross run. C3 loses 12.1 percentage points of supported coverage without changing the remaining gross count or run. A fourth blanket tightening would address neither the smooth ILM error nor the need to preserve visible shallow boundaries through deeper uncertainty. Further work should collect local evidence and then test per-boundary visibility supervision.

The annotation proposal contains 24 review items across nine development images and five animals. It includes the residual D98 ILM error, good manual tissue withheld in the two stricter passes, two accuracy-unscorable TS336 cases, and positive training examples from TS165 and TS241. The existing GUI already has local visibility/provenance controls; this experiment does not modify it or any label format. See ANNOTATION_NEXT_STEP.md and annotation_cards/.

Software verification: 41 tests passed; 114 delivered measurement files were checked for NaN, geometry, thickness, scope, ordering, jump and monotone-mask behavior; six deterministic failure-case reruns matched exactly. The original checkpoint and original Stage A trainer identity were verified. Final integrity results are in integrity_complete.json. Final-test and repeatability contents were blocked; no human labels, old artifacts, frozen dataset definitions or production defaults were written.
At approximately matched coverage, the previous simple-plus-ordered comparator retains 81.4% versus C2 80.5% (0.89 percentage points apart), with 43 versus 19 gross boundary errors and p95 7.71 versus 7.46 um. This supports an improved withholding tradeoff, while the exact-support comparison above still shows no placement improvement.
Integrity audit: 482 allowed development fingerprints verified, 3,181 previous artifact sizes/timestamps unchanged, and zero added files in the previous experiment roots. The new package is opt-in and outside the original Stage A trainer identity.
