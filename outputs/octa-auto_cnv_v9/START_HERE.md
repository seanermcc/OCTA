# Compare the two CNV v9 models

Double-click **OPEN_GALLERY.cmd**. The preview now includes disk-saved **Confirm Model 1**, **Confirm Model 2 adjusted**, and **Review Model 2** checkboxes. See **WEB_REVIEW_GUIDE.md** for their meaning and the next training/audit plan. The local HTML gallery contains all 50 acquisitions, including zero-candidate cases.

- Click an en-face view to inspect its native B-scan; row 0 and 511 buttons reach both ends. Wheel zoom and dragging are synchronized across views.
- Turn vessel/ONH overlays on independently. Use “Recover hidden candidates” and the down-ranked table filter to inspect m2 candidates below the display threshold.
- Model preference and notes save only in this browser; export JSON to keep a separate copy. They are not CNV labels.

Read **REPORT.md** for development results and limitations. Both deployable bundles are under **bundles/**. The deferred TS247 scan was excluded. No model has been chosen. The web confirmation round is enabled; correction flags are saved for a later GUI queue. Retraining never starts automatically.

To resume a failed compute/delivery stage, run **RUN_OR_RESUME.cmd** in this same release. Existing frozen manifests and complete fits are verified and reused.

Implementation details, batching measurements and the deterministic novelty replacement are documented in **IMPLEMENTATION_NOTES.md**. Actual post-laser days take precedence in the gallery when available.
