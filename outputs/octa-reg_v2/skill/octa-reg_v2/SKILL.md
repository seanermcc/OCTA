---
name: octa-reg_v2
description: Build and review ONH-centered tree shrew OCT en-face retinal montages using vessel overlaps, rigid pose graphs, and explicitly flagged uncertain placements. Use for retinal registration, stitching scans of one eye, pooled-date coverage maps, and cohort montage reviewers. Does not perform layer segmentation, RAW reconstruction, or human annotation.
---

# octa-reg_v2

Implement the vessel-based montage process in `G:/OCT_TreeShrew/octa`.
Read the repository's `AGENTS.md`, `README.md`, and `PIPELINE.md` for current
data contracts. The executable workflow is `code/octa_reg_v2/cohort.py`, with
graph assembly in `cohort_graph.py` and reviewer publication in `cohort_report.py`.
The first TS247 OD demonstration remains frozen in `outputs/octa-reg_v2/TS247_OD`.

## Identity and evidence

- Group by animal **number** and eye. Never register OD to OS or mix animals.
  Sex letters and nominal day labels are not identity. Pool dates when requested;
  retain acquisition dates in every record and describe the output as pooled.
- Use verified `outputs/octa-reg_v1/prepared` structural projections and selected
  vessel/ONH masks, checking their source hashes. Never reconstruct RAW files,
  retrain a segmentation model, or edit source images, masks or human labels.
- Explicit whole-scan exclusions remain excluded unless the user specifically
  changes that decision. Poor contrast, uncertain localization, an unreviewed
  mask and an explicit exclusion are different conditions.
- Native x is A-line column and y is B-scan row. Preserve native orientation;
  do not silently flip an eye. The current calibrated grid is 512 x 512 at
  approximately 1460/512 micrometers per pixel. Stop for an unsupported grid
  rather than resizing masks or assuming the filename's X500um is retinal extent.

## Registration process

1. Prefer a reviewed, fully visible ONH as the reference. An automatic disc fit
   or vessel convergence is an **estimated** origin. If neither is defensible,
   retain a reference-field coordinate system and mark ONH localization unresolved.
2. Find vessel-anchored SIFT correspondences, fit rigid rotation/translation with
   RANSAC, and refine with symmetric centerline distances. Test actual common
   tissue for vessel support, Dice, structural correlation and two-dimensional
   spatial support. Do not require three junctions: many real fields have long,
   unbranched trunks. One matched straight trunk is insufficient to locate a field.
3. Recover disconnected fields using whole-vessel rotation/translation search.
   Seek additional neighbors for sparse links. Use vessel convergence as a
   directional clue: an ONH left of a field places that field to its right;
   an ONH above-left places it below-right. Convergence alone does not determine
   an exact pose or confirm relative rotation.
4. Build and jointly fit the overlap graph. Check agreement across neighbors
   **before** discarding conflicting loop edges. A high-scoring false trunk match
   can corrupt a maximum-weight tree; several consistent neighbors can overrule it.
   Keep rejected edges and alternative proposals for inspection. Explicitly test
   whether every reviewed ONH maps to the same origin. Two separated copies of
   the disc reveal a wrong connection even when vessel scores look strong.
   Use reviewed ONH centers to constrain a fresh vessel-pattern angle search;
   prioritize those anatomical constraints, reject incompatible links, and flag
   remaining contradictions and connections that depend on flagged fields.
5. For low-contrast recovery, multiple spatially informative vessel overlaps plus
   ONH consistency may support a separate geometry-consensus proposal even when
   structural correlation fails. Retain that exception as flagged evidence.
6. Best-effort uncertain placements may attach disconnected components through a
   tentative overlap or an estimated ONH. These proposals must not move the
   supported backbone or inflate its supported-coverage statistic. Propagate
   uncertainty through tentative connections. If neither connection nor origin
   is defensible, retain the native field in the unlocalized group; do not invent
   an atlas location just to claim that every scan was placed.

## Reviewer requirements

Provide an animal-eye selector and independently toggleable **Supported** and
**Flagged / uncertain** groups. Uncertain fields use distinct outlines and expose
the reason, proposed pose and evidence. Preserve unlocalized fields for inspection
and show explicit exclusions separately. Keep uncertainty off by default for the
supported-coverage view; selecting a flagged field should offer its proposal.

Use visible tile boundaries like a fundus montage. Provide a compact representative
montage plus all-field footprints, per-field opacity and blink comparison. Repeated
scans occupy their actual overlapping positions; do not spread them out to make a
larger-looking retina. Label anatomic directions only when independently known.

Report observed union coverage separately from the bounding rectangle, and
supported coverage separately from coverage that includes uncertain proposals.
Do not call internal Dice or loop consistency independent registration accuracy.
Pooled dates form a coverage visualization, not a single-timepoint retina or
biological longitudinal measurement.

## Execute and verify

Activate the environment before running Python on this machine:

```powershell
. D:\Anaconda\shell\condabin\conda-hook.ps1
conda activate octa
Set-Location G:\OCT_TreeShrew\octa
$env:PYTHONPATH = "$PWD\code"
python -m octa_reg_v2.cohort --workers 4
python -m octa_reg_v2.cohort_anatomy
python -m octa_reg_v2.cohort_report
```

`--groups TS247_OD TS247_OS` limits a run. `--output` selects a new run directory.
The default cohort directory is `outputs/octa-reg_v2/all_samples`. Source and
algorithm fingerprints protect caches; use a new version/output directory if
inputs or registration code change. The frozen pilot has its own reproduction
command (`python -m octa_reg_v2`) and must not be overwritten by the cohort run.

Run the registration and cohort regression tests after algorithm changes. Verify
every inventory row appears once, no edge crosses animal-eye identity, excluded
scans have no atlas transform, transforms are rigid and invertible, uncertain
bridges cannot affect supported poses, and consumed source hashes are unchanged.
Inspect representative maps and the uncertain-group toggle in the actual browser.
Check every group's completion or recorded failure before saying the cohort is
finished. Preserve counts, transforms, input/code hashes, parameters, rejected
alternatives and the review report with the outputs.
