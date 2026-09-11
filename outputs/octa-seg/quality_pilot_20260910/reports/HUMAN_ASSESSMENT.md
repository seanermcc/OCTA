# Regional human assessment

Suggested strips: 0/24 rated; Good 0, Bad 0, Unsure 0. Free-browsing portions: 0.

Random and targeted results are kept separate. Unsure is not treated as Good or Bad. AUROC is undefined until both Good and Bad judgments exist in a sampling group. Higher metric values predict Bad for the reported AUROC; the signal/coverage metrics can have the opposite association. No fitted metric or probability calibration is claimed.

The entropy warning uses the fixed 75th percentile of all six volumes’ 64-column strip P95 entropy (0.698789), not a threshold tuned to ratings. The spike warning is a displayed-curve excursion >20 µm. entropy_spike_overlap.csv separates failures flagged by entropy only, spikes only, both, or neither.

The blinded comparison excludes reratings after metric revelation, preserving them in rating_pairs.csv. Estimates are descriptive within this small, clustered six-volume pilot, not independent A-line statistics or a population failure rate. Free-browsing ratings have a separate exploratory group, with latest marks winning per column and suggested spans excluded to avoid double counting.

No regional judgments have been collected yet; no metric success, failure rate, or optimization decision can be established.
