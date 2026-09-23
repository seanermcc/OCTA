# Final vessel / ONH overlay export v1

314 acquisitions: **58 saved manual records**, otherwise **256 frozen v1 proposals**.
For a manual record, both masks are copied exactly, including empty masks and drafts.
No v2 predictions are used. This is an export snapshot; subsequent GUI edits require
a new export. The original human annotations and model outputs are unchanged.

- `masks/<scan_id>.npz`: Boolean `vessel_mask` and `onh_mask`, native 512 x 512.
- `png_masks/<scan_id>_vessel.png` and `_onh.png`: lossless 0/255 binary masks.
- `overlays/<scan_id>_vessel.png` and `_onh.png`: transparent RGBA overlays,
  blue vessels and green ONH. Draw at the same size and origin as the en-face image.
- `manifest.json` / `inventory.csv`: acquisition identity, selected source and hash,
  review flags, annotation revision, notes, exclusion status, and output paths.
- `cnv_v8_mapping.json`: checked matches to the current CNV v8 30-acquisition set.
- `VERIFIED.json`: results of source-pixel, export, PNG and CNV grid verification.

All coordinates are **[B-scan, A-line]**, row = B-scan, column = A-line.
Use the native upper-left image origin: no resize, transpose, registration or flip.
Depth orientation is inapplicable to these en-face masks. CNV v8 uses the same
native acquisition grid, although its projection depth range can differ.

The fallback ONH mask is v1's existing human ONH exclusion mask. An empty fallback
does not prove ONH absence; v1 has no automatic ONH detector. Review flags are
preserved separately for vessel and ONH. Manual exports retain brush footprints,
uncertain-region masks, ONH edge masks and original scalar metadata. Untouched
automatic pixels are not new human training labels. Two previously excluded
poor-quality scans are included for complete visual export, with their exclusion
flags preserved; inclusion does not approve them for analysis or training.

## Load for the CNV v8 workflow

After activating the `octa` environment:

```python
import sys
sys.path.insert(0, r'G:\OCT_TreeShrew\octa\outputs\octo-vessel_onh_v2\final_output_v1')
from load_masks import load_masks

# a is the CNV v8 acquisition record.
masks, provenance = load_masks(a['scan_id'], a['source'])
vessel = masks['vessel_mask']
onh = masks['onh_mask']
# Display these independently on native structural OCT or OCTA en-face images.
# Inspect provenance['excluded_from_analysis'] and per-target review status
# before any analysis/training use. Neither mask modifies a CNV prediction.
```

The CNV model/viewer has not been modified by this export. Arrays and transparent
PNGs are ready for its overlay controls or another image viewer. A missing scan
raises an error rather than silently supplying an empty mask.

To recheck this frozen export, run `python build_export.py --verify` in this folder.
The builder refuses to overwrite an existing manifest.
