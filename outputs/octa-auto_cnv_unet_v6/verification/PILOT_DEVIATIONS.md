# Choices and bounded deviations

- Outputs use the user's revised folder name, `octa-auto_cnv_unet_v6`, with A/B/C in separate experiment folders.
- The annotation refresh found 34 conflicting pixels in D0 OD. Only those pixels were ignored; valid existing supervision was sufficient to proceed. No source annotation was repaired or written.
- Automatic maps were recovered from preserved neural positions and probabilities, rather than the live GUI's human-aware thickness maps. Existing automatic trace-denial, geometry and shadow rules were retained. Upstream human guards and current correction sources were inventoried and excluded from inputs.
- The first two-tile overfit check at 160 steps reached Dice 0.972, but its loss of 0.530 did not yet pass the conservative loss-reduction check. Extending this diagnostic to 800 steps gave Dice 1.000 and loss 0.0104. The diagnostic weights were discarded; every experiment started from random initialization.
- Batch size four fit the RTX 3060 Ti. All models kept the requested 100-epoch maximum, 32 batches per epoch, and patience 15. All nine runs stopped through validation patience. Checkpoint and threshold selection used D49 alone.
- Training was fast enough to run all three experiments at seeds 267, 268 and 269. The primary review overlays remain seed 267; no best holdout seed was selected. No all-label refit or depth architecture was added.
- The unchanged v3 suggestions are its saved candidate cores. They were evaluated exactly as saved, although the new model's target is a whole reviewed footprint. This comparison therefore includes a footprint-definition mismatch; detection and border metrics are reported separately.
- Three processed-volume reconstructions independently checked one training, validation and holdout example. Every reconstructed OCTA projection and selected structural B-scan matched the corresponding saved numerical input exactly. The 17-scan manifest additionally retains source/grid/crop identity, hashes, and automatic neural provenance.
- Review actions are comparison-derived proxies until a human inspects the new suggestions. The local reviewer records actual actions and focus-active time. No human review session or time-saving estimate was fabricated.

The pilot remains a within-TS267 development study with repeated tissue and upstream ALL_LABELLED exposure. Three random seeds do not make three biological replications.
