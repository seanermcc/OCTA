# Correct the 30 v8 Model 1 scans

Double-click **OPEN_MODEL1_CORRECTION.cmd** here, or the launcher with the same name in the v8 folder. This uses the latest v7 desktop editor, adapted for the exact 30 acquisitions in v8's comparison set. There are **100 initial Model 1 candidate regions** across these scans; these are proposals, not 100 confirmed CNVs. Ten acquisitions were used to fit Model 1; twenty were excluded from fitting. All ten animals had training exposure.

## Review

1. Orange outlines load automatically from Model 1's conservative `filtered_mask` (threshold 0.70, original opening and 64-pixel filter). Select a region in the list. Paint (B) adds to its footprint; Erase (E) trims it. Brush size is adjustable. Drawing a closed loop fills its interior.
2. **Keep CNV (K)** confirms a real region. **Remove (Delete)** rejects a false detection. **Unsure (U)** or **Exclude area** preserves uncertain/unreadable tissue as unknown. These do not become negative examples. Region-list areas remain provisional until the image is confirmed.
3. **Add CNV (N)** draws missed lesions. Check the whole field, including outside the predictions: a conservative model can miss small CNVs. The optional **Model 1 before filtering** overlay shows suppressed candidate pixels. It is a reference and does not create labels.
4. Keep one region per lesion. If a connecting bridge joins distinct lesions, erase the bridge and choose **Split disconnected**, then review each new draft. For fragments belonging to one lesion, paint the complete footprint in one region and Remove the redundant entries. Regions can be arbitrarily small; human corrections are never size-filtered.
5. Resolve all orange drafts. Click **Confirm entire image** after checking the entire field. All kept CNVs become positive, other assessable pixels become reviewed background, and uncertain/excluded pixels remain ignored. For an assessable image without CNV, remove the proposals, check **No-CNV present**, and confirm. Defer an indeterminate image.
6. **Next pending** advances through this fixed set. Completion is 30 reviewed acquisitions, including negatives; it is not a target of 30 positives. Save and autosave preserve drafts. Restart resumes the last scan and saved corrections take priority over proposals. Every geometry/classification change invalidates confirmation; reconfirm after editing.

Both en-face panels and the linked structural B-scan retain the v7 controls. Click an en-face location in Inspect mode to select its exact native B-scan/A-line. Wheel zooms, middle-drag pans, Fit views resets, Escape returns to Inspect. Vertical B-scan bands show lateral footprint intersections, not axial lesion volume.

## Measurements

Reports refresh after annotation saves. **Export confirmed sizes** explicitly refreshes them; **EXPORT_CONFIRMED_SIZES.cmd** does the same with the GUI closed. Outputs are in `reports/quantification/`:

- `lesions.csv`: one row per kept region from an explicitly confirmed image; observed area in pixels, µm² and mm², equivalent circular diameter, physical bounding box, and size-quality flags.
- `scans.csv`: all 30 scans, completion state, number of confirmed regions, ignored pixels, and total union CNV area per scan. Overlapping regions are counted only once in scan totals.
- `summary.json`: progress, total observed area, size quantiles/mean for all observed regions and separately for eligible complete lesions. Empty distributions stay empty until human confirmation.
- `training_manifest.json` and `targets/`: derived positive/known/ignored arrays from valid current confirmations, with label revision/hash, acquisition identity, animal/visit groups and Model 1 provenance. Use only the current manifest entries; previous target revisions remain for traceability and must not be globbed into training.

Calibration is the project's approximate **1460 µm / 512 pixels** in each en-face direction (2.8515625 µm/px); area is pixel count × 8.13140869140625 µm². Measurements are **2D footprints**, not 3D volumes. FOV-edge regions, regions touching uncertainty, overlapping region entries, and disconnected regions remain in the visible-area table but are excluded from the complete-lesion size distribution. Resolve accidental overlaps or fragmentation in the editor. FOV-truncated lesions can only supply observed area, not total biological size.

The same lesion may appear in multiple acquisitions or dates. Cohort totals here sum observations, not unique biological lesions. Preserve animal/eye/visit grouping for downstream analysis. Ten previously fitted cases are identified separately; these corrections are not independent validation of Model 1.

## Storage

Current human review lives only in this folder's `review/regions/`, with version history and a separate session. Model 1 weights/predictions, the v7 GUI/reviews, original labels and processed inputs remain unchanged. Setup writes a queue and proposal provenance, never confirmed annotation files. GUI loading seeds in-memory drafts; GUI saves are the only writer of real review records.

`verification/` contains isolated synthetic records and screenshots, never training labels. `verify.py` tests proposal identity, confirmed-only sizing, physical conversion, union totals, confirmation invalidation, save/resume, real native image loading and GUI editing. See `TRAINING_PLAN.md` for the next model.
