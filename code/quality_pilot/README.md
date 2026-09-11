# Frozen-v1 six-volume quality pilot

Activate the `octa` environment, set `PYTHONPATH` to the repository's `code`
directory, and run these separate processes in order:

```text
python -m quality_pilot.prepare
python -m quality_pilot.infer
python -m quality_pilot.export
python -m quality_pilot.analyze
python -m quality_pilot.finish
python -m quality_pilot.verify_gui
```

The first three stages resume at completed scans/B-scans. Inference reuses the
unchanged v1 neural functions; model weights, calibration and inference/decision
code are fingerprinted before starting and checked on each stage. No v1 folder,
input volume or original human annotation is written. CPU reporting and GPU
inference use separate processes to respect the workstation's BLAS constraints.

Outputs are under `outputs/octa-seg/quality_pilot_20260910`. Open its
`OPEN_QUALITY_REVIEW.cmd`. The existing CNV reviewer loads `QualityEditor` only
when `quality_review_queue` is configured. The mode intercepts mouse gestures
before the original canvas sees them; existing editing works when it is off.
Quality records have their own schema and folder, and are never loaded as
boundary annotations or training targets. The launcher intentionally presents
automatic curves before human overrides for the pilot ratings.

`UPDATE_RATING_COMPARISON.cmd` refreshes the separate random/targeted assessment,
including Unsure and reratings after warning revelation. It does not train or
calibrate a model. Human assessment and the resulting next-step decision remain
pending until actual ratings are supplied.

```text
python -m unittest quality_pilot.test_pilot octa_seg_v1.test_reviewer -v
python -m unittest octa_seg_v1.test_contract -v
python -m unittest cnv_review_v1.test_review -v
```

The controlled checks cover gaps, isolated spikes versus steps/broad changes,
shadow/crossing handling, ONH coordinates, sampling separation, rating persistence,
and real mouse-event separation from boundary/exclusion edits. `verify_gui` checks
real native source crops on both new scans and saves offscreen screenshots. It
does not claim that a GUI window is visible on the user's desktop.

Keep the numerical contract suite separate from the GUI suite on this workstation.
The combined process terminated inside NumPy correlation after Qt tests; both
suites pass in separate activated processes.
