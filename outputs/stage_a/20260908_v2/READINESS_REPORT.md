# Stage A preparation readiness — 2026-09-08

**Software is ready for the first controlled development run. The model is not validated or production-ready.** No full training campaign, development model selection, uncertainty calibration or final-test evaluation was launched.

The current user request limits this task to preparation and short training smoke tests. It takes precedence over broader pilot/promotion instructions in the older execution prompt. The implementation applies the octa-layer-segmentation skill's evidence and geometry safeguards while retaining the current eight-boundary contract and requested N=1 U-Net approach.

## Delivered

- `DATA_AUDIT_20260908.md`: dated eligibility and provenance audit.
- `manifest.json`, `partitions.json`, `historical_cohort.json`: frozen dataset, animal assignments, and separate original 53-B-scan benchmark.
- `targets/`, `scope/`, `cache/`, `cache_manifest.json`: versioned derived supervision, physical exclusions, and 160 verified single-channel native-depth image caches.
- `animal_coverage.csv`, `coverage_by_animal_surface_qc.csv`, `coverage_detail.csv`, `decisions.csv`: per-animal/surface/quality coverage and explicit decisions.
- `code/stage_a/`: 122,799-parameter eight-boundary 2-D U-Net; seven-band auxiliary head; masked losses; animal-balanced loading/training; checkpoint/resume; evaluation; native-coordinate resumable inference.
- `RUN_COMMANDS.md`: exact first development, resume, validation-comparator and inference commands.

## Verification

**16 tests passed**, covering the 250 µm physical mask, missing footprints/D0, legacy displacement/visibility/reliability exclusions, two-endpoint region supervision, masked gradients, geometry in both orientations, odd image dimensions, animal isolation, test lock, historical cohort separation, signed thickness bias, common-shift cancellation, checkpoint reload, and inference scope/shadow withholding.

The localized-error regression puts a 100 µm error in 51/512 columns: median remains zero, but p95 is 100 µm, gross-error fraction is 9.9609%, and contiguous extent is 51 columns (145.43 µm). Missing files, NaNs and abstentions remain in eligible denominators. Raw and retained errors, conditional prediction coverage, all-eligible failure fractions and thickness coverage are separate outputs.

The final CUDA smoke run performed **three training steps plus one resumed step**, with finite losses and nonzero finite gradients. Checkpoint reload produced exactly equal prediction tensors of shape `[1, 8, 512]`. Initial three-step runtime was about 14 seconds in the first smoke run, and peak allocated CUDA memory was about 618 MB; these are smoke measurements, not training-duration forecasts. See `smoke_final/run_step_000003.json` and `run_step_000004.json` for the final-code runs. No validation/test loader was instantiated for smoke training.

Evaluation plumbing ran on training data only: 12 decisions for the smoke model and all 72 training decisions for stored-auto and available v2 baselines. The v2 comparator lacks predictions for **36/72 training decisions**, which are recorded as missing instead of skipped. These reports are software checks and must not be read as trained-model performance. Historical v2 parameter development overlapped human examples and is documented as such.

Full-volume inference completed **all 512 B-scans of a training-animal WT volume** with the smoke checkpoint. Each chunk contains canonical and disk-coordinate rows, scope/shadow masks, entropy, withholding reason bits, and NaN-masked experimental thicknesses. The measured disk/canonical round-trip error is at most **0.00003052 pixels**, attributable to float32 storage. All validated-thickness fields remain NaN. `volume_test_results.json` records array/mask checks and the resume fingerprint check. The full-volume smoke used the earlier equivalent smoke checkpoint; final fingerprint checks do not change model computations.

The environment now has **PyTorch 2.8.0+cu126**, with working CUDA on the RTX 3060 Ti. Installation followed the [official PyTorch Windows/CUDA wheel instructions](https://pytorch.org/get-started/previous-versions/#v280), installing torch without unnecessary torchvision/torchaudio packages. Scientific package versions were unchanged, their imports and NumPy computation passed, and `pip check` found no broken requirements. Before/install records are preserved in `../20260908_v1/`; the after inventory and comparison are in this version. PyTorch warns that the CUDA region cross-entropy reduction lacks a deterministic implementation; checkpoint reload is exact, but fresh-run bitwise reproducibility across CUDA environments is not promised.

`integrity_and_environment.json` verifies 160 original labels, 32 review packs and 28 footprints unchanged, plus the QC/source join and cache fingerprints. The labeling GUI was never launched, closed or modified. The repeatability directory was not read or modified. All new data artifacts are under `outputs/stage_a/`; the initial incomplete audit remains explicitly superseded in version 1.

## Evidence limits and remaining human decisions

The eligible pool is **89 B-scans / 23 volumes / nine animals**, partitioned 48 train, 14 development validation and 27 test. All eight boundaries have evidence in each split. Only two validation and two test animals have corrected targets, and the only WT animal is in training. There is no independent WT generalization result. TS247/TS267 contribute unevenly; sampling balances animals and reports include animal-macro summaries.

Legacy edit flags establish surface-wide involvement, not local stroke provenance. The scientific validity of treating remaining columns of an edited surface as legacy supervision remains an evidence limitation. No local visibility targets were invented. A targeted provenance review on development examples may reduce this uncertainty without blocking the prepared run; there is no blanket relabeling requirement here.

The **250 µm buffer and 25 µm gross-error reporting cutoff are provisional**, not acceptance thresholds. Repeatability and the scientific measurement requirements must establish surface-specific error, thickness-bias, tail-risk and retained-coverage tolerances before final testing. The outer endpoint convention and RNFL measurement convention remain the existing documented definitions; any scientific reinterpretation requires an explicit separate decision.

Development validation is reserved for model selection and calibration. Entropy is only a candidate error signal. Full training, calibrated abstention/review yield, justified acceptance thresholds and final-test release remain future work. No corrected-core CNV capability, human-level accuracy or review-time budget is claimed.

The inference CLI currently operates on registered manifest sources and uses the frozen classical shadow mask. New-source registration, acquisition-shift validation and a promotion/export workflow must be completed before operational use on new scans. Validated measurement exports are deliberately unavailable in this experimental preparation release.
