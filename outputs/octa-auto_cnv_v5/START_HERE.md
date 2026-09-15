# CNV review v5

Save any edits in the older GUI before opening v5. All three launchers use the same editor and save folder:

| Launcher | Starting view |
|---|---|
| OPEN_OCTA_AUTO_CNV_V5.cmd | First scan, suggestions visible |
| OPEN_MANUAL_REVIEW.cmd | D14, suggestions hidden |
| OPEN_SAVED_MANUAL_D7.cmd | D7, suggestions hidden; saved manual outlines available |

## A short workflow

1. Select a suggestion or saved outline from **CNVs**, or choose **Add CNV** for a new lesion.
2. **Paint** adds pixels; a closed loop fills when released. **Erase** trims the selected region. Add CNV starts a separate region. **Keep CNV** confirms its footprint; **Remove** rejects it; **Unsure** preserves an uncertain region without turning it into a training target. Removed regions are retained in history and can be shown again or undone.
3. **Save** (Ctrl+S) saves partial work. It does not mean the entire image was checked.
4. **Finish scan** is for a genuinely complete inspection. First resolve every visible draft and saved outline, and mark unreadable or ambiguous areas **Unsure**. Its confirmation records that you checked the whole field and added all visible CNVs. Unmarked areas can then serve as reviewed background; unsure areas remain unknown. A completed scan with no CNVs and no uncertain regions is a reviewed absence. Any later edit makes the scan incomplete again.

Use **Undo/Redo** for region edits and decisions. Escape switches from painting to image inspection. Click either top image to inspect the exact B-scan/A-line. The slider and spin box move through B-scans. Wheel zooms the top images; middle-drag pans; **Fit views** resets them. Boundary editing, core/footprint switching, deficit maps and diagnostic panels have been removed.

## Two top panels and one B-scan

The left panel is structural OCT. The second panel shows **either OCTA or layer thickness**, selected from its dropdown. OCTA is the real `frame_OCTAAvg` channel, projected over the saved retinal depth crop. It is not a layer-specific OCTA slab or a thickness-derived substitute. Projection provenance and independently re-detected orientation are recorded in `octa_cache/`.

Thickness choices are Full retina, RNFL, GCL, IPL, INL, OPL, Photoreceptor composite and RPE band. In thickness mode, the B-scan shows only that layer's two endpoints, from the **same filtered/saved endpoint arrays** used to measure the map. Missing map pixels have no boundary lines across them. OCTA mode shows the structural B-scan without layer-boundary overlays. The B-scan is read-only in both modes.

Thickness units are µm, with the existing 1.12 µm/pixel axial scale. Map colors use the selected layer/scan's 2nd–98th percentile range; gray is unavailable. These remain experimental octa-seg_v1 / octa-thick measurements. Photoreceptor composite includes ONL; isolated ONL or segment thickness is not available from this eight-boundary export. This GUI does not retrain segmentation or smooth missing values.

## Your work stays separate

V5 reads the unchanged v4 scan/proposal snapshots and the current matching original manual CNV files. When no v5 review exists, the latest saved v4 region review is used, falling back to v3. Opening and browsing create no human labels. Editing a saved original outline makes a new v5 copy, with source provenance. Once v5 has its own saved revision, it takes precedence; later edits in older versions are not merged automatically.

New work saves under **outputs/octa-auto_cnv_v5/review/regions/**. Region masks, touched pixels, removed proposals, uncertainty, decisions and history are preserved. Whole-field review and whether automatic proposals were displayed are saved separately from individual region acceptance. Unedited proposals and partial unmarked areas are not automatically human ground truth. Exposure flags cover this GUI session and saved v5 provenance, not everything a reviewer may have seen in other tools. Review time is an aid for audit, not proof of a careful inspection.

The separate **plans/CNV_UNET_PLAN.md** describes the proposed model-development path. No CNV U-Net, training-data export, retraining, or automatic promotion is implemented in v5. The existing CNV suggestions remain unchanged.
