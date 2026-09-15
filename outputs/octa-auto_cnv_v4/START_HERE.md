# CNV manual review v4

Open **OPEN_MANUAL_REVIEW.cmd** to start manual drawing on D14 with automatic proposals hidden. **OPEN_OCTA_AUTO_CNV_V4.cmd** opens the ordinary review queue. Save any unsaved work in your v3 window before opening v4.

## Paint and save

1. Leave **Structural footprint** selected, click **Paint**, and drag around the CNV. Close the loop and release: its entire interior fills. A light tint shows the selected region's filled area.
2. **Erase** trims the region. Open paint strokes add only their brush area. **Undo region edit** and **Redo** work for both filling and erasing. A loop completed in multiple strokes also fills. Ordinary brush additions preserve earlier erased holes; deliberately drawing another closed loop fills its interior again.
3. For another separate lesion, click **Draw region** and drag its outline. Paint continues editing the selected region.
4. Click **Approve footprint**, then **Save all**. For uncertain regions, choose **Other**, add a note, and click **Complete region review**, then **Save all**.

Painting alone does not approve a region. The structural footprint and candidate core remain separate.

## Three linked panels

- Left: structural OCT en-face image.
- Middle: choose **RNFL, GCL, IPL, INL, OPL, Photoreceptor composite, or RPE band** using the dropdown or Previous/Next layer. It starts on GCL.
- Right: **Full retina thickness** stays fixed as you change the middle layer.

Both thickness panels show micrometers, a color scale, and exact values at the selected native pixel below. Color scales use each layer/scan's 2nd–98th percentiles; compare the numbers, not colors across different layers. Gray means unavailable. Thickness remains missing through shadows, invalid endpoint geometry, and the existing engine's withholding rules; gaps are never filled for display or measurement. All maps use saved experimental boundaries, not validated anatomical measurements. The structural-evidence display has been removed.

The eight-boundary model measures the photoreceptor composite as one band, including ONL. It cannot supply separate ONL, ELM or inner/outer-segment maps. Full retina is ILM to outer RPE; GCL is RNFL/GCL to GCL/IPL, and IPL is GCL/IPL to IPL/INL. Axial scale is 1.12 µm/pixel. The established octa-thick engine supplies all eight maps under its existing `exclude_unreliable` pilot policy. That policy can use available neural/contextual positions and genuine saved surface edits; it is not a confidence guarantee. Boundary provenance and reasons are retained in `scan.metadata['layer_thickness']` in memory. After saving boundary edits below, click **Refresh saved thickness** to update the maps. CNV-footprint painting does not alter layer boundaries or thickness.

## Existing manual work and separate saves

Original annotations remain in `G:/OCT_TreeShrew/octa/outputs/cnv_labels/`; matching D7/D28 outlines remain cyan and selectable from **Saved manual**. See the [existing manual inventory](G:/OCT_TreeShrew/octa/outputs/octa-auto_cnv_v3/MANUAL_ANNOTATIONS.md).

If a scan has a saved v3 region review and no v4 revision, v4 opens it read-only as the starting review. Subsequent edits save to **outputs/octa-auto_cnv_v4/review/regions/**, with v3 source hashes recorded in the region events. Opening or browsing creates no human label. Once v4 has a saved revision, it takes precedence over v3; edits made later in v3 are not silently merged. Boundary edits also save under v4, while existing v3 boundary labels remain readable. Unsaved edits in an already-open v3 window cannot transfer until you save them.

## Release scope and checks

This is a new GUI release in a separate folder. It reuses the same 17 acquisitions and exact v3 proposal/data snapshots; the CNV detection rules are unchanged. V1–v3, source volumes and original annotations remain untouched. The GUI computes thickness from the existing engine at load time, so saved boundary changes can be reflected without changing automatic CNV proposals.

Run **VERIFY.cmd** for painting/editing/review tests and all-scan GUI checks. **COMPLETE.json**, **implementation_manifest.json**, **input_manifest.json**, and **verification/** record verification and provenance.
