# octa-seg_v2 — focused review release

Open **[OPEN_OCTA_SEG_V2.cmd](OPEN_OCTA_SEG_V2.cmd)**. Everything new is in this folder. The existing GUIs, original annotations, v1 release, quality pilot and octa-thick outputs are unchanged.

**round_000 contains all ten complete volumes: 5,120 native B-scans.** It uses the existing neural model with a solid working ILM and more dashed candidates. This is a workflow/policy release, not a newly trained or validated improvement.

## First review session

Use **Next example** to work through the 30-example queue, or browse any scan and B-scan. Aim for 20–30 minutes; stop by 60. Ten random assessment B-scans remain separate from fitting. Twenty suggested training examples mix difficult areas and good-signal approvals.

* **Unreliable region** is the default. Drag horizontally over a vertical strip to withhold measurements across all eight boundaries. Available candidates remain amber dashes. The selected A-line interval is native and exact.
* **Clear regional mark** restores the underlying judgments; it does not label the region good.
* **Approve shown measurements** affirms only finite, visible solid segments in the selected range. It does not approve hidden boundaries or dashed guesses for position training.
* Choose **Edit boundary** to draw a selected boundary with the established gestures. A correction stays uncertain for measurement until affirmed.
* **Approve selected candidate position** records its exact coordinates for future position training. **Affirm selected boundary measurable** is a separate action; it can establish an ILM exception inside an otherwise unreliable strip.
* **Not traceable** removes both the selected boundary's measurement and candidate. **Exclude unusable image** suppresses all boundaries in that interval. In Edit mode, Ctrl+right-drag clears a v2 image exclusion.

Undo/redo and saves preserve revision history. Bookmarks, neighboring slices and the previous-policy comparison are available. Boundary checkboxes control display only. Scores, entropy/spike warnings and provenance sit behind **Inspect scores and provenance**. CNV/vessel/ONH overlays are read-only context; use **Refresh saved overlays** after editing them in their separate GUI.

## What is ready

* [Fixed ten-volume manifest](manifest.json), including the random selection pool and seed.
* [Complete round exports](round_000/volumes), [review providers](round_000/review_packs), and [30-example queue](round_000/review_queue.json).
* [90 diagnostic figures](round_000/figures): eight boundary dashboards and one three-B-scan sheet per volume.
* [Boundary coverage and warnings](round_000/reports/boundaries.csv), [thickness distributions](round_000/reports/thickness.csv), and [acquisition context](round_000/reports/acquisition_context.csv).
* [Policy/footprint/guard effect separation](round_000/reports/effect_decomposition.csv). Changes to vessel inputs are separated from ILM/candidate policy changes. No change is attributed to learning.
* [Native-volume verification](tests/volume_verification.json), [30 source-image alignment checks](tests/native_alignment.json), [real Qt interaction checks](tests/gui_verification.json), and [checkpoint ancestry audit](checkpoint_ancestry.json).
* [Training and resume commands](TRAINING_AND_RESUME.md) and [implementation/data contract](IMPLEMENTATION.md).

![Focused v2 reviewer](tests/screenshots/focused_reviewer.png)

## What awaits your feedback

The prior v1 feedback contains **26 exact corrected columns on one B-scan, with no affirmative reliability examples**. The audited training command preserved the current model because this is insufficient balanced feedback. Its decision is recorded in [round_001/training_status.json](round_001/training_status.json).

False-solid reporting, retention in explicitly approved good regions, candidate usefulness and positional improvement await withheld human assessment. Old Good/Bad/Unsure pilot ratings and whole-volume praise are not boundary training labels. The new default solid ILM is a working-policy decision, never a positive training label. Dashed candidates never enter thickness maps; shadowed and unreportable measurements remain NaN.
