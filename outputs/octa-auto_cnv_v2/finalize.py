"""Audit saved pilot, freeze numerical tables, and document failures honestly."""
from common import *
from algorithm import detect,quantify,grow,VARIANTS
from scipy import ndimage as ndi
import csv


def table(name,rows):
    with destination(HERE/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    checks=[];candidate_rows=[];sens=[];summary=[];locations=[]
    for visit in selected():
        sid=visit['scan_id'];out=HERE/'scans'/sid; a=npz(out/'maps.npz'); p=read(out/'provenance.json'); s=read(out/'summary.json')
        print('Verify',sid,flush=True)
        old=npz(ROOT/'outputs/octa-auto_cnv_v1/scans'/sid/'maps.npz')
        assert np.array_equal(old['automatic_thickness_um'],a['automatic_thickness_um'],equal_nan=True)
        c,records=detect(a);assert np.array_equal(c['candidate_labels'],a['candidate_labels'])
        m,d=quantify(a,c)
        for k in ('core','footprint','deficit_percent','background_supported'):
            assert np.array_equal(m[k],a[k],equal_nan=True),(sid,k)
        audit=next(r for r in read(LONG/'verification'/f'{sid}.json') if r['version']=='v2')
        assert audit['measurements']['sha256']==sha(volume_path(sid)/'measurements.npz')
        assert audit['native_rows_verified']==[0,256,511]
        assert np.isnan(a['automatic_thickness_um'][a['shadow']]).all()
        shapes=[a[k].shape for k in ('core','enface','automatic_thickness_um')];assert shapes==[(512,512)]*3
        for name in VARIANTS:
            assert np.array_equal(a[name+'__core'],a['core'])
            deficit=a[name+'__deficit_percent'];support=a[name+'__background_supported']
            assert np.isnan(deficit[~support]).all()
            assert np.isnan(deficit[~np.isfinite(a['automatic_thickness_um'])|a['vessel']|a['shadow']|a['low_signal']]).all()
            ok=np.isfinite(deficit)
            expected=100*(a[name+'__background_um'][ok]-a['automatic_thickness_um'][ok])/a[name+'__background_um'][ok]
            assert np.allclose(expected,deficit[ok],atol=1e-4)
            common=ok & np.isfinite(a['default__deficit_percent'])
            row=dict(scan_id=sid,variant=name,core_pixels=int(a['core'].sum()),supported_fraction=float(support.mean()),
                     measured_candidate_pixels=int((a['core'] & ok).sum()),
                     observed_footprint_mm2=float(a[name+'__footprint'].sum()*PIXEL_MM2) if ok.any() else None,
                     candidate_measurement_coverage=float(ok[a['core']].mean()) if a['core'].any() else None,
                     mean_deficit_difference_common_pp=float(np.mean(np.abs(deficit[common]-a['default__deficit_percent'][common]))) if common.any() else None)
            for t in (10,20,30):
                contour=deficit>=t; other=a['default__deficit_percent']>=t;union=common&(contour|other)
                row[f'contour{t}_observed_mm2']=float(contour.sum()*PIXEL_MM2) if ok.any() else None
                row[f'contour{t}_common_jaccard']=float((common&contour&other).sum()/union.sum()) if union.any() else None
            sens.append(row)
        for r in p['candidates']:
            mask=a['candidate_labels']==r['id'];ok=mask&np.isfinite(a['deficit_percent'])
            candidate_rows.append(dict(scan_id=sid,id=r['id'],row=r['row'],col=r['col'],priority=r['priority'],
                core_mm2=r['core_mm2'],persistence_rows=r['persistence_rows'],geometry_pixels=r['geometry_pixels'],
                artifact_fraction=r['artifact_fraction'],vessel_fraction=r['vessel_fraction'],shadow_fraction=r['shadow_fraction'],
                low_signal_fraction=r['low_signal_fraction'],seam_fraction=r['seam_fraction'],fov_clipped=r['fov_clipped'],
                measurable_core_fraction=float(ok.sum()/mask.sum()),
                supported_median_core_deficit_percent=float(np.median(a['deficit_percent'][ok])) if ok.any() else None,
                geometry_failures=json.dumps(r['geometry_failures']),human_reviewed=False))
        tol=grow(a['core']|a['footprint'],75)
        s['core_field_fraction']=float(a['core'].mean());s['tolerance_field_fraction']=float(tol.mean())
        s['measurable_candidate_pixels']=int((a['core']&np.isfinite(a['deficit_percent'])).sum())
        s['default_background_sufficient']=p['diagnostics']['default']['sufficient']
        s['observed_footprint_mm2']=s.pop('footprint_mm2')
        summary.append(s)
        if p['reference_review']['reviewed_cnv']:
            labels,n=ndi.label(a['manual_cnv'],np.ones((3,3)))
            distance=ndi.distance_transform_edt(~a['core'])*PIXEL_UM
            for k in range(1,n+1):
                mask=labels==k;y,x=np.nonzero(mask)
                locations.append(dict(scan_id=sid,manual_component=k,manual_row=float(y.mean()),manual_col=float(x.mean()),
                    minimum_core_distance_um=float(distance[mask].min()),core_overlap_fraction=float(a['core'][mask].mean()),
                    location_hit_75um=bool(tol[mask].any()),ambiguous_border_not_exact_truth=True))
        checks.append(dict(scan_id=sid,native_shape_verified=True,prior_source_row_check=audit['native_rows_verified'],
            prior_source_check_sha256=sha(LONG/'verification'/f'{sid}.json'),unchanged_thickness_vs_v1=True,
            candidate_reproduced=True,default_quantification_reproduced=True,all_six_variants_same_candidates=True,
            missing_exclusions_and_signed_units=True))
    table('summary.csv',summary);table('candidates.csv',candidate_rows);table('sensitivity.csv',sens);table('manual_location_comparison.csv',locations)
    write(HERE/'verification/native_checks.json',checks)
    sid='TS267_OD_2025-03-05_D14_s01_104048';a=npz(HERE/'scans'/sid/'maps.npz');old=npz(ROOT/'outputs/octa-auto_cnv_v1/scans'/sid/'maps.npz')
    failures=[]
    for j,(u,v) in enumerate(a['geometry_pairs']):
        if a['geometry_crossing'][230,j,85]:failures.append(dict(boundaries=[str(a['surface_names'][u]),str(a['surface_names'][v])],failure='crossing',violation_px=float(a['geometry_crossing_size_px'][230,j,85])))
    assert a['core'][230,85] and not old['core'][230,85] and not old['background_supported'][230,85]
    write(HERE/'verification/D14_regression.json',dict(scan_id=sid,native_bscan=230,native_aline=85,
        approximate_user_location_not_a_human_mask=True,v2_candidate=int(a['candidate_labels'][230,85]),
        v1_candidate=False,v1_supported=False,v2_default_supported=bool(a['background_supported'][230,85]),
        thickness_unavailable=not bool(np.isfinite(a['automatic_thickness_um'][230,85])),failures=failures,
        vessel=bool(a['vessel'][230,85]),shadow=bool(a['shadow'][230,85]),low_signal=bool(a['low_signal'][230,85]),
        structural_z=float(a['structural_context'][230,85]),linked_rows=[227,230,233]))
    original=ROOT/'outputs/octa-auto_cnv_v1';manifest=read(original/'implementation_manifest.json')
    preservation={name:sha(original/name)==digest for name,digest in manifest.items()}
    assert all(preservation.values()),preservation
    write(HERE/'verification/v1_preservation.json',preservation)
    write(HERE/'implementation_manifest.json',{p.name:sha(p) for p in HERE.iterdir() if p.suffix in ('.py','.cmd')})
    total=sum(s['candidate_count'] for s in summary);hits=sum(s['location_hits_75um'] for s in summary);refs=sum(s['reviewed_manual_components'] for s in summary)
    failed=sum(not s['default_background_sufficient'] for s in summary)
    text=f'''# octa-auto_cnv_v2 — integrated lesion review

All 17 selected TS267 acquisitions processed and verified. Experimental development pilot; human candidate review remains pending.

Open **OPEN_OCTA_AUTO_CNV_V2.cmd**. One window provides structural en face, geometry/structural evidence, selectable quantitative maps, and native B-scans with the established boundary editor. **RUN_PILOT.cmd --resume** resumes processing. **VERIFY.cmd** runs synthetic GUI/scientific tests and the saved-data audit. All v2 writes stay here.

## Measured result and limitations

- Location agreement: **{hits}/{refs}** reviewed manual-mask components within 75 um, versus **0/7** in v1. D7: 5/5; D28: 2/2. Components may be disconnected fragments of one lesion, not distinct lesions. Borders are approximate.
- D14 A-line 85 / B-scan 230 is now candidate **7**, despite unavailable thickness and no default reference support. No coordinate-specific rule or human annotation was created.
- Review burden: **{total} candidates**, versus {sum(s['v1_candidates'] for s in summary)} in v1; {sum(s['uncertain_candidates'] for s in summary)} explicitly uncertain/artifact challenges. Several large candidates follow vessels or field artifacts. More coverage can itself improve location agreement: candidate and 75-um tolerance field fractions are reported for every scan. This is not validated sensitivity or precision.
- **{failed}/17 default background fits are insufficient** after candidate/halo exclusion. Other scans can have supported background elsewhere while the candidate itself has no measurable deficit. A zero observed supported footprint is not a zero lesion area. Missing or unsupported regions never count as zero deficit.
- There are **no reviewed-normal pixels** in this pilot reference set. False-candidate performance and review rejection rate are unavailable until genuine review occurs. D0 is a challenge, not a confirmed negative.

## D14 structural inspection

The raw neural ILM crosses RNFL/GCL by 13.76 px; INL/OPL crosses OPL/ONL by 50.25 px; PR/RPE crosses outer RPE by 10.36 px at the supplied point. These are crossings, not nonfinite or out-of-crop positions. ILM and outer RPE fail because they cross intermediate surfaces, even though ILM remains above outer RPE. Vessel, shadow, low-signal, and automatic trace-loss flags are absent at this point.

Linked native B-scans 227, 230 and 233 show a localized disturbance of retinal band structure with unstable inner and outer neural traces. The appearance persists across the neighborhood, so it merits lesion review; neural curves are visibly unreliable there and do not establish lesion anatomy or recovered tissue thickness. See `verification/D14_linked_bscans.png` and `verification/D14_regression.json`.

## How to review

1. Select a candidate on a map or in the region list. Orange is the immutable automatic core; cyan is the existing manual comparison. Inspect the linked B-scans and reason panel. Use scan/B-scan selectors or native-map clicks; the same crosshair is shared.
2. Choose **Structural footprint** or **Candidate core**. Draw region adds a missed region; Redraw replaces the selected target. Paint/Erase use the established round brush; Split by stroke cuts a structural region into components. Core cutting preserves the structural footprint. Merge with joins selected regions. Undo/Redo retain masks, decisions and edit provenance.
3. **Approve footprint** explicitly approves the current structural footprint as Full Lesion. For Normal/Other, choose the category (explain Other), then **Complete region review**. Changing a category alone stays a draft. **Reject candidate** retains its original seed and rejection record. No action labels tissue outside the reviewed region.
4. Save all or Ctrl+S; scan changes and closing also save actual edits. Opening, navigating, selecting, or switching map variants writes no annotations. Reload saved supports resolving disk conflicts; a changed automatic seed is blocked for explicit reconciliation rather than transferring old approvals.
5. Select background variants to inspect 10/20/30% contours, reference sensitivity, and sample/support regions. The automatic core list cannot change. **Recompute assisted from reviewed footprints** uses current saved boundary corrections and footprint decisions: rejected/Normal regions stop excluding background, approved lesions add exclusions. Its candidate output remains the original automatic set. Assistance hashes and measurements are saved separately under `assisted_review/`; unchanged saved assisted results reload, stale ones are not reused.

Numeric contours, candidate cores and structural footprints are independent. Painting a footprint never changes a numerical contour. Quantitative recomputation is explicit and assisted. Pink outlines indicate missing thickness, blue vessel/shadow, lavender selected uncertain margins, mustard low signal, and gray reference-support edges. Clipping is reported per candidate. The background map includes explicitly labeled extrapolations; these never enter supported deficits or area summaries. No actual OCTA projection is loaded, so no view is labeled OCTA.

## Method and measurement contract

First-stage evidence uses every pair of eight raw neural boundaries, with exact crossing masks and violation sizes plus per-boundary nonfinite/out-of-crop masks. Connected geometry/automatic-trace loss, structural departures (robust local en-face residual), and measurable local thickness departures form interpretable proposals. Two-pixel closing connects fragments only for candidate geometry; a proposal requires at least 24 observed pixels over at least three B-scans. Isolated failures remain available as evidence. Geometry requires neither thinning nor structural confirmation to remain a tentative candidate. Vessel/shadow, low signal and row-seam evidence affect priority, never erase a candidate. A structural-only alternative uses z>=4; z>=2.5 with >=12 um local measured departure is another alternative. These are exploratory thresholds, not calibrated diagnostic probabilities. Closing can join adjacent abnormalities and vessel artifacts; split/merge review is essential.

Afterward, candidates and 90/150/210 um halos are excluded from background sampling. The preserved robust tile-quantile plane/quadratic fitter additionally excludes coherent low residual areas. Local coverage in at least three quadrants and >=8% of a 350 um neighborhood replaces v1's tile-center convex-hull support. Minimum fit sample fraction remains 8%, with sufficient populated tiles. This conservative rule often sacrifices measurements; a broad smooth halo can still contaminate a fitted reference. Six variants measure sensitivity to halo size, tile quantile and polynomial choice, not statistical uncertainty. Shared thinning footprints are possible and should not be summed as independent lesions.

Full retina is exactly **ILM to outer RPE edge ×1.12 um/pixel**, unchanged from v1. Signed deficit is **100 × (expected background − measured thickness) / expected background**. All maps retain native [B-scan,A-line] coordinates; lateral scale is approximately 1460/512 um per pixel. Missing measurements, shadows and unsupported estimates remain unavailable. Vessel and low-signal pixels are also excluded from quantitative deficit summaries. A fitted background is not recovered tissue. Supported observed contour/footprint area is partial coverage, not total anatomical lesion area.

The automatic branch removes target-specific position edits, human state denials and regional feedback where separable, retaining frozen neural predictions and automatic acquisition masks. Automatic geometry and human-assisted missingness are distinct. Upstream ALL_LABELLED segmentation training includes **TS267**; vessel context may include manual assistance. This is not independent detector validation. Other animals remain reserved for subsequent detector evaluation, distinct from their pre-existing upstream segmentation training exposure. No visits are registered and no longitudinal lesion-change claim is made. Day labels remain nominal.

## Files and next step

- `summary.csv`: v1/v2 location agreement, review burden, field coverage and reference availability.
- `candidates.csv`: native candidate locations, persistence, artifact fractions, boundary failures and measurable core coverage.
- `manual_location_comparison.csv`: per-component location agreement without treating borders as exact truth.
- `sensitivity.csv`: six reference variants, supported observed contour areas, common-support agreement and deficit changes.
- `scans/<scan>/maps.npz`, `provenance.json`, `overview.png`: automatic and clearly prefixed assisted results, masks, source hashes and images.
- `review/regions`: RegionStore-compatible human GUI records with draft category, edited-pixel runs, separate core runs, explicit reviewed/unreviewed runs, seed hashes and revision history. `review/surface_labels` uses the existing embedded boundary GUI. No old labels or released models are modified.
- `verification`: scientific/GUI tests, all-17 native and missing-data checks, D14 evidence, GUI captures, and v1 source-hash preservation.

**Next review:** inspect D14 candidate 7 first, then D7/D28 manual locations, D0 candidates, and broad vessel/seam candidates. Reject artifacts, inspect uncertain/clipped margins, approve only the footprint actually reviewed, then recompute the assisted reference. Do not use automatic proposal pixels as ground truth or report complete lesion area from the partial quantitative maps.

| Scan | v1 candidates | v2 candidates | Locations hit/available | Default support | Observed footprint mm² |
|---|---:|---:|---:|---:|---:|
'''
    for s in summary:
        area='unavailable' if s['observed_footprint_mm2'] is None else f'{s["observed_footprint_mm2"]:.5f}'
        text+=f'| {s["scan_id"]} | {s["v1_candidates"]} | {s["candidate_count"]} | {s["location_hits_75um"]}/{s["reviewed_manual_components"]} | {100*s["supported_fraction"]:.1f}% | {area} |\n'
    destination(HERE/'START_HERE.md').write_text(text,encoding='utf-8')
    examples=[v for v in selected() if (v['day_label'] in ('D0','D7','D14','D28') and v['eye']=='OD')]
    html='<html><head><meta charset="utf-8"><title>CNV v2 review examples</title><style>body{font:18px system-ui;background:#181b20;color:#eee;margin:32px}img{width:100%;max-width:1200px}a{color:#6ce}</style></head><body><h1>CNV v2 · review examples and failures</h1><p>Experimental; missing quantitative areas are unavailable. No longitudinal change claimed.</p>'
    for v in examples:html+=f'<h2>{v["scan_id"]}</h2><img src="scans/{v["scan_id"]}/overview.png">'
    html+='<h2>D14 linked neural geometry failures</h2><img src="verification/D14_linked_bscans.png"><h2>Integrated GUI</h2><img src="verification/integrated_gui.png"></body></html>'
    destination(HERE/'REVIEW_ATLAS.html').write_text(html,encoding='utf-8')
    write(HERE/'AUDIT_COMPLETE.json',dict(scans=17,candidates=total,location_hits=hits,manual_components=refs,insufficient_default_background=failed,automatic_review_pending=True,detector_hash=sha(HERE/'algorithm.py')))
    print('AUDIT COMPLETE',total,'candidates;',hits,'/',refs,'locations;',failed,'insufficient fits',flush=True)

if __name__=='__main__':main()
