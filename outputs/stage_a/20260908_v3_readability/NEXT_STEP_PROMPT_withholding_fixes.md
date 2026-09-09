# Next step — the two cheap withholding fixes (§6 step 5)

> **Timing note — read first.** This task is queued to run **after the usage-credit
> reset**. Do not start execution until credits have reset. Steps 1–3 below are
> pure analysis on existing arrays and are cheap; step 4 onward re-runs
> `stage_a.evaluate` on two splits plus the audit and comparison, so budget for
> that before starting. Keep logs on disk and inspect compact summaries; do not
> stream long console output.

---

## Where this sits

`outputs/stage_a/20260908_v3_readability/RUN_REPORT.md` §6 lists five steps.
This is **step 5** — the only one explicitly independent of the others:

> *(a) when a crossing is detected, consider withholding the whole A-line rather
> than only the two crossing surfaces — 7,447 manually-unreadable columns are
> only partially protected today; (b) the classical shadow mask misses 45 % of
> manually-unreadable columns, so shadow detection itself has headroom.*

It does not depend on training length (step 1) or on more corrected animals
(step 3), and it is not the readability gate (step 4) — it is the existing
reason-coded mask being made to do its own job properly.

**Sequencing interaction — important.** Fix (a) changes `code/stage_a/inference.py`,
which changes `code_identity()` and therefore invalidates checkpoint resume, the
same way the `train.py` guard in `NEXT_STEP_PROMPT_train_longer.md` does. If both
are going ahead, **land them on the same branch, before the longer training run
starts**, so there is one `code_identity` change and one set of tests rather than
two. Fix (a) affects inference/withholding only and does not change the trained
weights, so it does not alter what step 1 measures.

## The thing that decides whether this is cheap at all

**Fix (a) may be catastrophically expensive, and nobody has measured which.**

From `20260908_v2/dev_seed20260908/RUN_REPORT.md` §5 and §7, on the TS165 WT
volume: 2,097,152 boundary-columns, of which **443,805 (21.2 %) carry the
crossing bit**, spread over 262,144 A-lines. The crossing bit is set per
*surface*, so the number of **distinct A-lines containing at least one crossing**
is somewhere between:

- 443,805 / 8 = **55,476 A-lines (21 %)** — if scrambled columns flag many
  surfaces at once; fix (a) is then genuinely cheap; and
- 443,805 / 2 = **221,902 A-lines (85 %)** — if each crossing flags exactly the
  two surfaces that cross; fix (a) would then withhold 85 % of every volume and
  is a non-starter as stated.

That single number is the decision. Measure it before writing any code.

The user's standing constraint applies throughout: **simply hiding more columns
is not improvement.** Every claim here must be made at matched supported-tissue
coverage, or with the coverage cost stated alongside it.

## Read first

- `AGENTS.md`, `CLAUDE.md`, the `octa-layer-segmentation` skill.
- `outputs/stage_a/20260908_v3_readability/RUN_REPORT.md` — all of it, especially
  §2 (the audit, where the 22.6 % / 55 % / 7,447 numbers come from) and §6.
- `outputs/stage_a/20260908_v2/dev_seed20260908/RUN_REPORT.md` §5 and §7.
- `code/stage_a/inference.py` — `REASONS`, `prediction()`, how the crossing bit
  is currently assigned.
- `code/stage_a_readability.py` — `cmd_audit`, `_overlap`, `_method_metrics`.

## Do this, in order

### 0. Pre-flight

```powershell
Set-Location 'G:\OCT_TreeShrew\octa'
. 'D:\Anaconda\shell\condabin\conda-hook.ps1'; conda activate octa
$env:PYTHONPATH = 'G:\OCT_TreeShrew\octa\code'

python code\check_env.py
python code\stage_a_report.py          # record the before-numbers
python -m stage_a.test_stage_a          # must be 16/16
git status --porcelain
```

New output directory: `outputs/stage_a/<YYYYMMDD>_withholding_fixes/`. Do not
write inside `20260908_v2/` or `20260908_v3_readability/`.

### 1. Measure the distinct-A-line crossing rate — no code change

Pure analysis on arrays that already exist. Sources: the frozen
`20260908_v3_readability/eval_train/`, `20260908_v2/dev_seed20260908/eval_validation/`,
and the 512 chunks of `20260908_v2/dev_seed20260908/volume_TS165/`.

Report, per split and for the WT volume:

- distinct A-lines with ≥1 crossing bit, as a fraction of all A-lines;
- the **distribution of how many surfaces are flagged** in a crossing column
  (1, 2, 3, … 8) — this is the quantity the 21 %/85 % bracket turns on;
- how that interacts with the existing mask: of the A-lines that would newly be
  withheld under fix (a), what fraction are *already* fully withheld by shadow or
  scope (so cost nothing), and what fraction are currently fully retained;
- the same split by QC group and by animal.

### 2. Characterise the shadow misses — no code change

Of the manually-unreadable (`region_excluded`) columns the classical shadow mask
misses (45 %, and the 1,104 columns caught by *nothing*), describe what they
actually are, using the features already in
`20260908_v3_readability/features/columns.npz`:

- their distribution in `cnr`, `band_lowsig_frac`, `col_energy_z`,
  `band_grad_p90`, `neigh_corr` versus (i) shadow-detected columns and
  (ii) confirmed-readable columns;
- where they sit laterally (dark edges? interior?) and by QC group;
- **the question that decides fix (b): how many of them does the entropy gate
  from §3 already catch?** If the entropy gate at the `q0.94`–`q0.96` operating
  point already covers most of the 45 %, then a better shadow detector is
  redundant work and fix (b) should be dropped rather than built. Report the
  overlap explicitly.

Pull representative overlays for the misses via
`stage_a_readability.py display` so the characterisation is looked at, not just
tabulated.

### 3. Decision gate — write it down before touching `code/stage_a/`

State plainly, with the numbers from steps 1–2:

- **(a)** Is whole-A-line crossing withholding affordable? If the distinct-A-line
  crossing rate is high, do **not** implement it as stated. Evaluate the
  narrower variants instead and pick one on measurement:
  - withhold the crossing pair **plus any surface anatomically between them**
    (a crossing between ILM and IPL_INL makes RNFL_GCL and GCL_IPL meaningless
    too, but says nothing about RPE);
  - withhold the whole A-line only when the crossing count in that column
    exceeds a threshold, or the crossing depth extent exceeds a threshold;
  - leave crossing alone and let the entropy gate handle it.
- **(b)** Does an improved shadow detector add anything the entropy gate does not
  already provide? If not, say so and stop — that is a valid result.

If neither fix survives its measurement, **write the report and stop.** A
negative result here is worth as much as a change, and is cheaper.

### 4. Only if step 3 supports a change — implement it

- Branch `stage-a-withholding-fixes` (or the shared `stage-a-train-longer` branch
  if both changes are landing together — see the sequencing note above).
- Change `code/stage_a/inference.py` only. Do **not** weaken or bypass the
  `code_identity` guard, the `test_guard()` on the test split, or `common.verify()`.
- Keep the reasons **separate and reason-coded** — do not fold a widened crossing
  rule into the `shadow` bit. If the semantics of the crossing bit change, that
  change must be visible in `reason_bits`, and `REASONS` / the docstring must say
  what it now means.
- `python -m stage_a.test_stage_a` → 16/16 after the edit. If a test encodes the
  old per-surface crossing semantics, update the test deliberately and say so in
  the report — do not delete it.
- Commit with a message stating the semantic change and that it invalidates
  `code_identity` for existing checkpoints. Do not merge without review.

### 5. Re-measure at matched coverage

```powershell
python -m stage_a.evaluate --split train --predictor model `
  --checkpoint outputs/stage_a/20260908_v2/dev_seed20260908/best.pt `
  --out outputs/stage_a/<YYYYMMDD>_withholding_fixes/eval_train --device cuda
python -m stage_a.evaluate --split validation --predictor model `
  --checkpoint outputs/stage_a/20260908_v2/dev_seed20260908/best.pt `
  --out outputs/stage_a/<YYYYMMDD>_withholding_fixes/eval_validation --device cuda

python code\stage_a_readability.py audit `
  --eval-train outputs/stage_a/<YYYYMMDD>_withholding_fixes/eval_train `
  --eval-val   outputs/stage_a/<YYYYMMDD>_withholding_fixes/eval_validation
python code\stage_a_readability.py features --eval-train ... --eval-val ...
python code\stage_a_readability.py compare
```

Write regenerated `audit/`, `features/`, `compare/` under the **new** directory —
if `stage_a_readability.py` hardcodes `V3`, add an output argument rather than
overwriting the frozen v3 artifacts. Same checkpoint as v3 throughout, so the
only variable is the withholding rule.

Report the before/after against the v3 audit as a paired table:

| | v3 existing mask | with fix |
|---|---|---|
| unreadable tissue still measured (22.6 % baseline) | | |
| supported readable tissue withheld (13.4 % baseline) | | |
| retained p95 / worst contiguous gross run (21.0 µm / 91 col baseline) | | |
| retained coverage of supported tissue | | |

And re-run the three-way comparison so the fix and the entropy gate are compared
**at matched supported coverage**, not just each against the old mask. The
question to answer is whether the crossing fix buys anything the entropy gate
does not already buy more cheaply.

### 6. Report — `outputs/stage_a/<YYYYMMDD>_withholding_fixes/RUN_REPORT.md`

1. The distinct-A-line crossing rate and the surfaces-flagged-per-column
   distribution — the decision number, stated first.
2. What the 45 % shadow misses are, and how much of them the entropy gate
   already covers.
3. The decision from step 3 and its justification, including anything dropped.
4. If a change was made: the paired before/after table, the matched-coverage
   comparison against the entropy gate, and the coverage cost stated in absolute
   columns as well as fractions.
5. Representative cases — a success, a case where useful tissue was newly and
   unnecessarily rejected, and a remaining failure.
6. Whether this changes the §6 sequence for steps 1–4.

Standing disclosures: two corrected validation animals only, one B-scan dominates
the tails, absence of a manual exclusion is not proof of readability, classical
masks are comparators not human truth, nothing here is an acceptance criterion or
a validated measurement.

## Provenance rules (hard)

- **No final-test animal** (TS247, TS283, TS328) read, evaluated, inspected or
  unlocked. No `--final-test-protocol` created. **Repeatability tree not read.**
- **No human label, manifest, partition, footprint or checkpoint** written or
  modified. `label_gui.py` never launched. Human labels are never edited by a
  script.
- `20260908_v2/` and `20260908_v3_readability/` preserved unchanged; all new
  artifacts under `<YYYYMMDD>_withholding_fixes/`.
- Animal-level isolation maintained; training animals for fitting,
  dev-validation for exploratory comparison only.
- `python code\stage_a_report.py` before **and** after:
  `scientific_versions_unchanged: true`, `repeatability_data_read: false`,
  160 labels / 32 packs / 28 footprints unchanged.
- `python -m stage_a.test_stage_a` → 16/16 after any edit and again at the end.
- `code/stage_a/inference.py` is the **only** permitted change under
  `code/stage_a/`, committed on a branch, not merged without review. Any
  `stage_a_readability.py` change stays outside the package.
- No architecture change, no training run, no threshold fixed as an acceptance
  criterion, no production-readiness claim.
