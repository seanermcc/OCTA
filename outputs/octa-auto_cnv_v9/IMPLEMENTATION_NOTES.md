# Implementation and interpretation

The authoritative training cohort is `data/supervision.json`. It contains only
the latest confirmed correction round, with exact source snapshots and derived
targets. The deferred acquisition does not enter normalization, fitting, scorer
examples, or development scoring. No upstream label or report writer is imported.

`data/protocol.json` records the fixed animal partitions, inner scorer-fitting
roles, training budget, thresholds, feature set, regularization and matching.
`data/scoring_implementation.json` pins the evaluation implementation before any
held-out candidate extraction. Final all-label fits are kept separate from the
development fits and their out-of-sample outputs.

The first incomplete microbatch-one fit was archived under
`verification/superseded_microbatch1/`. A measured batching amendment restarts
every reported fit from fresh weights with all four patches in one batch.
GroupNorm and the per-tile mean loss preserve the effective-batch calculation;
mixed-precision arithmetic need not be bit-identical. This change does not
change epochs, optimizer steps, learning rate, weight decay, or sample sequence.

The final selection is `data/selection.json`. An additional audit of lesion
events in layer-review journals replaced one acquisition before selected-scan
inference. `data/selection_initial.json` and `data/novelty_supplement.json`
preserve the original selection, deterministic same-animal reserve replacement,
and both hashes. These journals are prior CNV supervision even though they are
stored with layer reviews.

Frozen v6 predictions locate difficult **confirmed background** patches only;
they never supply CNV truth. Those historical models and the automatic layer
providers may have prior animal exposure. Animal separation applies to the new
CNV networks and scorers, not to an independently trained end-to-end acquisition
pipeline. Saved-manual vessel/ONH context is human assisted; even frozen v1 may
inherit human ONH exclusions. Empty unreviewed ONH masks remain unknown.

`reports/export_overlap_audit.json` measures the exact exported masks separately
from availability-masked channels. The measured overlap is identical for this
cohort: 924 vessel-overlap pixels and zero ONH-overlap pixels out of 58,707 CNV
pixels. These are repeated acquisition observations, not unique biological
lesions or a vascular-density estimate.

The gallery uses validated cropped native structural providers, retaining all
512 B-scans and all 512 A-lines. Canonical depth offsets and display contrasts
are explicit. B-scan footprint intersections are lateral bands outside the
structural image; they are not axial lesion segmentation. All 100 served edge
rows were compared with their underlying native image arrays.

The GUI never writes CNV labels. Preferences are browser-local and exportable
as a separate JSON document. `correction_handoff.json` retains both prediction
choices for a later, explicitly requested correction queue. No model is chosen
automatically and no next training cycle is launched.

After delivery, use `predict_bundle.py --model 1|2 --scan SCAN_ID` from an
activated `octa` environment to apply a bundle to an acquisition with an existing
validated provider. New outputs remain under this v9 release. Each child Python
stage explicitly activates conda; direct executable invocation can omit the
Windows native-library setup on this workstation.
