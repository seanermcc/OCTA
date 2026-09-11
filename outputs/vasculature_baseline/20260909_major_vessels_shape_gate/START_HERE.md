# Major-vessel shape gate — same six scans

The new gate removes many small, compact and thin candidate regions while retaining long vessel bands. The same six saved input masks and the original contrast threshold (0.18) were used; no contrast parameters were retuned. Original proposals and human labels remain unchanged. These new files are automatic proposals for review.

![Shape-gated proposals](overview.png)

[See removed regions in orange](changes.png)

## The rule

Each surviving connected region must have at least 600 pixels of area, an estimated centerline span of at least 80 pixels, a median centerline width of at least 6 pixels, and a centerline-length/width ratio of at least 5. The length follows the band through curves and branches instead of judging only its bounding-box shape. This keeps a branching vessel tree from being rejected merely because its overall outline is round. With the nominal 1460-um field, 6 pixels is about 17 um and 80 pixels about 228 um; these are pilot cleanup settings, not validated biological cutoffs.

A single pass also removes terminal side branches shorter than 35 pixels or narrower than 6 pixels. Interior paths between junctions are retained, followed by another connected-component check. A weighted skeleton graph supplies a two-sweep estimate of centerline span. Pixel ownership is assigned to the nearest original centerline point when pruning a spur. The gate only removes existing candidate pixels; it does not fill gaps or invent vessel continuity. Median width is a component criterion, not a guarantee that every local cross-section is at least six pixels wide.

## What changed

| Scan | Connected regions before | After | Removed pixels |
|---|---:|---:|---:|
| TS165_OD_2025-04-29_WT_s06_114517 | 8 | 6 | 2,392 |
| TS165_OS_2025-04-29_WT_s02_121711 | 15 | 8 | 3,722 |
| TS247_OD_2024-10-30_D14_s05_105423 | 10 | 4 | 2,043 |
| TS267_OD_2025-04-16_D56_s03_102014 | 20 | 5 | 9,073 |
| TS305_OD_2025-08-07_D35_s01_114451 | 15 | 3 | 5,991 |
| TS325_OD_2026-03-03_D98_s01_131308 | 11 | 3 | 3,985 |

Across the six scans, connected regions went from 79 to 29, and 27,206 candidate pixels were removed. Fewer regions is a description of cleanup, not proof that every removed region was false. In particular, short real vessel fragments at the image edge may also be removed; the clipped upper-left vessel on TS267 is an example.

## Comparison against your two saved vessel masks

| Eye | Dice before -> after | Precision before -> after | Recall before -> after | Previously matched vessel pixels retained |
|---|---:|---:|---:|---:|
| TS165 OD | 0.724 -> 0.726 | 0.728 -> 0.750 | 0.719 -> 0.704 | 98.0% |
| TS165 OS | 0.730 -> 0.727 | 0.684 -> 0.706 | 0.782 -> 0.749 | 95.8% |

Precision improves on both labeled scans; recall drops slightly and mean Dice is essentially unchanged. Both masks are from TS165 and already informed baseline development, so this is a development comparison, not independent validation. Existing human ONH exclusions are reused identically in before/after measurements and shown in green. The unassessed outer ten pixels still count as misses where a human painted vessels. The four other scans have no reviewed vessel mask and therefore no measured accuracy here.

## Remaining errors

Round/compact islands between vessels are largely removed in these examples. Long acquisition borders and some elongated lesion artifacts still pass the band rule. The bottom border in TS305/TS325, the right-side seam in TS165 OS, and the horizontal lesion/streak regions in TS267 show this limitation. A shape gate cannot distinguish two structures that both look like long thick bands. Some real short fragments and smaller branches are removed as well. Existing gaps and width errors are not repaired by this cleanup.

## Verification and files

Six behavioral tests check rejection of round/short/thin regions, preservation of straight and curved bands and branching trees, removal of an isolated round blob and a short attached spur, and preservation of unsupported gaps. These synthetic checks verify the intended operation; they do not establish animal segmentation accuracy. Saved-array checks verify native grids, removal-only behavior, exclusions, and unchanged human/baseline files.

`parameters.json` contains the shared settings. `component_audit.json` records geometry and rejection reasons for every original candidate region. `metrics.json` records comparison measurements. `proposals/*_proposal.npz` stores the new mask, removed mask, exclusions, original-proposal path/hash and explicit automatic provenance. No human-label or training directory is written.

### Individual before/after comparisons

- [TS165_OD_2025-04-29_WT_s06_114517](TS165_OD_2025-04-29_WT_s06_114517.png)
- [TS165_OS_2025-04-29_WT_s02_121711](TS165_OS_2025-04-29_WT_s02_121711.png)
- [TS247_OD_2024-10-30_D14_s05_105423](TS247_OD_2024-10-30_D14_s05_105423.png)
- [TS267_OD_2025-04-16_D56_s03_102014](TS267_OD_2025-04-16_D56_s03_102014.png)
- [TS305_OD_2025-08-07_D35_s01_114451](TS305_OD_2025-08-07_D35_s01_114451.png)
- [TS325_OD_2026-03-03_D98_s01_131308](TS325_OD_2026-03-03_D98_s01_131308.png)

Reproduce after activating `octa`: `python code/vasculature_shape_gate.py`. Run the geometry checks with `python -m unittest discover -s code -p test_vasculature_shape_gate.py -v`.