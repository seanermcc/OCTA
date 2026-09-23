# Confirm CNVs in the web preview

Open **OPEN_GALLERY.cmd**. The same 50 acquisitions and frozen predictions remain available.

- **Confirm Model 1 CNVs** approves Model 1's complete result for this acquisition.
- **Confirm Model 2 adjusted CNVs** approves the fixed adjusted selection. Recovering hidden raw candidates for inspection does not add them to this confirmation.
- **Review Model 2** flags the acquisition for later GUI correction and clears its Model 2 confirmation. Confirming Model 2 clears the correction flag.

Check the entire field for missed or extra CNVs and outline errors before confirming. Confirming a zero-candidate result explicitly confirms no CNV. Unchecked means unconfirmed, never negative. Notes save when you leave their field. Wait for “Saved to disk” before closing the page.

Decisions are saved under **manual_review/decisions/** with immutable revision history in **manual_review/history/**. Each decision records exact model/prediction hashes, selected candidate IDs, native mask digests and thresholds. A changed prediction or concurrent edit is rejected rather than silently reusing the approval. All existing browser model preferences remain separate.

The current Model 2 correction list is **manual_review/model2_queue.json** (created after the first saved decision). The export controls also download the latest complete decisions or correction list. This is a list for preparing the later GUI queue, not a set of fabricated corrected masks.

**Both are good is a valid final approval**, even when the outlines differ. Confirmation means an acceptable outline, not a uniquely exact boundary. No conflict is raised solely because two approved masks differ.

For a future shared training target, prefer **confirmed Model 2 adjusted**; if only Model 1 is confirmed, its approved mask is the available target. Never substitute an unconfirmed Model 2 result. A Model 2 correction flag withholds its eligibility until it is corrected and confirmed. Both masks and both approvals remain available for optional model-specific training: Model 1 can use its own approved masks, and Model 2 can use its own approved adjusted masks. Nothing is unioned or counted as two independent scans.

The policy is recorded in **manual_review/training_target_policy.json** and applied by **review_store.interpret_approval** on read/export, including older saved approvals. Original decision files, notes and history are preserved. A historical `needs_target_resolution` field is superseded by this policy; future training code must consume the policy-aware export rather than interpret that legacy field in isolation. No retraining runs from these controls.

## Recommended next round

1. Review these 50 and finish GUI corrections for flagged cases, including missed CNVs. Accept reasonable boundary variation. For a shared dataset, use the approved-target preference above; keep genuinely unassessable areas unknown.
2. Retrain using valid prior corrections plus these completed reviews, with animal-grouped evaluation and training-only normalization. Fit the candidate scorer again on out-of-sample predictions.
3. Audit a separate balanced set of about 50 acquisitions after retraining. Freeze this audit selection before seeing the new predictions and keep it outside that fit. Include negatives, low-signal scans, small lesions, hidden candidates, model disagreements and a representative random component. Prefer animals outside fitting if available; otherwise call it an acquisition-level audit of represented animals.
4. If recall, false positives and footprint area errors meet your reporting needs across those groups, run inference over all eligible processed acquisitions and retain a flagged-review path. If the audit reveals systematic misses, use targeted correction and another independent audit rather than treating the full-cohort predictions as confirmed labels.

“About 50” is a practical audit batch, not a statistically guaranteed validation sample size. v9 adjusted Model 2 reduced held-out false positives from 1.86 to 0.17 per acquisition, but its recall fell from 81.8% to 50.0%. Its clean appearance alone does not establish that omitted lesions are absent. All current gallery animals were represented in the final v9 fit, though these acquisitions were not used in fitting.

This recommendation is based chiefly on the local v9 measurements. For general context, [Active label cleaning for improved dataset quality under resource constraints](https://www.nature.com/articles/s41467-022-28818-3) studies annotation quality, and [Suggestive Annotation](https://arxiv.org/abs/1706.04737) studies selecting both informative and representative samples for biomedical segmentation.

For the next controlled Model 1/Model 2 comparison, a common approved target set is the simpler default: changing both the model inputs and its training targets would mix their effects. Model-specific targets remain a valid separate experiment. Multiple plausible segmentations are an established way to represent boundary ambiguity; see [A Probabilistic U-Net for Segmentation of Ambiguous Images](https://arxiv.org/abs/1806.05034). This release preserves approved alternatives without introducing a new probabilistic architecture or claiming one is necessary.
