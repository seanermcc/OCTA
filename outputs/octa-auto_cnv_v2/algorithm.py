"""Lesion-first rules. Detector has no background or human-mask argument."""
import numpy as np
from scipy import ndimage as ndi
from reference import VARIANTS, Parameters, grow, keep, smooth_finite, structural_context, background
from common import PIXEL_UM


def geometry(rows, offset, depth):
    nonfinite = ~np.isfinite(rows)
    outside = np.isfinite(rows) & ((rows < offset) | (rows >= offset + depth))
    crossing = []; pairs = []; sizes = []
    for a in range(rows.shape[1]):
        for b in range(a+1, rows.shape[1]):
            delta = rows[:, a] - rows[:, b]
            bad = np.isfinite(delta) & (delta >= 0)
            crossing.append(bad); pairs.append((a, b))
            sizes.append(np.where(bad, delta, 0))
    return dict(geometry_nonfinite=nonfinite, geometry_out_of_crop=outside,
                geometry_crossing=np.stack(crossing, axis=1), geometry_pairs=np.array(pairs),
                geometry_crossing_size_px=np.stack(sizes, axis=1).astype('float32'),
                geometry_any=nonfinite.any(1) | outside.any(1) | np.any(crossing, axis=0))


def detect(a):
    context = structural_context(a['enface'], a['vessel'])
    # Seam evidence is a row-wide intensity jump, not a veto on lesion pixels.
    row_signal = np.median(a['enface'], axis=1)
    jumps = np.abs(np.diff(row_signal, prepend=row_signal[0]))
    scale = max(.1, 1.4826*np.median(np.abs(jumps-np.median(jumps))))
    seam = np.broadcast_to((jumps > np.median(jumps)+5*scale)[:, None], context.shape).copy()
    t = a['automatic_thickness_um']
    local = smooth_finite(t, 24) - smooth_finite(t, 3)
    flags = a['geometry_any'] | a['automatic_trace_loss']
    # Keep small isolated failures as an evidence layer, but require persistent
    # clusters for the candidate queue. No global reference is read here.
    signal = flags | ((context >= 2.5) & (local >= 12)) | (context >= 4)
    connected = ndi.binary_closing(signal, iterations=2) | signal
    labels, count = ndi.label(connected, np.ones((3, 3)))
    cores = np.zeros(signal.shape, np.int32); records = []
    for label in range(1, count+1):
        mask = labels == label
        yy, xx = np.nonzero(mask)
        observed = mask & signal
        rows = np.unique(yy)
        persistent = len(rows) >= 3 and observed.sum() >= 24
        if not persistent:
            continue
        k = len(records)+1; cores[mask] = k
        artifact = a['vessel'] | a['shadow'] | a['low_signal'] | seam
        af = float(artifact[mask].mean()); sf = float((context[mask] >= 1).mean())
        record = dict(id=k, row=float(yy.mean()), col=float(xx.mean()), pixels=int(mask.sum()),
                      bscan_span=[int(yy.min()), int(yy.max())], persistence_rows=len(rows),
                      geometry_pixels=int((mask & a['geometry_any']).sum()),
                      trace_loss_pixels=int((mask & a['automatic_trace_loss']).sum()),
                      structural_fraction=sf, artifact_fraction=af,
                      vessel_fraction=float(a['vessel'][mask].mean()), shadow_fraction=float(a['shadow'][mask].mean()),
                      low_signal_fraction=float(a['low_signal'][mask].mean()), seam_fraction=float(seam[mask].mean()),
                      fov_clipped=bool((yy==0).any() or (xx==0).any() or (yy==mask.shape[0]-1).any() or (xx==mask.shape[1]-1).any()),
                      priority='structurally supported' if sf >= .1 and af < .5 else 'uncertain / artifact challenge',
                      geometry_failures=[])
        names = list(a['surface_names'])
        for j, (u,v) in enumerate(a['geometry_pairs']):
            m = mask & a['geometry_crossing'][:, j]
            if m.any(): record['geometry_failures'].append(dict(type='crossing', boundaries=[str(names[u]),str(names[v])], pixels=int(m.sum()), maximum_violation_px=float(a['geometry_crossing_size_px'][:,j][m].max())))
        for key, kind in [('geometry_nonfinite','nonfinite'),('geometry_out_of_crop','out-of-crop')]:
            for j,n in enumerate(names):
                nbad = int((mask & a[key][:,j]).sum())
                if nbad: record['geometry_failures'].append(dict(type=kind, boundaries=[str(n)], pixels=nbad))
        records.append(record)
    return dict(core=cores>0, candidate_labels=cores, structural_context=context,
                seam=seam, isolated_evidence=signal & (cores==0), evidence_signal=signal,
                local_thickness_departure_um=local.astype('float32')), records


def quantify(a, candidates, p=Parameters(), thickness=None, extra_excluded=None):
    t = a['automatic_thickness_um'] if thickness is None else thickness
    exclusion = grow(candidates.get('background_core', candidates['core']), p.halo_exclusion_um)
    if extra_excluded is not None: exclusion |= extra_excluded
    maps, diag = background(t, a['vessel'], a['shadow'], a['low_signal'], p, exclusion)
    # Local sampling support replaces the tile-centre convex hull. Require
    # samples in at least three quadrants of a 350-um neighbourhood, plus a
    # minimum local sample fraction. Extrapolations remain explicit estimates.
    eligible = maps['background_regions']; radius = max(1, int(p.support_distance_um/PIXEL_UM))
    quadrant_count = np.zeros(t.shape, np.uint8)
    for sy,sx in [(0,0),(0,1),(1,0),(1,1)]:
        # Separable box sums, constant padding never manufactures edge support.
        q = ndi.uniform_filter(eligible.astype(float), size=radius, mode='constant')
        dy = radius//2 * (1 if sy else -1); dx = radius//2 * (1 if sx else -1)
        q = ndi.shift(q, (dy,dx), order=0, mode='constant', cval=0)
        quadrant_count += q >= .03
    coverage = ndi.uniform_filter(eligible.astype(float), size=2*radius+1, mode='constant')
    supported = (quadrant_count >= 3) & (coverage >= .08) & (maps['background_um']>0) & ~maps['border'] & diag['sufficient']
    maps['background_supported'] = supported
    maps['background_local_coverage'] = coverage.astype('float32')
    maps['background_quadrants'] = quadrant_count
    maps['candidate_halo_excluded'] = exclusion
    valid = supported & np.isfinite(t) & ~a['vessel'] & ~a['shadow'] & ~a['low_signal']
    d = np.full(t.shape, np.nan, 'float32')
    d[valid] = 100*(maps['background_um'][valid]-t[valid])/maps['background_um'][valid]
    maps['deficit_percent'] = d
    thin = d >= 10
    links = ndi.binary_closing(thin | candidates['core'], iterations=3) | thin | candidates['core']
    lab,_ = ndi.label(links, np.ones((3,3)))
    ids = np.unique(lab[grow(candidates['core'],20)]); ids=ids[ids>0]
    maps['footprint'] = thin & np.isin(lab, ids)
    maps['core'] = candidates['core'].copy()
    maps['uncertain_margin'] = grow(candidates['core'],15) & (~supported | a['vessel'] | a['shadow'] | a['low_signal'])
    for threshold in (10,20,30): maps[f'contour{threshold}'] = d>=threshold
    diag.update(supported_fraction=float(supported.mean()), support_rule='three local sampling quadrants and >=8% local coverage within 350 um; no tile-centre polygon', candidate_independent=True)
    return maps, diag

