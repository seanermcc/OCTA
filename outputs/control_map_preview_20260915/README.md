# Recovered control-map / ONH atlas preview

Open [the image gallery](index.html).

```json
{
  "status": "preview_complete",
  "recovered_scans": 72,
  "selected_scans": 6,
  "localized": 3,
  "registration_pairs": 3,
  "registration_passed": 0,
  "changed_current_inputs": 6,
  "source_snapshot": "F:\\OCT_TreeShrew\\octa\\outputs\\octa-seg\\octa-seg_v1\\control_map_v1",
  "full_cohort_complete": false
}
```

This is a historical cached-input pilot, not the original full-cohort completion. All 72 recovered preparation artifacts matched their saved SHA256 checksums. The six-scan selection favors three visible ONH anchors and their nearest scan-number neighbors from the same eye/date. The registration and A/B screen settings are unchanged. Source annotations, segmentation and the external drive were not modified.

Current upstream file comparisons are recorded in tables/current_input_comparison.csv. Changed inputs are not incorporated into this snapshot. Newer annotations are not validated by the cache audit. Full-cohort batch audit remains skipped under the original authorization. Provisional ONH coordinates and automatic masks require review. Unlocalized measurements remain in local summaries, but cannot contribute to ONH maps. Blank pixels remain missing.

Reproduce in activated octa: `python outputs/control_map_preview_20260915/build_preview.py`.
