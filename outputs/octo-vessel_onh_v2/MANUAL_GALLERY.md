# v1 / manual / v2 comparison

Open **v1_manual_v2.html** or **OPEN_GALLERY.cmd**. The former index is archived as
**index_archived_20260915.html**, with its model display name corrected to **v2**.
The original index URL redirects to the new comparison.

September 15, 2026 inventory: **58 latest saved manual segmentations**, then
**27 flagged scans without a saved manual segmentation**, then **229 remaining
scans**. Manual scans show **v1 / manual / v2**; other scans show **v1 / v2**.
The starting flags come from the saved 85-scan vessel/ONH review queue. Existing
browser flags are merged, so later triage can change the second group's count.

The latest masks come from `../octo-vessel_onh_v1/labels`; they include 16 saved
records added since the 42-record training snapshot. Review status and ONH
visibility appear on each manual card. Saved masks may contain untouched v1
pixels, and unfinished targets remain drafts. No annotation, review decision,
model, or prediction is modified. The frozen training snapshot and independent
held-out results remain available as alternate views. Scored-support overlays
refer to that frozen snapshot and are not overlaid on the newer manual panel.

## Rebuild

In the activated `octa` environment, build into a separate output folder:

```bat
python build_manual_gallery.py --release F:\OCT_TreeShrew\octa\outputs\octo-vessel_onh_v2 --destination D:\Projects\octa\outputs\vessel_manual_gallery_preview
node check_manual_gallery.cjs D:\Projects\octa\outputs\vessel_manual_gallery_preview
```

`manual_gallery_manifest.json` records annotation revisions/hashes and queue
provenance. The builder verifies all image paths, source identities and geometry,
and checks each rendered manual overlay against the source mask pixel-for-pixel.
The Node check executes the page script offline and checks panel order, section
counts, filters, search, exclusions, and archived v2 naming. Browser visual QA
was unavailable because the browser URL policy blocked the local file URL.

Publication uses the existing gallery assets and adds only the new manual
overlays/data/HTML, an archived comparison, and the updated launcher/templates.
The original HTML bytes are also preserved in `index_original_20260915.html.bak`.
