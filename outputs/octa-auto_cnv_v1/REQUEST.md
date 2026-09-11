Build an experimental CNV segmentation and quantitative thinning workflow using the existing full-volume maps in `G:\OCT_TreeShrew\octa`.

Start with **TS267 in the longitudinal v2 thickness workflow (“octa-long-v2”)**. Read `AGENTS.md`, `README.md`, `PIPELINE.md`, the `octa-layer-segmentation` skill, and `outputs/longitudinal_assessment/START_HERE.md`. Inspect the current thickness viewer and its actual measurement policy before implementation. Activate the `octa` environment before running Python.

### Objective

Produce editable automatic CNV proposals and quantitative maps of surrounding thinning. The user’s existing manual CNV footprints were drawn from structural en-face images, where edges were often ambiguous. Treat them as evidence of lesion location and approximate extent—not exact ground-truth borders.

The observed pattern is:

- A localized center with unavailable/unreliable measurements, pronounced thinning, or both.
- A surrounding zone approximately 10–30% thinner than unaffected retina.
- A wider thinning halo sometimes extending to roughly twice the lesion diameter.

These are hypotheses to measure, not mandatory shape or threshold rules. Do not require every lesion to have a missing center, be circular, or have the same halo size.

### User’s background examples

The user marked suitable background with the cursor in three TS267 screenshots:

- `C:\Users\seane\AppData\Local\Temp\codex-clipboard-bc2faa5b-0fb0-4d0f-8d7c-c8bd9b84346c.png`
- `C:\Users\seane\AppData\Local\Temp\codex-clipboard-4a878764-9583-414a-8be5-4ce47faa03c5.png`
- `C:\Users\seane\AppData\Local\Temp\codex-clipboard-88494c32-12ff-40d5-9c47-0db0d28539a2.png`

Inspect them if available. The cursor marks apparently unaffected, measurable full retina between vessels, away from vessel shadows/exclusion zones and lesion-associated thinning. These are visual reference examples, not saved training annotations. Match them to source scans if possible; do not guess scan identities. Missing temporary screenshots should not block work.

### Background and quantitative measurements

Use native numerical arrays, not screenshot colors. Confirm which boundary endpoints define the viewer’s “Full retina” thickness and preserve that definition.

Estimate expected unaffected thickness as a spatially varying background. Do not apply the upper-right region’s mean across the entire scan: normal thickness varies spatially.

Automatically select candidate background regions excluding vessels and their surrounding affected zones, image borders, unmeasurable regions, and candidate lesions with their halos. Use an interpretable, conservative method and check sensitivity to background selection. Avoid allowing a broad lesion halo to lower its own reference.

Report percentage deficit where thickness and background are supported:

`100 × (expected background − measured thickness) / expected background`

Preserve signed values in numerical outputs. Missing thickness is not zero and must remain missing. A smooth background fit is an estimate, not recovered tissue measurement. Flag unsupported extrapolation and scans lacking sufficient background.

### Outputs

Keep these concepts separate:

1. **Candidate lesion core:** supported by localized severe thinning, clustered measurement loss, and structural context.
2. **Lesion-associated thinning footprint:** an operational quantitative extent, with the chosen rule explicitly recorded.
3. **Surrounding thinning contours:** initially show 10%, 20%, and 30% deficits and their sensitivity to background estimation. These are descriptive contours, not established anatomical CNV boundaries.

Handle irregular shapes, multiple lesions, overlapping halos, vessel crossings, and lesions clipped by the field of view. Do not automatically equate every hole or thin patch with CNV. Use existing vessel proposals/manual vessel work and structural en-face context to help distinguish artifacts.

### Provenance and circularity

Audit what caused each unavailable measurement: automatic uncertainty, vessel/shadow policy, invalid geometry, or explicit human exclusion.

Determine whether existing CNV footprints or human review decisions influenced the map inputs, model states, or reporting policy. A detector that recovers holes introduced by prior human review must be described as assisted segmentation.

Evaluate automatic performance with target CNV annotations and their downstream effects excluded from detection inputs where feasible. If this cannot be separated, document the limitation and do not claim independent detection. Keep human-assisted and automatic results distinguishable.

### Implementation and review

Start with a simple, interpretable method using existing maps. Add a small learned component only if measurements justify it; a large neural-network training project is outside the initial scope.

Build on the existing thickness/en-face viewer where practical. Provide overlays for:

- Background reference regions and estimated background.
- Candidate cores and lesion-associated footprints.
- Percentage thinning and selectable contours.
- Unmeasurable regions and uncertain or clipped margins.
- Existing manual footprints for comparison.

Allow the user to inspect the background selection and adjust or reject proposals through the established GUI annotation workflow. Automatic proposals must be stored separately from human labels. Never write human label files from a script or silently promote automatic pixels to ground truth.

Keep outputs isolated under `outputs/`. Preserve existing labels, released models, and source data.

### Validation and delivery

First deliver a working TS267 pilot across available longitudinal v2 acquisitions, including baseline/non-lesion scans and difficult examples. Do not claim longitudinal lesion change without registration.

Measure candidate agreement with reviewed manual lesion locations, apparent misses, false candidates on reviewed unaffected scans, and stability of area/contours under reasonable parameter changes. Do not count unreviewed tissue as confirmed negative or treat ambiguous manual edges as exact truth.

TS267-only tuning cannot establish cross-animal performance. Reserve other animals for subsequent evaluation and disclose any upstream model training overlap.

Run appropriate functional checks for native coordinates, units, missing-data handling, provenance, and save/reload behavior. Deliver a launcher, visual examples including failures, saved quantitative outputs, and a concise report explaining the algorithm, measurements, limitations, and next review step.

Proceed with implementation using reasonable defaults. Do not require the user to delineate background in every scan. Ask only if an unresolved scientific definition prevents a meaningful result.