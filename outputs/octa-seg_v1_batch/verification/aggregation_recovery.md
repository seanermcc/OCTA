# Final aggregation recovery

On 2026-09-11 the supervisor stopped while assembling cohort tables because it re-read a QC marker during that scan's schema upgrade. The last two workers finished successfully; all 314 per-scan QC completion markers existed before recovery began. The stale supervisor snapshot reported 312 completed scans.

The aggregation routine now takes a snapshot of each scan's marker, tables and reuse provenance while holding its per-scan lock. It no longer re-reads mutable markers after releasing those locks. This changes table assembly only, not model inference, thresholds or scan results.

The final cohort audit was restarted, with output saved to logs/final_audit_recovery.log. FINAL_VERIFIED.json is the authoritative success marker; this note does not itself establish that the audit passed.

The first recovery audit passed every source/input/artifact integrity check, then stopped on an incorrect expected layer-row count. The frozen model defines eight thickness entries plus INNER_RETINA; QC additionally includes eight explicitly unavailable entries, totaling 17 per scan, or 5,338 rows. All 17 names occur exactly once for each of the 314 scans. The audit now checks the exact Cartesian product of scan IDs and the defined layer names instead of an incorrect constant of 18. No data rows were removed or changed. A full rerun is logged to logs/final_audit_recovery_2.log, now with per-scan integrity progress.

Final full rerun passed on 2026-09-11 at 07:00:32 local: all 314 acquisitions, 2512 boundary rows and 5338 layer rows. See FINAL_VERIFIED.json. No scan failures remain.
