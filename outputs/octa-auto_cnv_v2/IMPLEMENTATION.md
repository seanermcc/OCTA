# Storage and integration contract

The implementation stays entirely in this directory. `common.py` limits pipeline
writes here and activates imports for the existing engine without changing it.
The launchers activate the octa environment before Python. `reference.py` is a
local snapshot of v1's robust reference helpers; its legacy proposal functions
are not called. `algorithm.detect` has no background input. `quantify` performs
candidate-guided reference fitting afterward; optional reviewed background cores
only affect assisted reference exclusion, never the saved automatic core output.

`loader.py` reads the fixed native exports, checks measurement/geometry hashes,
and adapts them to the existing CNV reviewer. `viewer.Window` extends that
reviewer in the same window, reusing `EnfaceCanvas`, `_brush_mask`, outline
rasterization, the embedded boundary GUI, and the RegionStore history protocol.
All map clicks retain [B-scan,A-line] coordinates; source crops are not rotated.
No structural or deficit image is labeled OCTA.

`review_store.ReviewStore` preserves the existing `1-cnv-region-review` envelope
and native row-run encoding, extending individual records with:

- `core_runs`: candidate-core draft, independent of structural `runs`.
- `edited_runs` / `core_edited_runs`: where GUI strokes touched the targets.
- `draft_category`: intended classification while review remains unfinished.
- `decision`: unreviewed, approved, or rejected; explicit GUI action required.
- `reviewed_runs` and `unreviewed_runs`: explicit approval versus draft scope.
- `seed_ids`, seed file SHA-256, events, prior revisions and coordinates.

An unfinished region is serialized with standard `category=Unclassified`, even
if its draft category is Full Lesion. Thus legacy readers do not automatically
promote partially edited seeds. Approved Normal is a reviewed region, not a CNV
footprint; consumers must honor category. Rejection retains the mask and seed as
a reviewed decision rather than deleting provenance. No pixels outside a reviewed
region become reviewed negatives. Existing study annotations are only comparison
inputs. The original automatic mask remains in `proposals/`.

Region saves use RegionStore's disk fingerprint/revision/history checks plus an
exclusive save lock. Reload saved explicitly discards the current draft only
after a GUI prompt. A different automatic seed is refused for explicit source
reconciliation; approvals are not transferred to a changed prediction. Boundary
saves retain the established local-stroke, displaced, visibility and exclusion
contract. Only GUI event handlers call annotation persistence; automated tests
use synthetic fixtures under verification and remove those temporary fixtures.

Assisted recomputation reads current saved boundary corrections through the real
thickness engine and records its metadata and correction fingerprints. Approved
lesion footprints guide exclusions; rejected/Normal cores stop excluding the
background. Original candidates still appear in the assisted output. A saved
assisted result reloads only when source-map, region-review and surface-input
hashes match; edits invalidate the in-memory result. Assisted outputs are not
human ground truth or automatic detector validation.

`VERIFY.cmd` runs the scientific/GUI fixture suite, reproduces the saved numerical
results, opens all 17 acquisitions in the actual GUI, and seals a completion
record. `COMPLETE.json` means implementation/pilot checks complete, never human
review or independent validation complete. `release_source/` is a source snapshot
for provenance, not a second runnable installation. Upstream reused modules are
fingerprinted in `dependency_manifest.json`; v1 remains in its own directory.
