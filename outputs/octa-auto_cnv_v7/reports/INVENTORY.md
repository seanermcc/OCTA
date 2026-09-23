# Inventory and queue

Fresh disk scan: 332 processed files; 324 known distinct acquisitions; 11 animals total.
253 eligible acquisitions across 10 non-WT animals. TS165 is WT and excluded. Strictly after day 7; D7 excluded.
Unmapped discoveries: 0. Indexed unavailable processed acquisitions: 11.

Queue membership means eligible for inspection, never known CNV-positive. Full reserve persists beyond the first 30 candidates.
Fresh sampled source fingerprints cover every disk file. Potential duplicates are grouped across names; known duplicate groups retain earlier full-file hashes with current size/mtime checks. This is not a fresh full-volume hash audit.

Seed 20260918. Numeric animal cycles; each animal cycles seeded visit order before repeating visits; shuffled acquisitions within visits. Selection uses neither labels nor model scores.

| Animal | Candidates | Visits |
|---|---:|---:|
| TS169 | 13 | 1 |
| TS241 | 37 | 5 |
| TS247 | 30 | 4 |
| TS250 | 13 | 2 |
| TS267 | 47 | 7 |
| TS283 | 6 | 1 |
| TS305 | 26 | 4 |
| TS325 | 32 | 8 |
| TS328 | 19 | 4 |
| TS336 | 30 | 6 |

One-visit animals have acquisition diversity only. Repeats are not independent animals/lesions. Pool exhaustion is recorded in config.json.
TS336 July 28 retains indexed D56 identity although its folder says D77. Both are nominal post-D7 labels; actual interval is unknown. The discrepancy remains in every applicable queue record.
D92 is parsed if numeric day is missing; 6 mo means nominal 180 days solely for eligibility, not a recovered laser date.
An active queue is never regenerated automatically. New discoveries require an explicit new queue version; restarting prepare_queue.py preserves this one.