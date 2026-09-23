# TS241 OD: bounded local alignment

Started from saved v2 human review revision 194, confirmed montage. Original files remain unchanged.

14 of 26 fields received small automatic adjustments. Field 6 is fixed. Maximum center movement: 7.999 native px; maximum absolute rotation: 1.000°; maximum corner movement: 12.559 px.

76 usable existing overlaps. Mean held-out alignment score: 0.3488 before -> 0.3701 after. Improved pairs: 47; decreased by more than .002: 17. These are internal registration scores, not independent anatomical accuracy.

The objective combines broad structural vessel contrast, locally normalized detail, and detail outside dilated large-vessel masks. Only already overlapping images were considered. Spatially interleaved pixels held out from fitting were used to accept/reject each proposal. At most five stronger neighbors influence a field; flagged fields cannot pull supported fields. All limits are relative to the original saved pose, not cumulative between passes. Scale, shear, and reflection are forbidden.

The original flagged/supported categories and notes are retained exactly. Modified images lose individual confirmation in this new proposal; unchanged confirmations are retained with source attribution. The new whole montage is unconfirmed. Source review history is untouched. Pink CNV overlays retain the frozen v3 display sources and did not drive this local fit.

Residual mismatch can remain from image contrast, vessel projection width, motion, or scale differences. Local rigid adjustment cannot remove those distortions. No layer or CNV segmentation was rerun.

| Field | Center shift (px) | Rotation (degrees) | Maximum corner shift (px) |
|---|---:|---:|---:|
| 1 | 0.489 | +0.133 | 1.294 |
| 2 | 0.059 | -0.298 | 1.925 |
| 3 | 7.742 | -0.880 | 12.559 |
| 4 | 0.000 | +0.000 | 0.000 |
| 5 | 2.773 | +0.922 | 8.170 |
| 6 | 0.000 | +0.000 | 0.000 |
| 7 | 1.859 | +0.006 | 1.889 |
| 8 | 0.000 | +0.000 | 0.000 |
| 9 | 4.644 | +0.717 | 8.807 |
| 10 | 0.000 | +0.000 | 0.000 |
| 11 | 0.000 | +0.000 | 0.000 |
| 12 | 0.000 | +0.000 | 0.000 |
| 13 | 0.000 | +0.000 | 0.000 |
| 14 | 0.000 | +0.000 | 0.000 |
| 15 | 7.999 | -0.397 | 10.194 |
| 16 | 0.000 | +0.000 | 0.000 |
| 17 | 0.000 | +0.000 | 0.000 |
| 18 | 3.211 | +1.000 | 9.409 |
| 19 | 1.324 | +0.552 | 4.638 |
| 20 | 2.982 | -0.271 | 4.657 |
| 21 | 1.965 | -0.813 | 7.087 |
| 22 | 0.000 | +0.000 | 0.000 |
| 23 | 2.774 | -0.410 | 5.091 |
| 24 | 0.000 | +0.000 | 0.000 |
| 25 | 0.334 | -0.567 | 3.880 |
| 26 | 1.822 | -0.070 | 2.259 |