"""Baseline matcher unchanged; forest localization deliberately separates ONH status."""
import numpy as np
from control_map_v1.geometry import (features, register, fit_onh, branches, convergence,
                                     apply, xy_grid, sample_native)

def onh_fit(arrays, info, cfg):
    """An uncertain-region boundary is not a visible anatomical boundary."""
    if not info['onh_available']:return dict(resolved=False,reason='ONH unavailable')
    from scipy import ndimage as ndi
    mask=arrays['selected_onh_mask'];empty=np.zeros_like(mask)
    edge=arrays.get('selected_onh_edge_mask',empty).copy()
    if not edge.any():edge=mask & ~ndi.binary_erosion(mask)
    uncertain=arrays.get('selected_onh_region_excluded',empty)
    edge &= ~uncertain
    if edge.any():result=fit_onh(empty,edge,arrays['spacing'],cfg)
    else:result=dict(resolved=False,reason='No assessable visible boundary')
    result['evidence_status']='reviewed_assessable' if info['onh_assessable'] else 'unreviewed_or_unassessable_proposal'
    return result

def pixel_to_physical(spacing):
    return np.diag([spacing[1], spacing[0], 1.])

def footprint(info):
    h,w=info['shape']; sy,sx=info['spacing']
    return np.array([[-.5*sx,-.5*sy],[(w-.5)*sx,-.5*sy],[(w-.5)*sx,(h-.5)*sy],[-.5*sx,(h-.5)*sy]])

def build_components(infos, pairs, cfg):
    ids=sorted(infos); groups={s:{s} for s in ids}; adjacency={s:[] for s in ids}
    edges=sorted([m for m in pairs if m['status']=='automatic_proposal'],
                 key=lambda m:(m['residual_um'],m['scan_a'],m['scan_b']))
    for m in edges:
        a,b=m['scan_a'],m['scan_b']; m['tree_edge']=False
        if groups[a] is groups[b]: continue
        if (infos[a]['animal'],infos[a]['eye']) != (infos[b]['animal'],infos[b]['eye']):
            raise ValueError('Cross-animal/eye edge forbidden')
        merged=groups[a]|groups[b]
        for s in merged: groups[s]=merged
        mat=np.asarray(m['matrix']);m['tree_edge']=True
        adjacency[a].append((b,mat));adjacency[b].append((a,np.linalg.inv(mat)))
    components=[]; scanmap={};seen=set()
    for root in ids:
        if root in seen: continue
        members=sorted(groups[root]);seen.update(members)
        transforms={root:np.eye(3)};todo=[root]
        while todo:
            a=todo.pop()
            for b,ab in adjacency[a]:
                if b not in transforms:
                    transforms[b]=transforms[a]@np.linalg.inv(ab);todo.append(b)
        inconsistent=False; cycles=[]
        for m in edges:
            a,b=m['scan_a'],m['scan_b']
            if a not in transforms or b not in transforms:continue
            # Actual field corners, also valid for unequal native pixel spacings.
            corners=footprint(infos[a])
            delta=apply(corners,transforms[a])-apply(apply(corners,np.asarray(m['matrix'])),transforms[b])
            m['cycle_error_um']=float(np.linalg.norm(delta,axis=1).max())
            if not m['tree_edge']: cycles.append(dict(pair_id=m['pair_id'],error_um=m['cycle_error_um']))
            inconsistent |= m['cycle_error_um']>cfg['cycle_limit_um']
        # Confirmed fits and convergence proposals NEVER connect or invalidate a component.
        onh=[]
        for s in members:
            for key in ('visible_onh','convergence'):
                loc=infos[s].get(key,{})
                if loc.get('resolved'):
                    onh.append(dict(scan_id=s,method=key,confirmed=key=='visible_onh' and infos[s].get('onh_assessable',False),
                        center_um=apply(np.asarray(loc['center_um']),transforms[s]).tolist(),
                        uncertainty_um=loc.get('uncertainty_um'),diameter_um=loc.get('diameter_um')))
        discrepancies=[]
        for i,a in enumerate(onh):
            for b in onh[i+1:]:
                d=float(np.linalg.norm(np.array(a['center_um'])-b['center_um']))
                tol=max(cfg['onh_max_uncertainty_um'],(a['uncertainty_um'] or 0)+(b['uncertainty_um'] or 0))
                if d>tol: discrepancies.append(dict(a=a['scan_id']+':'+a['method'],b=b['scan_id']+':'+b['method'],distance_um=d,tolerance_um=tol))
        excluded=any(infos[s].get('excluded_from_analysis') or infos[s].get('status')=='blocked' for s in members)
        state='withheld_loop_inconsistent' if inconsistent else 'excluded_or_blocked' if excluded else 'singleton' if len(members)==1 else 'automatic_proposal'
        c=dict(component_id=root,reference_scan=root,animal=infos[root]['animal'],eye=infos[root]['eye'],members=members,
               status=state,registration_consistent=not inconsistent,non_tree_cycles=cycles,
               onh_proposals=onh,onh_disagreements=discrepancies,
               onh_status='disagreement_for_review' if discrepancies else 'reviewed_fit_available' if any(o['confirmed'] for o in onh) else 'proposal_only' if onh else 'unresolved',
               component_to_fundus=None,anatomical_directions='unknown')
        components.append(c)
        for s in members:
            mat=transforms[s];info=infos[s]
            scanmap[s]=dict(component_id=root,reference_scan=root,matrix_to_component=mat.tolist(),
                matrix_from_component=np.linalg.inv(mat).tolist(),pixel_to_native_physical=pixel_to_physical(info.get('spacing',[1,1])).tolist(),
                pixel_to_component=(mat@pixel_to_physical(info.get('spacing',[1,1]))).tolist(),
                footprint_um=apply(footprint(info),mat).tolist() if 'shape' in info else None,
                component_status=state,component_to_fundus=None)
    return components,scanmap
