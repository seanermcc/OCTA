# TS165 OD vessel-size check — 2026-09-22

Read-only analysis of the ten native prepared images and current v2 review revision 87. No montage, human decisions, masks, or calibration were changed.

## Findings

The width discrepancy is present in the source en-face projections. All ten are 512 x 512, and every saved placement has unit singular values: the reviewer rotates/translates without scan-specific zoom. The shared lateral calibration is approximate, not independently validated per acquisition. The processed MATLAB file inspected (scan 9) contains only the two 512 x 512 x 1024 image channels, without an optical magnification setting.

Matched structural dark-band widths at half local contrast (not anatomical vessel diameter):

| Comparison | Sites | First scan, px | Second scan, px | Second / first |
|---|---:|---:|---:|---:|
| 1 vs 9 | 4 | 23.9–25.1 | 31.4–33.5 | 1.3–1.4 |
| 8 vs 9 | 2 | 32.3–33.3 | 31.4–31.8 | 0.9–1.0 |
| 7 vs 8 | 2 | 27.0–28.3 | 31.8–32.7 | 1.1–1.2 |
| 4 vs 7 | 3 | 16.1–17.6 | 18.3–18.9 | 1.1–1.2 |

The 4 vs 7 comparison concerns the narrower central trunk; the other pairs concern the giant trunk. Sites differ between pair comparisons, so these ranges should not be treated as identical-segment measurements across all four scans. Edge-crossing profiles were rejected.

## Scale interpretation

Diagnostic rotation/translation/scale fits of scan 9 against scans 1, 2, and 3 favored approximately 1.20–1.25 times enlargement of the earlier images. Scan 1 coarse correlation increased from 0.72 (rigid) to 0.86–0.87 (scale permitted); scan 3 from 0.80 to 0.89. These fits describe an effective image-scale mismatch, not calibrated optical zoom. Fine-band image correlation includes vessel edges and is not independent small-vessel validation. Trunk-excluded correlations remained modest (~0.23–0.28 for the best scan 1/3 vs 9 fits). A uniform rescale does not align every small branch.

Scans 7 and 8 have similar fitted overall scale (~1.02 for 7 -> 8) but a 13–21% width difference in their overlapping giant trunk. Scan 8 and 9 giant-trunk widths differ by only ~2–6% at the sampled sites. Scan 7 is close to unit scale in its limited overlaps with 4 and 5, yet its narrower central trunk is ~6–17% broader than scan 4. Thus there is no defensible single zoom factor shared by 7–9. Projection/contrast broadening and spatial distortion remain possible explanations; acquisition optical magnification cannot be established from the available processed images alone.

## Method and limitations

Native structural images were used, not vessel-mask widths. Cross-vessel profiles average seven along-vessel samples, smooth at sigma 1 pixel, and measure the outer half-depth crossings relative to a linear local background. Local rotations were used to place approximately corresponding transects; widths remain in each image’s native pixels. Four scan 1/9 sites and two each for 7/8 and 8/9 are a targeted check, not an exhaustive vessel-diameter study.

Automatic SIFT correspondences were mostly sparse, clustered, or false; pair_fits.json is exploratory output and its scales are NOT accepted measurements. Similarity fits are diagnostic only and were never written into the registration. Low-scoring fits and trial failures remain recorded for transparency. Full-frame montage quality must not be inferred from a large-trunk correlation alone.

Files: native_vessel_comparison.png (equal pixel-scale visual); width_profiles_1_9.png (transects/profiles); width_measurements.json (coordinates and measured widths); source_audit.json (source hashes and saved rigid-transform checks).