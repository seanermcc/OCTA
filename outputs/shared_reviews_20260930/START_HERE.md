# Shared boundary reviews — September 30, 2026

The Mac and Windows reviewers on the Passport now automatically include every
currently confirmed lead B-scan in **Shared / starred samples**. Cases explicitly
marked For review or Especially ambiguous are included too. **Shared** has no
star; **★ Starred** means the lead explicitly marked the case ambiguous. Use the
filter to see all shared cases, starred only, or shared without stars.

The separate **My review status** column shows the signed-in reviewer's Not
started, Started (draft), Confirmed, or Needs reconfirmation status. Opening a
case loads that reviewer's own work, not the lead's boundaries, lesion masks or
notes. Save and reopen existing reviewer windows to load this application update.

## Count checked here

At the initial audit, the active lead store had 29 journals: 20 confirmed B-scans
in 13 scan volumes, seven drafts, one needing reconfirmation, and one with no
review work. The original F:/octa/reviewers and E:/reviewers copies had the same
cases, with 21 confirmations. Their extra confirmation is TS247 OD D35 s01,
B-scan 282, which has subsequent edits in the active store and needs confirmation
again. These stores contained no additional unique reviewed B-scans.

The new shared list contained 21 B-scans across 14 volumes: all 20 initially
confirmed cases plus the explicitly shared reconfirmation case. Two were starred
and 19 were shared without a star. Lead editing continued during verification,
so confirmation counts can change until edited cases are confirmed again.
Sharing does not confirm, star, or alter a human annotation.

## Shichu on Mac

1. Connect the Passport drive. Keep the main `octa` folder together, including
   `Mac_Boundary_Reviewer` and `For_Segmentation`. The Mac mounts the drive by
   volume name, not the Windows letter F:.
2. Open `octa/OPEN_BOUNDRY_REVIEWER_MAC.command`. This package supports Apple
   Silicon (M1 or newer). First launch needs internet to install its private
   Python environment; subsequent launches use the installed environment.
   If Finder refuses to execute the launcher from the drive, open Terminal,
   type `/bin/bash `, drag the `.command` file into Terminal and press Return.
3. Enter reviewer ID **shichu**. Click **Shared / starred samples**, leave
   **Shared by: lead** and **All shared** selected, and open a case under her ID.
   Previous/Next selected B-scan follows that list. The optional unfinished
   checkbox hides only cases Shichu herself has confirmed.
4. Review **CNV-Core** (purple) and **Full-CNV Lesion / RPE-Disrupt** (cyan)
   separately. The circled i gives their exact definitions. The pink auto-CNV
   overlay is separate. Confirm entire B-scan when review is complete.

Keep the drive connected while reviewing. Her new Mac saves go to
`~/Documents/OCTA_Boundary_Reviews/portable-20260923/Reviews/reviewers/shichu`.
They **do not automatically sync back to F:**. Preserve that complete folder
and return a copy as a separate handoff for merging; do not overwrite another
copy of ongoing Shichu work. The existing Mac first-launch seed preserves her
previously copied local work. This update reads the current lead selections
directly from the drive even on an already-initialized Mac, without replacing
local reviewer files. An older local Shichu folder may still need a separate
merge if she has worked independently on more than one computer.

On Windows, open `octa/OPEN_BOUNDARY_REVIEWER.cmd` and enter **shichu**.
Windows saves to `octa/For_Segmentation/Reviews/reviewers/shichu` on the drive.
Do not run concurrent writing sessions using the same reviewer ID/store.

## Verification

The Mac package retains both CNV categories. Forty contract tests and Qt tests
of separate draw/erase, undo/redo, save/reopen, definitions and auto-overlay
visibility passed on Windows using the Mac package. The shared-browser test
checks unstarred confirmation inclusion, star filters, independent review/save,
draft status, invalidated confirmation exclusion, and unchanged synthetic lead
records. Read-only live checks confirm provider identity and availability for
all shared cases in both installed packages. Native macOS execution remains
unverified here; its launcher supports `--verify-mac` on the actual Mac.

`inventory.json` is the initial audit; `windows_live.json` and `mac_live.json`
are later snapshots. `before/` preserves the application files changed in this
update. This update writes application code and verification fixtures, not
human review records.
