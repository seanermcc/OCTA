# octa-reg_v2: all-sample retinal registration

19 animal-eye groups; 324 scans accounted for. Dates pooled by request. OD and OS are always separate. 167 supported placements, 154 uncertain proposals, 1 unlocalized fields, 2 explicit exclusions.

The placement reviewer starts with both supported and flagged fields visible. **Show flagged / uncertain** toggles best-effort proposals with orange outlines and their reasons. Day checkboxes, confirmation, and drag/rotate correction are described in `REVIEW_GUIDE.md`; saved placement reviews remain separate from this automatic report. Selecting a field exposes its native image, source date, reasons and overlap evidence; opacity and blink permit visual inspection. An unlocalized field remains inspectable without a fabricated position.

Maps without a reviewed disc explicitly distinguish an estimated ONH from an unresolved reference-field origin. Vessel convergence is a directional clue, not a substitute for registration. Tentative overlaps and anatomy-only placements cannot move the supported backbone or enter the supported-coverage total.

Methods follow the `octa-reg_v2` skill: vessel-anchored SIFT, rigid RANSAC, symmetric centerline refinement, whole-vessel full-rotation searches, neighbor-consensus checks, global rigid fitting, and separately flagged low-contrast or tentative proposals. A separate ONH-consistency pass constrains alignment using reviewed disc centers, rejects anatomically contradictory edges and flags remaining origin disagreements. Thresholds and the search plan are in the source code pinned per group; `anatomy_code_hashes.json` pins the additional check. No layer segmentation, RAW reconstruction, training, label editing, nonrigid distortion or synthesized tissue was performed.

Verification: passed; 324 inventory rows; 1612 consumed source files unchanged. Every stored pose and inverse is rigid and finite; explicit exclusions lack transforms; every edge remains within one animal-eye group. These checks and internal overlap scores do not establish independent registration accuracy. Review the flagged fields before interpreting coverage or making anatomical measurements.

The original TS247 OD pilot and v1 outputs are preserved. Run details and all candidate evidence are in each group's folder. Open `OPEN_REVIEWER.cmd` to use the loopback-only save-enabled review server. A generic static server cannot save placement reviews.

