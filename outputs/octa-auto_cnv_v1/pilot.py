"""Run the TS267 pilot from frozen native longitudinal v2 arrays."""
import argparse
import csv
import gc
from types import SimpleNamespace
from common import *
from algorithm import run, VARIANTS, grow
from scipy import ndimage as ndi

CAUSES = {1: 'automatic not traceable', 2: 'vessel/shadow exclusion',
          4: 'invalid neural geometry', 8: 'explicit human not traceable',
          16: 'explicit human unreliable', 32: 'human image exclusion/rejected B-scan',
          64: 'regional human unreliability', 128: 'unattributed viewer missing',
          256: 'low acquisition signal (background/core guard, not viewer withholding)'}

def geometry_valid(rows, offset, depth):
    valid = np.isfinite(rows) & (rows >= offset) & (rows < offset+depth)
    for a in range(rows.shape[1]):
        for b in range(a+1, rows.shape[1]):
            crossing = np.isfinite(rows[:, a]) & np.isfinite(rows[:, b]) & (rows[:, a] >= rows[:, b])
            valid[:, a] &= ~crossing
            valid[:, b] &= ~crossing
    return valid

def inputs(sid):
    v = volume(sid)
    d, g = v.d, v.g
    base = npz(v.path/'v1_matched_baseline.npz')
    # Assert the saved raw branch is unaffected by v2 position edits.
    if not np.array_equal(base['raw_position_branch'], d['raw_position_branch'], equal_nan=True):
        raise ValueError('Raw branch differs from frozen neural baseline')
    rows = base['raw_position_branch']
    prob = base['probabilities']
    cal = read(ROOT/'outputs/octa-seg/octa-seg_v1/calibration/deployment_vessels.json')['thresholds']
    denied = np.zeros(rows.shape, bool)
    uncertain = np.zeros(rows.shape, bool)
    for k, c in enumerate(cal):
        # Matches decide()'s unsupported-calibration reset, without human guards.
        if c['supported']:
            denied[:, k] = prob[:, k, 0] <= c['not_traceable_cutoff']
        uncertain[:, k] = ~((prob[:, k, 0] >= c['trace_cutoff']) & (prob[:, k, 1] >= c['reliability_cutoff'])) | (not bool(c['supported']))
    valid = geometry_valid(rows, v.offset, v.images.shape[1])
    endpoint_ok = valid & ~denied
    delta = (rows[:, 7]-rows[:, 0])*1.12
    shadow = g['shadow']
    automatic = np.where(endpoint_ok[:, 0] & endpoint_ok[:, 7] & ~shadow & (delta > 0), delta, np.nan).astype(np.float32)
    viewer = v.maps[0][0][0].copy()
    reason = v.messages[:, [0, 7]]
    cause = np.zeros(v.shape, np.uint16)
    cause[np.any(denied[:, [0, 7]], axis=1)] |= 1
    cause[shadow | g['vessel']] |= 2
    cause[~np.all(valid[:, [0, 7]], axis=1)] |= 4
    cause[np.any(np.isin(reason, [5, 23]), axis=1)] |= 8
    cause[np.any(v.unreliable[:, [0, 7]], axis=1)] |= 16
    cause[np.any(np.isin(reason, [7, 8, 23]), axis=1)] |= 32
    cause[np.any(d['reason'][:, [0, 7]] == 15, axis=1)] |= 64
    # Preserve original guards separately: current viewer reason 23 conflates causes.
    cause[~np.isfinite(viewer) & ((cause & 255) == 0)] |= 128
    low = g.get('low_signal', np.zeros(v.shape, bool))
    cause[low] |= 256
    arrays = dict(automatic_thickness_um=automatic, viewer_thickness_um=viewer,
                  enface=v.enface.astype(np.float32), vessel=g['vessel'], shadow=shadow,
                  low_signal=low, unavailable_cause_bits=cause,
                  automatic_trace_loss=np.any(denied[:, [0, 7]], axis=1),
                  automatic_measurement_loss=~np.isfinite(automatic),
                  automatic_uncertainty=np.any(uncertain[:, [0, 7]], axis=1),
                  invalid_geometry=~np.all(valid[:, [0, 7]], axis=1),
                  viewer_endpoint_reason=reason, frozen_endpoint_reason=d['reason'][:, [0, 7]],
                  viewer_endpoint_sources=v.sources[0][:, [0, 7]],
                  automatic_endpoints_crop_px=rows[:, [0, 7]]-v.offset)
    prep = read(v.path/'prepared.json')
    audit = dict(scan_id=sid, viewer_metadata=v.metadata(), preparation=prep,
                 cause_bits=CAUSES, cause_counts={name: int(np.sum((cause & k) != 0)) for k, name in CAUSES.items()},
                 cause_note='Overlapping provenance flags, not exclusive causes. Reason 23 conflates current human not-visible, image exclusion and rejection; original reasons are retained.',
                 automatic_input='Raw neural positions; no target CNV mask, manual position, human state, regional feedback or context estimate. Retains automatic trace denial and original shadow mask.',
                 vessel_assistance='Vessel context enters the state head. Saved manual vessel work, when present, remains an assistance source.',
                 upstream_training_overlap=True,
                 independent_detection_claim=False,
                 automatic_missing_pixels=int(np.isnan(automatic).sum()), viewer_missing_pixels=int(np.isnan(viewer).sum()),
                 viewer_only_missing_pixels=int(np.sum(np.isfinite(automatic) & ~np.isfinite(viewer))),
                 input_hashes={str(v.path/n): sha(v.path/n) for n in ('geometry.npz', 'measurements.npz', 'v1_matched_baseline.npz', 'prepared.json', 'human_overrides_provenance.json', 'human_guard_provenance.json')})
    audit['frozen_human_overrides'] = read(v.path/'human_overrides_provenance.json')
    audit['frozen_human_guards'] = read(v.path/'human_guard_provenance.json')
    del v
    return arrays, audit

def manual_reference(sid, source, shape):
    from eight_surface import cnv_labels as CL
    from cnv_review_v1.data import decode_mask
    mask = np.zeros(shape, bool)
    normal = np.zeros(shape, bool)
    audit = {'reviewed_cnv': False, 'reviewed_absence': False, 'sources': []}
    path = ROOT/'outputs/cnv_labels'/f'{sid}_cnv.npz'
    if path.exists():
        record = CL.load_label(path)
        if record['scan_id'] != sid or tuple(record['native_shape']) != shape or Path(record['source_volume']).resolve() != Path(source).resolve():
            raise ValueError('Manual reference coordinates/source mismatch')
        mask = record['cnv_mask'].copy()
        audit.update(reviewed_cnv=bool(record['reviewed_targets'][0]),
                     reviewed_absence=bool(record['reviewed_targets'][0]) and not bool(mask.any()))
        audit['sources'].append(dict(path=str(path), sha256=sha(path)))
    # Region judgments are read only as evaluation evidence, never passed to run().
    for root in (ROOT/'outputs/cnv_review_v1/regions', LONG/'v2/reviewer/regions'):
        path = root/f'{sid}_regions.json'
        if not path.exists():
            continue
        data = read(path)
        if data['scan_id'] != sid or tuple(data['native_shape']) != shape or Path(data['source_volume']).resolve() != Path(source).resolve():
            raise ValueError('Region reference coordinates/source mismatch')
        for r in data['regions']:
            if r['category'] == 'Full Lesion':
                mask |= decode_mask(r['runs'], shape)
                audit['reviewed_cnv'] = True
            elif r['category'] == 'Normal':
                normal |= decode_mask(r['runs'], shape)
        audit['sources'].append(dict(path=str(path), sha256=sha(path)))
    if audit['reviewed_absence']:
        normal[:] = True
    return mask, normal, audit

def components(mask):
    labels, count = ndi.label(mask, np.ones((3, 3)))
    return [labels == i for i in range(1, count+1)]

def evaluate(maps, manual, normal, review):
    candidates = components(maps['core'])
    references = components(manual) if review['reviewed_cnv'] else []
    proposed = maps['core'] | maps['footprint']
    tolerated = grow(proposed, 75)
    hits = [bool(np.any(r & tolerated)) for r in references]
    return dict(candidate_count=len(candidates), reviewed_manual_components=len(references),
                location_hits_75um=sum(hits), apparent_location_misses=len(hits)-sum(hits),
                false_candidates_in_reviewed_normal=sum(bool(np.all(normal[c])) for c in candidates) if normal.any() else None,
                candidates_touching_reviewed_normal=sum(bool(np.any(normal[c])) for c in candidates) if normal.any() else None,
                reviewed_normal_pixels=int(normal.sum()),
                manual_supported_fraction=float(np.mean(maps['background_supported'][manual])) if manual.any() else None,
                manual_core_overlap_fraction=float(np.mean(maps['core'][manual])) if manual.any() else None,
                manual_footprint_overlap_fraction=float(np.mean(maps['footprint'][manual])) if manual.any() else None,
                manual_edge_truth=False)

def figure(sid, arrays, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.subplots_adjust(left=.055, right=.975, bottom=.07, top=.89, wspace=.36, hspace=.38)
    lo, hi = np.percentile(arrays['enface'], [2, 98])
    for ax in axes.ravel():
        ax.imshow(arrays['enface'], cmap='gray', vmin=lo, vmax=hi)
        ax.set_xlabel('Native A-line', fontsize=9); ax.set_ylabel('Native B-scan', fontsize=9)
        ax.tick_params(labelsize=8)
    def line(ax, a, color, label):
        if a.any() and not a.all():
            ax.contour(a, [.5], colors=[color], linewidths=.8)
            from matplotlib.lines import Line2D
            ax.add_line(Line2D([], [], color=color, label=label))
    ax = axes[0, 0]
    line(ax, arrays['core'], '#ff6347', 'Candidate core')
    line(ax, arrays['footprint'], '#ffd45b', 'Associated thinning')
    line(ax, arrays['manual_cnv'], '#5edcff', 'Manual comparison')
    ax.set_title('Automatic proposals / manual location')
    if ax.get_legend_handles_labels()[0]: ax.legend(fontsize=7, loc='lower left')
    im = axes[0, 1].imshow(arrays['automatic_thickness_um'], cmap='viridis', vmin=180, vmax=360)
    fig.colorbar(im, ax=axes[0, 1], label='Full retina (µm)', shrink=.8)
    axes[0, 1].set_title('Neural positions; review effects removed')
    im = axes[0, 2].imshow(arrays['background_um'], cmap='viridis', vmin=180, vmax=360)
    line(axes[0, 2], arrays['background_regions'], '#f6ff80', 'Background samples')
    line(axes[0, 2], arrays['background_supported'], 'white', 'Supported reference')
    axes[0, 2].set_title('Estimated spatial reference / selected regions')
    fig.colorbar(im, ax=axes[0, 2], label='Estimated µm', shrink=.8)
    im = axes[1, 0].imshow(arrays['deficit_percent'], cmap='coolwarm', vmin=-30, vmax=40)
    for threshold, color in ((10, 'gold'), (20, 'orange'), (30, 'red')):
        line(axes[1, 0], arrays[f'contour{threshold}'], color, f'{threshold}%')
    axes[1, 0].set_title('Signed deficit; gray = unsupported/missing')
    fig.colorbar(im, ax=axes[1, 0], label='Deficit (%)', shrink=.8)
    im = axes[1, 1].imshow(arrays['deficit_sensitivity_span'], cmap='magma', vmin=0, vmax=15)
    axes[1, 1].set_title('Reference sensitivity (not a confidence interval)')
    fig.colorbar(im, ax=axes[1, 1], label='Percentage-point span', shrink=.8)
    reason = np.zeros((*arrays['shadow'].shape, 4))
    reason[~np.isfinite(arrays['automatic_thickness_um'])] = (1, .2, .4, .6)
    reason[arrays['shadow'] | arrays['vessel']] = (.2, .7, 1, .7)
    reason[~arrays['background_supported']] = (.7, .7, .7, .55)
    axes[1, 2].imshow(reason)
    axes[1, 2].set_title('Pink: missing · blue: vessel · gray: no reference')
    for ax in axes.ravel(): ax.title.set_fontsize(10)
    fig.suptitle(sid+'\nocta-auto_cnv_v1 · experimental; no visit registration', fontsize=13, y=.98)
    fig.savefig(destination(output), dpi=125)
    plt.close(fig)

def process(visit):
    sid = visit['scan_id']
    print('Loading', sid, flush=True)
    arrays, audit = inputs(sid)
    results, diagnostics = {}, {}
    sensitivity_rows = []
    for name, params in VARIANTS.items():
        maps, diag = run(arrays['automatic_thickness_um'], arrays['vessel'], arrays['shadow'],
                         arrays['automatic_measurement_loss'], arrays['low_signal'], arrays['enface'], params)
        results[name], diagnostics[name] = maps, diag
        sensitivity_rows.append(dict(variant=name, core_mm2=float(maps['core'].sum()*PIXEL_MM2) if diag['sufficient'] else None,
                                     footprint_mm2=float(maps['footprint'].sum()*PIXEL_MM2) if diag['sufficient'] else None,
                                     **{f'contour{t}_mm2': float(maps[f'contour{t}'].sum()*PIXEL_MM2) if diag['sufficient'] else None for t in (10, 20, 30)},
                                     supported_fraction=diag['supported_fraction']))
    maps = results['default']
    arrays.update(maps)
    stack = np.stack([r['deficit_percent'] for r in results.values()])
    count = np.isfinite(stack).sum(axis=0)
    low = np.min(np.where(np.isfinite(stack), stack, np.inf), axis=0)
    high = np.max(np.where(np.isfinite(stack), stack, -np.inf), axis=0)
    arrays['deficit_sensitivity_span'] = np.where(count >= 2, high-low, np.nan).astype(np.float32)
    arrays['sensitivity_supported_count'] = count.astype(np.uint8)
    for name, r in results.items():
        for key in ('deficit_percent', 'background_um', 'background_regions', 'background_supported', 'core', 'footprint'):
            arrays[f'{name}__{key}'] = r[key]
    # Human-informed viewer branch is deliberately distinguishable.
    assisted, assisted_diag = run(arrays['viewer_thickness_um'], arrays['vessel'], arrays['shadow'],
                                  ~np.isfinite(arrays['viewer_thickness_um']), arrays['low_signal'], arrays['enface'])
    for key in ('background_um', 'background_regions', 'background_supported', 'deficit_percent', 'core', 'footprint'):
        arrays['assisted__'+key] = assisted[key]
    manual, normal, review = manual_reference(sid, visit['source'], arrays['shadow'].shape)
    arrays.update(manual_cnv=manual, reviewed_normal=normal)
    metrics = evaluate(maps, manual, normal, review)
    arrays['candidate_labels'], _ = ndi.label(maps['core'], np.ones((3, 3)))
    records = []
    for i, mask in enumerate(components(maps['core']), 1):
        yy, xx = np.nonzero(mask)
        records.append(dict(id=i, row=float(yy.mean()), col=float(xx.mean()), core_mm2=float(mask.sum()*PIXEL_MM2),
                            missing_fraction=float(np.mean(~np.isfinite(arrays['automatic_thickness_um'][mask]))),
                            uncertain_margin=bool(np.any(grow(mask, 20) & (~maps['background_supported'] | maps['border']))),
                            fov_clipped=bool(np.any(grow(mask | (maps['footprint'] & grow(mask, 200)), 35)[[0, -1]]) or np.any(grow(mask, 35)[:, [0, -1]])),
                            overlaps_manual=bool(np.any(grow(mask, 75) & manual))))
    metadata = dict(format=VERSION, visit=visit, axis_order='B-scan,A-line', native_shape=list(manual.shape),
                    full_retina_endpoints=['ILM', 'RPE (outer edge)'], axial_um_per_px=1.12,
                    lateral_um_per_px=PIXEL_UM, area_scale='approximate 1460 um field / 512 in both axes',
                    automatic_proposal=True, human_reviewed=False,
                    footprint_rule='Connected >=10% measurable deficit associated within 20 um of core, 3-pixel closing for association only; no measurements filled.',
                    audit=audit, reference_review=review, diagnostics=diagnostics,
                    assisted_diagnostics=assisted_diag, sensitivity=sensitivity_rows,
                    metrics=metrics, candidates=records)
    out = HERE/'scans'/sid
    save_npz(out/'maps.npz', **arrays, metadata_json=np.array(json.dumps(metadata)))
    write(out/'provenance.json', metadata)
    figure(sid, arrays, out/'overview.png')
    save_npz(HERE/'proposals'/f'{sid}.npz', core=maps['core'], footprint=maps['footprint'],
             proposal_mask=maps['core'] | maps['footprint'], scan_id=np.array(sid),
             source_volume=np.array(visit['source']), native_shape=np.array(manual.shape),
             axis_order=np.array('B-scan,A-line'), human_reviewed=np.array(False))
    summary = dict(scan_id=sid, day=visit['day_label'], eye=visit['eye'],
                   background_sufficient=diagnostics['default']['sufficient'],
                   supported_fraction=diagnostics['default']['supported_fraction'],
                   core_mm2=float(maps['core'].sum()*PIXEL_MM2), footprint_mm2=float(maps['footprint'].sum()*PIXEL_MM2),
                   viewer_only_missing_pixels=audit['viewer_only_missing_pixels'], **metrics)
    write(out/'summary.json', summary)
    print('Completed', sid, 'cores', metrics['candidate_count'], 'supported', round(summary['supported_fraction'], 3), flush=True)
    del arrays, results, stack
    gc.collect()
    return summary

def report():
    visits = selected()
    rows = [read(HERE/'scans'/r['scan_id']/'summary.json') for r in visits if (HERE/'scans'/r['scan_id']/'summary.json').exists()]
    if not rows:
        return
    with destination(HERE/'summary.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    table = ['| Scan | Cores | Footprint mm² | Reference support | Manual locations hit/total |', '|---|---:|---:|---:|---:|']
    for r in rows:
        table.append(f"| {r['scan_id']} | {r['candidate_count']} | {r['footprint_mm2']:.4f} | {r['supported_fraction']:.1%} | {r['location_hits_75um']}/{r['reviewed_manual_components']} |")
    total = sum(r['reviewed_manual_components'] for r in rows)
    hits = sum(r['location_hits_75um'] for r in rows)
    unsupported = sum(not r['background_sufficient'] for r in rows)
    text = f'''# octa-auto_cnv_v1 — TS267 experimental pilot

Completed {len(rows)}/{len(visits)} selected longitudinal v2 acquisitions. Outputs and future review are isolated here.

Open **OPEN_OCTA_AUTO_CNV_V1.cmd** for native maps, background selection, selectable 10/20/30% contours, reference sensitivity and linked B-scans. Use **Edit proposals** to open the established region annotation GUI with separate, unclassified automatic seeds. Redraw, remove, or classify a region there; only explicit GUI actions save review. **RUN_PILOT.cmd** reruns this pilot, preserving review files. Maps are frozen snapshots; rerun after upstream corrections change.

## Measurement and method

Full retina exactly preserves the thickness viewer's ILM → outer RPE edge definition, ×1.12 µm/px. Coordinates are native [B-scan,A-line], with no image rotation or resampling. Area uses the approximate 1460 µm field in both directions. Signed deficit is 100 × (reference − thickness) / reference. Missing values remain NaN. Neither a fitted reference nor a missing core is recovered tissue thickness.

The main branch starts from saved neural positions, discards target-specific position corrections, context estimates, human state denials and regional feedback, and retains automatic trace denial, geometry checks and shadows. The separately named assisted branch uses the actual current viewer's default map. Automatic uncertainty is retained as a separate flag: this pilot follows the viewer's preliminary available-position policy, not a validated reliability claim. The viewer does not directly honor v2 regional reason 15 as an unreliability exclusion; that existing behavior is recorded, not changed here.

The reference fits a robust quadratic surface to 48-pixel tile 60th percentiles. It excludes borders, low signal, vessels/shadows plus 25 µm, and iteratively excludes coherent >7% thinning plus a 150 µm buffer. Suspected halos cannot re-enter the reference. At least 8% of pixels and 18 populated tiles are required. Support is confined to the tile-center convex hull and within 350 µm of retained samples. Extrapolated reference values are visible estimates; deficits outside support stay NaN. {unsupported} scans have insufficient background. A broad, smoothly varying halo can still be absorbed by the fit; sensitivity and manual background inspection are essential.

Cores require ≥1600 µm² coherent ≥30% thinning, or clustered automatic measurement loss next to ≥15% thinning, with a local structural departure in at least 10% of core pixels. Vessels, shadows, low signal and borders suppress cores. These heuristic gates can miss lesions, including vessel-crossing and peripheral lesions. Unconfirmed severe regions and clustered loss are retained separately. The footprint is the measurable ≥10% component associated with a core; a 3-pixel closing is used only for connectivity. Missing/vessel gaps are never turned into measured footprint. Multiple cores may share a footprint. Contours are descriptive deficit extents, not CNV anatomy.

Six reference variants vary halo exclusion (90/150/210 µm), tile quantile (50/60/70%), and plane versus quadratic fit. Saved area changes and per-pixel spans are sensitivity measurements, not statistical confidence intervals. Variant-specific support is saved; support differences must be considered when comparing areas.

## Pilot measurements

Location agreement: {hits}/{total} reviewed manual components intersect a proposal within 75 µm. This tolerance measures approximate location agreement, not exact border accuracy. Unreviewed regions are never confirmed negatives. Where reviewed unaffected scans/regions are absent, false-positive performance is unavailable; baseline candidate counts remain review candidates. Other TS267 manual masks on unselected repeat acquisitions were not transferred to this grid.

{chr(10).join(table)}

Every scan has an overview, numerical maps, sensitivity variants, candidates and detailed provenance under `scans/`. Pink missing centers, blue vessel exclusions, gray unsupported reference and zero-candidate/low-support cases are deliberately included as failure examples. See `summary.csv` for apparent misses and reviewed-normal counts.

## Circularity and limitations

No target CNV footprint enters the detector or reference fit. Frozen raw positions match the pre-v2 baseline exactly. Inspection of `octa_seg_v1.predict.one` and v2 inference shows that CNV masks do not enter inference; vessel masks enter the state head. The upstream ALL_LABELLED models were trained on TS267 as well as the other labeled animals. This is a development pilot with training overlap, not independent detection validation or cross-animal performance. Existing manual vessels can still assist the state predictions. Human-derived missing regions may drive the assisted branch and must not be credited as automatic detections.

`provenance.json` records source hashes, original reasons, human guard records and current correction hashes. `unavailable_cause_bits` allows overlapping causes; viewer reason 23 cannot alone distinguish not-visible from image exclusion/rejection, so original guard provenance is retained. No human labels or released models are modified. The three supplied screenshots were inspected as visual background examples; their crop lacks scan IDs, so no scan identity or background training annotation was inferred.

Visits are not registered; no longitudinal lesion change is claimed. Day labels are nominal because actual laser intervals are unavailable. Next review: inspect baseline candidates and manual-location misses, reject artifacts, inspect reference regions on broad halos, and review uncertain/clipped margins. Only then consider other animals; all current upstream model training overlaps must remain disclosed.
'''
    destination(HERE/'START_HERE.md').write_text(text, encoding='utf-8')
    write(HERE/'status.json', dict(completed=len(rows), expected=len(visits), all_complete=len(rows)==len(visits), scans=[r['scan_id'] for r in rows]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scan')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    for visit in selected():
        if args.scan and args.scan != visit['scan_id']:
            continue
        if args.resume and (HERE/'scans'/visit['scan_id']/'summary.json').exists():
            continue
        process(visit)
    report()

if __name__ == '__main__':
    main()
