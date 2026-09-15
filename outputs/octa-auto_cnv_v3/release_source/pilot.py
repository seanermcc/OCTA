"""Run the TS267 pilot from frozen native longitudinal v2 arrays."""
import argparse
import csv
import gc
from types import SimpleNamespace
from common import *
from algorithm import detect, geometry, quantify, VARIANTS, grow, RULES
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
    audit['assisted_review_regions']=[]
    for root in (ROOT/'outputs/cnv_review_v1/regions', LONG/'v2/reviewer/regions',HERE/'review/regions'):
        path = root/f'{sid}_regions.json'
        if not path.exists():
            continue
        data = read(path)
        if data['scan_id'] != sid or tuple(data['native_shape']) != shape or Path(data['source_volume']).resolve() != Path(source).resolve():
            raise ValueError('Region reference coordinates/source mismatch')
        for r in data['regions']:
            if root==HERE/'review/regions':
                if r.get('decision')!='approved':continue
                if r.get('seed_ids'):
                    audit['assisted_review_regions'].append(dict(id=r['id'],category=r['category'],source=str(path)))
                    continue  # Automatic-seeded approvals are not independent manual reference.
            if r['category'] == 'Full Lesion':
                mask |= decode_mask(r.get('reviewed_runs',r['runs']), shape)
                audit['reviewed_cnv'] = True
            elif r['category'] == 'Normal':
                normal |= decode_mask(r.get('reviewed_runs',r['runs']), shape)
        audit['sources'].append(dict(path=str(path), sha256=sha(path)))
    if audit['reviewed_absence']:
        normal[:] = True
    mask &= ~normal
    return mask, normal, audit

def components(mask):
    labels, count = ndi.label(mask, np.ones((3, 3)))
    return [labels == i for i in range(1, count+1)]

def evaluate(maps, manual, normal, review):
    candidates = components(maps['core'])
    references = components(manual) if review['reviewed_cnv'] else []
    proposed = maps['core']
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
    axes[0, 2].set_title('Reference estimate (includes extrapolation)' if np.isfinite(arrays['background_um']).any() else 'Reference unavailable: insufficient background')
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
    reason[~arrays['background_supported']] = (.7, .7, .7, .35)
    reason[~np.isfinite(arrays['automatic_thickness_um'])] = (1, .2, .4, .6)
    reason[arrays['shadow'] | arrays['vessel']] = (.2, .7, 1, .7)
    reason[arrays['low_signal']] = (.9, .7, .1, .6)
    axes[1, 2].imshow(reason)
    axes[1, 2].set_title('Pink: missing · blue: vessel/shadow · gray: no reference')
    for ax in axes.ravel()[1:]:
        line(ax, arrays['core'], '#ff6347', 'Candidate core, independent of reference')
    for ax in axes.ravel(): ax.title.set_fontsize(10)
    fig.suptitle(sid+'\nocta-auto_cnv_v3 · experimental; no visit registration', fontsize=13, y=.98)
    fig.savefig(destination(output), dpi=125)
    plt.close(fig)



def process(visit):
    sid = visit['scan_id']; print('Loading',sid,flush=True)
    snapshot=ROOT/'outputs/octa-auto_cnv_v2/scans'/sid/'maps.npz'
    prior=read(snapshot.parent/'provenance.json');audit=prior['audit']
    for path,digest in audit['input_hashes'].items():
        if sha(path)!=digest:raise RuntimeError('Upstream inputs changed; regenerate source snapshots before v3: '+path)
    with np.load(snapshot,allow_pickle=False) as d:
        keys=[k for k in d.files if k.startswith(('automatic_','geometry_','viewer_','frozen_')) or k in ('enface','vessel','shadow','low_signal','unavailable_cause_bits','invalid_geometry','surface_names')]
        arrays={k:d[k] for k in keys}
    audit={**audit,'v2_input_snapshot':str(snapshot),'v2_input_snapshot_sha256':sha(snapshot),
           'assisted_snapshot_note':'Frozen upstream assisted thickness; use the GUI recompute action for new corrections.'}
    evidence,records=detect(arrays); arrays.update(evidence)
    results={}; diagnostics={}; sensitivity=[]
    for name,p in VARIANTS.items():
        m,d=quantify(arrays,evidence,p); results[name]=m; diagnostics[name]=d
        sensitivity.append(dict(variant=name, candidate_count=len(records), supported_fraction=d['supported_fraction'],
            footprint_mm2=float(m['footprint'].sum()*PIXEL_MM2) if d['sufficient'] else None,
            **{f'contour{t}_mm2':float(m[f'contour{t}'].sum()*PIXEL_MM2) if d['sufficient'] else None for t in (10,20,30)}))
        for key,value in m.items(): arrays[name+'__'+key]=value
    maps=results['default']; arrays.update(maps)
    stack=np.stack([m['deficit_percent'] for m in results.values()]); valid=np.isfinite(stack)
    count=valid.sum(0); high=np.max(np.where(valid,stack,-np.inf),0); low=np.min(np.where(valid,stack,np.inf),0)
    arrays['deficit_sensitivity_span']=np.where(count>=2,high-low,np.nan).astype('float32')
    arrays['sensitivity_supported_count']=count.astype('uint8')
    assisted,ad=quantify(arrays,evidence,thickness=arrays['viewer_thickness_um'])
    for key,value in assisted.items(): arrays['assisted__'+key]=value
    manual,normal,review=manual_reference(sid,visit['source'],arrays['core'].shape)
    arrays.update(manual_cnv=manual,reviewed_normal=normal)
    metrics=evaluate(maps,manual,normal,review)
    v1=read(ROOT/'outputs/octa-auto_cnv_v1/scans'/sid/'summary.json')
    for r in records:
        mask=arrays['candidate_labels']==r['id']
        r['core_mm2']=float(mask.sum()*PIXEL_MM2)
        r['missing_fraction']=float((~np.isfinite(arrays['automatic_thickness_um'][mask])).mean())
        r['unsupported_fraction']=float((~maps['background_supported'][mask]).mean())
    metadata=dict(format=VERSION,visit=visit,axis_order='B-scan,A-line',native_shape=list(manual.shape),
        full_retina_endpoints=['ILM','RPE (outer edge)'],axial_um_per_px=1.12,lateral_um_per_px=PIXEL_UM,
        automatic_proposal=True,human_reviewed=False,audit=audit,reference_review=review,diagnostics=diagnostics,
        assisted_diagnostics=ad,assisted_note='Current upstream human-assisted thickness; automatic candidate set retained. No human holes enter automatic detection.',
        metrics=metrics,candidates=records,sensitivity=sensitivity,v1_metrics=v1,
        v2_metrics=prior['metrics'],detector_rules=RULES,screened_regions=json.loads(str(evidence['screened_records_json'])),
        implementation_hashes={p.name:sha(p) for p in HERE.glob('*.py')},
        candidate_seed_sha256=__import__('hashlib').sha256(arrays['candidate_labels'].tobytes()).hexdigest())
    out=HERE/'scans'/sid
    save_npz(out/'maps.npz',**arrays,metadata_json=np.array(json.dumps(metadata)))
    write(out/'provenance.json',metadata)
    figure(sid,arrays,out/'overview.png')
    seed=HERE/'proposals'/f'{sid}.npz'
    if not seed.exists() or not np.array_equal(npz(seed)['candidate_labels'],arrays['candidate_labels']):
        save_npz(seed,core=maps['core'],proposal_mask=maps['core'],candidate_labels=arrays['candidate_labels'],
            scan_id=np.array(sid),source_volume=np.array(visit['source']),native_shape=np.array(manual.shape),human_reviewed=np.array(False))
    summary=dict(scan_id=sid,day=visit['day_label'],eye=visit['eye'],**metrics,
        v1_candidates=v1['candidate_count'],v1_location_hits=v1['location_hits_75um'],
        supported_fraction=diagnostics['default']['supported_fraction'],
        footprint_mm2=float(maps['footprint'].sum()*PIXEL_MM2) if diagnostics['default']['sufficient'] else None,
        uncertain_candidates=sum(r['priority'].startswith('uncertain') for r in records))
    summary.update(v2_candidates=prior['metrics']['candidate_count'],screened_regions=len(metadata['screened_regions']),
                   count_warning=bool(evidence['count_warning']),core_field_fraction=float(maps['core'].mean()))
    write(out/'summary.json',summary)
    print('Completed',sid,'candidates',len(records),'location hits',metrics['location_hits_75um'],flush=True)
    return summary


def report():
    rows=[read(HERE/'scans'/v['scan_id']/'summary.json') for v in selected() if (HERE/'scans'/v['scan_id']/'summary.json').exists()]
    if rows:
        with destination(HERE/'summary.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    write(HERE/'status.json',dict(completed=len(rows),selected=17,independent_validation=False,human_review_pending=True))
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--scan'); p.add_argument('--resume',action='store_true'); args=p.parse_args()
    for v in selected():
        if args.scan and args.scan!=v['scan_id']: continue
        if args.resume and (HERE/'scans'/v['scan_id']/'summary.json').exists(): continue
        process(v); report(); gc.collect()

