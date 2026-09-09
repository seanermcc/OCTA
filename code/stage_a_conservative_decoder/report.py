"""Write reviewable experiment and annotation handoff documents from saved results."""
import json
import re
from stage_a.common import OUT, read_csv

RUN=OUT/'stage_a/20260908_v6_conservative_decoder'
OLD=OUT/'stage_a/20260908_v5_readability_ordered'


def num(x,d=2): return 'unavailable' if x in ('',None) else f'{float(x):.{d}f}'
def pct(x): return 'unavailable' if x in ('',None) else f'{100*float(x):.1f}%'
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',*['| '+' | '.join(map(str,r))+' |' for r in rows]])


def links(text):
    return re.sub(r'\]\(((?:figures|annotation_cards)/[^)]+)\)',lambda m:']('+str(RUN/m[1]).replace('\\','/')+')',text)


def run():
    plan=json.loads((RUN/'plan.json').read_text()); stages=[s['name'] for s in plan['stages']]
    main=read_csv(RUN/'comparison_summary.csv'); byname={r['method']:r for r in main}
    labels={'epoch124_existing':'Epoch 124 existing','readability_ordered':'Previous learned + ordered',
        'simple_rule':'Previous simple gate','simple_ordered':'Previous simple + ordered',
        stages[0]:'C1 bounded / partial',stages[1]:'C2 tighter signal',stages[2]:'C3 strict signal'}
    lines=['**Stage A: three conservative decoder checkpoints — 2026-09-08**','',
        'C2 is the most useful of the new review checkpoints: large retained errors disappear, while 80.5% of eligible manual surface positions remain. It does not meet all prespecified development criteria. C3 lowers leakage further but discards another 4,209 supported positions without removing the remaining 19-column ILM failure. Keep C2 for inspection and move to local visibility annotation; no version is promoted to production.','',
        table(['Method','Supported retained / 34,809','Coverage','Leak / 17,096','Median / p95 (um)','Gross >25 um','Worst run'],[
            [label,byname[name]['supported_measured'],pct(byname[name]['supported_coverage']),
             str(byname[name]['unreadable_surface_measured'])+' / '+pct(byname[name]['unreadable_leakage']),
             num(byname[name]['boundary_median_um'])+' / '+num(byname[name]['boundary_p95_um']),
             byname[name]['boundary_gross_n'],byname[name]['worst_retained_gross_run']] for name,label in labels.items()]),'',
        'Coverage uses 34,809 eligible manual boundary positions in 14 B-scans from TS169 and TS325. Leakage uses 8 × 2,137 explicitly human-excluded columns across all 38 validation decisions. The 24 other validation decisions contribute withholding diagnostics, not boundary-accuracy targets. Errors are conditional on retention; missing values do not count as correct. The 2,782 readable proxy columns are weak reviewed positives, not calibrated local visibility labels. Columns within a B-scan are correlated; these are descriptive development results, not independent-sample confidence estimates.','',
        'The epoch-124 boundary model and cached native predictions are unchanged: zero training updates. C1 retains the original scope, shadow, missing-value and crossing rejections; nothing rejected by those protections is recovered. It evaluates uncertainty separately for each boundary, restricts candidates to supported posterior rows within 3 pixels of the original expectation, orders every retained surface pair, and withholds abrupt jumps and short fragments. C2 inherits all C1 rejections, narrows movement to 2 pixels, and adds the prior entropy-plus-signal gate at its training 98th percentile. C3 inherits C2, uses 1.5 pixels and the 95th-percentile gate, and requires longer intervals. These are three saved configurations, not three trained neural networks.','',
        'Continuity limits come from eligible manually segmented training curves: C1 uses max(6 pixels, twice the training 99.9th-percentile adjacent slope) for each boundary. C2 and C3 reduce these limits to 75% and 50% respectively, with floors of 4 and 3 pixels. Minimum retained lengths are 6, 8 and 16 columns. Entropy caps are training manual-position quantiles 99.5%, 99% and 98.5%. The posterior candidate cost is at most log(20) below its own peak. One-pixel ordering is geometric; no published thickness priors or classical boundary locations are ground truth. Steep unsupported intervals are withheld rather than flattened. These limits can also remove genuine steep anatomy.','',
        'Each disconnected interval is decoded independently with bounded neighbor penalties. Removals trigger re-solving so rejected positions no longer influence neighbors. Retained masks only shrink between checkpoints. Measurement arrays contain NaN gaps; thickness requires both endpoints to be retained, finite and ordered. Validated thickness arrays remain entirely NaN. Raw predictions, overlapping reason bits, configuration fingerprints and source snapshots accompany every checkpoint.','',
        '**What the images establish**','',
        'D98: the previous combined method retained 390/1,592 supported positions (24.5%). C1 retains 1,414 (88.8%); C2 retains 1,091 (68.5%); C3 retains 873 (54.8%). The added coverage reveals a real unresolved disagreement with manual ILM at zero-based columns 232–250: 19 retained errors above 25 um, up to 39.2 um. This is a smooth, low-entropy error, so increasingly strict jump and signal filters do not identify it. The manual reference remains the scoring target.','',
        'b0510: C1 removes most false upper plateaus but retains nine gross GCL/IPL errors, reaching 506.7 um. C2 and C3 withhold all 4,096 possible boundary positions. Their boundary accuracy on this image is unavailable, not perfect. This is successful abstention from a catastrophic output, not recovered segmentation. RPE has no eligible manual target here; TOTAL and RPE thickness therefore cannot certify this example.','',
        'Readable controls: the TS169 b0164 image retains 98.4%, 97.4% and '+pct(next(r for r in read_csv(RUN/stages[2]/'per_bscan.csv') if r['key']==plan['focus'][2])['supported_coverage'])+' through C1/C2/C3. The TS325 D42 b0023 image retains 97.9%, 83.9% and 73.7%. The latter loss is substantial and is a reason to collect local visibility instead of applying a stricter whole-column gate.','',
        '[D98 comparison](figures/D98_comparison.png) · [b0510 comparison](figures/b0510_comparison.png) · [Readable control](figures/readable_control.png) · [Accuracy–coverage curves](figures/accuracy_coverage.png)','',
        '**Withholding helps; relocating the curves does not improve mean accuracy**','',
        table(['Checkpoint','Identical supported positions','Raw MAE (um)','Decoded MAE (um)','Raw / decoded gross'],[
            [r['stage'],r['n_identical_supported_positions'],num(r['raw_mae_um'],3),num(r['decoded_mae_um'],3),r['raw_gross_n']+' / '+r['decoded_gross_n']] for r in read_csv(RUN/'paired_location_effect.csv')]),'',
        'On exactly the same retained positions, decoding slightly worsens mean error by about 0.06 um. The principal gain is withholding bad positions, not more accurate boundary placement. No future model-training claim should be based on these decoder results. The fixed prior threshold grid is compared descriptively in approximate_matched_coverage.csv; matches are approximate, and their coverage differences are stated. No new validation threshold search was used.','',
        '**Animal and quality results**','']
    animal=[]
    for s in stages:
        for r in read_csv(RUN/s/'by_stratum.csv'):
            if r['axis']=='animal': animal.append([labels[s],r['group'],r['supported_measured']+' / '+r['supported_surface_columns'],pct(r['supported_coverage']),num(r['boundary_p95_um']),pct(r['unreadable_leakage'])])
    lines += [table(['Checkpoint','Animal','Supported retained / eligible','Coverage','p95 (um)','Leakage'],animal),'',
        'TS336 has no eligible manual boundary positions and no explicit whole-column exclusions in this validation set. Its accuracy and unreadability leakage are unavailable; retained unknown positions are not evidence of correctness.','',
        table(['C2 quality stratum','Supported retained / eligible','Coverage','p95 (um)','Gross'],[[r['group'],r['supported_measured']+' / '+r['supported_surface_columns'],pct(r['supported_coverage']),num(r['boundary_p95_um']),r['boundary_gross_n']] for r in read_csv(RUN/stages[1]/'by_stratum.csv') if r['axis']=='qc']),'',
        '**Every layer remains reported**','',
        'These are experimental thickness errors against eligible manual endpoint pairs, not checks against published layer thicknesses. A low median does not clear a local gross failure. No layer is silently omitted.','',
        table(['Layer','C2 retained / eligible','C2 median / p95 (um)','C2 gross','C3 coverage','C3 p95 (um)'],[
            [r['name'],r['n_retained']+' / '+r['n_eligible'],num(r['median_abs_um'])+' / '+num(r['p95_abs_um']),r['n_gross'],pct(q['coverage']),num(q['p95_abs_um'])]
            for r in read_csv(RUN/stages[1]/'boundary_thickness_metrics.csv') if r['axis']=='pooled' and r['kind']=='thickness'
            for q in read_csv(RUN/stages[2]/'boundary_thickness_metrics.csv') if q['axis']=='pooled' and q['kind']=='thickness' and q['name']==r['name']]),'',
        'The checkpoint folders also contain all eight boundary tables, thickness results by animal/quality/biology/scope, per-B-scan worst runs, useful labelled tissue lost, overlapping exclusion reasons and individual measurement views. Existing legacy labels have surface-wide edit evidence rather than exact stroke provenance; the frozen eligibility approximation is preserved for comparison and does not establish per-column local visibility.','',
        '**Stopping decision and next productive work**','',
        'All three configurations fail at least one criterion frozen before C1. C2 meets pooled coverage, leakage, gross fraction, maximum error and crossing criteria, but fails corrected-animal coverage, readable-control coverage and maximum contiguous gross run. C3 loses 12.1 percentage points of supported coverage without changing the remaining gross count or run. A fourth blanket tightening would address neither the smooth ILM error nor the need to preserve visible shallow boundaries through deeper uncertainty. Further work should collect local evidence and then test per-boundary visibility supervision.','',
        'The annotation proposal contains 24 review items across nine development images and five animals. It includes the residual D98 ILM error, good manual tissue withheld in the two stricter passes, two accuracy-unscorable TS336 cases, and positive training examples from TS165 and TS241. The existing GUI already has local visibility/provenance controls; this experiment does not modify it or any label format. See ANNOTATION_NEXT_STEP.md and annotation_cards/.','',
        'Software verification: 41 tests passed; 114 delivered measurement files were checked for NaN, geometry, thickness, scope, ordering, jump and monotone-mask behavior; six deterministic failure-case reruns matched exactly. The original checkpoint and original Stage A trainer identity were verified. Final integrity results are in integrity_complete.json. Final-test and repeatability contents were blocked; no human labels, old artifacts, frozen dataset definitions or production defaults were written.']
    lines.append('At approximately matched coverage, the previous simple-plus-ordered comparator retains 81.4% versus C2 80.5% (0.89 percentage points apart), with 43 versus 19 gross boundary errors and p95 7.71 versus 7.46 um. This supports an improved withholding tradeoff, while the exact-support comparison above still shows no placement improvement.')
    lines.append('Integrity audit: 482 allowed development fingerprints verified, 3,181 previous artifact sizes/timestamps unchanged, and zero added files in the previous experiment roots. The new package is opt-in and outside the original Stage A trainer identity.')
    (RUN/'RUN_REPORT.md').write_text(links('\n'.join(lines)+'\n'),encoding='utf-8')
    annotation=['**Next annotation step — proposal only**','',
        'Start with the saved nine-image pilot. The decoder experiment is complete; this queue is ready for human review, but no new annotation files have been created. Its 24 items are selected review suggestions, not visibility labels.','',
        'Use the clean-image panel on each card before considering any model overlay. For each boundary and interval, record visible, locally unidentifiable, or unknown. Separately record whether a position is reliable enough to analyze. Draw a boundary only where it can be identified. Keep every unreviewed region unknown. Mark whole-column exclusion only when the image is unusable for every boundary; local loss of a deep boundary must not erase a visible ILM. Darkness alone does not establish invisibility.','',
        'Highest priority is D98 ILM columns 232–250: all three decoders retain a 25–39 um error against the existing manual reference. Review its exact visible boundary and record local drawing support. Next inspect b0510: C2/C3 withhold the entire image, so the pilot must establish which intervals can still be traced. Then review useful tissue lost in D42 b0023/b0508 and TS169 b0164. Add the two TS336 images with no eligible boundary-accuracy labels and the two training controls.','',
        table(['Image','Partition','Suggested items','Card'],[[key,next(r['split'] for r in read_csv(RUN/'annotation_queue_proposal.csv') if r['key']==key),sum(r['key']==key for r in read_csv(RUN/'annotation_queue_proposal.csv')),'[Open](annotation_cards/'+key+'.png)'] for key in dict.fromkeys(r['key'] for r in read_csv(RUN/'annotation_queue_proposal.csv'))]),'',
        'The CSV gives zero-based start and end-exclusive A-line coordinates. Cards show the corresponding inclusive endpoint for reading. Items spanning all 512 columns request a review pass, not continuous drawing across unreadable tissue.','',
        'The current eight_surface/label_gui.py already supports left-drag drawing, shift+right-drag local invisibility, ctrl+shift+right-drag visibility restoration, alt+right-drag local unreliability, shift+left-drag explicit review, and whole-column right-drag exclusion. Verify the displayed controls before the session because that GUI belongs to separate ongoing work. This experiment has not changed or launched it. Human annotations must be saved through the GUI into a new, versioned label destination; preserve existing labels and the frozen evaluation targets.','',
        'The next training target must use actual local drawn provenance for boundary positions and explicit local visibility states for per-boundary readability. Reviewed automatic lines, taper joins, ordering-displaced points, absent labels and unknown regions cannot become drawn boundary ground truth. Existing legacy surface-wide flags cannot recover missing stroke history. Reviewed visibility can support a separate visibility target without turning the automatic boundary into a position target.','',
        'Keep the original animal splits. Training-side annotations may support model fitting; the repeatedly inspected validation examples remain development diagnostics. Do not claim independent validation by relabelling these examples. After a small annotated pilot, audit known/unknown counts, visible versus unidentifiable balance, and endpoint support for every layer before specifying the next bounded model experiment. Final-test and repeatability data remain unopened.','',
        'A useful pilot outcome is paired evidence within the same A-line: ILM visible while a deeper boundary is explicitly unidentifiable, plus clear positive intervals for every surface. This directly addresses the useful coverage lost by whole-column rejection. Agreement on local visibility and faithful stroke provenance come before adding more threshold rules.']
    (RUN/'ANNOTATION_NEXT_STEP.md').write_text(links('\n'.join(annotation)+'\n'),encoding='utf-8')


if __name__=='__main__': run()
