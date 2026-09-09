# Full processed volumes in the labeling GUI

Double-click [OPEN_FULL_VOLUMES.cmd](G:/OCT_TreeShrew/octa/outputs/stage_a/20260909_full_labeled_cohort/full_volume_review/OPEN_FULL_VOLUMES.cmd).

The **Volume** selector changes between the four processed volumes. The **B-scan** number and slider jump directly to any of the 512 images, numbered 0–511. Page Up / Page Down also move between images. Previously rejected images remain accessible in this full-volume view.

These packs use the already saved model predictions and the same retinal image crop as the original nine-image review packs. No model was retrained and no inference was repeated. Existing compatible manual annotations are restored by the labeling GUI; exporting these packs does not create or modify labels. All original editing and saving controls remain available.

Simply browsing does not resave an existing annotation. Actual edits and changed review decisions still save through the labeling GUI, preserving the original automatic baseline of resumed manual annotations.

The original `review_queue/packs` folder contains only the selected review candidates. The new `full_volume_review/packs` folder contains every B-scan. The numerical `experimental_measurements.npz` files are analysis arrays, not GUI packs.

Automatic boundaries are proposals, not ground truth. The model's outer boundaries remain unvalidated. Only human review and editing in the labeling GUI can create manual annotations.
