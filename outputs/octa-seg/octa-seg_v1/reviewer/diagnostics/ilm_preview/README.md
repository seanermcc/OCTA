# ILM inspection overlay — GUI extension

The current CNV reviewer offers **Show model ILM (white dots; view only)**,
enabled when the reviewer opens. Restart the reviewer with the existing
`OPEN_OCTA_SEG_V1.cmd` launcher to load the updated interface.

The overlay reads `raw_position_branch` from each frozen volume's
`measurements.npz` and applies the saved canonical crop offset. It does not
alter the v1 model, predictions, calibration, reported positions, thickness,
training dataset, or original release source snapshot.

Human not-traceable markings, image exclusions, rejected reviews, automatic
not-traceable states, and invalid coordinates create gaps. Human unreliable
markings allow this explicitly unvalidated inspection overlay; they do not
turn it into a measurement. The overlay is never copied into the editable
label arrays or uncertain-candidate approval targets. To supply a corrected
position, use the existing draw-and-explicitly-approve workflow.

Implementation: `code/octa_seg_v1/ilm_preview.py` and the current reviewer
adapter. Verification: `python -m unittest octa_seg_v1.test_ilm_preview
octa_seg_v1.test_reviewer cnv_review_v1.test_review -v` (26 tests passed).
`verification.json` records checks on all four volume sources;
`reviewer_preview.png` is an offscreen rendering, not proof of desktop visibility.

The original `START_HERE.md` and `code_snapshot` remain frozen records of the
initial scientific release. This note documents the later display extension.
