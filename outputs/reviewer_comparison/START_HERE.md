# Lead and Shichu: retinal boundary comparison

Open **[OPEN_COMPARISON.cmd](OPEN_COMPARISON.cmd)**. The viewer is also available
at [http://127.0.0.1:8818/](http://127.0.0.1:8818/) while its local server is running.
Double-click `index.html` for the complete offline viewer without Python.

This is a read-only snapshot updated on September 29, 2026 from
`F:\octa\reviewers\lead` and `F:\octa\reviewers\shichu`. No labels, journals,
models, or source volumes were changed. Generated outputs live here.

## What was found

**Refresh on September 29, 2026, 2:58 PM:** the comparison now reads Lead's live
save folder, `F:\octa\For_Segmentation\Reviews\reviewers\lead`, through
`REFRESH_COMPARISON.cmd`. It includes the reconfirmed TS247 D21 B325 (revision
113) and TS250 D27 B380 (revision 126). The tables below describe the original
comparison; use the viewer and `summary.json` for current scores.

| Reviewer | Saved B-scans | Confirmed | Drafts |
|---|---:|---:|---:|
| lead | 29 | 21 | 8 |
| shichu | 27 | 25 | 2 |

There are **9 exactly matching B-scans**, all confirmed by both reviewers, across
TS241, TS247 and TS250. Another 20 are lead-only and 18 are Shichu-only: 47 distinct
saved slices altogether. Different B-scan indices are never paired or registered.

| Comparison scope | Paired boundary/A-lines | Mean absolute separation | P95 separation | Within 5 µm |
|---|---:|---:|---:|---:|
| Both confirmed, after validity masks | 22,559 | **1.06 µm** | 5.14 µm | 94.7% |
| Both drew reliable strokes | 2,555 | **3.22 µm** | 9.50 µm | 80.8% |

These scopes cover 61.2% and 6.9%, respectively, of the 36,864 possible
boundary/A-line pairs in the nine matched slices. The equal-B-scan mean distances
are 1.27 µm and 2.63 µm; the table above weights each paired point equally.

Both people started from the same frozen prediction. Therefore the first row
includes matching unchanged model curves and is not an independent hand-drawing
agreement estimate. The second row isolates overlapping reliable strokes but
covers a small, selected part of the retina. Neither measurement establishes
which reviewer is correct or evaluates segmentation accuracy against independent
ground truth. No confidence interval or population-level reliability claim is made.

The largest whole-slice mean in the confirmed scope is **4.04 µm** for
`TS250_OD_2026-03-20_D24_s03_142449`, B-scan 45. Some boundaries have no jointly
eligible positions there; their missing scores remain visible in the table.

## Using the viewer

1. Choose a slice on the left. The initial order puts larger confirmed differences first.
2. Compare the two synchronized OCT panes or the combined overlay beneath them.
3. Select a boundary to isolate it. Hover to inspect a signed local distance.
4. Set the difference threshold in microns. Highlighted curve pieces and the
   filled gap in the overlay locate differences above that threshold.
5. Scroll within an image to zoom; drag to pan. **Fit retina** restores the crop,
   and **Full depth** shows the entire saved image. Both views share coordinates.
6. Click a heatmap row or table row to select its boundary. Gray heatmap cells
   indicate missing paired measurements, not zero separation.
7. Switch between confirmed, drawn-only, and all-saved diagnostic scopes.
   **Show unscored curves** exposes the remaining saved geometry as gray dashes.
8. **Export this slice: CSV** writes all 4,096 boundary/A-line records, their
   eligibility, signed and absolute differences, and the chosen threshold.
   **Save comparison: PNG** captures the current side-by-side view and settings.
9. **Saved CNV annotations** shows each person's region and edge in their own
   pane and in the combined overlay: cyan for lead, pink for Shichu. Toggle
   regions, edges, or either reviewer independently. Turn off **Retinal
   boundaries** to focus on CNV. Regions are full-depth lateral spans, not
   tissue masks. Solid edges are marked reliable, dashed edges unreliable,
   and dotted edges not traceable; image-excluded edge portions are dimmed.
   Hover for local CNV status. Each review's CNV confirmation or draft status
   appears above the images. Saved drawings remain visible independently of
   retinal eligibility; a visible CNV edge is not necessarily approved.
10. **Hyperreflective dots (Hyper_Ref)** displays each reviewer's exact saved
    brush footprints, using cyan for lead and pink for Shichu. **Lead dots**
    and **Shichu dots** work independently of the CNV toggles, in both the
    individual panes and the combined overlay. Turn off CNV and retinal
    boundaries to isolate the dots. Outlines and translucent fill preserve the
    painted mask; image-excluded portions are dimmed. No dots marked does not
    establish absence. Totals count painted pixels, not individual dots.
    The shared lesion review confirmation applies to CNV and Hyper_Ref;
    unconfirmed dot drafts are identified. PNG exports include the overlays.

When opened through the launcher, exports save directly to this folder's
`exports` subdirectory and the viewer displays the resulting full path.
When opened as an offline HTML file, exports use the browser's download handling.
The ready-made `boundary_differences.csv` provides all eight boundaries for all
nine shared slices in all three scopes; `inventory.csv` lists every saved slice.

## Exactly what is measured

Signed distance = `(Shichu canonical depth − lead canonical depth) × 1.12 µm/px`.
Positive means Shichu placed the boundary deeper. Absolute distance, median,
95th percentile, maximum, RMSE, signed bias and the fraction within 5 µm are
included in the exported tables/summary. The viewer's within-limit fraction
responds to its adjustable threshold.

The authoritative v3 event interpreter replays each journal only to its saved
undo cursor. It validates confirmation snapshots, geometry revisions and identities.
Provider hashes, native image shape, acquisition fingerprint, boundary names and
crop offset must match before comparison. Saved canonical images are reused as-is;
full-depth curve coordinates are displayed after subtracting the canonical crop
offset. No raw volume reconstruction or orientation guessing is involved.

Confirmed scope intersects current approval masks after the existing v3
visibility, reliability, anatomy, image exclusion, geometry, vessel and shadow
rules, including the existing manual shadow-override policy. Drawn scope
intersects reliable manual-stroke masks and excludes joins and displacement.
It may include saved drafts; it is distinct from whole-B-scan confirmation.
All-saved scope only requires finite on-image geometry and is explicitly diagnostic:
unreviewed and denied curves can contribute, so it must not be used as a human
agreement score. Eligibility differences are reported separately from distance.

The eight named retinal surfaces are retained, including boundaries with no
paired support. CNV regions and edges are displayed from each saved journal
cursor, including drafts and uncertainty marks; they do not contribute to
retinal distance scores. Hyper_Ref paint is also displayed independently of
those scores, directly from the saved brush masks at their native coordinates.

## Why the journals were used

Compatibility NPZs and context JSONs can lag behind their journals. One lead draft,
`TS241_OD_2024-09-25_D42_s03_111600_b0200`, contains a compatibility-curve discrepancy
of up to 73.96 pixels relative to the current journal replay. It is not one of the
nine matched comparisons. The viewer consistently uses authoritative replay,
including current confirmation status, instead of mixing those representations.

## Refresh and verification

Run **[REFRESH_COMPARISON.cmd](REFRESH_COMPARISON.cmd)** after new reviews have been
saved and copied into the source folders. Then reload the viewer. Existing exports
remain snapshots of the settings/data used when they were created.

The builder and UI source are in `code/reviewer_compare/`. With `octa` activated:

```bat
python code\reviewer_compare\build.py
python code\reviewer_compare\test_compare.py
python code\reviewer_compare\verify_snapshot.py
```

The builder accepts `--lead`, `--shichu`, `--providers` and `--output` for another
drive layout. Inputs must use the supported v3 journal format; incompatible data
fail explicitly. Labels lacking journals are reported rather than silently guessed.

Validation: nine tests passed, including CNV state, uncertainty, erasure and
undo replay, plus Hyper_Ref crop coordinates, painting, erasure and undo.
All 56 reviewer records' CNV arrays and Hyper_Ref masks were independently replayed
from their saved journal cursors. All 47 native image sizes and all three
comparison scopes were checked; reviewer-swap invariance and missing-score behavior
passed; 78 journal/provider hashes were rechecked unchanged. Browser testing covered
scope and boundary changes, threshold changes, search/no-results, unmatched slices,
zoom, fit, rendered overlays, and CSV/PNG creation. The test CSV contained 4,096
rows and exactly 1,203 scored points for TS250 D24 B45, matching its viewer count.
The resulting PNG was reopened for visual verification. See `verification.json`
and `source_manifest.json` for machine-readable evidence.
