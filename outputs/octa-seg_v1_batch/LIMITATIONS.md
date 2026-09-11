# Material limitations for preliminary analysis

The frozen v1 deployment calibration marks ILM unsupported (`supported=false`, trace/reliability cutoffs 1.01). The unchanged v1 reporting contract therefore withholds automatic ILM. **Segmentation-reported RNFL, TOTAL and INNER_RETINA thickness are unavailable**, because they require reported ILM. This is an existing v1 behavior, not a new batch exclusion or a processing failure. The raw ILM position remains saved.

The existing octa-thick preliminary policy may use available raw/context/human positions, while retaining its established denials, exclusions, shadow masking, crossing checks and explicit-unreliability handling. Consequently it can show RNFL and full-retina values where the stricter segmentation-reported table is empty. These two policies are named and reported separately. No threshold was changed to manufacture coverage.

The model's reporting states failed animal-excluded validation. Sigmoid traceability/reliability and positional entropy are model assessments, not calibrated correctness probabilities or human visibility. These exports are preliminary review material, not a new accuracy claim.

Layer SD, IQR, MAD, percentiles and local jumps can reflect actual anatomy or CNV pathology as well as motion or segmentation errors. Within-scan SD is not measurement uncertainty. No combined acquisition-quality score is defined.

The automatic shadow stage includes its existing broad-mask safeguard (a B-scan shadow fraction above 0.6 is reset to zero), and vessel proposals may contain artifacts. The masks are preserved as separate proxies and are not human annotations. Saved vessel masks may be drafts or partly reviewed automatic proposals; provenance states this.

Human surface judgments are read through the existing adapter. Legacy whole-boundary judgments lack precise stroke locations. Explicit scan-quality ratings remain separate and blank until entered; regional Good/Bad/Unsure strip labels and generic segmentation acceptance are not converted.

Repeat comparison uses the existing translation-only fingerprint workflow. Its comparability flag is based on the best peer, while median disagreement includes all scored peers, so mixed-overlap groups require care. No between-visit registration or longitudinal change estimate is produced.

Source identity is checked using path, native shape, file size, mtime and three sampled 1-MiB SHA-256 blocks; it is not a full cryptographic hash of each 4-GB source. All derived artifact, checkpoint and dependency hashes are full-file. The two extra duplicate processed files were compared using full-file SHA-256 and are byte-identical copies of indexed acquisitions.

One complete longitudinal TS267 v1 export was reproduced with exact equality of all important measurement/state/mask arrays; see `verification/longitudinal_v1_exact_match.json`. This is a processing-consistency check, not independent model validation.
