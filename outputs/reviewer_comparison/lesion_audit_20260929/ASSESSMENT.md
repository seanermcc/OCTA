# Lead/Shichu review and lesion-training assessment — 2026-09-29

Recommendation: preserve and use this work, but complete a focused adjudication round before pooling lesion labels or fitting a replacement layer model. A small development fine-tuning experiment becomes reasonable after that cleanup. These data do not yet establish reliable layer measurements inside CNV.

## Access and inventory

The authoritative journals in `F:/octa/reviewers/lead` and `F:/octa/reviewers/shichu` are accessible. All 56 journal hashes still match the September 28 comparison. The 29 lead journals in `F:/octa/For_Segmentation/Reviews/reviewers/lead` are byte-identical copies, not additional reviews. The local Mac-check copy also has the same 29 filenames. This inventory describes the supplied current reviewer sets, not unsynchronized work on other computers or the entire historical training cohort.

| Reviewer | Saved B-scans | Confirmed | Draft | Confirmed, unique to reviewer |
|---|---:|---:|---:|---:|
| lead | 29 | 21 | 8 | 12 |
| shichu | 27 | 25 | 2 | 16 |

Nine identical native B-scans are confirmed by both: 47 distinct saved slices, 37 distinct confirmed slices, ten draft-only slices. Confirmed work spans 22 acquisitions and four animals (TS169, TS241, TS247, TS250); paired work spans three animals. All confirmed records are assigned development. The two reviews of one B-scan do not count as two independent images. Different acquisitions may still show the same lesion; independent lesion identities were not established here.

Active review time medians are 5.47 minutes for lead and 7.00 for Shichu; this is a workload measure, not proof of annotation correctness.

## Retinal boundaries in and near the lesion

The authoritative v3 importer was replayed against native frozen providers, including current confirmation, geometry, visibility/reliability, exclusion, vessel and shadow-override policies. It reproduces the original 22,559 jointly approved and 2,555 jointly drawn points. Images were inspected for all nine shared cases; all 56 records received numerical auditing. The unmatched contact sheet is a survey aid, not a completed expert adjudication.

| Scope, nine paired B-scans | Jointly approved points | Mean absolute separation | P95 |
|---|---:|---:|---:|
| All eligible positions | 22,559 | 1.06 µm | 5.14 µm |
| Lesion extent marked by either reader | 4,443 | 2.32 µm | 9.29 µm |
| Lesion extent marked by both readers | 1,548 | 3.19 µm | 13.36 µm |
| Approximately 100 µm outside either-reader extent | 4,417 | 1.16 µm | 4.83 µm |
| Remaining columns | 13,699 | 0.61 µm | 3.68 µm |

The approximately 100 µm margin is 35 native A-lines at the nominal 1460/512 µm pitch, within the selected B-scan. It is not a registered two-dimensional perilesional annulus. The remaining columns are not necessarily healthy or artifact-free. Mean/P95 values pool correlated boundary/A-line points; they are descriptive agreement, not model accuracy or independent observations. Both readers started from the same prediction. Restricting to overlapping reliable manual strokes gives 3.22 µm overall, 3.69 µm inside the both-reader region, and 2.63 µm in the outside margin.

**Coverage is the larger lesion problem.** In columns both readers marked as lesion, only 1,548/3,432 possible boundary/A-line pairs (45.1%) have an eligible position from both. At 666 points (19.4%) one reader explicitly marked unreliable/not traceable while the other approved a position. These disagreements vanish from a distance-only score. Across the larger either-reader lesion extent, this conflict affects 1,846/8,128 points (22.7%). Neither reader is uniformly the more conservative one across all examples. No anatomical-absence labels occur in the confirmed lesion regions; no-trace must not be reinterpreted as tissue absence.

The core has 429 overlapping lesion columns across seven B-scans. By boundary:

| Boundary | Jointly eligible columns / 429 | Mean absolute separation |
|---|---:|---:|
| ILM | 400 | 1.94 µm |
| RNFL/GCL | 268 | 1.79 µm |
| GCL/IPL | 238 | 1.30 µm |
| IPL/INL | 103 | 8.32 µm |
| INL/OPL | 44 | 16.43 µm |
| OPL/photoreceptor composite | 34 | 8.99 µm |
| Photoreceptor/RPE | 97 | 6.44 µm |
| Outer RPE edge | 364 | 2.39 µm |

These small, selected denominators preclude a general ranking of boundary accuracy. They show why a good all-layer average cannot validate the middle/outer retinal subdivisions at a lesion. A layer thickness needs two defensible endpoints, so its usable coverage may be smaller still. Missing/uncertain endpoints should remain missing.

Visually, recognizable bands on lesion flanks often have closely aligned curves. Through disrupted tissue, some saved curves bend toward bright foci, form narrow spikes, or disappear under one reader's uncertainty marks while the other retains a curve. These are specific candidates for expert adjudication, not grounds to declare a whole reviewer correct. Healthy-reference priors must not flatten those lesions into normal anatomy.

## New lesion annotations

All 46 confirmed reviewer records carry the lesion confirmation contract. Across distinct confirmed slices, 30 have a positive CNV region from at least one reader, 31 have an eligible CNV edge, and 30 have eligible Hyper_Ref paint. Those counts are not independent lesions and include the inconsistencies below.

1. **Lateral extent convention differs systematically.** In all seven shared cases with nonempty regions from both, lead's entire region is contained in Shichu's larger region. Median intersection-over-union is 0.565 (range 0.371–0.626). Across all paired positive unions, including the empty-lead example, pooled IoU is 0.422. This pattern suggests a core-versus-broader-affected-region convention; that interpretation needs the reviewers' confirmation.
2. **CNV edge is not interchangeable between readers.** Seven shared slices have overlapping eligible edges: 329 columns, mean separation 12.14 µm, P95 37.42 µm, maximum 86.00 µm. Shichu is 9.18 µm shallower on average (signed Shichu minus lead). TS241 B244 shows a relatively flat lead trace with steep endpoint drops versus a shallower irregular Shichu trace; TS250 B387 also differs strongly in depth/shape. Decide which visible interface and which endpoints the tentative definition intends. Do not average incompatible structures or train a vertical endpoint stroke as a confidently traced surface.
3. **Hyper_Ref needs example-based calibration.** Pooled Dice in jointly known pixels is 0.604. This is a restricted, selection-dependent overlap, not whole-lesion detection accuracy; an empty region can leave only painted positives known. Some differences concern isolated dots versus larger connected bright areas near the RPE. Agree on confluence, continuity with RPE, and uncertain brightness before fitting. General experimental evidence supports using illustrated annotation examples rather than merely lengthening text instructions: [Rädsch et al., 2023](https://www.nature.com/articles/s42256-023-00625-5).
4. **Four confirmed lead records have lesion paint/edges but no CNV region.** Under the current exporter, a confirmed empty region is negative region supervision in usable columns. These require adjudication/reconfirmation before the region task consumes them. Edge/Hyper_Ref outside a region is permitted by the GUI, so this is a semantic audit flag, not a corrupt-file claim.
5. **Four Shichu records on acquisitions named beforelaser contain positive CNV annotations.** Their OCTs show conspicuous outer-retinal disruption; the filename alone cannot settle their biological identity. Verify true laser dates, possible previous lesions and the intended target. Do not erase them solely because of the name, and do not pool them as CNV solely because a tool was used.

## Concrete correction/discussion list

All B-scan and A-line indices below are zero-based native indices. Full IDs are retained in the CSVs.

| Priority example | Why revisit | Image |
|---|---|---|
| TS247 D21 s03 B325 | Jointly approved IPL/INL and INL/OPL differ up to 51 and 59 µm near A-lines 31–53; lead has no eligible lesion edge, Shichu does. Inspect the spike and which interface is visible. | [Comparison](TS247_OD_2024-11-06_D21_s03_104157_b0325.png) |
| TS250 D27 s01 B380 | Lead region empty despite edge and dots; Shichu marks 210 columns. Retinal curves also disagree at disrupted tissue. | [Comparison](TS250_OD_2026-03-23_D27_s01_112447_b0380.png) |
| TS241 D42 s03 B244 and s05 B219 | CNV-edge mean differences 21.57 and 16.53 µm; settle dark-interface identity and endpoint shape. | [B244](TS241_OD_2024-09-25_D42_s03_111600_b0244.png), [B219](TS241_OD_2024-09-25_D42_s05_112207_b0219.png) |
| TS250 D24 s03 B45 | Lead denies broad inner-layer portions while Shichu retains some; inspect visibility and PR/RPE versus lesion edge, rather than judging only shared positions. | [Comparison](TS250_OD_2026-03-20_D24_s03_142449_b0045.png) |
| TS247 D35 s01 B282 | Region spans 62 versus 167 columns; differing Hyper_Ref selection near the bright outer complex. | [Comparison](TS247_OD_2024-11-20_D35_s01_112538_b0282.png) |
| TS250 D24 s02 B387 | CNV-edge mean difference 16.49 µm, despite closer retinal curves. | [Comparison](TS250_OD_2026-03-20_D24_s02_141857_b0387.png) |
| TS247 2024-10-17 s11 B234/B411/B422 and s12 B330 | Check chronology/target identity for four beforelaser-named CNV-positive reviews. | [Four images](beforelaser.png) |

Additional lead confirmations with empty region: TS247 D35 s03 B184 (Hyper_Ref); TS250 D24 s04 B64 and B260 (edge and Hyper_Ref). These plus B380 are the four above. Correct only after reviewer adjudication, through the GUI. Keep the original independent judgments and save consensus as identifiable later work.

Confirmed records also contain geometry warnings: 2,967 unresolved boundary/A-line positions for lead and 1,594 for Shichu. These are excluded from eligible position targets, not silently approved. Review concentrations include lead TS241 D42 s05 B212 (559) and TS250 OS D7 s02 B440 (570). Some may be off-image endpoints or ordering conflicts rather than lesion mistakes; inspect the cause before correcting. Never force an invisible boundary into a plausible location merely to clear a warning.

## Recommended sequence

1. Use the nine shared cases for convention-setting and adjudication now. Agree on the lateral CNV region, the precise dark-lesion edge, Hyper_Ref inclusion, and visible versus uncertain versus anatomically absent boundaries. Retain unreadable regions as uncertainty evidence. Revisit affected unmatched examples after agreeing on those rules.
2. Complete meaningful drafts and add a bounded next block of roughly 12–18 diverse reviews: lesion centers, both margins/transitions, readable tissue, and difficult non-CNV/ONH/shadow negatives. Favor additional animals and independent lesions over adjacent slices. This is a proposed collection increment, not a proven minimum sample size. Double-review a subset and inspect several with model curves initially hidden to check anchoring.
3. Freeze a versioned, adjudicated development snapshot. The new whole-B-scan contract permits valid confirmed unchanged/joined/moved positions; legacy labels keep their old eligibility rules. Preserve manual-origin versus retained-prediction origin. Drafts are not whole-approved examples. Do not count repeat readers as independent cases or silently average conflicts.
4. Run an isolated layer fine-tuning pilot against the frozen model with the same animal-disjoint evaluation cases. Include useful legacy data to check retention, but audit checkpoint ancestry: these records are all development and there is no demonstrated untouched final test here. No random A-line/B-scan split across the same animal or lesion.
5. Train CNV region, edge presence/depth and Hyper_Ref with separate heads/masks after resolving semantics. They are not additional members of the ordered retinal layer stack. Start from OCT appearance; a later footprint-guided experiment must use realistically predicted en-face footprints at evaluation and account for upstream training exposure. A footprint provides location, not layer coordinates or proof of visibility.
6. Judge success separately at lesion interior, margins and readable distant tissue: per-boundary error/tails and gross failures, visibility/uncertainty disagreement, usable coverage, and valid thickness coverage. A model can lower measured error by withholding almost everything, so error and coverage must be assessed together. No normal-thickness target inside CNV.
7. Repeat the main comparison with manual shadow-override columns included and excluded. Current confirmations gain 4,506 lead and 4,687 Shichu eligible position points from the override policy. Treat this as a separate data group, not independent evidence that previously shadowed tissue is readable everywhere.

## Reproducibility and limits

See [review inventory](review_inventory.csv), [regional boundary measurements](paired_boundaries_by_region.csv), [lesion agreement](lesion_agreement.csv), [summary](summary.json), and [source hashes](source_hashes.json). The read-only script is `../audit_lesions_20260929.py`; `inspect_details.py` generates additional survey figures and detail findings. Activation of the octa environment is required. Sources were hashed again after the main analysis and were unchanged. No human labels, model weights, or training configuration were modified, and no training was started.

This assessment compares annotations and inspects saved OCT images. It does not adjudicate biological CNV identity, prove a reviewer correct, evaluate a newly trained model, or establish independent full-cohort lesion counts.
