# octa-seg_v1 implementation and commands

Versioned implementation: `code/octa_seg_v1`. Integration edits add an opt-in editor/queue hook, an initial-scan setting, and read-only fallback for existing CNV region classifications to `code/cnv_review_v1`. The existing vessel-proposal selector also now recognizes an empty manually brushed mask as saved work; this changed none of the frozen cohort's masks.

Activate octa before running Python. Stages, in order:

```
python -m octa_seg_v1.audit
python -m octa_seg_v1.train
python -m octa_seg_v1.predict labels
python -m octa_seg_v1.evaluate
python -m octa_seg_v1.predict volumes
python -m octa_seg_v1.export
python -m octa_seg_v1.queue
python -m octa_seg_v1.report
python -m octa_seg_v1.verify
```

Use the release runner for resuming, not multiple concurrent stage commands. Inspect progress.json and the runner lock before restarting. All completed position/state checkpoints are preserved. The source volume and neighboring context are read again only when a volume's neural stage was interrupted before its completion marker; completed per-B-scan network inference is reused.

Tests run in separate processes because this installation's Torch and NumPy BLAS libraries load incompatible OpenMP runtimes. No unsafe duplicate-runtime override is used. Neural training/inference use Torch and non-BLAS array operations. Registration, evaluation, plotting and GUI work are Torch-free.

Tests:
```
python -m unittest octa_seg_v1.test_contract -v
python -m unittest octa_seg_v1.test_neural -v
python -m unittest octa_seg_v1.test_reviewer cnv_review_v1.test_review -v
```

Operational state codes: 1 reliable (experimental); 2 not traceable; 3 uncertain. Reason codes are in `octa_seg_v1.decisions.REASONS`; context_reason 0 means a candidate met all context gates, 1 means insufficient/forbidden context. All arrays use B-scan,boundary,A-line except masks (B-scan,A-line), images (B-scan,depth,A-line), probabilities (B-scan,boundary,traceability/reliability,A-line), and thickness (B-scan,layer,A-line).

Feedback is intentionally outside the frozen dataset. `approved_position_mask` in the GUI adapter requires a latest explicit per-column approval, unchanged stored coordinates, affirmative current visibility/reliability, and no displacement/exclusion/rejection. An unchanged approved automatic candidate retains `local_reviewed`, not `local_drawn`; a v2 importer must opt into explicit approval events separately. Generic review verdicts never grant this approval. A later denial or changed position invalidates earlier approval.

Limitations: four evaluation animals; sparse clustered state annotations and very few direct ILM positions; state heads share evidence features across boundaries; all-label initialization inherits legacy approximation; no calibrated probability or clinical/research reliability guarantee; fixed motion/context gates can reject recoverable shapes; no OCTA intensity channel was trained (OCT image plus en-face OCTA-derived vessel context); automatic vessel seams/lesion artifacts remain possible; local rigid translations cannot resolve all nonrigid motion. No full 314-volume run was attempted.
