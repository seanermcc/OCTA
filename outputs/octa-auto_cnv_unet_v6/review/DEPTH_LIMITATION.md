# Depth information and persistent errors

The pilot retains a 2D architecture. Its two optical images average signal through the saved retinal crop. They discard the axial position of a bright or dark feature and the distinction between a vessel-associated shadow extending downward and disruption near an outer retinal band. Eight scalar thickness maps summarize endpoint gaps; they do not restore the missing B-scan appearance.

The primary-seed error atlas was inspected alongside canonical structural B-scans. These are qualitative image observations for error triage, not new human annotations or biological adjudications:

- **D98 OD, B-scan 343 / A-line 466:** A misses a kept footprint near the right of the field. B and C recover it. Neighboring B-scans show outer-band irregularity at that location and altered overlying appearance. Depth offers additional context, but recovery by B/C means this case does not demonstrate that a depth-input architecture is necessary.
- **D98 OD, B-scan 35 / A-line 86:** B suggests part of an elongated vessel-associated region near the top of the image. The neighboring B-scans show a localized superficial feature and vertically extending signal loss beneath it. Those axial relationships are absent from mean projections. The automatic shadow/vessel measurements support flagging this as an artifact-confounded false suggestion against the saved reference; they do not certify its biology.
- **D98 OD, B-scan 221 / A-line 14:** B and C suggest a small bright feature near the left edge that is outside the completed-field CNV reference. It also appears as a focal bright feature in the B-scans. The saved crop and edge location limit assessment, and the atlas alone does not establish whether depth can resolve its status. Keep this case for human adjudication rather than turning it into a new label automatically.

The files ending `_0066.png`, `_0067.png` and `_0068.png` in `depth_atlas/` show these examples with native coordinate crosshairs. The full local reviewer can scroll every B-scan. Surface curves are not treated as human depth labels.

All six primary-seed C holdout matches trigger the predefined outline-correction proxy. That is evidence of residual outline mismatch, not evidence that it originates exclusively from missing depth. Sparse or inconsistent footprint supervision, acquisition artifacts, and initialization variation remain alternative explanations. The three-seed evaluation should be read with these cases.

No depth model was added or tuned against these holdout errors. A future comparison can test a shallow B-scan-stack/2.5D input if human review repeatedly identifies distinctions that are visible in depth but irrecoverable from en-face inputs. Record **Depth needed?** and the visible evidence in the review page first. Quantitative improvement would still need independent animals and upstream-model exposure control.

No new human review has occurred for this release. The active-time fields are empty; the agent's visual inspection is not counted as human review effort.
