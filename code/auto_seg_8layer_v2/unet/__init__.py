"""Phase 1 data pipeline and evaluation harness for the multi-task U-Net.

See ``outputs/auto_seg_8layer_v2/UNET_PLAN.md``.  This package contains **no**
model or training code: it builds inputs, targets, masks and folds, and scores
predictions against the human labels.  Every module is importable and testable
on its own; ``test_phase1.py`` exercises all of them.
"""
