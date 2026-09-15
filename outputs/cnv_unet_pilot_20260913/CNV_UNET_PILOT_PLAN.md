# CNV U-Net pilot: thickness and missing-measurement patterns

Prepared September 13, 2026. Deliverable: an actionable experiment plan and refreshed saved-review inventory. No model has been implemented or trained in this planning task; no thickness/CNV association has yet been measured here.

## Decision

Start a compact en-face CNV U-Net experiment with the annotations available now. More labeling can follow the first predictions; it is not a prerequisite for trying the model. Include thickness and its missingness from the first experiment, with an image-only comparator to find out whether they help.

The earlier report and its model plan are background, not new user instructions. Their proposed requirement to collect a larger multi-animal pilot first is not a gate on this exploratory run. The objective now is a useful first set of suggested CNV footprints for review, with an honest within-animal evaluation.

## Current labels

The fresh read of v5 files found 15 saved acquisitions, 14 with both complete status and whole-field confirmation, 25 approved Full Lesion entries, 8 approved Other/Unsure entries, 19 rejected entries, and one draft. All are TS267. These are entries across visits, not 25 independent biological lesions.

D0 OD, D7 OD, and D14 OD are now complete, updating the handoff's older count of 11. D0 OS remains partial with a draft. Selected D28 OS and D35 OS have no v5 record. Three completed OS fields record reviewed absence (D14, D42, D98). D0 is not automatically healthy: its OD file explicitly contains two kept regions. Preserve those judgments and flag day/biology questions for later review rather than relabeling by date.

`CURRENT_REVIEW_STATUS.json` contains the source paths, hashes, and per-file counts. This refresh checks metadata and decisions, not mask bounds, overlaps, or biological correctness. The exporter must repeat the pixel-level checks against these newer revisions.

Target contract:

- Approved Full Lesion, with completed classification and valid reviewed-mask provenance: positive footprint.
- Completed field: background outside positive and ignored areas.
- Unsure, unresolved draft, exclusion, or inconsistent/overlapping judgment: ignore and report the conflict.
- Partial field: confirmed positive pixels can be used; unmarked pixels remain unknown. D0 OS currently adds no positive supervision and can be omitted from fitting.
- Missing file: no supervision. Retain these scans for later prediction/review.
- Rejected proposals: retain for error analysis; do not automatically label every removed outline as background, since removals can include duplicates. Completed-field background is enough for the first run.

Unreliable thickness does NOT invalidate a confidently reviewed CNV target. Image/annotation uncertainty and thickness availability need separate masks.

## Inputs and output

Use native 512 x 512 [B-scan, A-line] numerical arrays, aligned on the exact acquisition. Output one CNV score per pixel and candidate footprints. Train on the whole manual footprint, including supported edges; do not substitute the heuristic candidate core or thinning contour for the target.

| Input | Initial channels | Purpose |
|---|---:|---|
| Structural OCT en-face | 1 | Tissue appearance and spatial context |
| Actual OCTA projection | 1 | Flow-channel appearance; current cache is a saved-retinal-crop projection, not a layer-specific slab |
| Thickness in micrometers | 8 | Full retina, RNFL, GCL, IPL, INL, OPL, photoreceptor composite, RPE band |
| Automatic availability masks | 8 | Tell the model which layer measurements are missing |
| Automatic shadow mask | 1 | Help distinguish common vessel-associated dropout |

Initial full model: 19 channels. All eight thickness outputs remain represented even when weak. Full retina here is ILM to outer RPE edge, not a substituted BM measurement. Photoreceptor composite is not isolated ONL.

Normalize observed thickness using training-set layer medians and robust scales. In the model tensor only, set missing normalized entries to zero and pair them with availability=0. Zero is a computational placeholder, never a measured thickness. Preserve NaNs in saved measurement products; do not interpolate shadows or impute missing tissue for quantification. Do not normalize every thickness map independently to its own color range, which would erase between-scan numerical differences.

Add separate automatically generated reason channels only after inspecting what the exports actually support: endpoint absence/withholding, nonpositive gaps/crossings, low signal, and continuous endpoint uncertainty. Do not invent distinct failure reasons from a single NaN mask. A finite value means available under a specified experimental policy, not proven reliable.

### Avoid human information in the inputs

The v5 loader calls the octa-thick engine, which searches manual surface sources and uses explicit human unreliability. Copying its displayed maps would mix automatic inputs with review information. Merely setting the external manual-source list empty may also be insufficient: inspect baked-in overrides and `human_overrides_provenance.json`.

Build the automatic input stack from an identified, frozen automatic position/reporting export, its automatic geometry/shadow outputs, and source images. If an export includes manual changes, recover or regenerate its automatic branch from the frozen model. Save the policy, checkpoint hashes, projection metadata, coordinate checks, and source hashes. Human corrections and human unreliable marks may be used for a separately named descriptive analysis, never as autonomous model inputs or human-derived missingness channels.

The upstream layer model is ALL_LABELLED and has seen this cohort. Current CNV results therefore remain development results even with CNV visit holdouts. Later animal-independent evaluation must also account for upstream model exposure.

## What to learn about lesion interiors

The hypothesis is that CNV may combine altered thickness in measurable surrounding tissue with a compact, multilayer loss of measurable boundaries centrally. This is a hypothesis to test, not an established finding in this task.

Prepare a descriptive profile alongside the first model, without making completion of that analysis a prerequisite for training:

1. Define an analysis interior by eroding each kept footprint by 25 micrometers, with 10 and 50 micrometer sensitivity checks. This is a geometric interior proxy, not a human-labeled biological core. Report lesions too small to retain an interior and FOV-clipped lesions separately. Never use heuristic `core_runs` as core ground truth.
2. Compare that interior, the remaining footprint edge, and an exterior 0-100 micrometer band. Exterior tissue can still be affected; call it perilesional tissue, not healthy control. Exclude other lesions, unsure/unreviewed regions, and known unusable annotation areas.
3. For every layer and region, report measurable fraction, available-value median/IQR, and reason-specific unavailable fractions when reasons exist. An entirely missing interior has no thickness median; its missing fraction is still an observed result.
4. Compare against reviewed nonlesion locations in the same field and reviewed negative fields. Match or stratify by signal, shadow/vessel proximity, image position, and edge proximity so an association is not simply a vessel or scan-quality effect. Include artifact-rich negatives, not only clean retina.
5. Examine combinations of unavailable layers, size/shape of missing patches, and whether surrounding measurable tissue changes. Do not assume every CNV is thin or every layer fails together.
6. Summarize at lesion/acquisition/visit level, showing individual cases. Repeated views of the same tissue and thousands of pixels are not independent samples; with one animal, do not report animal-population confidence intervals.

Do not feed human-mask-defined interiors, rings, distances, or reference fits into the U-Net. They are descriptive tools only. Any later local-deviation input must be calculated without CNV labels by the same rule at training and inference, with its own support mask.

## First training recipe

A compact 2D U-Net is a suitable starting architecture, following the encoder/decoder and skip-connection approach of the [original U-Net paper](https://arxiv.org/abs/1505.04597). That literature motivates the architecture, not its expected performance here. Keep nnU-Net as a later comparator rather than a dependency of this first attempt; see its [primary paper](https://www.nature.com/articles/s41592-020-01008-z).

Proposed starting settings, to record before fitting:

- Four downsampling stages with widths 16, 32, 64, 128 and a 256-channel bottleneck; GroupNorm; one output logit. Random initialization, separate from the boundary-model head.
- Native-resolution 256 x 256 tiles with balanced sampling of lesion-containing and reviewed-background tiles. Sample acquisitions before tiles so a large lesion or many crops do not dominate. Include whole negative fields in evaluation. Use overlapping tiled inference on all 512 x 512 pixels and blend overlap scores.
- AdamW, learning rate 0.001, batch size 4 subject to GPU memory, weight decay 0.0001. Start with at most 100 epochs of 32 batches, retain the best validation checkpoint, and stop after 15 epochs without improvement. These are pilot defaults, not tuned optima or runtime promises.
- Masked binary cross-entropy plus masked soft Dice on positive-containing supervised tiles. Normalize by known pixels, skip all-unknown tiles, and retain BCE for empty/negative tiles. Mask ignored pixels out of every loss term and metric.
- Consistent flips and modest translations across all inputs/targets; mild OCT/OCTA intensity perturbation. Preserve native scan-axis artifacts initially rather than assuming 90-degree rotations are harmless. Do not perturb thickness as though it were optical intensity.
- Optional thickness-channel dropout can test dependence on measurements, but must update availability consistently and be reported as simulated missingness. It must not be presented as a realistic model of CNV failure.

First check a tiny-set overfit and finite loss/inference. Then run these equal-budget comparisons on identical partitions:

| Experiment | Inputs | Question |
|---|---|---|
| A | Structural OCT + OCTA | How useful are the images alone? |
| B | Images + eight availability masks + shadow | Does measurement failure add information? |
| C | Images + eight thickness maps + eight availability masks + shadow | Do numerical thickness patterns add value beyond missingness? |

Optional diagnostic D uses availability and shadow alone. Strong apparent performance there warrants checking artifact, eye, and positional shortcuts. A thickness-only experiment cannot identify the effect of thickness independently of missingness unless the fill/mask behavior is handled explicitly. Start with one fixed seed per experiment, then repeat the leading comparisons with three seeds before claiming a stable improvement. Never hard-cap the output lesion count or require circular predictions.

## Evaluation possible now

Suggested initial temporal split, fixed before fitting:

- Train: D0, D7, D14, D28, D35, D42 (16 kept entries across available reviews).
- Validation: D49 (3 kept entries; its completed OS field contributes reviewed background outside Unsure).
- Development holdout: D56 and D98 (6 kept entries; D98 OS is an explicit negative field).

Keep both eyes and every repeat from a visit in the same partition, and assign partitions before generating crops or augmentations. No labels transfer between repeats. D0 OS and the two absent OS records contribute no assumed background. Validate positive/known-negative pixel counts after export.

This tests later visits of the SAME animal, potentially the SAME lesions. It cannot exclude tissue memorization or establish generalization to new animals. All current positive entries are OD and no OS entry is a kept CNV: eye-associated image structure is another potential shortcut even without an eye-ID input. Do not input animal, eye, visit/day, absolute coordinate channels, or heuristic candidate masks. Later development needs both lesion-positive and negative examples across multiple animals/eyes.

Select checkpoints and a threshold using D49 only; keep holdout results out of tuning. With so few scans, report every result rather than a single headline score. If holdout errors guide a later revision, relabel those scans as development data rather than maintaining a claim of untouched evaluation.

Compare A/B/C and the frozen v3 heuristic on the same known-label regions. Report lesion recall, false positives per completed scan, precision, Dice/IoU on known pixels, boundary error only along reviewed boundaries, merges/splits, and count/area errors. Define one-to-one overlap matching in advance (initial IoU >= 0.1 for detection, with 0.25 and 0.5 sensitivity analyses); do not confuse permissive detection matching with accurate borders. Do not give empty-vs-empty fields a perfect Dice that inflates the lesion summary; report false-positive area/count there instead.

Report errors in lesions with low versus high automatic measurement coverage, across all eight layers, and show vessel/shadow negatives separately. Predictions in Unsure/unknown regions are unscored and listed for review. Do not penalize a prediction solely for occupying an ignored region; inspect partially ignored objects separately.

Save full native score maps before thresholding, all components without a count cap, overlays, the exact model/configuration, input/label manifests, losses, and per-scan metrics. Sigmoid scores are not calibrated certainty. After evaluation, a separately labeled all-available-data fit may provide review suggestions; its fitted scans are not independent test results.

## First useful delivery and later labels

Implementation order: audit/export the existing labels; build automatic image/thickness/missingness inputs; verify masking, alignment and provenance; run A/B/C; produce a comparison and reviewable predictions. The interior-pattern analysis accompanies this sequence. Preserve human files and store model suggestions in a separate versioned output folder; a suggestion becomes a human annotation only through GUI review.

For the next annotation round, prioritize confident CNV with unavailable thickness, non-CNV shadows/segmentation failures, image-vs-thickness model disagreement, potential misses, and a fixed random sample. Add other animals and both lesion-positive and negative eyes as early as feasible. More examples of the same TS267 lesion over time do not replace that diversity.

Success for this first attempt is a measurable reduction in missed lesions, false suggestions, or correction effort on the available development scans. Reliable automatic lesion detection can coexist with unavailable thickness inside a lesion: segmentation area may be reported while layer thickness remains NaN and coverage is stated explicitly.
