# Reviewing v6 suggestions

Run `OPEN_REVIEW.cmd` in the release folder. The review queue includes possible misses, false suggestions, model disagreements, unreviewed acquisitions and a fixed random sample. All original annotations remain in their original GUI.

Select a case and compare A, B, C and the unchanged v3 suggestion with the saved reference. Scroll the linked native B-scans. Judge whether depth information could distinguish the error from a true lesion.

Click **Start review** before inspecting a case. Record actual additions, removals, outline corrections and acceptances for the selected model arm, then save. The timer counts only while the page is visible and focused; pause for interruptions. These observations are saved separately in `human_observations.jsonl`. They are not automatically converted into lesion labels.

The comparison display is not blinded or randomized between model arms. A fair time-saving comparison needs matched or randomized human sessions with a clear task definition, and must account for carryover. Existing historical GUI times do not measure effort for these new predictions.

The development holdout is already inspected for this pilot. If its errors inform later model fitting, retain its status as development data. Future independent evaluation needs new animals unseen by both the CNV model and the upstream layer model.
