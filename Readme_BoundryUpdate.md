# Boundary segmentation GUI update — 2026-09-30

Release marker: **boundary-review-2026-09-30**. The filename intentionally uses
`Boundry` so it matches the requested handoff name.

The updated boundary reviewer source is included in this GitHub repository at
`outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3/`. This is the current GUI;
older dated portable snapshots elsewhere in the repository are not the current
application. GitHub carries source, launchers, tests and documentation. Scan
caches, model binaries, generated comparison datasets, and human reviewer
journals are excluded by `.gitignore` and must be available separately.

## What changed

- **CNV-Core** (purple) and **Full-CNV Lesion / RPE-Disrupt** (cyan) are separate
  tools with independent saved regions. They can overlap. Drawing, erasing,
  undo/redo and save/reopen preserve their separate identities. The circled
  **i** explains the definitions.
- **Show auto-CNV (pink)** controls the automatic context overlay in the B-scan
  and en-face navigator independently of manual annotations.
- **Shared / starred samples** includes confirmed lead B-scans and explicitly
  shared cases. A star means explicitly marked ambiguous; ordinary shared cases
  have no star. Filters distinguish all shared, starred, and shared without stars.
- **My review status** distinguishes Not started, Started (draft), Confirmed,
  and Needs reconfirmation. Opening a shared case uses the signed-in reviewer's
  own work. Sharing does not copy another reviewer's answers or confirm a case.
- The read-only **lead/Shichu comparison viewer** has synchronized boundaries,
  differences in microns, a boundary/A-line heatmap, exports, and independently
  selectable saved lesion overlays. Its source is in `code/reviewer_compare/`.
- Windows launchers, Apple Silicon Mac packaging/support, recent demo and
  preview utilities, and the manual vessel-gallery updates are included.

These are application updates, not a new segmentation-model accuracy claim or
a refit of the anatomical priors. Existing migration behavior and scientific
limitations are described in the linked release guides below.

## Get and confirm the update on the home computer

From your existing OCTA repository, save any local work first, then run:

```text
git switch main
git pull --ff-only origin main
git log -1 --oneline
git status --short
git ls-files Readme_BoundryUpdate.md
git ls-files outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3/gui.py
git grep -n "Shared / starred samples" -- outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3/gui.py
git grep -n "CNV-Core" -- outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3/lesion_tools.py
```

The two `ls-files` commands must print the requested paths. The `grep` commands
must find the updated controls in the current source. If the pull reports local
changes or diverged history, preserve that work and resolve it before proceeding;
do not reset it away.

For an exact synchronization check immediately after fetching:

```text
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git diff --exit-code origin/main -- Readme_BoundryUpdate.md outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3
```

Matching commit IDs confirm the checkout is at the fetched GitHub `main`.
No output and exit code 0 from `git diff` confirms these local GUI files match it.

## Open the GUI

Save and close an already-running reviewer, then reopen it to load new code.

**Windows with the prepared Passport:** the repository-root
`OPEN_BOUNDARY_REVIEWER.cmd` (also `OPEN_BOUNDRY_REVIEWER.cmd`) delegates to
`F:\octa\OPEN_BOUNDARY_REVIEWER.cmd`. Connect that prepared drive as F:.
It launches the drive's installed application, not the Git checkout. Pulling
GitHub alone does not update a separate drive installation.

**Run the Git checkout on Windows:** in an Anaconda Prompt, activate `octa`,
change to your checkout root, and run:

```text
conda activate octa
python outputs/octa-seg/octa-seg_v3/review/launch.py --check-paths
python outputs/octa-seg/octa-seg_v3/review/launch.py
```

The first command checks that the launcher resolves this checkout. The GUI also
needs the corresponding local scan/provider outputs and PySide6 environment.
A clone without those datasets cannot display the lab scans. Activate the
environment instead of calling its Python executable directly. Some older
`.cmd` wrappers assume `D:\Anaconda`; the commands above use your activated
environment and avoid that machine-specific installation path.

**Apple Silicon Mac:** use `OPEN_BOUNDRY_REVIEWER_MAC.command` with the prepared
`Mac_Boundary_Reviewer` and `For_Segmentation` folders on the Passport. Those
installed folders and their data are not supplied by a Git clone. The launcher
can prompt for the drive's `octa` folder. See the Mac guide below for setup and
`--verify-mac`. Native macOS execution has not been verified from this Windows
machine.

In the opened GUI, confirm that CNV-Core, Full-CNV, the circled i, Show auto-CNV
(pink), and Shared / starred samples are visible. Enter your own reviewer ID.
Shared-case counts depend on available journals; an empty list alone does not
mean the code update is missing.

Windows Passport reviews save under `octa/For_Segmentation/Reviews/reviewers`.
Mac reviews save under
`~/Documents/OCTA_Boundary_Reviews/portable-20260923/Reviews/reviewers` and do not
automatically sync back to the drive or GitHub. Preserve those journals separately.

## Verification performed for this commit

On Windows in the activated `octa` environment, all 40 CNV/GUI contract tests
and all nine comparison tests passed. Offscreen Qt interaction checks passed
for separate draw/erase, undo/redo, save/reopen, definitions and automatic-overlay
visibility. The shared-browser interaction check passed, including filters,
independent saves, draft status, and preservation of the synthetic lead records.
These checks used isolated synthetic fixtures, not edits to human review files.
Native Mac execution remains to be checked on the Mac.

## Further details

- [CNV tools and migration](outputs/cnv_distinctions_20260929/README.md)
- [Shared review workflow and dated counts](outputs/shared_reviews_20260930/START_HERE.md)
- [Current reviewer guide](outputs/octa-seg/octa-seg_v3/review/START_HERE.md)
- [Apple Silicon Mac setup](outputs/mac_boundary_20260923/support/START_HERE_MAC.md)
- [Comparison viewer guide](outputs/reviewer_comparison/START_HERE.md)
