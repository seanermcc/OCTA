# Final CNV assessment

Double-click **OPEN_FINAL_CNV_ASSESSMENT.cmd**, or open
[the running assessment](http://127.0.0.1:8805/).

The September 22 snapshot displays **218 CNV entries across 217 acquisitions**:
**73 manual training references, 10 Model 2 results, 78 Model 3 results and
57 newly confirmed Model 3 correction results**. The second view contains
**105 confirmed no-CNV samples and two deferred / poor-image samples**.
All 324 acquisitions are represented across the two views. Each image is
Structural OCT en face with one selected set of final CNVs. No OCT-A, vessels,
ONH or competing-model overlays are shown.

Click an image to enlarge it. Use **Needs review**, **Good**, and optional notes.
The CNV display menu switches between outline, light fill and hidden. Use the
source/assessment filters or search an animal, date or scan ID. Arrow keys move
between samples in the enlarged view; O toggles the overlay. Notes also save
when moving to another sample or closing the enlarged view. Wait for **Saved to
disk** before closing the browser. In the manual / good CNV group, entries
without a Needs review flag count as **Good (default)**. After reviewing the
collection, click **Confirm all samples** to save explicit approval for all
unflagged CNV entries, including entries hidden by filters. Existing review
flags and notes are preserved. This button never confirms the no-CNV/deferred
view; deferred samples remain uncertain rather than becoming negatives.

## Selection

- Manual / training is the exact frozen Model 3 training reference, including
  hand-corrected masks and explicitly approved model outlines used for training.
  It takes precedence over the original model predictions for those acquisitions.
- Both models confirmed: choose Model 3 (53 non-training acquisitions).
- Only Model 3 confirmed: choose Model 3 (25 non-training acquisitions).
- Confirm Model 2 + Review Model 3: choose Model 2 as final/good (10 acquisitions).
- All 57 saved, completed positive Model 3 correction reviews are included
  using their confirmed edited masks, not the original predictions.
- The second view contains 77 explicit no-CNV decisions, 28 training negatives
  and two still-unconfirmed poor-image cases. Their original notes are retained.
- One training acquisition, TS267_OD_2025-02-19_D0_s02_112013, also carries a
  completed Model 3 correction. Both its original training reference and newly
  confirmed correction are kept as separate, clearly labeled entries, with
  independent assessment flags. This accounts for 218 entries / 217 acquisitions.

## Saving and provenance

New assessments save only to `assessment/decisions`, with append-only revisions
in `assessment/history`. Collection approvals are saved atomically in
`assessment/batches`; later individual flags supersede the saved bulk approval.
Original training targets and v9 model review records
are never written. **Export assessments** downloads JSON with the current
assessments, flagged sample selection provenance and both collections.

The local server binds to 127.0.0.1:8805. Opening index.html directly cannot save
assessments; use the launcher. The gallery is a deliberate snapshot, so later
changes to the old Model 2/3 reviewer do not silently replace these masks.
Tokens bind assessments to selected masks and source revisions. Stale browser
saves are rejected instead of overwriting another tab's work.

`build.py` reproduces the snapshot from the Model 3 frozen supervision and
current Model 2/3 decisions and completed correction reviews, verifying prediction contracts, selected mask
hashes, training targets, image hashes and acquisition identity. Run it only
when deliberately refreshing the selection, then restart the local server.
`verify.py` checks all 761 display assets and source preservation.
Activate the **octa** conda environment before running either Python script.

`test_assessment.py` tests the selection rules, durable revisions, stale-save
rejection, bulk confirmation, flag/note preservation, secondary-view exclusion
and invalid inputs with synthetic temporary records. Browser save
testing uses port 8806 and `verification/ui_v2_assessments`, entirely separate
from the real assessment directory. Test flags are not human judgments.

The displayed CNVs retain their existing human confirmation. The new interface
does not itself provide a biological quality assessment or retrain a model.
