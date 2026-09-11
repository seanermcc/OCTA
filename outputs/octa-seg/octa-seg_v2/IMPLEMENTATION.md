# V2 contract and locations

All new implementation and artifacts live here, including `code/octa_seg_v2`. Existing GUI/source files and original annotation files are unchanged. The new GUI imports the established native canvas, en-face reader, and `Pack.save` label writer as read-only dependencies from the project's `code` folder. The position/state checkpoint references remain the frozen v1 files; reused image and position caches retain their original paths and hashes. This is an isolated workspace, not a duplicate of the multi-gigabyte dataset.

## Round 000 policies

* Eight named boundaries retain the current meanings: ILM, RNFL_GCL, GCL_IPL, IPL_INL, INL_OPL, OPL_ONL, PR_RPE, RPE. The outer RPE endpoint is not relabeled as an independently measured Bruch's membrane.
* Finite, cropped, ordered neural ILM is solid under `ilm_working_default` (reason 12). Human unreliability, denials, hard exclusions and invalid geometry still apply. Other boundaries retain the initial v1 score thresholds.
* Uncertain candidates prefer independently checked registered context. Otherwise the current finite, noncrossing neural position is available across arbitrarily wide uncertain stretches. Candidate source codes: 0 none, 1 registered context, 2 neural proposal, 3 human position. No candidate propagates through a not-traceable or excluded interval.
* `reported_positions`, `raw_position_branch`, `uncertain_estimates`, `state`, `probabilities` and thickness array shapes retain the v1 contract. Measurement arrays use full canonical depth. Review-pack `surfaces` and `uncertain_estimates` subtract `label_offset`; compatibility `surfaces` contains only reported measurements. Full native A-line and B-scan indices are preserved.
* Shadowed thickness and thickness lacking either reportable endpoint remain NaN. Dashed candidates never enter thickness calculations. ILM working policy is explicitly recorded for consumers such as octa-thick; its existing outputs are untouched.

## Feedback

`reviewer/regional_feedback/<scan>_bNNNN.json` is the authoritative GUI-written event journal. Each record includes native half-open A-line interval, scan/B-scan identity, action, timestamp, model identity, data role, revision/history and optional reason. Candidate approvals include exact full-depth coordinates. Regional records remain separate from boundary stroke provenance and from pilot Good/Bad/Unsure ratings.

Latest regional defaults apply across all boundaries. Later explicit boundary review can override regional reliability. Clearing a region restores underlying judgments without asserting that unmarked pixels are good. Denials, hard exclusions, changed coordinates and superseding corrections revoke positional approvals. Model-specific approvals cannot transfer to a new provider. Missing marks stay unknown.

`reviewer/surface_labels` is serialized exclusively through the existing GUI `Pack.save` and `eight_surface.labels` writer. It is a compatibility view of explicitly recorded v2 events, not a replacement for original human labels. Unedited automatic values in it are never positional evidence. Journal writes use conflict checking, a short exclusive lock and atomic replacement; previous revisions and abandoned redo branches remain in history. The training importer reads only the explicit event journal and the audited v1 exact-coordinate events, not default label flags.

`datasets/*` are immutable derived snapshots. `tests/*` are excluded from every importer. Assessment feedback is held out from the new fitting/calibration being assessed. It cannot establish generalization to an animal already seen by an ancestor checkpoint.

## Comparisons

`round_000/reports/effect_decomposition.csv` separates historical six-volume pilot coverage, v1 with current footprints, original-human-guard effects, and v2 policy effects. The same unchanged position model is used throughout; footprint changes affect both state-head inputs and the decision defaults. None of these effects is a learned change.

`boundaries.csv` retains finite coverage, entropy, invalid/crossing fractions and jump/spike diagnostics. `thickness.csv` retains mean, median, SD, IQR, finite coverage and local variation together. `acquisition_context.csv` keeps signal/motion/repeat axes separate. ONH distance uses only existing masks or a labeled partial-edge proxy; absent marks stay unknown. Figures show CNV context without adjusting the model toward a common thickness profile.

The four additional scan identities, selection pool, random seed and animal-balanced sampling rationale are frozen in `manifest.json`. They are not replaced based on model appearance. Read-only saved vessel work, including reviewed-empty masks and drafts, takes precedence over automatic proposals. The two pilot acquisitions without vessel work now have isolated automatic shape-gated proposals under `proposals`, with automatic provenance and no human label files.
