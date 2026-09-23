# octa-reg_v1 — completed vessel-only experiment



Run status: **complete**. 10 acquisitions, 1 animal–eye groups, 45 same-eye candidate pairs.

0 pairs passed fixed internal gates; 45 rejected; 0 blocked; 0 implementation failures.

0 scans connect through passing edges; 0 belong to consistent multi-scan components. 10 singletons remain independently positioned. 0 components are withheld for loop disagreement.

Elapsed wall time: 11.7 s; summed pair compute 8.6 s; 0 pairs resumed.



## Measured strata



```json

{
  "mask_sources": {
    "primary_export": 10
  },
  "selections": {
    "frozen_v1": 8,
    "saved_manual": 2
  },
  "mask_source_performance": {
    "primary_only": {
      "rejected": 45,
      "total": 45
    }
  },
  "review_state_performance": {
    "both_reviewed": {
      "rejected": 1,
      "total": 1
    },
    "mixed": {
      "rejected": 16,
      "total": 16
    },
    "neither_reviewed": {
      "rejected": 28,
      "total": 28
    }
  },
  "interval_performance": {
    "within_session": {
      "rejected": 45,
      "total": 45
    }
  },
  "rejection_gates": {
    "insufficient_vessel_anchored_inliers": 45
  }
}

```



## Review and interpretation



Open index.html or OPEN_GALLERY.cmd. Each component has its own coordinates. Select one date for imagery; across-date view shows footprints only. Pair view supplies alpha/flicker and selected vessel/ONH/centerline overlays. A rejected fit with a matrix is explicitly diagnostic. No-fit pairs appear side by side with no implied alignment. Click images to recover native B-scan/A-line indices.

The queue has 1 deduplicated pairs: highest, median and lowest passing Dice per eye, plus failure examples. independent_landmarks is deliberately empty, with three separated overlap regions suggested for later annotation. No human accuracy measurement exists.

Automatic junctions, Dice, RANSAC residuals and loops are internal support only. The inherited baseline does not model bend sequences, crossings versus bifurcations, path lengths or full vascular topology. Lesion-related structural features can still influence descriptors despite vessel gating. CNV mode is off.

ONH circle fits retain 150 degree arc, 25 um residual and 150 um uncertainty gates. Only assessable reviewed fits are anatomical evidence. Unreviewed fits and vessel convergence remain proposals. Straight branch fragments can share a trunk and are not necessarily independent; convergence cannot establish rotation or bridge components.

Relative registration and ONH disagreement are separate: ONH disagreements prompt review without invalidating vessel-consistent components. Only registration cycle inconsistency withholds a connected component. The forest is not joint global optimization.

The en-face cache sidecar documents fresh depth orientation; no en-face flips or resizing are applied. Physical calibration is approximate unless explicitly validated. Sources are read-only; source_integrity.json records post-run hashes of every consumed cache, sidecar and mask. Processed volume identities/fingerprints are inherited from verified cache sidecars, not rehashed as terabyte-scale raw inputs.

Unavailable input is retained as blocked. Missing ONH is unknown. Empty selected vessels remain empty. Saved manual records include drafts and inherited automatic pixels; review states are shown independently. No CNV/lesion masks, layer measurements, model loaders or raw reconstruction are used.



## Prioritized next measurements



1. Annotate independent correspondences in the queued passing and rejected cases; inspect vessel mask omissions, motion stripes and cropped overlap before attributing matcher failures to anatomy.

2. Insufficient vessel-anchored inliers dominate rejections: compare corrected-mask support and curved-vessel/bend/topology descriptors on this frozen queue before changing matching gates.

3. Evaluate global optimization only within independently validated connected components if loop inconsistency is substantial. It cannot resolve missing overlap or justify joining disconnected fields. ONH localization is a separate lower-priority experiment for components without reviewed disc evidence.



## Future CNV adapter contract



A separately versioned comparison may accept scan_id, source identity, native Boolean mask and [B-scan,A-line] grid, model/review provenance, revision/SHA256, and coverage/unknown status from a verified v9 or later export. The signature reserves cnv_snapshot=null. Import final policy-aware masks, never gallery thresholds/browser preferences. Missing masks mean unknown. CNV may be overlaid or evaluated as an alignment exclusion; do not match evolving lesions, propagate them across dates or alter this saved vessel-only baseline.



## Implementation notes



Adapter correction during execution: five newer TS336 records omitted optional n_slow/n_fast inventory fields. Their existing optical cache and fresh-source sidecar agree on the native grid; the adapter now validates dimensions when present and records the sidecar basis otherwise. The complete cohort was rerun with this correction. Uncertain ONH regions are removed from original visible edges without manufacturing a boundary around an uncertainty hole. Failed RANSAC consensus diagnostics are recovered by an identical deterministic reporting-only fit. These changes do not relax any matching gate.

See verification/ for contract tests, smoke/resume checks, source integrity, numerical coordinate audits, visual review notes and known limits. The command `python outputs/octa-reg_v1/verify_release.py` independently audits the final products and tests rotation recovery between unequal physical grids.

Pure control_map_v1.geometry functions are imported unchanged. The new forest wrapper uses actual image corners for cycle checking, keeps ONH disagreement separate, and stores explicit pixel→physical→component transforms/inverses. All matching constants and implementation hashes are frozen in snapshots/. Only pair artifacts resume; preparation, components and reports are rebuilt. Two compute threads and one atomic writer are used. No relaxed gates or alternative matcher is selected after seeing outcomes.