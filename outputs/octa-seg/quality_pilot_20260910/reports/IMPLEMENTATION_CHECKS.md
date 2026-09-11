# Implementation checks

43 distinct tests passed across the pilot (9), existing v1 reviewer (8),
measurement contract (12), and existing CNV review workflow (14).

The numerical contract suite and GUI suites were run in separate activated
processes. A combined run terminated during NumPy correlation after the Qt
tests; separate runs completed successfully. The reproducible commands are in
`code/quality_pilot/README.md`.

Real-data verification confirms:

- Six complete exports, 512 B-scans and eight boundaries each.
- The original four raw predictions and entropy are identical to the frozen
  results; their recomputed states equal the saved automatic states.
- Model weights, calibration and v1 prediction/decision code hashes are unchanged.
- Both new GUI volumes match their canonical source crops at native rows 0,
  255 and 511. Provider rows and crop offsets agree with full-depth results.
- Primary thickness is NaN under shadow masks; not-traceable locations have no
  uncertain candidate.
- 48 boundary-map images and 24 suggestions are present: two random, one entropy,
  and one spike selection per scan, with the specified spatial separation.
- Controlled gaps do not bridge; isolated spikes, steps, and broad deformations
  produce distinct diagnostics without changing the input surface.
- Actual quality-mode mouse events leave boundary coordinates, provenance,
  visibility and exclusion states untouched. Undo/clear/reopen remain separate.
- Real-volume GUI verification produced no boundary labels or quality ratings.
  Offscreen screenshots were visually inspected; this is not a claim that a
  desktop window was opened for the user.

Regional human judgments remain pending (0/24 suggested strips rated).
