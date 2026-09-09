# Four-boundary decoder feasibility: read-only crossing recount

Recounted saved predictions from the longer-trained Stage A development
checkpoint (epoch 124), for training-split WT volume
`TS165_OS_2025-04-29_WT_s02_121711`.

Input: `outputs/stage_a/20260908_v4_longtrain/dev_seed20260908/volume_TS165/`
(`b0000.npz` through `b0511.npz`, 512 chunks).

No decoder was implemented or evaluated here. No prediction, checkpoint,
human label, footprint, or production setting was changed.

## Method

Read `canonical_rows`, `surface_names`, `reason_bits`, and `shadow` from each
saved chunk with NumPy in the activated `octa` environment. Verify the first
four names are ILM, RNFL_GCL, GCL_IPL, IPL_INL. Define an adjacent crossing as
`rows[i] > rows[i+1]`. For the four-boundary result, use only the first three
adjacent pairs. Count each A-line once if any of those pairs crosses. Separately
flag both involved endpoints, counting each boundary-column once. Equality is
not a crossing. These are raw prediction counts before scope/shadow withholding.

## Measurements

| Quantity | Count |
|---|---:|
| B-scans | 512 |
| A-lines | 262,144 |
| ILM / RNFL_GCL pair crossings | 14,173 |
| RNFL_GCL / GCL_IPL pair crossings | 37,465 |
| GCL_IPL / IPL_INL pair crossings | 58,331 |
| Distinct A-lines with any of those crossings | 90,821 (34.6455%) |
| B-scans with any of those crossings | 512 / 512 |
| Boundary-columns flagged by those three pairs | 206,031 |
| Median B-scan flagged-boundary fraction, four-boundary denominator | 18.6035% |
| Inner-crossing A-lines also flagged by the saved shadow mask | 27,093 |
| Stored crossing flags on first four surfaces, including interaction with INL_OPL | 220,058 |
| Stored crossing flags on all eight surfaces | 392,486 |

Pair counts overlap and must not be summed as distinct A-lines. The reproduced
all-eight count matches the longer-run volume verification report. The original
checkpoint's 14.94% median and newer checkpoint's 13.51% median in that report
use all-eight boundary-columns as their denominator; they are not distinct
A-line percentages.

## Interpretation and limits

Ordering failure directly affects the four surfaces needed for RNFL, GCL, and
IPL. Testing a simultaneous decoder on frozen U-Net scores is therefore a
focused next experiment. Zero crossings after imposing order would be a
structural guarantee, not evidence of correct anatomy or recovered usable
measurements. Measure boundary and thickness error, valid coverage, decoder
displacement, and behavior in unreadable tissue against eligible human evidence.

This is one training WT volume. It estimates neither new-animal performance nor
CNV performance, and does not show which of the 90,821 A-lines are recoverable.
No final-test animal data were inspected. Existing raw validity and visibility
reasons must not be erased merely because constrained predictions are ordered.
