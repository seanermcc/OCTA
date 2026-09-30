# Boundary reviewer for Apple Silicon Mac

Prepared for the requested Apple M1 Pro / macOS Tahoe 26.6.1. This is a separate
application copy. Native execution on that Mac must still be verified there.

## Open it

1. Keep `OPEN_BOUNDRY_REVIEWER_MAC.command`, `Mac_Boundary_Reviewer`, and
   `For_Segmentation` together in the main `octa` folder on the external drive.
2. Double-click `OPEN_BOUNDRY_REVIEWER_MAC.command`.
3. First launch downloads and installs private Apple Silicon Python 3.11 tools
   and reviewer libraries. Keep internet access available and allow several
   minutes. Progress and a local log are shown. No administrator password or
   existing Python installation is needed. Later launches use the installed tools.
4. Enter your own reviewer ID. Use `lead` only when continuing lead's work.

If Finder reports missing execution permission on the NTFS drive, open Terminal,
type `/bin/bash ` (including a trailing space), drag the main `.command` file
into Terminal, then press Return. This runs the same launcher without changing
drive permissions. Alternatively extract `MAC_LAUNCHER.zip` onto the Mac desktop
and double-click that launcher. It asks you to select the main `octa` folder on
the drive. The ZIP preserves the launcher's executable permission.
Do not disable Gatekeeper globally if macOS asks you to approve a downloaded file.

## Where things are saved

- Existing scan arrays are read directly from `For_Segmentation`. They are not
  duplicated and no Windows runtime is installed or moved.
- On the first successful launch, existing `Reviews/reviewers` and
  `Reviews/review_queues` are copied byte-for-byte to
  `~/Documents/OCTA_Boundary_Reviews/portable-20260923/Reviews`.
- All subsequent Mac edits are saved in that local Reviews folder using the
  existing GUI writer. They are **not automatically synchronized to Windows**.
  To transfer completed work, copy your reviewer subfolder back as a separate
  handoff for review/merging. Do not overwrite somebody else's concurrent work.
- Existing local reviews are never overwritten by setup or by a later launch.
  Later changes to the external drive's review files are not automatically merged.
- Logs, checks and synthetic verification records are under the sibling `runtime`
  folder. Python tools live in `~/.octa-boundary-reviewer`.
- Keep the external drive connected while reviewing. If macOS requests access
  to Documents or removable volumes, allow access for Terminal/the reviewer.

The external drive is NTFS. Reading caches from it is supported; all Mac writes
go to the locations above. Copying the complete data folder onto a writable Mac
disk is also supported if the relative folder arrangement is retained.

## Mac controls

Use Command-S to save, Command-Z to undo, Command-Y to redo. Qt maps the original
Control modifier to Command on macOS. Option replaces Alt in modified gestures.
Enable secondary click on the trackpad or use a mouse for right-drag gestures;
Control-click can conflict with those gestures. The in-app editing key is updated
in the Mac copy. Annotation semantics and frozen predictions are unchanged.

## Verification on the Mac

Run the same command from Terminal with `--verify-mac` appended. It checks native
ARM64 Python and Cocoa Qt, loads a real cached scan read-only, checks existing
saved positions, and exercises synthetic editing/save/reopen through the GUI.
It records `result.json` and a screenshot in the local `runtime/checks` folder.
Human annotations are not created or modified by that test.

The Windows-side build checks cannot verify macOS window rendering, trackpad
behavior, permissions or native library loading. See `VALIDATION.json` for the
checks actually completed before transfer.

## Package contents and provenance

`project` duplicates the Python application, portable manifest and calibration.
Only the copied review destination and Mac gesture help are adjusted. The original
Windows files remain at `Full/_Project`. `BUILD_MANIFEST.json` records source
hashes and modified copies. `requirements-mac.txt` pins the seven review libraries
to the Windows package's versions; it intentionally excludes model-training tools.

The bootstrap downloads Miniforge 26.7.2-0 for macOS ARM64 from the official
conda-forge release and verifies its pinned SHA-256 before running it:
https://github.com/conda-forge/miniforge/releases/tag/26.7.2-0

If first-time installation is interrupted, rerun the command. Partial base
installations are preserved under timestamped names. A completed environment
can launch without internet; this package is not a fully offline first installer.
