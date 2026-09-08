# Experimental Stage A pipeline

The runnable package is `stage_a`, with project `code` on `PYTHONPATH` and conda `octa` activated. The prepared snapshot and command guide are in `outputs/stage_a/20260908_v2/`.

`audit` freezes standard first-round decisions, scope masks and metadata; `cache` builds native single-B-scan images; `partitions` freezes animals; `train` implements the small U-Net, masked losses and checkpoint/resume; `evaluate` reports column-level and thickness errors with coverage; `inference` writes resumable native-coordinate predictions. `test_stage_a` covers mask, geometry, evaluation, split, checkpoint and inference invariants.

No component writes human annotations or reads the repeatability label tree. Derived target arrays are training artifacts, not human-label files. The final-test partition is locked by default. See the dated audit for the unavoidable legacy surface-wide supervision limitation.

Current output is experimental. The smoke checkpoint is a software test, never a release model. Full training, calibration, scientific acceptance and production promotion remain separate work.
