# cnv_analysis_v1

Spatial and longitudinal CNV thickness analysis, using the manual CNV outlines
and subsequent region classifications. This is an **experimental measurement
workflow**; octa-seg_v1 has not become a validated measurement model.

**The full analysis was authorized without the final batch audit on 2026-09-11.**
`BATCH_AUDIT_OVERRIDE.json` records the user's instruction. The run retains
scan-level artifact, native-grid, source-revision, and registration checks.
It does not claim that `FINAL_VERIFIED.json` or the final batch audit passed.
The initial inventory found 62 footprints in 19 scans from nine animals;
`tables/inventory.csv` records actual coverage and availability.

Use `RUN_CNV_ANALYSIS_V1.cmd` to resume the saved configuration and override. It resumes saved
work. `INVENTORY_CNV_ANALYSIS_V1.cmd` refreshes the inventory at any time.
Registration proposals and ONH localization may require review; inspect the
overlays and instructions in the [code guide](../../../../code/cnv_analysis_v1/README.md).

## Completed results

Completed analysis: 123 figures; 314 frozen scan inputs; 62 manual footprints in 19 scans from 9 animals.

The normalized post-D0 cohort plots include 7 animals. Clipped outlines remain in absolute-distance tables; prelaser outlines remain separate.

The final batch audit was skipped as requested. Thickness measurements remain experimental. Only scans with existing manual outlines contribute changing-footprint measurements. Unverified cross-scan matches are excluded from tracked summaries; fixed-tissue plots currently contain reference observations and do not establish longitudinal tissue change. Changing-footprint visit means can describe independently outlined visits. Missing measurements remain blank.

[Figure index](FIGURE_INDEX.md) · [Image gallery](FIGURE_GALLERY.html) · [Captions](FIGURE_CAPTIONS.md)

## Analysis contract

- Eight measurements use the current octa-thick `exclude_unreliable_um` policy:
  full retina (ILM to **outer RPE edge**), RNFL, GCL, IPL, INL, OPL,
  photoreceptor composite, and RPE band. Isolated ONL is unavailable.
- Diameter is `2 sqrt(area / pi)` using physical pixel dimensions. Distances
  are shortest distances to the actual pixel outline, including concavities.
  Interior is separate. Six bands cover 0–0.5D through 2.5–3D outside the edge.
  Lower boundaries are inclusive, upper boundaries exclusive, except the final
  outer edge is included. A pixel is represented by its physical center and
  its footprint by its full pixel rectangle.
- Absolute-distance sensitivity bands default to 0–100 through 500–600 µm.
  Incomplete diameters stay out of normalized summaries and remain in absolute
  measurements. Verified same-session footprints can recover a clipped outline
  only when its exterior is covered by the combined observed fields.
- Other lesion interiors and ONH tissue are excluded from surrounding bands.
  Overlapping surroundings go to the nearest physical lesion edge. Exact ties
  use deterministic lesion order and have their own recorded area.
  ONH exclusions can use a verified transferred outline or an explicitly
  recorded visible-edge disc estimate when no native outline exists; their
  origin is exported separately in `onh_exclusion_source`.
- Arithmetic means preserve source NaNs, shadows, exclusions, unreliable
  endpoints, and invalid geometry. Unusually thin/thick values are not removed.
- FOV coverage compares the unmasked band in the observed field with the full
  geometric band. Measurement coverage compares finite measured area with the
  available area after ownership and tissue exclusions. These are different
  denominators. Complete-band sensitivity uses at least 98% geometric coverage;
  it does not imply measurement reliability or a completely observed layer.
- Repeat acquisitions are averaged within lesion/visit, then visits within
  tracked lesions, lesions within eyes, eyes within animals, and animals equally.
  Animal-cluster bootstrap intervals use 2,000 draws with a fixed seed. A single
  animal cannot provide an animal-cluster interval. Unmatched observations remain
  in raw tables and plots but do not enter identity-dependent summary lines.
- Changing-footprint timecourse means need unique lesions within each eye/visit,
  without asserting that lesions are matched across dates. One annotated
  acquisition in an eye/visit supplies that local uniqueness. Multiple unmatched
  acquisitions in the same eye/visit stay out of the mean to avoid repeat
  overweighting, while their individual observations remain visible. Fixed-tissue
  trajectories and pooled distance summaries retain their cross-visit identity
  requirements. The longitudinal tables record `identity_scope` explicitly.
- Fixed regions use the first usable post-laser tracked footprint and diameter;
  changing regions require the visit's own mask. Both are sampled on each native
  thickness grid. Missing detection does not establish disappearance.
- Actual `days_post_laser` takes priority. Otherwise numeric D labels are nominal.
  Month labels such as “6mo” stay categorical; no invented day conversion occurs.
  D0 and explicitly prelaser observations stay separate from post-D0 pooling.
- Provisional image N/S/E/W → **D*/V*/N*/T*** is stated on anatomical figures.
  ONH ambiguity excludes only ONH associations. Off-image vessel convergence
  requires localization review; it is independent of thickness and CNV detection.

## Output layout

| Path | Contents |
| --- | --- |
| `config.json`, `inventory.json` | Analysis settings and scan/annotation inventory |
| `provenance/annotations.json` | Read-only source paths, revisions, hashes |
| `registration/` | Rigid transform proposals, diagnostics, overlays, ONH records, identities |
| `alignment_edits.json`, `identity_edits.json` | Optional derived alignment/identity review; never source annotations |
| `thickness/`, `frozen_inputs.json` | Frozen exact viewer-policy maps and measurement provenance |
| `tables/lesion_visit_layer_band.csv` | One row per observation, layer, band, region and distance definition |
| `tables/*summary.csv` | Balanced animal/cohort summaries and complete-band sensitivity |
| `maps/` | Native ring assignments, physical distances, diameter-normalized observed maps and coverage |
| `fig/` | One sequentially numbered final figure collection |
| `FIGURE_CAPTIONS.md`, `figure_manifest.json` | Captions, exact source tables and selection rules |
| `checkpoints/` | Hash-verified resumable scan measurements |
| `verification/` | Unit, synthetic, and real-data interface validation, separate from cohort results |
| `reproducibility_manifest.json`, `ANALYSIS_COMPLETE.json` | Final artifacts and release-specific completion proof |

Figures cover per-animal/cohort distance curves, schematic heatmaps and rings,
observed maps with coverage, ONH distance/sector associations when localization
is supported, and fixed/changing longitudinal panels. Empty bands remain blank;
partial band observations are visibly marked. Every figure is connected to its
numerical table, and the image/number/caption/table checks are saved.

Real-data validation images are under `verification/` and are explicitly labeled
as validation. Artificial end-to-end figures are under `verification/synthetic/`;
they are not study results. Source annotations and segmentation outputs are
checked for unchanged hashes during real validation.

The automatic release is separate `cnv_analysis_v2`, defaults to candidate cores,
adds broad-footprint sensitivity, and requires both the batch and automatic
completion gates. It reuses v1's frozen thickness maps and settings. Actual
coverage, matched scans, and expanded coverage remain separate. Automatic cores
partly depend on thickness, so thickness patterns cannot independently validate
their detection.
