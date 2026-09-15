# Annotation and automatic-input audit

Saved v5 files: 15. No human annotation file was changed.

15 saved acquisitions: 14 completed fields, 25 kept CNV entries, eight Unsure entries, one draft. The latest mask audit found 34 positive/uncertain conflict pixels in D0 OD; they were excluded. All other kept runs passed bounds, index and reviewed-mask checks. No draft or removed suggestion became an independent negative label.

The three historical reviewed-absence OS fields retain the recorded completion status. Their brief historical active-review times are an audit limitation, not proof of poor review; they are included with provenance. No new biological adjudication is claimed.

| Visit / eye | Split | Completed | Positive pixels | Known negative pixels | Ignored pixels |
|---|---|---:|---:|---:|---:|
| D0 OD | train | True | 13121 | 245191 | 3832 |
| D0 OS | train | False | 0 | 0 | 262144 |
| D7 OD | train | True | 5927 | 254732 | 1485 |
| D7 OS | train | True | 0 | 256775 | 5369 |
| D14 OD | train | True | 7222 | 254922 | 0 |
| D14 OS | train | True | 0 | 262144 | 0 |
| D28 OD | train | True | 5499 | 256645 | 0 |
| D28 OS | train | False | 0 | 0 | 262144 |
| D35 OD | train | True | 8151 | 253993 | 0 |
| D35 OS | train | False | 0 | 0 | 262144 |
| D42 OD | train | True | 6322 | 255822 | 0 |
| D42 OS | train | True | 0 | 262144 | 0 |
| D49 OD | validation | True | 5305 | 256302 | 537 |
| D49 OS | validation | True | 0 | 261070 | 1074 |
| D56 OD | holdout | True | 5601 | 256543 | 0 |
| D98 OD | holdout | True | 6965 | 255179 | 0 |
| D98 OS | holdout | True | 0 | 262144 | 0 |

`data/manifest.json` preserves exact source paths, full annotation hashes, region events, original completion/timing records, external correction fingerprints, embedded guard/override provenance, neural checkpoint hashes and input sources.

Embedded human state codes were present in the operational D28 OD export (7,808 boundary-pixels). These operational states were excluded: automatic inputs were recomputed from the raw neural positions and probabilities, verified against all 512 neural files per scan. The raw geometry CNV field and original en-face human labels were not model inputs.

For all 17 acquisitions, the upstream vessel mask exactly matched a hashed automatic unreviewed proposal. No ONH mask was present that could have injected manual ONH information into proposal generation. Code review confirmed that only structural images and the automatic vessel mask enter upstream neural inference; CNV masks are display/analysis fields. Shadow generation is image-based. External corrections were inventoried and never loaded by the input builder.

The upstream layer-data manifest includes 42 TS267 records, among animals TS165, TS169, TS241, TS247, TS250, TS267, TS283, TS305, TS325, TS328, TS336. No new-animal or end-to-end independent evaluation is claimed.
