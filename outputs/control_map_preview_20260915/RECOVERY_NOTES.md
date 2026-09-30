# Atlas recovery — September 15, 2026

## What was recovered

The original data drive is mounted at `F:\OCT_TreeShrew`, although saved paths name `G:` (and some launcher settings name `E:`).

Original atlas: `F:\OCT_TreeShrew\octa\outputs\octa-seg\octa-seg_v1\control_map_v1`.
Its saved status stops during preparation at **72/314 acquisitions**. It contains 72 prepared NPZ maps and 72 source records, with no registration results or finished figures. All 144 artifacts matched the SHA256 checksums in the original preparation markers.

| Animal | OD | OS |
|---|---:|---:|
| TS165 | 10 | 10 |
| TS169 | 9 | 4 |
| TS241 | 26 | 13 |

Only three recovered scans pass the existing standalone ONH localization rules; all three use visible-edge fits. The other 69 require better localization evidence or registration before contributing to an ONH-centered atlas.

## New bounded pilot

`build_preview.py` selects each of those three anchors and its nearest scan-number neighbor from the same eye/date: six scans, three eyes, two animals. It uses the original configuration and production registration, localization, exclusions, and aggregation functions. It does not change source annotations, segmentation, or the external drive.

All three tested neighboring-scan registrations fail because of insufficient vessel-anchored structural matches. Therefore the three neighbors remain unlocalized and no repeat-tissue correspondence is claimed. Their measurements remain in local tables and native maps.

For the six selected scans, cached input fingerprints still match the thickness exports, geometry, QC masks and preparation records. Only the shared launch configuration differs from its saved checksum. This is explicitly a recovery of the September 11 prepared snapshot, not a refresh using newer review annotations. Exact comparisons are in `tables/current_input_comparison.csv`.

## Full-batch readiness

The external batch contains all ten required files for each of its 314 manifest acquisitions (3,140 files checked for existence). Its `FINAL_VERIFIED.json` records success for 314 scans, native grids and input artifact hashes. All five tables named by that proof match their saved SHA256 hashes after resolving the old drive paths to F:.

This corrects the earlier impression from the Git checkout alone that the batch audit might be unavailable. The old atlas started under an audit waiver; the completed batch proof is now present on the data drive. The current inspection has not repeated the full upstream artifact audit.

A complete atlas still requires preparing the remaining 242 scans, resolving old absolute paths and cache validity, and running registration and summaries across the full selection. The six-scan preview is not a completed full atlas or a representative healthy-retina reference. Do not pool it as such.
