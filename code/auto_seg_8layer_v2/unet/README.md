# Phase 1 — data pipeline and evaluation harness

Implements Phase 1 of `outputs/auto_seg_8layer_v2/UNET_PLAN.md`. **No model and
no training code lives here** — that is Phase 2, and it is blocked on labels.
Everything in this package is testable against what exists today.

Run from `code` with `octa` activated:

```bash
python auto_seg_8layer_v2/unet/run_phase1.py --census-only
```

```bash
python auto_seg_8layer_v2/unet/run_phase1.py
```

```bash
python auto_seg_8layer_v2/unet/test_phase1.py
```

`run_phase1.py --rerun-v2` additionally re-runs the revision-2 cascade through
the real volume pipeline and checks the harness reproduces
`qc/variant_comparison.json:v2_outer_anchor__priors_five`. It reads ~15 source
volumes and takes several minutes; the default self-test needs no volume read.

## Modules

| module | does | does not |
|---|---|---|
| `flatten.py` | integer per-A-line shifts anchored on `tissue_bounds`' posterior edge; lossless round trip; crop; wrap mask | touch the ILM — it is the known-bad surface |
| `tensors.py` | 3-B-scan averages (`bscan_avg=3`) read from each source `.mat`, one bulk read per volume, cached with a manifest | ever fall back to a review-pack image |
| `targets.py` | 9-class region maps, 8-channel per-column Gaussian boundary maps, and the loss masks | conflate `surface_edited` / `surface_displaced` / `surface_visible` / `surface_reliable` / `region_excluded` |
| `dataset.py` | assembles a `Sample`: 2 channels, targets, weights, and the geometry needed to invert the flattening | know anything about a model |
| `folds.py` | `leave_two_animals_out(animal_ids)` over whatever animals are labelled now | hardcode an animal list |
| `evaluate.py` | µm errors per surface and per layer, stratified by acquisition QC group and control/CNV; self-test against the published numbers | score against the automatic output — only human labels are truth |

## The three decisions the plan pre-committed, and what was actually done

1. **Averaged inputs.** `tensors.py` rebuilds every training image as
   `average_bscans(imgs, 3)` from the source volume. `run_phase1.py` prints
   every volume it reads, and `assert_not_pack_images` raises if any cached
   image is bit-identical to the unaveraged pack image — so a silent fallback
   fails loudly instead of quietly training on the wrong distribution.
2. **Integer shifts.** `apply_shifts` refuses a float shift array
   (`TypeError`), and the round trip is asserted with `np.array_equal`, not
   `allclose`, on synthetic data and on every real labelled B-scan.
   The roll is circular, which is what makes it exactly invertible; the pixels
   it wraps in are marked in `valid_mask`, zeroed in the input, and given zero
   region-loss weight.
3. **Generated folds.** `leave_two_animals_out` takes the animal list computed
   from the labels. Adding animals changes the fold count with no code edit
   (6 animals → 15 folds, 11 → 55).

## Masking semantics, stated once

- A **boundary** is supervised where the human *drew* it (`surface_edited`),
  *saw* it (`surface_visible`), *left it reliable* (`surface_reliable`), on an
  A-line they did not exclude (`region_excluded`), inside the crop.
- `surface_displaced` alone never qualifies a surface and never disqualifies a
  drawn one — the ordering constraint moving a line is a different question
  from a human drawing it.
- A **region** is supervised only where **both** bounding surfaces are.
- `rejected` and `accepted` B-scans are not evidence and are dropped
  (`targets.supervised_records`). Nothing gets an invented target: unsupported
  pixels get zero weight.

## Coordinates

Everything in a `Sample` is in flattened, cropped coordinates. Predictions must
go back through `dataset.to_image_rows(rows, sample.shifts, sample.row0)`
before being compared with a human label or written to disk. The evaluation
harness only accepts predictions already in original image coordinates.
