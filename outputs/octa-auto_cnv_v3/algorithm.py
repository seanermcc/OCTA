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


def broad_evidence(a):
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




# User-specified anatomical prior: compact rounded foci between vessel trunks.
# These are development thresholds, not independent diagnostic validation.
RULES = dict(min_area_px=250, max_diameter_px=120, max_aspect=2.0,
             min_solidity=.70, min_circularity=.48, max_trunk_fraction=.12,
             primary_limit=4, usual_count=2, field_margin_px=28)


def vessel_trunks(vessel):
    from skimage.measure import regionprops
    labels,_=ndi.label(vessel,np.ones((3,3)))
    trunks=np.zeros_like(vessel)
    for r in regionprops(labels):
        length=max(r.bbox[2]-r.bbox[0],r.bbox[3]-r.bbox[1])
        aspect=r.axis_major_length/max(r.axis_minor_length,1)
        if length>=160 or (length>=50 and aspect>=3):trunks[labels==r.label]=True
    return trunks


def detect(a):
    from skimage.measure import regionprops,perimeter_crofton
    broad,_=broad_evidence(a)
    trunks=vessel_trunks(a['vessel'])
    corridor=grow(trunks,10)
    context=broad['structural_context']
    flags=a['geometry_any'] | a['automatic_trace_loss']
    signal=(flags & (context>=.65)) | (context>=3) | ((context>=1.5)&(broad['local_thickness_departure_um']>=12))
    signal &= ~corridor & ~a['low_signal']
    density=ndi.gaussian_filter(signal.astype(float),3)
    components=ndi.binary_fill_holes(density>=.30)
    labels,_=ndi.label(components,np.ones((3,3)))
    accepted=[]; screened=[]; screens=np.zeros(signal.shape,np.int32)
    for prop in regionprops(labels):
        mask=labels==prop.label;y,x=np.nonzero(mask)
        if prop.area<24:continue
        aspect=float(prop.axis_major_length/max(prop.axis_minor_length,1))
        circularity=float(min(1,4*np.pi*prop.area/max(perimeter_crofton(mask,4)**2,1)))
        fraction=float(trunks[mask].mean())
        cy,cx=prop.centroid
        edge=bool(y.min()<RULES['field_margin_px'] or x.min()<RULES['field_margin_px'] or y.max()>=mask.shape[0]-RULES['field_margin_px'] or x.max()>=mask.shape[1]-RULES['field_margin_px'])
        reasons=[]
        if prop.area<RULES['min_area_px']:reasons.append('too small')
        if prop.equivalent_diameter_area>RULES['max_diameter_px']:reasons.append('broad / diffuse')
        if aspect>RULES['max_aspect']:reasons.append('elongated')
        if prop.solidity<RULES['min_solidity']:reasons.append('irregular / fragmented')
        if circularity<RULES['min_circularity']:reasons.append('not round enough')
        if fraction>RULES['max_trunk_fraction'] or corridor[int(cy),int(cx)]:reasons.append('vessel-following / on vessel')
        if edge:reasons.append('field edge: uncertain truncated shape')
        if len(np.unique(y))<5:reasons.append('insufficient persistence')
        sf=float((context[mask]>=1).mean());gf=float(flags[mask].mean())
        if sf<.5:reasons.append('weak structural corroboration')

        score=float(circularity*prop.solidity*(.5+gf)*(.5+min(float(np.mean(context[mask]))/3,1)))
        rec=dict(id=0,row=float(cy),col=float(cx),pixels=int(prop.area),bscan_span=[int(y.min()),int(y.max())],
            persistence_rows=len(np.unique(y)),geometry_pixels=int((a['geometry_any']&mask).sum()),
            trace_loss_pixels=int((a['automatic_trace_loss']&mask).sum()),structural_fraction=sf,
            artifact_fraction=float((a['low_signal']|broad['seam']|trunks)[mask].mean()),
            vessel_fraction=float(a['vessel'][mask].mean()),trunk_fraction=fraction,
            shadow_fraction=float(a['shadow'][mask].mean()),low_signal_fraction=float(a['low_signal'][mask].mean()),
            seam_fraction=float(broad['seam'][mask].mean()),fov_clipped=edge,
            circularity=circularity,aspect_ratio=aspect,solidity=float(prop.solidity),diameter_um=float(prop.equivalent_diameter_area*PIXEL_UM),
            score=score,priority='rounded intervascular focus; needs review',geometry_failures=[],screen_reasons=reasons)
        for j,(u,v) in enumerate(a['geometry_pairs']):
            m=mask & a['geometry_crossing'][:,j]
            if m.any():rec['geometry_failures'].append(dict(type='crossing',boundaries=[str(a['surface_names'][u]),str(a['surface_names'][v])],pixels=int(m.sum()),maximum_violation_px=float(a['geometry_crossing_size_px'][:,j][m].max())))
        for key,kind in [('geometry_nonfinite','nonfinite'),('geometry_out_of_crop','out-of-crop')]:
            for j,n in enumerate(a['surface_names']):
                nbad=int((mask&a[key][:,j]).sum())
                if nbad:rec['geometry_failures'].append(dict(type=kind,boundaries=[str(n)],pixels=nbad))
        if reasons:screened.append((mask,rec))
        else:accepted.append((mask,rec))
    # Nearby fragments of one rounded disturbance must not consume several slots.
    # Bridge only <=50 um gaps when the combined convex envelope stays rounded,
    # compact and between trunks. The inferred envelope is a proposal, not tissue.
    from skimage.morphology import convex_hull_image
    changed=True
    while changed:
        changed=False
        for i in range(len(accepted)):
            if changed:break
            for j in range(i+1,len(accepted)):
                left,lr=accepted[i];right,rr=accepted[j]
                if not np.any(grow(left,50)&right):continue
                merged=convex_hull_image(left|right)
                props=regionprops(merged.astype('uint8'))[0]
                circ=min(1,4*np.pi*merged.sum()/max(perimeter_crofton(merged,4)**2,1))
                if props.axis_major_length/max(props.axis_minor_length,1)>2 or circ<.55 or trunks[merged].mean()>.08 or props.equivalent_diameter_area>RULES['max_diameter_px']:continue
                rec=dict(lr);yy,xx=np.nonzero(merged)
                rec.update(row=float(yy.mean()),col=float(xx.mean()),pixels=int(merged.sum()),
                    bscan_span=[int(yy.min()),int(yy.max())],persistence_rows=len(np.unique(yy)),
                    circularity=float(circ),solidity=1.,aspect_ratio=float(props.axis_major_length/max(props.axis_minor_length,1)),
                    geometry_pixels=int((a['geometry_any']&merged).sum()),trace_loss_pixels=int((a['automatic_trace_loss']&merged).sum()),
                    diameter_um=float(props.equivalent_diameter_area*PIXEL_UM),score=max(lr['score'],rr['score']),
                    geometry_failures=lr['geometry_failures']+rr['geometry_failures'],
                    joined_fragments=int(lr.get('joined_fragments',1)+rr.get('joined_fragments',1)))
                accepted[i]=(merged,rec);accepted.pop(j);changed=True;break
    accepted.sort(key=lambda p:(-p[1]['score'],p[1]['row'],p[1]['col']))
    extras=accepted[RULES['primary_limit']:];accepted=accepted[:RULES['primary_limit']]
    for mask,r in extras:r['screen_reasons']=['count sanity check: additional rounded focus'];screened.append((mask,r))
    core=np.zeros(signal.shape,np.int32);records=[];screen_records=[]
    for i,(mask,r) in enumerate(accepted,1):
        core[mask]=i;r['id']=i
        for key,source in [('vessel_fraction',a['vessel']),('trunk_fraction',trunks),('shadow_fraction',a['shadow']),('low_signal_fraction',a['low_signal']),('seam_fraction',broad['seam'])]:r[key]=float(source[mask].mean())
        r['structural_fraction']=float((context[mask]>=1).mean())
        r['artifact_fraction']=float((a['low_signal']|broad['seam']|trunks)[mask].mean())
        r['geometry_failures']=[]
        for j,(u,v) in enumerate(a['geometry_pairs']):
            bad=mask&a['geometry_crossing'][:,j]
            if bad.any():r['geometry_failures'].append(dict(type='crossing',boundaries=[str(a['surface_names'][u]),str(a['surface_names'][v])],pixels=int(bad.sum()),maximum_violation_px=float(a['geometry_crossing_size_px'][:,j][bad].max())))
        for key,kind in [('geometry_nonfinite','nonfinite'),('geometry_out_of_crop','out-of-crop')]:
            for j,n in enumerate(a['surface_names']):
                nbad=int((mask&a[key][:,j]).sum())
                if nbad:r['geometry_failures'].append(dict(type=kind,boundaries=[str(n)],pixels=nbad))
        records.append(r)
    for i,(mask,r) in enumerate(screened,1):screens[mask]=i;r['id']=i;screen_records.append(r)
    import json
    broad.update(core=core>0,candidate_labels=core,vessel_trunks=trunks,screened_labels=screens,
        screened_records_json=np.array(json.dumps(screen_records)),round_focus_density=density.astype('float32'),
        isolated_evidence=broad['evidence_signal']&(core==0),count_warning=np.array(len(extras)>0))
    return broad,records



