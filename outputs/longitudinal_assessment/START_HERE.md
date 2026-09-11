# Longitudinal assessment — TS267 and TS328

**Complete:** 22 full acquisitions, 44 versioned exports, ready for segmentation
review and octa-thick. See [RUN_REPORT.md](RUN_REPORT.md) for the visit-by-visit handoff.

This is a separate group from the original ten-volume assessment. Processing status
is recorded in `status.json`; `COMPLETE.json` is written only after every selected
volume has passed export and octa-thick compatibility checks for both versions.

## Commands

Thickness launchers live in `outputs\octa-thick_v1`. Batch and segmentation
launchers live here; run-specific scripts and checks are in `code/`, and the
initialization log is in `logs/`. The project root contains no launchers for this run.

- **PROCESS_LONGITUDINAL.cmd** — process or resume this group only.
- **OPEN_LONGITUDINAL_SEG_v1.cmd** — browse and correct v1 segmentations.
- **OPEN_LONGITUDINAL_SEG_v2.cmd** — browse and correct v2 segmentations.
- **[octa-thick_long_v1.cmd](../octa-thick_v1/octa-thick_long_v1.cmd)** — open longitudinal thickness v1.
- **[octa-thick_long_v2.cmd](../octa-thick_v1/octa-thick_long_v2.cmd)** — open longitudinal thickness v2.

From the longitudinal assessment folder, the batch command is
`LONGITUDINAL_ASSESSMENT.cmd run`. To open thickness analysis, use
`..\octa-thick_v1\octa-thick_long_v1.cmd` or `..\octa-thick_v1\octa-thick_long_v2.cmd`.
The older `OPEN_LONGITUDINAL_THICK_v1.cmd` / `v2.cmd` launchers remain compatible aliases in `outputs\octa-thick_v1`.
`LONGITUDINAL_ASSESSMENT.cmd status` lists the number checked and the remaining scans.

Each version has its own review records and thickness exports. Octa-thick's
**Open correction GUI** opens the matching longitudinal segmentation reviewer.
After saving corrections, use **Reload corrections** in octa-thick.

## Included visits

The fixed selection is in [visits.csv](visits.csv), with source paths in
[manifest.json](manifest.json). One full acquisition per eye per available visit
is selected by lowest acquisition number, then earliest acquisition time.
This deterministic selection is not a claim that these are the best repeats.
The manifest also records the other repeats and unavailable acquisitions.
The source-folder audit found 76 processed acquisitions and no unindexed sources;
54 repeat acquisitions are outside this fixed one-per-eye/visit selection.

| Animal | Nominal visits | Full volumes |
|---|---|---:|
| TS267 | D0, D7, D14, D28, D35, D42, D49, D56, D98 | 17 |
| TS328 | Before laser, D21, D49, D56, D63 | 5 |

TS267 includes both eyes except OS at D56: its three acquisitions have no
processed volume. TS328 has OD only in the index. TS267 D21 and TS328 D7/D14
are absent from the index. Each included acquisition contains all 512 native
B-scans and 512 A-lines, giving 11,264 B-scans per processing version.

Actual `days_post_laser` values are unavailable in the current index for these
animals. Dates are preserved and day labels remain explicitly nominal; they are
not silently converted to exact follow-up intervals. Animal identity is numeric
(TS328 includes the scans named TS328M).

## Processing and interpretation

Both versions use the released v1 position and state checkpoints; v2 round_000
applies its current working/reporting policy to those predictions. No training
or parameter refitting occurs. Input preparation follows v2, including current
footprints and unreviewed vessel proposals where no vessel mask exists. The two
versions share matching source images, masks and neural predictions, then apply
their own reporting and contextual-estimate rules. Original human denials are
read from the existing workflow; this command never creates human labels.

Each version exports eight boundary surfaces, reporting states, separate uncertain
candidates, and thickness arrays. Exported primary thickness retains NaN for
shadowed or unreportable endpoints. Octa-thick retains its existing preliminary
policy of using available model positions while excluding explicit human
unreliability by default. Its measurement availability is not a validation result.

The native coordinate checks compare source B-scans 0, 256 and 511 against the
cached images. Both versions are loaded through the actual octa-thick engine;
checks cover dimensions, shadow NaNs, provider coordinates, and point/map units.
Results are saved separately for each scan under `verification/`.

These are experimental outputs for human review. This group does not register
visits, align lesion ROIs across dates, or establish longitudinal thickness change.
The original ten-volume group, released models, source volumes and existing
annotations remain outside this group's output paths.
