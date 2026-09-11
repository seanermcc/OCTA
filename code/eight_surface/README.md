# Eight-boundary OCT review workflow

This folder is a new workflow.  It does not replace or modify the original
ten-surface GUI and its labels.

The only drawn boundaries are, in order:

```
ILM, RNFL_GCL, GCL_IPL, IPL_INL, INL_OPL, OPL_ONL, PR_RPE, RPE
```

`PR_RPE` is the former RPE-complex peak. `RPE` is its outer edge (the endpoint
formerly named BM). ELM and IS/OS are not drawn. The band from `OPL_ONL` to
`PR_RPE` is reported as `PHOTORECEPTOR`.

From `code`, with `conda activate octa`:

```powershell
# first smoke test
python eight_surface/batch_segment.py --limit 2

# batch output is isolated from the old cascade
python eight_surface/batch_segment.py

# Select from the supplied ranked QC workbook: 16 bottom-score volumes, 8 near
# the 50th percentile, and 8 near the 90th percentile. The final queue is
# 96 low : 32 medium : 32 high B-scans.
python eight_surface/select_review_scans.py `
  --workbook C:\Users\seane\Downloads\oct_scan_quality_ranked.xlsx

# segment just those selected volumes with the new eight lines
python eight_surface/batch_segment.py `
  --selection ..\outputs\eight_surface\qc_review_groups.csv

# Build the 1:1:3 quality mix. Each scan also carries median-ranked B-scan
# controls, so correction is never taught only on its own failures.
python eight_surface/review.py pack --all ..\outputs\eight_surface\segmented `
  --selection ..\outputs\eight_surface\qc_review_groups.csv --group low `
  --n 5 --out-dir ..\outputs\eight_surface\review
python eight_surface/review.py pack --all ..\outputs\eight_surface\segmented `
  --selection ..\outputs\eight_surface\qc_review_groups.csv --group medium `
  --n 3 --out-dir ..\outputs\eight_surface\review
python eight_surface/review.py pack --all ..\outputs\eight_surface\segmented `
  --selection ..\outputs\eight_surface\qc_review_groups.csv --group high `
  --n 3 --out-dir ..\outputs\eight_surface\review

# resume automatically at the next undecided B-scan
python eight_surface/label_gui.py ..\outputs\eight_surface\review
```

After the packs are made, preserve an immediately comparable pre-manual image
for every selected volume. The chosen B-scan is the pack's median control, so
it is included in the GUI queue:

```powershell
python eight_surface/prepost_images.py pre
```

This writes `outputs\pre-images_8layer_Gui\` plus a manifest tying each image
to its pack and B-scan. After manual labels exist, make matched post-manual
images with `python eight_surface/prepost_images.py post`.

## What the B-scan editor records, and at what scale

Four judgements, deliberately kept apart. Conflating any two of them is how
this workflow poisons its own training set.

| scope | control | meaning |
|---|---|---|
| whole B-scan, all boundaries | right-drag | the **image** is unusable in these A-lines: shadow, edge artefact, no signal. Nothing can be measured here. |
| whole B-scan, one boundary | list checkbox / `q` | do not analyse this boundary anywhere in this B-scan; the directly adjacent layers become `NaN`. The line stays drawn. |
| whole B-scan, one boundary | `v` | this boundary was not visible **anywhere** in this B-scan. |
| **A-line range, one boundary** | shift/alt+right-drag | this boundary cannot be identified confidently *here*, or is not reliable enough to analyse *here*, while every other boundary in the same columns is untouched. |

The local marks are the new ones, and they are what the CNV round needs. Beside
a lesion the outer `RPE` edge is perfectly visible; through its centre it is
not; and the `ILM` is fine all the way across. Before this existed the only
options were to disable the outer boundary for the entire B-scan or to exclude
those columns for every boundary at once, and both throw away measurements that
the image actually supports.

"Not visible" is a statement about the recorded image. It is **not** a claim
that the tissue is absent — an obscured RPE and a destroyed RPE look the same
here, and this format deliberately cannot tell them apart.

### Local controls

```
shift+right-drag       active boundary: cannot identify confidently here
ctrl+shift+right-drag  active boundary: restore visibility here
alt+right-drag         active boundary: locally unreliable for analysis
ctrl+alt+right-drag    active boundary: locally reliable
shift+left-drag        active boundary: reviewed, the automatic line is right
u                      active boundary: back to unreviewed
```

The ruler across the top of the image shows the active boundary's state in
every column: grey unreviewed, green drawn or reviewed, magenta not
identifiable, amber unreliable. Local marks are also drawn as translucent bands
along the boundary itself, so the pixels being judged stay readable.

**Unknown is a third state.** A column nobody has ruled on is not visible and
not invisible, and no consumer may read it as either.

### Drawing provenance is recorded automatically

Every A-line of every boundary carries one code, derived from what actually
happened to it:

| code | meaning | boundary-position evidence? |
|---|---|---|
| `drawn` | a human stroke covered this column | **yes — the only one** |
| `taper` | software join fading the stroke offset back onto the automatic line | no |
| `displaced` | the ordering constraint moved it; nobody drew it | no |
| `drawn_then_displaced` | drawn, then shoved by ordering. History kept, trust withdrawn | no |
| `reviewed` | a human explicitly reviewed the automatic line and left it | no — it is a visibility/measurability label, not a position target |
| `auto` | untouched automatic output | no |
| `unavailable` | a label written before this format recorded any of this | see below |

A stroke over 40 A-lines marks 40 A-lines, not the whole boundary. Support is
taken from the stroke itself, never from `surfaces - auto_surfaces`: a column
can differ by nothing because the automatic answer was already right, and by a
lot because the taper moved it.

Undo, redo, `r`, `shift+R`, save and resume all carry this history with the
line. An undo that restored the line while leaving the file claiming a human
drew there would be worse than no history at all.

## Label format `3-local-provenance`

New arrays, all `[8, A-line]`: `local_drawn`, `local_taper`,
`local_displaced`, `local_reviewed`, and the tri-state `local_visibility` and
`local_reliability` (`0` unknown, `1` yes, `2` no). The existing `[8]` flags
`surface_edited` / `surface_displaced` / `surface_visible` / `surface_reliable`
and the `[A-line]` `region_excluded` are still written and still mean exactly
what they always meant, so an older reader sees what it always saw. The `[8]`
flags are now *derived* from the local record rather than tracked separately,
which is what stops the two levels from disagreeing.

### Legacy labels — the conservative policy

Every label written before this format loads unchanged and reports
`local_provenance_available = False`. Nothing migrates them, and no script
rewrites human evidence; `label_gui.py` via `eight_surface/labels.py` remains
the only writer. Resuming a pack that contains a legacy label does not upgrade
its silence into a claim either.

The only inference made on a legacy file is the one that is actually sound: a
boundary whose `surface_edited` and `surface_displaced` flags are both false
was touched by nobody, so every column of it is genuinely `auto`. Everything
else becomes `unavailable` — explicitly "this file never recorded it" — rather
than a guessed stroke extent, because `surfaces - auto_surfaces` cannot recover
intent.

Consumers choose what to do with `unavailable` through `legacy_policy`:

- **`"surface_flag"`** (default) — treat a boundary flagged `surface_edited` as
  if the human had drawn every non-excluded column of it. This reproduces
  exactly what every consumer did before this format existed, verified column
  for column on all 101 corrected labels currently on disk (296,789 supervised
  columns, identical mask). It is an *approximation of unrecorded intent*, and
  it over-claims by however much of the boundary the stroke did not cover.
- **`"strict"`** — legacy files supply no boundary-position supervision at all.
  Nothing is invented. Use it to measure what the approximation above is worth.

Legacy files never supply local visibility supervision under either policy:
their columns are `unknown`, which carries zero weight and is never read as
"not visible". A whole-surface flag switched *off* is honoured, and forces "no"
in every column; a flag left on is the default, not a positive claim.

The recommended audit is to relabel a small subset of existing corrected
B-scans in the new GUI and compare `"surface_flag"` supervision against the
recorded strokes on the same images. Until that is measured, treat any result
that leans on legacy labels as carrying an unquantified over-claim.

## B-scan labels downstream

`auto_seg_8layer_v2/unet/targets.py` now masks per boundary **and per A-line**:

- `column_valid(record, legacy_policy)` — the `[8, A-line]` mask everything
  else is built from.
- `boundary_weight` — zero wherever the human gave no answer *in that column*.
- `region_column_supervised` / `region_weight` — a region is supervised in a
  column only when **both** of its bounding surfaces are valid in that same
  column. This is what stops a lesion core, where the outer boundary is
  unidentifiable, from being supervised as a confidently measured RPE band
  because the same boundary was drawn 200 A-lines away.
- `visibility_target` / `visibility_weight`, `reliability_target` /
  `reliability_weight` — measurability supervision on its own mask, with
  `unknown` columns at zero weight.
- `reviewed_only` — explicit review, returned separately so it can be counted
  or fed to a measurability head, and never mistaken for a drawn position.

`volume.thickness_maps` accepts `surface_reliable` as `[surface]`,
`[B-scan, surface]` or `[B-scan, surface, A-line]`. Only the last can blank the
RPE band through a lesion core while leaving the inner layers measured in the
same columns. Whole-column exclusions and shadow masking are unchanged.

Run the tests with `python eight_surface/test_local_provenance.py` from `code`.
They use synthetic fixtures in temporary directories; the only contact with the
real label directory is a read-only check that every existing file still loads
and is not modified.

After manual corrections:

```powershell
python eight_surface/review.py refit `
  --labels ..\outputs\eight_surface\labels `
  --out ..\outputs\eight_surface\priors_refit.json

# only if the report identifies trusted systematic corrections
python eight_surface/batch_segment.py `
  --priors ..\outputs\eight_surface\priors_refit.json --overwrite
```

The refit consumes only boundaries that were actually redrawn, visible, and
left included in analysis, excluding hand-marked bad A-lines. It will not learn
from automatic lines echoed into an accepted label file.

## Integrated en-face labels and segmentation review

The en-face masks remain independent of the retinal-surface labels. The editor
shows structural and OCTA projections plus a linked B-scan at the bottom. The
bottom panel overlays all eight automated surfaces as dashed colored lines.
When a saved correction exists, it is shown as a solid line over the unchanged
automatic baseline.

From `code`, after activating `octa`:

```powershell
python eight_surface/cnv_gui.py ..\outputs\eight_surface\segmented `
  --labels ..\outputs\cnv_labels `
  --surface-labels ..\outputs\eight_surface\labels
```

The two en-face panels share native `[B-scan, A-line]` coordinates. In
**Navigate** mode, click either panel to update the B-scan, use the row slider,
or press Page Up/Page Down. Double-click the bottom B-scan (or use
`Check/correct this B-scan`) to open just that row in the established manual
editor. Acceptance, correction strokes, visibility/reliability marks, and
B-scan exclusions are therefore saved by `label_gui.py` with their normal
provenance. One-line packs are retained in
`outputs/eight_surface/enface_line_review/` so a surface label's source-pack
reference is not disposable.

The en-face editor stores three distinct area masks:

| colour | class | tools |
|---|---|---|
| red | CNV | closed outline or adjustable round brush |
| blue | vasculature | adjustable round brush |
| green | ONH | adjustable round brush |

In a brush mode, left- or right-drag paints and Ctrl+right-drag erases, matching
the B-scan exclusion/clear gesture. Set the brush-head diameter in the side
panel; the cursor circle previews its native-grid size.

The older one-pixel ONH edge remains visible when a version-2 label is opened,
but new ONH labels are filled brush masks. No filled area is inferred from a
legacy edge; use `Old edge` under `Clear a whole mask` to remove it if needed.

Each class has its own `reviewed` checkbox. A checked empty mask means the scan
was inspected and that class is absent; an unchecked empty mask means nobody
labelled it. Painting a manually started mask checks the corresponding class.
When editing an automatic vessel starting mask, explicitly tick `Vasculature
reviewed` once the full mask has been inspected. Use `Mark all three reviewed`
only after all three have actually been inspected.

Each `outputs/cnv_labels/<scan_id>_cnv.npz` file uses label format
`4-enface-vessel-proposals` and stores `cnv_mask`, `vasculature_mask`,
`onh_mask`, and `reviewed_targets` in `CNV, VASCULATURE, ONH` order, plus the
existing provenance fields. Version 1, 2 and 3 labels still load. Their CNV review
status is preserved; a positive legacy ONH edge counts as evidence that ONH
was inspected, but no legacy empty mask becomes a negative vessel/ONH label.
En-face files still contain no surfaces or thickness values.

The 32-scan queue now has automatic major-vessel starting masks in
`outputs/eight_surface/vasculature_proposals`. Open `python open_enface_vessels.py`
from `code` after activating `octa` to start at the first unfinished vessel review.
The ordinary `cnv_gui.py` also discovers these proposals automatically.
Existing manual vessel masks, reviewed empty masks and saved drafts always take
priority. CNV and ONH annotations retain their existing contents and review flags.

Automatic seeds start unreviewed. Brush changes can be saved as unfinished drafts;
navigation and closing still save dirty work. Empty drafts are preserved and are
not refilled from the proposal on reopening. Tick `Vasculature reviewed` and save
when complete. Format 4 stores the starting-mask path/hash, initial mask and exact
brush footprint, alongside the review decision, so unchanged automatic pixels are
distinguishable from painted edits. Undo/redo includes the footprint. Old labels
do not acquire retrospective brush provenance. The sidebar scrolls on smaller screens.

`prepare_vasculature_queue.py` reproduces the 32 proposals with the approved 0.18
contrast threshold and unchanged shape gate. It never writes human labels. The
[queue report](../../outputs/vasculature_baseline/20260909_queue32/START_HERE.md)
contains the preparation and verification details.

After one or more footprint labels exist, build lesion-centred correction
packs:

```powershell
python eight_surface/cnv_review.py `
  --cnv-labels ..\outputs\cnv_labels `
  --segmented ..\outputs\eight_surface\segmented `
  --out-dir ..\outputs\eight_surface\cnv_review

python eight_surface/label_gui.py ..\outputs\eight_surface\cnv_review `
  --labels ..\outputs\eight_surface\labels
```

By default each lesion pack requests 3 core, 2 rim, 2 nearby, and 2 remote
B-scans. The mask is partitioned in physical units: a 75-um boundary rim and a
250-um nearby zone, with the inner rim reduced automatically for small lesions
so the lesion never loses its core. Remote selections are saved as controls.
Every pack includes `selection_role`, a per-A-line `lesion_zone`, the matching
CNV-mask rows, physical distances, and CNV-label provenance. The existing
surface GUI ignores none of the required standard fields and can therefore
open these packs without a second surface-label format.
