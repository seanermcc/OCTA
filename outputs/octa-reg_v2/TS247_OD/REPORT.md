# TS247 OD — pooled ONH montage

All **33 eligible scans** are placed in one ONH-centered map. One previously excluded scan remains out. All dates (2024-10-17 through 2024-11-26) were pooled at the user's request; dates remain attached to each source field.

Open `index.html` or `OPEN_MONTAGE.cmd`. The default montage displays **9 representative fields**, chosen by incremental observed coverage. Use **All scans** for all 33, **Footprints** for their boundaries, and select a scan to bring it forward. Opacity and Space-to-blink let you inspect overlap. `montage.png` is the annotated export; `montage_clean.png` is the map without its caption.

## Observed coverage

- Union of placed, 5-pixel-border-cropped fields: **8.83 mm²**, approximately **4.31 single-field areas**.
- Bounding extent: approximately **3.86 × 3.74 mm**. The bounding rectangle includes blank space; it is not the observed area.
- Reference ONH: reviewed visible disc in `TS247_OD_2024-10-17_beforelaser_s10_120645` (display field 07).
- Scale remains approximate (1460 µm across 512 pixels). Native display orientation is retained. Temporal/nasal and superior/inferior are not established from these files.

## What changed from v1

The original run depended on sparse ORB texture matches and required three vessel junctions. This pilot uses vessel-anchored SIFT matches, then searches whole vessel curves over rotation and translation for difficult fields. It measures symmetric centerline agreement, common-tissue vessel Dice, structural correlation, and two-dimensional spatial support. Matching one straight trunk cannot pass the spatial-support check.

The graph starts at the ONH reference, resolves conflicting placements using agreement across neighbors, and jointly fits rigid poses. No image is stretched or nonrigidly warped. Convergence toward the ONH contributes a directional consistency check for the low-contrast recovery; convergence alone does not establish an exact position. The other fields are placed by overlapping vessel geometry. Source tiles are composited without synthesized tissue or forced gap filling.

## Evidence and remaining uncertainty

- 528 eligible descriptor comparisons; 71 passed that stage. 54 additional whole-curve searches are recorded.
- 93 pairwise constraints retained after graph consistency checks; 1 conflicting constraint rejected. A high-scoring wrong-trunk match for display field 17 was overruled by four agreeing neighbors.
- Display field **22** (`TS247_OD_2024-11-20_D35_s01_112538`) has low structural contrast. Six informative vessel overlaps agreed, and its inferred convergence lay about 38 µm from the reference ONH before final joint fitting. Its intensity-correlation gate was explicitly waived under this separate consensus rule; the viewer flags it.
- Internal pose-loop RMS: median **4.0 µm**, maximum **42.4 µm**. These are graph-consistency residuals, **not independent accuracy measurements**.
- All placements remain automatic research proposals. Single-link peripheral fields deserve particular review. Their transforms, neighbor counts, and pair metrics are retained in `montage.json` and `verification.json`.
- Mixing dates can mix laser lesions and acquisition appearances. This is a coverage montage, not a single-timepoint image or a longitudinal outcome measurement. Repeated scans mostly revisit the same territory; 33 scans do not imply 33 distinct fields of retina.
- Excluded: `TS247_OD_2024-11-06_D21_s02_103301`. Reason retained from the existing review: Explicit human instruction; scan excluded from training, tuning, evaluation and analysis.

## Verification and provenance

Five synthetic/regression tests passed: known rigid recovery with partial overlap, rejection of a single straight trunk as spatial support, no-overlap handling, ONH direction/inverse coordinates, and a false high-score graph bridge overridden by neighbor consensus. Real-output checks verified every transform and inverse, positive unit determinant, exclusion handling, per-scan final overlap support, and unchanged hashes for 166 consumed source files. Original volumes, optical caches, masks, human labels and v1 products were not modified.

`RELEASE.json` pins code, source files, package versions and the curve-search plan. A later source/code change prevents silent reuse of released caches. `montage.json` contains pixel and micrometer transforms and inverses; `pairs/`, `curve_pairs/`, and `consensus_pairs/` preserve candidate evidence and rejected alternatives. No training or new human labels were produced.

## Reproduce

From the repository root in an activated `octa` conda environment:

```powershell
$env:PYTHONPATH = "$PWD\code"
python -m octa_reg_v2
python -m octa_reg_v2.verify
```

The pilot is deliberately bounded to TS247 OD on its verified 512 × 512 grid. Implement another animal or modified algorithm in a new output version.
