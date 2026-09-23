# octa-reg_v1 — completed vessel-only experiment



Run status: **complete**. 324 acquisitions, 19 animal–eye groups, 3695 same-eye candidate pairs.

15 pairs passed fixed internal gates; 3629 rejected; 51 blocked; 0 implementation failures.

25 scans connect through passing edges; 25 belong to consistent multi-scan components. 299 singletons remain independently positioned. 0 components are withheld for loop disagreement.

Elapsed wall time: 445.5 s; summed pair compute 435.5 s; 0 pairs resumed.



## Measured strata



```json

{
  "mask_sources": {
    "primary_export": 314,
    "legacy_geometry_fallback": 10
  },
  "selections": {
    "frozen_v1": 256,
    "saved_manual": 58,
    "automatic/unreviewed": 10
  },
  "mask_source_performance": {
    "fallback_involved": {
      "rejected": 245,
      "total": 245
    },
    "primary_only": {
      "rejected": 3384,
      "automatic_proposal": 15,
      "blocked": 51,
      "total": 3450
    }
  },
  "review_state_performance": {
    "both_reviewed": {
      "rejected": 111,
      "automatic_proposal": 5,
      "total": 116
    },
    "mixed": {
      "rejected": 778,
      "automatic_proposal": 1,
      "blocked": 14,
      "total": 793
    },
    "neither_reviewed": {
      "rejected": 2740,
      "automatic_proposal": 9,
      "blocked": 37,
      "total": 2786
    }
  },
  "interval_performance": {
    "across_date": {
      "rejected": 3008,
      "blocked": 45,
      "automatic_proposal": 6,
      "total": 3059
    },
    "within_session": {
      "rejected": 621,
      "automatic_proposal": 9,
      "blocked": 6,
      "total": 636
    }
  },
  "rejection_gates": {
    "branch_matches": 81,
    "insufficient_vessel_anchored_inliers": 3548,
    "structural_correlation": 8,
    "vessel_dice": 2
  }
}

```



## Review and interpretation



Open index.html or OPEN_GALLERY.cmd. Each component has its own coordinates. Select one date for imagery; across-date view shows footprints only. Pair view supplies alpha/flicker and selected vessel/ONH/centerline overlays. A rejected fit with a matrix is explicitly diagnostic. No-fit pairs appear side by side with no implied alignment. Click images to recover native B-scan/A-line indices.

The queue has 17 deduplicated pairs: highest, median and lowest passing Dice per eye, plus failure examples. independent_landmarks is deliberately empty, with three separated overlap regions suggested for later annotation. No human accuracy measurement exists.

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

## Audited examples and checks

See [representative cases](verification/REPRESENTATIVE_CASES.md), [verification notes](verification/VERIFICATION.md), [release audit](verification/release_audit.json), and [resume/invalidation check](verification/resume_invalidation.json).


## Coverage by animal and eye

| Animal | Eye | Scans | Eligible | Connected | Candidate pairs | Blocked pairs | Within-session proposals | Across-date proposals |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| TS165 | OD | 10 | 10 | 2 | 45 | 0 | 1 | 0 |
| TS165 | OS | 10 | 10 | 0 | 45 | 0 | 0 | 0 |
| TS169 | OD | 9 | 9 | 2 | 36 | 0 | 1 | 0 |
| TS169 | OS | 4 | 4 | 2 | 6 | 0 | 1 | 0 |
| TS241 | OD | 26 | 26 | 0 | 325 | 0 | 0 | 0 |
| TS241 | OS | 19 | 18 | 0 | 171 | 18 | 0 | 0 |
| TS247 | OD | 34 | 33 | 2 | 561 | 33 | 1 | 0 |
| TS247 | OS | 12 | 12 | 0 | 66 | 0 | 0 | 0 |
| TS250 | OD | 10 | 10 | 0 | 45 | 0 | 0 | 0 |
| TS250 | OS | 9 | 9 | 0 | 36 | 0 | 0 | 0 |
| TS267 | OD | 28 | 28 | 0 | 378 | 0 | 0 | 0 |
| TS267 | OS | 27 | 27 | 2 | 351 | 0 | 1 | 0 |
| TS283 | OD | 10 | 10 | 3 | 45 | 0 | 2 | 0 |
| TS283 | OS | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| TS305 | OD | 28 | 28 | 2 | 378 | 0 | 0 | 1 |
| TS305 | OS | 2 | 2 | 0 | 1 | 0 | 0 | 0 |
| TS325 | OD | 34 | 34 | 0 | 561 | 0 | 0 | 0 |
| TS328 | OD | 21 | 21 | 10 | 210 | 0 | 2 | 5 |
| TS336 | OD | 30 | 30 | 0 | 435 | 0 | 0 | 0 |


## Next measured experiment

The primary bottleneck is vascular correspondence: 3548 of 3629 rejected pairs lacked sufficient vessel-anchored inliers; 81 failed junction support. A concrete review example has Dice 0.919, 55 inliers and 0 matched junctions (TS247_OD_2024-11-26_D42_s06_115502 to TS247_OD_2024-11-26_D42_s07_115937). Its major trunks align closely in the diagnostic overlay, but no independent human accuracy has been measured. Use the saved independent-landmark queue to separate mask omissions and motion artifacts from descriptor failures, then test curved-vessel/bend and centerline-constellation matching for fields with few junctions. This is a separately versioned comparison, not a change to these gates. Global optimization is a later priority: only 1 non-tree loop check is available in this sparse graph. ONH localization cannot repair missing tissue correspondences and remains a separate proposal task.
