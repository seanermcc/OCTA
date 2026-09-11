# En-face annotation and segmentation-review GUI

**Created:** 2026-09-09  
**Project:** OCT-A tree shrew CNV pipeline  
**Primary program:** [`code/eight_surface/cnv_gui.py`](../code/eight_surface/cnv_gui.py)

## Executive summary

The former CNV footprint-labeling window is now an integrated en-face
annotation and retinal-surface review tool. It retains the paired structural
OCT and OCTA en-face images, adds the automated eight-boundary segmentation to
the linked structural B-scan at the bottom, and connects that preview to the
existing provenance-aware manual segmentation editor.

The window supports three independent en-face area labels:

1. CNV footprint.
2. Vasculature or vessel-affected area.
3. Optic nerve head (ONH) footprint.

CNV can be drawn either as a closed outline or with a round brush.
Vasculature and ONH are painted with an adjustable round brush rather than a
closed boundary tool. The three masks remain independent from retinal-surface
labels and do not automatically exclude any surface or thickness measurement.

The B-scan preview displays the automated segmentation as dashed colored
lines. If a saved manual correction exists for that B-scan, the corrected
surfaces are displayed as solid colored lines over the unchanged automatic
baseline. Double-clicking the B-scan opens only that line in the established
manual segmentation window, where it can be accepted, corrected, rejected, or
marked locally invisible/unreliable.

## Why the GUI was built this way

The interface deliberately keeps several different questions separate:

- **Where is CNV, vasculature, or ONH in the en-face field?** Answered by the
  three two-dimensional en-face masks.
- **Is an automated retinal boundary correctly positioned?** Answered only in
  the manual B-scan segmentation editor.
- **Can a boundary be seen or measured at a particular A-line?** Answered by
  the surface editor's local visibility and reliability marks.
- **Is the entire B-scan column unusable for every boundary?** Answered by the
  existing B-scan whole-column exclusion gesture.

These states are not interchangeable. A vessel mask does not prove that a
surface is wrong, an ONH mask does not by itself decide which boundaries are
measurable, and a plausible automatic surface is not automatically human
ground truth.

The separate-window design was chosen for B-scan correction because the
existing editor already records exact stroke provenance, taper regions,
ordering displacement, visibility, reliability, exclusions, review time, and
verdicts. Embedding a second simplified surface editor inside the en-face
window would have duplicated that logic and risked producing incompatible or
weaker labels.

## Screen layout

The main window has three linked image panels:

- **Top left — structural OCT en face.**
- **Top right — OCTA en face.**
- **Bottom — structural B-scan with segmentation overlays.**

Both en-face panels use the acquisition's native `[B-scan, A-line]` grid. A
cyan crosshair identifies the selected B-scan and A-line in both panels. The
same A-line is shown as a cyan vertical cursor on the B-scan.

The right side panel contains:

- Previous/next scan controls.
- Direct B-scan number entry and a B-scan slider.
- Previous/next B-scan buttons.
- A segmentation-overlay visibility toggle.
- A button to open the current B-scan in the manual surface editor.
- Adjustable brush-head diameter.
- Independent CNV, vasculature, and ONH review checkboxes.
- Whole-mask clearing controls.
- Separate structural and OCTA brightness/contrast controls.
- Notes and annotation progress/status.

## En-face annotation controls

### Modes

| Mode | Purpose | Shortcut |
|---|---|---:|
| Navigate | Select a B-scan/A-line from either en-face image | `N` |
| CNV outline | Draw a closed CNV footprint; it closes and smooths on release | `D` |
| CNV brush | Paint or erase CNV directly | `B` |
| Vasculature brush | Paint or erase the vasculature mask | `V` |
| ONH brush | Paint or erase the filled ONH footprint | `O` |

### Brush gestures

- Left-drag or right-drag paints the active mask.
- Ctrl+right-drag erases the active mask.
- The brush-head diameter can be changed from 1 to 160 native pixels.
- A round cursor preview shows the brush footprint at the current zoom.
- Brush paths are interpolated continuously, preventing holes when the mouse
  moves quickly.

The right-drag behavior mirrors the existing B-scan convention in which a
right-drag marks an excluded region and Ctrl+right-drag clears it.

### Undo, redo, and clearing

Undo and redo preserve all three masks, the legacy ONH edge, and the three
per-class review states together. Clearing a whole mask requires confirmation.
Clearing is treated as an explicit review decision: an empty reviewed mask
means the class was inspected and judged absent.

An old ONH edge can be removed with **Old edge** under **Clear a whole mask**.

## Per-class review status

Each en-face class has an independent review checkbox:

- `CNV reviewed`
- `Vasculature reviewed`
- `ONH reviewed`

This distinction is essential for training:

- **Checked and non-empty:** reviewed positive mask.
- **Checked and empty:** reviewed and absent.
- **Unchecked and empty:** unknown; nobody has supplied a negative label.

Painting a class automatically marks that class reviewed. **Mark all three
reviewed** is available as a shortcut after all three classes have actually
been inspected.

Changing scan or closing the main window saves unsaved en-face changes.
`Ctrl+S` saves explicitly.

## Automated and manual segmentation display

The B-scan preview uses the current eight-boundary definition:

1. `ILM`
2. `RNFL_GCL`
3. `GCL_IPL`
4. `IPL_INL`
5. `INL_OPL`
6. `OPL_ONL`
7. `PR_RPE`
8. `RPE`

Display conventions:

- **Dashed colored line:** current automated segmentation.
- **Solid colored line:** saved manual correction.
- **Accepted:** the automatic result was reviewed and accepted.
- **Corrected:** at least one boundary was corrected in the manual editor.
- **Rejected:** the B-scan was rejected for surface review.
- **Unreviewed:** no saved surface verdict exists for that B-scan.

The segmentation overlay can be hidden without changing any annotation.

### Opening the manual editor

Double-click the bottom B-scan or press **Check/correct this B-scan**. The GUI
creates a persistent one-line review pack in:

```text
outputs/eight_surface/enface_line_review/
```

That pack contains the selected structural B-scan, automatic surfaces,
confidence, shadow mask, native B-scan index, current cascade version, and
source-segmentation provenance. It then opens the existing editor from
[`code/eight_surface/label_gui.py`](../code/eight_surface/label_gui.py).

Only that established editor writes retinal-surface labels. Existing automatic
baselines are preserved when a manual label is reopened, even if the volume was
subsequently re-segmented under the same cascade name.

## Surface-review controls in the separate window

The separate surface editor retains its established controls:

| Gesture/control | Meaning |
|---|---|
| Left-drag | Redraw the active boundary |
| Shift+left-drag | Explicitly reviewed: automatic line is right here |
| Right-drag | Exclude an A-line range for every boundary |
| Ctrl+right-drag | Clear the whole-column exclusion |
| Shift+right-drag | Active boundary cannot be identified here |
| Ctrl+Shift+right-drag | Restore local visibility |
| Alt+right-drag | Active boundary is locally unreliable |
| Ctrl+Alt+right-drag | Restore local reliability |
| `A` | Accept the automatic B-scan |
| `X` | Reject the B-scan |
| `Ctrl+S` | Save |

Surface labels continue to distinguish human strokes, software taper,
ordering displacement, explicit review, untouched automatic output, local
visibility, local reliability, and whole-column exclusions.

## Label files

### En-face labels

En-face labels are stored in:

```text
outputs/cnv_labels/<scan_id>_cnv.npz
```

The current format is:

```text
3-enface-multiclass-brush
```

Important fields include:

| Field | Shape/type | Meaning |
|---|---|---|
| `cnv_mask` | `[B-scan, A-line]` boolean | CNV footprint |
| `vasculature_mask` | `[B-scan, A-line]` boolean | Vasculature/affected area |
| `onh_mask` | `[B-scan, A-line]` boolean | Filled ONH footprint |
| `onh_edge_mask` | `[B-scan, A-line]` boolean | Preserved legacy ONH edge |
| `annotation_names` | three strings | `CNV, VASCULATURE, ONH` |
| `reviewed_targets` | three booleans | Per-class reviewed/unknown state |
| `source_volume` | string | Processed structural/OCTA volume |
| `source_segmentation` | string | Segmentation used when labeling |
| `retina_band` | two integers | Stored source-depth crop |
| `vitreous_at_high_index` | boolean | Orientation detected from the data |
| `revision` | integer | Monotonically increasing save revision |
| `labelled_at` | timestamp | Save time |
| `labeller` | string | Operating-system user unless supplied |
| `notes` | string | Free-text annotation notes |

The en-face file deliberately contains no retinal surfaces or thickness maps.

### Surface labels

Manual B-scan labels remain in:

```text
outputs/eight_surface/labels/
```

They continue to use the independent local-provenance surface-label format.
The en-face GUI reads these labels only to display verdicts and saved manual
corrections.

## Backward compatibility

Both earlier en-face formats remain readable:

- `1-enface-footprint`
- `2-enface-footprint-onh-edge`

No existing label is rewritten merely by opening or navigating through it.
When an older label is loaded:

- Its CNV footprint and CNV reviewed state are preserved.
- Its ONH edge is preserved and shown as a bright green line.
- A positive ONH edge counts as evidence that ONH was inspected.
- No filled ONH area is fabricated from the edge.
- Vasculature remains unknown.
- An empty legacy ONH edge remains unknown rather than becoming an ONH-negative
  label.

Therefore an existing ONH boundary does **not** need to be redrawn. A filled
ONH mask is needed only if the project wants an ONH area target for training or
regional analysis.

## Data loading and orientation safeguards

The GUI starts from current `*_processedVolumes.mat` products through their
segmentation outputs. It never reconstructs data from `.RAW` files.

[`code/eight_surface/cnv_data.py`](../code/eight_surface/cnv_data.py) performs
the following checks:

- Requires the current eight-boundary cascade version.
- Requires the stored surface names to match the current definition exactly.
- Loads the segmentation arrays only for B-scan overlays, never to construct
  en-face ground truth.
- Reads structural and OCTA projections independently from the processed
  volume.
- Re-detects orientation from the structural depth profile and ignores the
  historically unreliable stored orientation flag.
- Uses the segmentation's stored retina crop so B-scan pixels and surface
  coordinates remain aligned.
- Verifies surface, confidence, shadow, B-scan, and A-line dimensions.
- Reads the structural retina band once so navigating between B-scans does not
  repeatedly decompress the same HDF5 chunks.

Canonical display orientation remains vitreous at depth zero.

## Files changed or added

| File | Role |
|---|---|
| [`code/eight_surface/cnv_gui.py`](../code/eight_surface/cnv_gui.py) | Integrated GUI, brush interaction, overlays, B-scan navigation, and separate-window launch |
| [`code/eight_surface/cnv_data.py`](../code/eight_surface/cnv_data.py) | Loads and validates surface arrays alongside structural/OCTA image data |
| [`code/eight_surface/cnv_labels.py`](../code/eight_surface/cnv_labels.py) | Version-3 multi-class en-face label schema and backward-compatible loader |
| [`code/eight_surface/test_cnv_workflow.py`](../code/eight_surface/test_cnv_workflow.py) | Multi-class label, brush, and legacy-format tests |
| [`code/test_enface_segmentation_gui.py`](../code/test_enface_segmentation_gui.py) | Off-screen integrated GUI and one-line manual-editor test |
| [`code/eight_surface/README.md`](../code/eight_surface/README.md) | Updated operating instructions |
| [`README.md`](../README.md) | Added the integrated GUI to the quick-start table |

## Validation performed

The implementation was checked in the activated `octa` environment.

- Python compilation passed for all changed Python modules.
- 46 relevant tests passed.
- The test suite covered:
  - Multi-class label save/load and revisioning.
  - Adjustable continuous round-brush rasterization.
  - Version-2 label compatibility without invented negative masks.
  - En-face GUI mask painting and saving.
  - Automated surface overlay construction.
  - One-line review-pack creation.
  - Opening the real manual surface-editor window for the selected line.
  - Existing eight-surface label and reliability behavior.
  - Local drawing/review/visibility/reliability provenance.
  - Existing full-volume GUI navigation.
- All 28 existing en-face labels loaded successfully without being rewritten.
- One current real processed volume was read as a smoke test:
  - Native grid: `512 x 512`.
  - B-scan crop: `531 x 512`.
  - Surfaces: `512 x 8 x 512`.
  - Retina band: source-depth indices `56:587`.
  - Orientation was detected as vitreous at the high stored index and displayed
    canonically after preparation.

At the time of implementation, the configured segmentation directory contains
32 volumes from 11 animals. Twenty-eight have an existing en-face label and
four do not. Existing labels predate the vasculature and filled-ONH masks, so
those new classes remain unknown until explicitly reviewed.

## Recommended first labeling round

The recommended immediate task is en-face labeling, not a fixed quota of
B-scan corrections.

1. Review approximately 30 diverse volumes for CNV, vasculature, and ONH.
2. Make sure empty masks are explicitly checked as reviewed only after the
   relevant class has actually been inspected.
3. Choose a smaller calibration subset of approximately 6–10 volumes.
4. In each calibration volume, inspect about two B-scans:
   - One through a CNV core, ONH, or vessel-affected region.
   - One clean comparison line.
5. Accept the automatic segmentation when it is correct.
6. Correct only genuine errors; do not create corrections to meet a quota.
7. Retain local not-visible and unreliable marks wherever the image cannot
   support a trustworthy boundary.

This supplies roughly 12–20 strategically reviewed B-scans without spending
time redrawing already-correct lines. The project already has 102 corrected
B-scans, so this calibration round can focus on measuring regional failure
rather than immediately expanding the correction count.

## Modeling outlook

Thirty full en-face labels can support a useful feasibility experiment but are
not equivalent to millions of independent samples. Pixels within a volume are
strongly correlated, and repeated scans from one animal are not independent.
Evaluation should therefore remain animal-excluded rather than splitting
pixels or neighboring B-scans randomly.

### En-face model

A first model could use paired structural and OCTA projections with separate
CNV, vasculature, and ONH output heads. Appropriate uses include:

- CNV footprint proposal.
- ONH localization and exclusion from inappropriate retinal-layer analyses.
- Vasculature or vessel-shadow localization.
- Active-learning suggestions for the next scans to annotate.

Automatically predicted masks should remain proposals until tested on animals
excluded from training.

### Improving retinal-surface segmentation

The en-face masks can support surface-model improvement without being treated
as boundary ground truth. Useful analyses include:

- Compare manual surface error inside and outside CNV, ONH, and vascular
  regions.
- Select CNV-core, lesion-rim, vessel-heavy, ONH-adjacent, and clean-control
  B-scans for manual review.
- Train a boundary-visibility or regional-reliability head.
- Hard-mine B-scans where the surface model is uncertain and the biological
  mask indicates an important region.
- Test whether a lesion-aware choice of B-scan averaging is beneficial. The
  current measurements show control scans improving with more averaging while
  CNV scans often worsen in total-retinal thickness, making this a promising
  measured question rather than a setting to change globally.

Vascular areas should not be excluded automatically. The earlier apparent
vessel-contamination signal fell to correlations of at most 0.08 after shared
spatial trend was removed. The new masks should first be used to measure
whether corrected surface errors, confidence, or local visibility actually
change in vessel-affected regions.

## Open annotation decision

Before a large labeling pass, define exactly what `vasculature_mask` means.
There are two scientifically different targets:

1. **Visible vessel anatomy** on the en-face OCTA projection.
2. **Vessel-shadow or vessel-affected area** where B-scan layer segmentation
   may be disrupted.

For optimizing retinal-surface segmentation, the second target is more direct.
For building a general vessel detector, the first is appropriate. If both goals
matter, they should become two separate masks before extensive labeling rather
than mixing two meanings inside one training target.

## Launch command

From `G:\OCT_TreeShrew\octa\code`, after activating the environment:

```powershell
conda activate octa
python eight_surface\cnv_gui.py ..\outputs\eight_surface\segmented `
  --labels ..\outputs\cnv_labels `
  --surface-labels ..\outputs\eight_surface\labels
```

Optional one-line pack destination:

```powershell
  --line-review ..\outputs\eight_surface\enface_line_review
```

