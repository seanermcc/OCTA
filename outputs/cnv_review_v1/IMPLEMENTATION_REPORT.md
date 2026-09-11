# CNV region review GUI — 2026-09-09

Implemented in a new `code/cnv_review_v1` folder. Original application files
were reused as imports and left unchanged. New annotations save exclusively to
`outputs/cnv_review_v1`; source annotations remain read-only.

The 32-scan application links structural and OCTA en face images to an embedded
eight-boundary editor. It displays recorded manual-stroke spans at their native
B-scan rows, supports selection and direct boundary correction, and stores
individual outlined regions with Full Lesion / Normal / Other categories and
free-text notes. Existing outlines begin unclassified. Other without explanatory
notes remains a saved draft.

Saved or proposed major-vessel footprints appear throughout both views. The
B-scan overlay represents corresponding A-line columns, with no claim of vessel
depth. Automatic prediction folders can be selected and reloaded. The current
full-cohort model is used for its four exported volumes; the other 28 scans use
the explicitly named existing cascade. Original manual geometry, its automatic
baseline and uncertainty flags take priority when a correction exists.

## Verification

**14 synthetic Qt behavior tests passed.** They cover mouse selection, native
navigation, region creation/redraw/delete/undo, category/notes persistence,
incomplete Other drafts, boundary editing and uncertainty retention, original
label protection, rejected rows, automatic provider priority and mismatches,
concurrent region saves, and programmatic checkbox restoration.

**Five real volumes loaded successfully.** For each of the four recent model
volumes, the selected B-scan's displayed pixels were exactly equal to the
corresponding full-volume manual-review image:

| Scan | B-scan checked | Saved reviews loaded | Source |
|---|---:|---:|---|
| TS247 OD D21, 2024-11-06 s03 | 131 | 13 | Full-cohort model |
| TS325 OD 6mo, 2026-05-26 s01 | 106 | 14 | Full-cohort model |
| TS165 OS WT, 2025-04-29 s02 | 80 | 15 | Full-cohort model |
| TS283 OD D7, 2025-01-29 s02 | 89 | 13 | Full-cohort model |
| TS267 OD D56, 2025-04-16 s03 | 256 | 6 | Existing cascade fallback |

Final read-only verification preserved hashes of **224 existing annotation
files** and **four original GUI/data files**, with **zero new boundary or region
annotations created by browsing**. See `verification/real_data_checks.json`
and `verification/behavior_tests.txt`. These checks validate integration and
data preservation, not segmentation accuracy or biological classifications.

An initial verification run exposed a Qt tooltip/checkbox signal bug while
restoring a globally unreliable boundary. The entire surface-list rebuild is
now guarded against annotation changes, with a regression test. Its single
unintended new-folder artifact was isolated under
`verification/quarantined-not-human` with a `.not-human` extension. It is not a
human label, is not an active input, and must not be used for training. The
original source file was unchanged. The full five-volume read-only check was
repeated successfully after the fix.

## Use

Double-click `code/cnv_review_v1/OPEN_CNV_REVIEW.cmd`. It activates `octa` before
launching. Detailed controls, output fields and future automatic-export format
are documented in `code/cnv_review_v1/README.md`.
