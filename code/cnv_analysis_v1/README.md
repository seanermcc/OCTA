# CNV analysis v1

Read-only spatial and longitudinal analysis of the experimental octa-seg_v1
thickness measurements. Outputs belong to
`outputs/octa-seg/octa-seg_v1/cnv_analysis_v1/`.

From the repository root, activate the environment and use:

```powershell
conda activate octa
$env:PYTHONPATH = "$PWD/code"
python -m cnv_analysis_v1 inventory
python -m cnv_analysis_v1 register
python -m cnv_analysis_v1 measure
python -m cnv_analysis_v1 figures
# Or all stages, with checkpoints:
python -m cnv_analysis_v1 run
```

`inventory` and `register` can prepare work before the full batch completes.
By default, `measure`, `figures`, and the measurement portion of `run` require the batch's
actual `FINAL_VERIFIED.json`, a matching scan count, and unchanged audited table
hashes. Any override requires recorded user authorization. After batch completion, refresh
the inventory and registrations before measuring. Individual native maps and
per-scan measurement checkpoints are reused only with matching revisions and
artifact hashes. An explicitly recorded `batch_audit_override` in the saved
configuration can waive only the final batch-audit marker, retaining the required
per-scan outputs and all downstream integrity checks. The user authorized that
override for this v1 run on 2026-09-11. Use `--config` with the saved output
configuration to retain it. Without that override, running `run` while the gate is absent records the blocker and
exits; it does not start a background monitor.

The output's `START_HERE.md` describes the files, review protocol, assumptions,
and current validation. Human source annotations and segmentation products are
never written by this package. The viewer engine's stale-export bookkeeping is
redirected into this analysis folder.

## Verification

```powershell
python -m unittest cnv_analysis_v1.test_analysis -v
python -m cnv_analysis_v1.verify_synthetic
python -m cnv_analysis_v1.verify_real
```

Synthetic verification writes only under `verification/synthetic`. It tests the
full measurement and figure pipeline using artificial inputs, never annotation
files. Real verification is a bounded interface/arithmetic check on three
animals; it is not a final cohort analysis or accuracy validation.

## Registration and identity review

Physical transforms map a scan's `[x_um, y_um, 1]` coordinates to its same-eye
reference scan. They contain rotation and translation only. The reference uses
identity; every non-reference image registration remains proposed until reviewed.
The numerical quality thresholds screen proposals, not proof of correspondence.
Inspect `registration/overlays/` and `registration/records/`. Copy selected entries
from `alignment_edits.example.json` into `alignment_edits.json`, enter `reviewer`,
`evidence`, and a nonnegative `uncertainty_um`, and set `state` to `verified` or
`rejected`. Adjust the matrix if necessary. The `reference_scan` and
`input_revision` must still match the proposal. These are derived alignment
records, not human retinal annotations. Rerun `register` after editing.

Independent vessel-branch convergence produces only proposed off-image ONH
locations. Review the saved `vessel_branch_axes_um`; a verified alignment edit
may supply corrected `vessel_branches_um` and `onh_verified: true`. Each branch
is a list of native physical `[x_um,y_um]` points. At least three suitably
oriented branches are required. Invisible or ambiguous ONH localization remains
unavailable; it does not invalidate local CNV thickness.

`registration/identities.json` records unique matches, new verified locations,
unmatched observations, and ambiguous splits/mergers. To correct identity, create
`identity_edits.json` containing the current digest of `registrations.json`
(the JSON-content digest, available from `cnv_analysis_v1.common.digest(read(...))`)
as `registration_revision`, plus `identities`, a list of objects containing
`scan_id`, `lesion_id`, `track_id`, `state`, `reviewer`, and `evidence`. An empty
track ID excludes an ambiguous observation from identity-dependent summaries.
To establish a reviewed new lesion, set `new_track: true` and use a track ID
starting with that eye's `reference_scan` followed by `:`. Unmatched footprints
otherwise remain outside identity-dependent summaries. Unverified image matches
can carry `proposed_track_id` without becoming eligible.
Cross-eye identities and duplicate same-scan track assignments are rejected.
Source annotations are never replaced by these derived records.

## Future automatic release

```powershell
python -m cnv_analysis_v1 run --release v2 --annotation-source automatic_core
```

This writes `cnv_analysis_v2` and preserves v1. It additionally requires the
automatic workflow's independently passed `FINAL_VERIFIED.json` (or an explicitly
configured `auto_gate`) and v1's frozen thickness maps. The existing TS267 pilot
does not currently supply that completion gate. All 314 available thickness
inputs are frozen by v1, including animals without manual outlines, to support
later coverage expansion. v2 defaults to cores and also measures broad footprints
as `changing_footprint_sensitivity`; shared footprints that span multiple cores
remain ambiguous rather than being counted as independent tracked lesions.
Matched-scan and expanded-coverage summaries are separate. Configuration can be
supplied with `--config`; a frozen output refuses configuration changes.
