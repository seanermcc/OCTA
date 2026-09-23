# TS305_OD: pooled retinal montage

28 source scans: 20 overlap-supported, 8 uncertain proposals, 0 unlocalized, 0 explicitly excluded.

Origin: **reviewed_onh**. Dates are pooled at the user's request; animal and eye are never mixed. Unresolved origins use a reference-field coordinate system, not a claimed optic-disc location.

Supported union coverage: approximately **5.28 mm²**, or **2.58 single-field areas**. Including tentative placements gives 8.10 mm²; that separate number is not established retinal coverage. Scale is approximate, 1460/512 µm per native pixel. Coverage is rasterized at 2.95 µm and excludes five border pixels and nonfinite observations.

The reviewer has independent Supported and Flagged / uncertain toggles. Uncertain proposals cannot adjust the supported graph. Fields without defensible spatial evidence remain available as native images. Explicit exclusions have no atlas transform.

33 accepted overlap constraints; 1 conflicting constraints quarantined. Registration uses vessel-anchored SIFT, full-rotation vessel-curve searches, rigid symmetric-distance refinement, neighbor consensus and joint pose fitting. Single-link fields, inconsistent overlaps, geometry-only low-contrast recovery and tentative connections carry visible reasons. No tissue is synthesized or stretched.

All placements are automatic research proposals. Internal agreement is not independent accuracy. Pooled scans may show different lesion appearances and acquisition artifacts. Neither temporal/nasal orientation nor a single-day biological state is inferred.

`registration.json`, `pair_evidence.json` and `montage.json` retain candidate transforms, alternatives, masks' provenance and review reasons. `cache_context.json` pins all consumed source files and registration code. The original data, human labels, v1 run and TS247 pilot remain unchanged.
