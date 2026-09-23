"""Measured run report and frozen source inventory."""
import collections,csv,json
import numpy as np
from pathlib import Path
from .inputs import OUT
from octa_reg_v2.run import read,write,sha

def report(root=OUT):
    summary=read(root/'summary.json');manifest=read(root/'inputs/manifest.json');groups=read(root/'run_plan.json')['groups']
    pairs=trials=accepted=cnv_pairs=small_pairs=changed=0;rows=[];dev=[]
    for g in groups:
        data=read(root/g/'review_registration.json');p=read(root/g/'pair_evidence.json');pairs+=len(p)
        trials+=sum(r['trial_count'] for r in p);accepted+=sum(r['accepted'] for r in p)
        cnv_pairs+=sum(r.get('cnv_support') is not None for r in p)
        small_pairs+=sum(r.get('small_support') is not None for r in p)
        if not data['inherited_review']:changed+=sum(r['corner_rms_px']>50 for r in data['changes_from_v2'])
        for i,s in enumerate(data['scans']):
            c=data['cnv_sources'][i]
            rows.append(dict(group=g,scan_id=s['scan_id'],registration_tier=data['graph']['tiers'][str(i)],
                cnv_source=c['source'],cnv_complete=c['complete'],cnv_pixels=c['pixels'],cnv_weight=c['weight'],cnv_provenance=c.get('provenance','')))
        if data['development_comparison']:
            records=[r for r in data['development_comparison'] if r['review_tier']=='supported' and r['confirmed']]
            dev.append(dict(group=g,n=len(records),v2_median_px=float(np.median([r['v2_corner_rms_px'] for r in records])),
                            v3_median_px=float(np.median([r['v3_corner_rms_px'] for r in records]))))
    with (root/'SCAN_PROVENANCE.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    metrics=dict(pair_comparisons=pairs,candidate_trials=trials,accepted_pairs=accepted,graph_trials=3*len(groups),
        pairs_with_small_vessel_evidence=small_pairs,pairs_with_cnv_location_evidence=cnv_pairs,
        large_change_proposals_flagged=changed,development=dev)
    write(root/'SEARCH_METRICS.json',metrics)
    t=summary['totals'];development='\n'.join(f"| {r['group']} | {r['n']} | {r['v2_median_px']:.1f} | {r['v3_median_px']:.1f} |" for r in dev)
    sources='\n'.join(f"- {name}: {count} fields" for name,count in manifest['cnv_counts'].items())
    review_counts=manifest['placement_reviews']
    review_description='; '.join(f"{g} revision {r['revision']} (whole montage confirmed: {r['montage_confirmed']})" for g,r in review_counts.items())
    inherited_rows=[r for review in review_counts.values() for r in review['records']]
    confirmed_count=sum(r['placement_confirmed'] for r in inherited_rows)
    flagged_count=sum(r['review_tier'] in ('uncertain','unlocalized') for r in inherited_rows)
    (root/'REPORT.md').write_text(f'''# octa-reg_v3 · pooled retinal montage release

All {t['total']} acquisitions are accounted for in {len(groups)} separate animal-eye groups: **{t['supported']} supported, {t['uncertain']} flagged, {t['unlocalized']} unlocalized and {t['excluded']} source exclusions**. Reviewed eyes preserve the user's saved geometry, categories and individual confirmations; the other {len(groups)-len(review_counts)} eyes were re-registered. All dates are pooled. This is a revised classical rigid-registration pipeline, not a newly trained neural network.

## What changed

The run evaluated **{pairs:,} scan pairs and {trials:,} candidate poses**, plus {3*len(groups)} graph-priority trials. It includes full-field SIFT on locally equalized structure and fine detail, two descriptor ratios/random seeds per channel, old v2 alternatives, CNV-center starting proposals, and multi-start refinement combining large and small vessel distances. Fine ridges are extracted at 1–3 pixel scales outside a seven-pixel trunk-centerline band and selected CNVs. These are image-derived candidate features: they capture small branches but can also include trunk edges, RNFL texture and acquisition artifacts. They are not new validated vessel masks. Fine texture is evaluated separately from large-vessel agreement. Candidate metrics, strongest rejected alternatives and ambiguity margins are saved per pair. Example overlays are in `verification/features/large_and_small_vessels.png`.

CNV locations contributed to ranking for {cnv_pairs} pair comparisons; small-vessel evidence was available for {small_pairs}. These are availability counts, not correct-registration counts. Confirmed/manual CNVs have greater weight than predictions. Across dates the location weight is lower and shapes are not forced to agree, because lesions change. CNV agreement cannot independently pass the vessel gates. Explicit no-CNV fields are preserved as absence; unchecked or empty predictions are not negatives.

Three graph fits prioritize balanced evidence, fine detail or large vessels. Internal loop agreement and ONH conflicts choose a trial. Fields moving more than 50 pixels in corner RMS from v2 are flagged for review ({changed} automatic fields); tentative connections do not certify dependent fields. The final safety pass refits only supported observations. No image is resized, stretched, flipped or reconstructed from RAW.

## Your TS165 corrections

The exact source reviews are {review_description}. {confirmed_count} fields were individually confirmed; {flagged_count} fields remain flagged. Manual ONH origins are carried forward. Inherited confirmations are explicitly identified as inherited and are not fabricated new review actions. v2 originals and all CNV annotations remain unchanged.

The automatic search was also checked against supported, individually confirmed TS165 placements, after aligning each result's reference field to the same human frame. The table reports median per-field corner-coordinate RMS discrepancy in native pixels (including the fixed reference), before substituting the exact human poses for delivery.

| Eye | Supported reference fields | v2 discrepancy (px) | v3 discrepancy (px) |
|---|---:|---:|---:|
{development}

OD improves substantially in this development comparison; OS does not consistently improve. Large errors remain for some fields. This is not held-out accuracy, and internal scores or a larger montage do not establish anatomical correctness. The source images with enlarged vessels have not been scale-corrected: changing physical scale would need acquisition calibration, not a cosmetic fit.

## Selected CNV sources

The input snapshot uses the latest v9 Model3 gallery and its current correction records. Corrections supersede earlier targets, followed by explicit absence, frozen manual supervision and confirmed model choices. Draft corrections contribute only explicitly kept regions with reduced weight; unsure/excluded pixels are masked. Predictions requested for correction are withheld when no correction or confirmed alternative exists.

{sources}

`SCAN_PROVENANCE.csv` gives the chosen source, confirmation state and registration category per scan. `inputs/manifest.json` records hashes and immutable review snapshots. `registration.json` preserves raw graph results; `review_registration.json` contains the final safety pass; `automatic_trial_graph.json` preserves automatic TS165 alternatives. `development/round1` preserves the first TS165 trial. No segmentation labels, learned weights or source images were changed.

## Reviewer and reproducibility

Open `OPEN_REVIEWER.cmd` or http://127.0.0.1:8774/. Pink CNV outlines, day filters, flagged toggles, move/rotate, Move ONH, notes and categories are available. See `REVIEW_GUIDE.md` for saving and the downstream analysis contract. Native x-right/y-down orientation is preserved; anatomical NSEW remains unconfirmed.

Activate the `octa` conda environment, set PYTHONPATH to the repository `code` directory, then run `python -m octa_reg_v3.run --output <fresh-folder> --workers 4`, `python -m octa_reg_v3.finalize --output <fresh-folder>`, `python -m octa_reg_v3.publish --output <fresh-folder>`, and `python -m octa_reg_v3.report --output <fresh-folder>`. Input or algorithm changes require a new folder. Released review baselines must not be rebuilt after human v3 edits without explicit reconciliation.

`verification.json` records complete inventory, animal/eye isolation, rigid transforms, source hashes and exclusion checks. `UI_VERIFIED.json` records browser tests on isolated copies. These implementation checks are not registration accuracy validation.
''',encoding='utf8')
    print(json.dumps(metrics),flush=True)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args();report(a.output)
