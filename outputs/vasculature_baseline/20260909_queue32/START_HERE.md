# 32 en-face scans ready for vessel correction

All 32 scans in the existing eight-surface en-face queue now have automatic
major-vessel proposals using the approved contrast threshold (0.18) and the
unchanged continuous-band shape gate. The original six proposal masks reproduce
exactly. The GUI loads the automatic mask for scans without saved vessel work.

Three vessel masks were already saved when the queue was prepared: TS165 OD,
TS165 OS and TS169 OS. All three are preserved; the remaining 29 scans start from
automatic masks. All 28 existing CNV/en-face annotation files passed a before/after
SHA-256 check during preparation. Existing CNV and ONH annotations are retained.

## Editing

After activating the `octa` environment, run from the project directory:

```
python code/open_enface_vessels.py
```

This opens the first unfinished vessel review. At preparation that is
`TS241_OD_2024-09-25_D42_s03_111600`, scan 4 of 32. Previous scans remain accessible.
The ordinary en-face GUI launcher also loads these proposals by default.

1. Select **Vasculature brush** (V).
2. Left- or right-drag adds vessel pixels; **Ctrl+right-drag erases**.
3. Adjust the brush diameter as needed. Undo/redo includes the edits.
4. When the full vessel mask is checked, tick **Vasculature reviewed**.
5. Use **Save en-face labels** (Ctrl+S), then move to the next scan.

Edits can also be saved as unfinished drafts; navigation and closing save dirty
work. Drafts resume exactly as saved, even after erasing every vessel pixel.
They are never replaced by a freshly loaded automatic mask. The sidebar scrolls
so review and save information remain reachable on smaller screens.

## Annotation provenance

Automatic proposals are separate files under
`outputs/eight_surface/vasculature_proposals/`; preparation never writes to the
human annotation directory. The human's save action in the GUI writes label
format `4-enface-vessel-proposals`. Older formats 1, 2 and 3 still load.

The saved annotation stores the initial mask, proposal path and SHA-256, actual
brush footprint, final mask, and explicit per-class review decision. A brush
edit to an automatic seed leaves vessels unreviewed until the reviewer checks
the class. Untouched automatic pixels are therefore distinguishable from a
human brush stroke. Checking reviewed is a human review decision, not a claim
that every pixel was redrawn. Older manual labels have no retrospective stroke
provenance. CNV and ONH retain their prior contents and review flags.

Saved nonempty manual masks, reviewed empty masks and saved automatic drafts
all take priority over proposals. Loading an untouched proposal and closing
without edits creates no human annotation.

## Verification

- All 32 proposal IDs, native grids, source-volume paths and retinal bands match
  the corresponding scan. GUI loader validation succeeds on every file.
- The original six shape-gated proposals match exactly; no algorithm parameters
  were retuned for the rest of the queue.
- All 28 existing human annotation files were unchanged at the end of preparation,
  before reopening the interactive GUI.
- Eighteen functional checks passed: eight new seed/draft lifecycle tests, one
  existing integrated GUI test, and nine existing CNV workflow tests. They cover
  erase/undo/redo, save/reload, reviewed absence, preservation of manual masks,
  empty drafts, explicit review, source/grid validation, old label formats, CNV
  pack compatibility and linked B-scan review. The CNV tests were rerun from the
  code directory after an initial test-command import-path error.

The small-blob cleanup retains its pilot limitations: long borders and elongated
artifacts may look like vessel bands; short real fragments can be removed and
gaps can remain. These are editable starting masks, not validated final results.

## Files

- [Scans 1–16](overview_1.png)
- [Scans 17–32](overview_2.png)
- `previews/`: individual proposal previews.
- `manifest.json`: all 32 results, algorithm settings, code hashes and initial
  human-label hashes.
- `queue_verification.json`: proposal validation and which scans load human work.
- `gui_ready.json` and `gui_ready.png`: startup verification from the launcher.

`python code/prepare_vasculature_queue.py` regenerates the proposal files without
writing human labels. Existing manual work and drafts continue to take precedence
in the GUI if proposals are regenerated.
