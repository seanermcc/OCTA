# Thickness and automatic availability patterns

These are descriptive within-TS267 measurements from the recovered automatic branch, not a CNV biomarker validation. Twenty-five kept entries span nine OD visits and can represent repeated views of the same lesions. Individual entries, scans and visits remain in the tables.

The table averages regions within each visit and then gives each visit equal weight. Availability is the fraction finite under the experimental policy; it is not validated reliability. Perilesional means the 0–100 µm exterior band, not healthy tissue. Artifact-rich nonlesion locations are reviewed background with automatic vessel, shadow or low-signal flags.

| Layer | 25 µm interior availability | Footprint edge | Perilesional | Artifact-rich background |
|---|---:|---:|---:|---:|
| Full retina | 36.8% | 54.0% | 83.5% | 3.1% |
| RNFL | 28.0% | 50.4% | 78.0% | 2.1% |
| GCL | 20.3% | 42.6% | 78.3% | 2.5% |
| IPL | 7.1% | 21.4% | 74.0% | 1.1% |
| INL | 7.0% | 21.4% | 76.7% | 1.3% |
| OPL | 22.9% | 42.2% | 82.9% | 3.1% |
| Photoreceptor composite | 25.7% | 43.6% | 83.2% | 3.0% |
| RPE band | 33.8% | 52.5% | 85.2% | 3.5% |

## Controlling for artifact and position strata

Matched nonlesion contrasts use the same acquisition, structural-signal quartile, automatic shadow/vessel status, 4×4 position cell and FOV-edge stratum. A stratum needs at least 25 eligible background pixels. Results are descriptive: neither matched pixels nor repeated lesions are independent experimental units.

| Layer | Lesion minus matched-background availability | Median matched footprint coverage |
|---|---:|---:|
| Full retina | -26.1% | 85.8% |
| RNFL | -29.7% | 85.8% |
| GCL | -39.8% | 85.8% |
| IPL | -58.2% | 85.8% |
| INL | -58.7% | 85.8% |
| OPL | -40.3% | 85.8% |
| Photoreceptor composite | -38.9% | 85.8% |
| RPE band | -30.5% | 85.8% |

There are 8 entirely unavailable layer/interior combinations out of 200. Those entries retain their unavailable fraction and have no thickness median.
Empty geometric interiors: 10 µm: 0; 25 µm: 0; 50 µm: 3. FOV-clipped footprints: 0. Empty interiors are not zero-thickness tissue.

## What the measurements do and do not support

Missing measurements also occur in reviewed nonlesion artifact regions. Shadow pixels are deliberately withheld by the automatic thickness policy, so the very low artifact-region availability is partly deterministic and is not evidence that CNV causes missingness. Availability alone therefore does not establish CNV specificity. A difference from matched background remains an association within one animal, and depends on the upstream experimental reporting/geometry policy. It does not identify a biological core or a particular cause of signal failure.

The full tables retain observed-value thickness median/IQR for every layer, lesion interior, edge and perilesional region; 10/25/50 µm sensitivity analyses; missing-layer bit combinations; and automatic cause bits. Any layer with no finite values is reported as unavailable. No thickness interpolation or imputation is used for these summaries.

Model B combines availability masks and shadow. Its comparison with A cannot isolate missingness. Model C adds numerical thickness to that combined set. Read the seed comparison before interpreting an apparent benefit.

Files: `regions_by_layer.csv`, `visit_summaries.csv`, `missingness_combinations.csv`, `matched_nonlesion_contrasts.csv`, and `lesion_geometry.csv`.

![Per-visit automatic availability](availability_by_visit.png)
