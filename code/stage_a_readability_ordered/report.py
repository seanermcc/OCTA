"""Render the completed experiment's factual report from saved measurements."""
import json
from collections import defaultdict
from stage_a.common import OUT, read_csv

RUN=OUT/'stage_a/20260908_v5_readability_ordered'
METHODS=['epoch124_existing','readability_only','ordered_only','readability_ordered','simple_rule','simple_ordered']
LABELS=dict(epoch124_existing='Epoch 124 existing',readability_only='Readability alone',ordered_only='Ordered alone',
    readability_ordered='Readability + ordered',simple_rule='Entropy + signal',simple_ordered='Entropy + signal + ordered')


def pct(value): return f'{float(value)*100:.2f}%'
def num(value): return f'{float(value):.2f}' if value not in ('',None) else 'unavailable'
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
        ['| '+' | '.join(map(str,r))+' |' for r in rows])+'\n'


def run():
    summary={r['method']:r for r in read_csv(RUN/'comparison_summary.csv')}
    prep=json.loads((RUN/'prepared.json').read_text()); train=json.loads((RUN/'training_complete.json').read_text())
    details=read_csv(RUN/'boundary_thickness_by_stratum.csv'); strata=read_csv(RUN/'comparison_by_stratum.csv')
    paired=read_csv(RUN/'paired_common_support.csv'); scans=read_csv(RUN/'per_bscan_summary.csv')
    losses=read_csv(RUN/'partial_visibility_loss.csv'); matched=read_csv(RUN/'matched_coverage.csv')
    audit=read_csv(RUN/'annotation_audit.csv')
    totals=prep['totals']
    count_table=table(['Split','B-scans','Weak positive','Explicit negative','Unknown','Strong local positive'],[
        [s,sum(r['split']==s for r in audit),t['weak_positive'],t['explicit_negative'],t['unknown'],t['strong_positive']]
        for s,t in totals.items()])
    comparison=table(['Method','Supported measured / 34,809','Coverage','Leakage / 17,096','Leakage','Boundary median / p95 (um)','Gross / measured','Worst run'],[
        [LABELS[m],summary[m]['supported_measured'],pct(summary[m]['supported_coverage']),summary[m]['unreadable_surface_measured'],
         pct(summary[m]['unreadable_leakage']),num(summary[m]['boundary_median_um'])+' / '+num(summary[m]['boundary_p95_um']),
         summary[m]['boundary_gross_n']+' / '+summary[m]['supported_measured'],summary[m]['worst_retained_gross_run']] for m in METHODS])
    paired_table=table(['Exact common columns','n','Median A / B (um)','p95 A / B (um)','MAE A / B (um)','Gross A / B'],[
        [LABELS.get(r['method_a'],r['method_a'])+' → '+LABELS.get(r['method_b'],r['method_b']),r['n_common'],
         num(r['median_a'])+' / '+num(r['median_b']),num(r['p95_a'])+' / '+num(r['p95_b']),
         num(r['mae_a'])+' / '+num(r['mae_b']),r['gross_a']+' / '+r['gross_b']]
        for r in paired if r['name']=='ALL'])
    approximate=table(['Method','Training quantile','Actual readable gate coverage','Supported coverage','Leakage','p95 (um)','Worst run'],[
        [r['method'],r['train_target_coverage'],pct(r['readable_gate_coverage']),pct(r['supported_coverage']),
         pct(r['unreadable_leakage']),num(r['boundary_p95_um']),r['worst_retained_gross_run']]
        for r in matched if r['match_axis']=='readable_gate_coverage' and r['target_coverage']=='0.95' and r['ordered']=='False'])
    report=f'''# Stage A: whole-column readability and ordered decoding — 2026-09-08

**Completed development experiment; not a promotion candidate.** The combined method reduces manual-exclusion leakage and breaks measurements into intervals, but loses useful labelled tissue and retains catastrophic, anatomically ordered mistakes. It does not outperform the existing entropy-plus-signal rule consistently. No production threshold was enabled.

Following the user's clarification, **only frozen manual segmentations are boundary/thickness ground truth**. Published layer thicknesses and classical surfaces are not truth or fitting targets. Existing scope and classical-shadow masks remain withholding protections only.

## Result at the prespecified exploratory operating point

The same 38 validation decisions were evaluated; 14 have eligible manual boundary evidence, from **TS169 and TS325 only**. TS336 is rejected-only and contributes no boundary accuracy evidence. All errors are in micrometres; gross means absolute error >25 um, the existing provisional reporting cutoff. Runs are consecutive A-lines within one B-scan and one boundary.

{comparison}

Readability + ordered and entropy + signal have an unusually close **supported-coverage match: 75.04% versus 74.98%**, a 0.063 percentage-point difference (22 surface-columns). The combined method has slightly less leakage and a shorter worst run (13 versus 19), but larger p95 error and **153 versus 79 retained gross errors**. This is a mixed tradeoff, not superiority.

The combined method drops 7,266 previously retained supported positions and adds 297, for a net loss of 6,969. Its error-or-withheld fraction rises from 6.83% to 25.40%. A lower conditional p95 therefore cannot be called a general segmentation improvement.

Thickness results are also mixed: combined TOTAL median/p95 is 2.24/5.61 um versus 2.16/6.39 for existing withholding; GCL median worsens 2.46 → 2.59 um and RPE-band p95 worsens 9.82 → 11.20 um. **TOTAL and the RPE band have no eligible endpoint pair in b0510**, so their zero gross-error counts do not clear that catastrophic case. All eight bands remain in the tables with their own denominators.

## Annotation audit and target limitations

{count_table}

Every development label is `2-surface-reliability`, with whole-surface edit/visibility/reliability flags. **None records exact local stroke coverage.** The current GUI code supports newer local provenance, but no frozen file has it; neither the GUI nor labels were changed by this experiment.

- Negative: explicit human `region_excluded`, independent of B-scan verdict. These remain distinct from boundary-position supervision.
- Weak positive: all eight existing boundary masks eligible; corrected verdict; all eight surfaces edited, visible, reliable, and not displaced; at least 8 strokes and 30 seconds active review. The qualifying positive files actually have 47–204 seconds of review. Positive loss weight is **0.25**, explicitly acknowledging the coarse evidence.
- Unknown: everything else. Unedited/missing labels, rejected verdict alone, invisible individual surfaces, classical shadows, and outside-scope regions do not become unreadability negatives. An explicit exclusion overrides any positive proxy.

These are **weak review proxies, not certified per-column readable labels**. They do not recover which columns a stroke traversed. The strict local policy has **zero positive examples** in either split. A fully local, human-readability-supervised experiment cannot be supported by this snapshot; this run tests the strongest documented coarse proxy while preserving the original boundary eligibility contract. The positive-review duration is a filter, not proof of attention at each A-line. Uncertainty about the positive labels remains a central limitation.

## Model and fixed budget

All encoder, bridge, decoder, boundary-head and region-head parameters come from **epoch 124**, unchanged and frozen. Raw rows, entropy and old reason masks reproduce exactly on **110/110** development B-scans. There is no boundary retraining confound.

The new 64,641-parameter head uses the frozen decoder's 8 feature channels pooled into 16 depth bins, plus the normalized image in 32 depth bins (160 channels total). Three lateral convolutions span 57 A-lines. This retains depth-specific contrast/attenuation patterns and neighboring image structure; there is no darkness-only rejection rule or vessel/ONH classifier. The simple comparator retains the prior standardized entropy-mean + entropy-max − CNR + low-signal-fraction rule; its normalization uses training data only. Additional classical continuity metrics are not readability labels and were not used as truth.

`PRESPECIFIED_PLAN.json` was saved and fingerprinted before training: seed 20260909; **40 epochs × 48 steps = 1,920 updates**, AdamW lr 0.0003, decay 0.0001, gradient clip 5, animal-balanced sampling, horizontal flips of cached features/targets. Loss is class-macro BCE on known columns, explicit negatives weight 1, weak positives 0.25; unknown loss is zero. Readability loss weight 1; boundary and region update weights zero.

Selection: minimum animal-macro validation readability loss, earliest exact tie; no extension or parameter search. **Epoch {train['best_epoch']}** was selected, loss {train['best_loss']:.6f}. Training the cached-feature head took **{train['seconds']:.2f} seconds**; all 1,920 losses/gradients were finite and nonzero, and checkpoint round-trip was exact. Later validation losses worsen. Proxy AUROC is 0.902 training / 0.709 validation; neither score nor loss establishes calibrated readability.

The displayed gate is the **training 95% positive-proxy coverage quantile**, not a validation-chosen operating point. Its usable-score cutoff is about 0.007386, illustrating that these weighted-loss sigmoid scores are **not calibrated probabilities**. Actual validation gate coverage is 85.91% for the head and 87.46% for the simple rule; final all-eight measurement coverage is lower (81.24% for combined). The fixed grid is 50, 70, 80, 85, 90, 95, 98, 99 and 100% training proxy coverage. It is not an optimization search.

## Ordered decoding and its limitations

Canonical order is ILM → RNFL_GCL → GCL_IPL → IPL_INL → INL_OPL → OPL_ONL → PR_RPE → RPE. Exact column-wise dynamic programming requires a one-native-pixel geometric gap. It never fits normal layer thicknesses.

Posterior candidates must lie within log(20) of their own peak. A column is withheld if any boundary exceeds its **training eligible-target p99.5 entropy** or lacks finite support, or if eight supported ordered rows are infeasible. Entropy caps range 0.419–0.840; full values and counts are in `continuity_measurements_train.csv`.

One forward and one backward coordinate-descent sweep add a continuity penalty of `0.15 × min(|depth difference| / scale, 4)` per neighbor. Scales are the training manual adjacent-column slope p99, floored at 2 px: 2.386 px for ILM, 2 px for the others. These are conservative soft penalties, **not hard slope limits**, and the legacy manual curves themselves contain software-smoothed/untouched sections. Scope, shadow, readability, unsupported and infeasible gaps split the problem; no neighbor crosses a rejected gap and no gap is interpolated. This is not a global two-dimensional optimum.

Ordering is demonstrable, image support is not guaranteed: model posterior concentration can still be confidently wrong. The bounded penalty permits extremely large jumps, as b0510 demonstrates. It was not tightened after seeing validation failures.

Raw predictions contain 48,230 crossing-flagged boundary-columns / 155,648 (30.99%). Existing withholding already yields zero measured adjacent crossings; ordered measurements also have zero. On the 46,648 boundary-columns retained by ordered-only, 1,239 raw positions were crossing-flagged before decoding and zero afterward. **341 manually supported positions are recovered from old crossing withholding, but 100/341 are grossly wrong.** Zero crossing is not a quality certificate.

## Separating relocation from rejection

`decoder_support_raw` applies ordered-only support to the old raw rows while retaining the old crossing protection. Its p95 is 7.80 um and worst run 19; ordered-only gives 7.92 um and 29. Exact shared-column comparisons remove the remaining selection difference:

{paired_table}

Outside the learned rejection mask, combined decoding changes **3,731** common supported positions by more than 1 px. Of 25,824 common positions, 1,619 improve and 2,228 worsen by >1 um. These are decoder changes, not head retraining; mean absolute error increases despite fewer gross errors. The full paired thickness results are also reported. No boundary-location error is scored inside explicit human exclusions because no eligible manual truth exists there.

At approximately 95% **readable-gate** coverage, the fixed-grid comparison is:

{approximate}

These do **not** match supported-surface coverage (91.05% versus 83.35%). `matched_coverage.csv` additionally discloses absolute mismatch for supported coverage and final all-eight coverage; exact shared-column comparisons above are preferable when assessing relocation.

## Reviewed failures and readable controls

- **D98 b0061:** baseline 1,504/1,592 supported positions and 1,467/2,448 unreadable surface-positions measured. Combined retains only **390/1,592 (24.50%)**, with 184/2,448 leakage. Its retained gross count reaches zero by rejecting most useful tissue. Ordered-only actually lengthens the worst gross run from 19 to 29. The far-right unsupported region is greatly reduced, but the left/middle labelled retina is over-withheld.
- **Catastrophic b0510:** readability alone changes none of the baseline retained measurements. Combined retains **568/2,561 (22.18%)** supported positions; 141 remain gross. Its worst retained run shortens from 44 to 13, but p95 rises **421.63 → 525.28 um**. The overlay visibly contains an ordered stack at the wrong depth and large jumps. This case is not solved. The simple rule withholds the entire case, whose missing accuracy remains unavailable rather than zero error.
- **Readable TS169 b0164:** baseline retains 2,718/2,720 supported positions; combined retains 2,288 (84.12%). The simple rule retains 2,718. Much of the lost tissue still follows visible, manually labelled structure.
- **Readable TS325 D42 b0023:** combined retains 2,552/2,894 (88.18%) versus baseline 2,890; p95 improves 9.71 → 8.65 um. The simple rule has p95 7.91 but only 80.44% support coverage. Both useful retention and omissions are visible in the shared-scale comparison.

All **14 eligible measurement overlays** and **five six-panel comparisons** are in `review/`. They show raw predictions, NaN-gapped measurements, eligible manual targets, explicit exclusions, readable scores, reasons and thickness. Plots use canonical native depth (vitreous at 0); old reports used reversed disk depth. Numerical arrays include the verified inverse disk mapping. All panels within a comparison share image scaling and depth range.

## Is finer per-surface visibility justified?

**A targeted collection study is justified; its benefit is not yet proven.** Whole-column rejection loses **5,230** previously retained positions that were within 5 um of the manual target, including **613 ILM positions**. For 278 of those ILM positions, the ILM passes its own entropy cap but another boundary fails, causing whole-column rejection. This is measurable lost useful coverage that per-surface decisions could potentially preserve.

That evidence does not establish that ILM should be retained inside an explicit whole-image exclusion: frozen eligibility deliberately has zero human boundary targets there. Location supervision, local visibility, and whole-image unreadability must remain separate. Earlier step 2—per-surface × per-A-line visibility—is a possible follow-up annotation collection, **not implemented here**. Existing format capability does not fill the legacy annotation gap.

## Validation, integrity and reproducibility

See `REPORT_TABLES.md` for all eight boundary and thickness results, denominators, animal/quality strata, matched coverage and exact paired comparisons. Error statistics are conditional on retained finite ordered measurements; missing/withheld counts and fractions remain explicit. `qc_group` is the frozen review grouping, not a newly calibrated acquisition-quality label; high-quality validation evidence is confounded with TS169.

Only the same two corrected validation animals select the head and support its reported performance. There is no independent calibration set, no held-out WT validation animal, no final-test/repeatability evaluation, no new human labels, and no production promotion. All old checkpoints, frozen definitions and labels are preserved. Access was restricted by the dated guard; content fingerprints cover allowed development files only, not locked animal contents.

The final code lives in the separate `code/stage_a_readability_ordered/` package, preserving the original trainer's code identity and resume behavior. Packaging changed import paths after evaluation, not model/decoder computation; final tests and checkpoint reproduction verify this. Figure rendering was isolated from PyTorch after an OpenMP DLL conflict; no unsafe duplicate-runtime override, installation or library upgrade was used.

Final verification: **11 new tests + 16 original tests pass**. All 110 packaged-model boundary predictions reproduce exactly; full-image versus cached-head scores differ by zero; D98 b0061 and b0510 decoder outputs reproduce exactly. All 266 measurement files preserve experimental status and NaN gaps. **334 allowed development fingerprints** verify; **2,689 old artifacts** retain size and modification time, with no added old-root artifacts. Locked file contents were not hashed. Details: `final_software_verification.json` and `integrity_complete.json`.

The recorded `reproduce.ps1` gives the command sequence. Prepare/train/evaluate refuse completed destinations. Plan, training histories, both head checkpoints, original checkpoint fingerprint, fixed-grid measurements, raw validation logits, reason arrays, paired comparisons and integrity/test results remain under this dated root. Human-label writers were never called. **Decision: retain this as a failed development candidate and collect stronger local evidence before threshold calibration or further claims.**
'''
    # Read the exact recorded count instead of letting prose drift from CSV data.
    change_rows=read_csv(RUN/'changes_outside_readability_mask.csv')
    changed=sum(int(r['boundary_changes_gt1px']) for r in change_rows if r['category']=='outside_readability_rejection')
    report=report.replace('**3,731**',f'**{changed:,}**')
    (RUN/'RUN_REPORT.md').write_text(report,encoding='utf-8')
    tables=['# Stage A readability/ordering — complete development tables\n',
        'Experimental. Ground truth is frozen manual segmentation only. Unavailable cells have no measured evidence.\n',
        '## Headline comparison\n',comparison]
    for kind in ('boundary','thickness'):
        names=[]
        for r in details:
            if r['kind']==kind and r['name'] not in names: names.append(r['name'])
        tables.append(f'## {kind.title()} errors\n\nEach cell: median / p95 um; gross >25 um count / retained count (eligible denominator).\n')
        mapping={(r['method'],r['name']):r for r in details if r['kind']==kind and r['axis']=='pooled'}
        rows=[]
        for name in names:
            cells=[]
            for m in METHODS:
                r=mapping[m,name]
                cells.append(f"{num(r['median_abs_um'])} / {num(r['p95_abs_um'])}; {r['n_gross']}/{r['n_retained']} ({r['n_eligible']})")
            rows.append([name]+cells)
        tables.append(table(['Surface/band']+[LABELS[m] for m in METHODS],rows))
    tables.append('## Animal and available quality strata\n\nLeakage = measured / explicit-negative surface-columns; supported = measured / eligible manual positions. TS336 has no accuracy evidence.\n')
    tables.append(table(['Method','Axis','Group','Supported measured/eligible','Leakage measured/denominator','Median/p95 um','Worst run'],[
        [LABELS[r['method']],r['axis'],r['group'],r['supported_measured']+'/'+r['supported_surface_columns'],
         r['unreadable_surface_measured']+'/'+r['unreadable_surface_denominator'],num(r['boundary_median_um'])+'/'+num(r['boundary_p95_um']),r['worst_retained_gross_run']]
        for r in strata if r['method'] in METHODS and r['axis'] in ('animal','qc')]))
    tables.extend(['## Exact common-support comparisons\n',paired_table,'## Approximate readable-gate coverage match\n',approximate,
        '## Readability supervision audit\n',count_table,'## Useful supported positions lost by combined method\n'])
    tables.append(table(['Surface','Supported lost','Old error ≤5 um lost','Due to readability','Another boundary fails entropy'],[
        [name]+[sum(int(r[k]) for r in losses if r['surface']==name) for k in ('supported_lost','useful_le5um_lost','due_readability','due_deeper_entropy_only')]
        for name in sorted({r['surface'] for r in losses})]))
    tables.append('## Machine-readable detail\n\n`boundary_thickness_by_stratum.csv` includes all surfaces, bands, animal/QC/biology/scope strata, signed biases, coverage, gross and failure-or-withheld fractions. `per_bscan_surface_and_thickness.csv` includes worst-run start/end coordinates. `paired_common_support.csv` includes every layer on identical endpoint sets. `coverage_error_curves.csv` contains all 36 fixed-grid points; `matched_coverage.csv` reports achieved matches and mismatches on three separate coverage axes. `per_bscan_summary.csv` retains rejected/ineligible cases rather than excluding them.\n')
    (RUN/'REPORT_TABLES.md').write_text('\n'.join(tables),encoding='utf-8')


if __name__=='__main__': run()
