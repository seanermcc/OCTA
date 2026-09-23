"""Adapters only. No calls to annotation writers, including synthetic tests."""
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from .common import read, npz, fingerprint, digest

def decode(runs, shape):
    mask = np.zeros(shape, bool)
    for y,a,b in runs:
        if not 0<=y<shape[0] or not 0<=a<b<=shape[1]:
            raise ValueError('Region outside native grid')
        mask[y,a:b] = True
    return mask

def resolve_regions(base, regions):
    """Classified regions supersede inherited components, including negative labels."""
    remaining = base.copy(); result = []; denied = np.zeros_like(base)
    # A classified imported component can have a changed outline. Remove the whole
    # overlapping inherited component, not just the new brush pixels.
    components,n = label(base)
    for r,mask in regions:
        if r['category'] not in ('Full Lesion','Normal','Other','Unclassified'):
            raise ValueError('Unknown classification')
        touched = np.unique(components[mask]); touched = touched[touched>0]
        remaining[np.isin(components,touched)] = False
        remaining[mask] = False
        if r['category'] in ('Normal','Other'):
            denied |= mask | np.isin(components,touched)
        elif r['category']=='Full Lesion' or (r['category']=='Unclassified' and touched.size):
            result.append((r['id'], mask, 'human_classified' if r['category']=='Full Lesion' else 'inherited_unclassified'))
    result = [(i,m & ~denied,s) for i,m,s in result if (m & ~denied).any()]
    parts,n = label(remaining & ~denied)
    for k in range(1,n+1):
        mask = parts==k
        result.append((digest(mask.nonzero()[0].tolist()+mask.nonzero()[1].tolist())[:12],mask,'manual_outline'))
    return result,denied

def load(c,r):
    from eight_surface.cnv_labels import load_label
    sid = r['scan_id']; shape = tuple(r['native_shape'][:2])
    blank = np.zeros(shape,bool); base=blank.copy(); onh=blank.copy(); edge=blank.copy()
    vessel=blank.copy(); refs=[]; spacing=np.asarray(c['field_um_yx'])/shape
    p=Path(c['enface_labels'])/f'{sid}_cnv.npz'; reviewed=False
    if p.exists():
        d=load_label(p)
        if d['scan_id']!=sid or d['native_shape']!=shape or Path(d['source_volume']).resolve()!=Path(r['source']).resolve():
            raise ValueError('En-face annotation source/grid mismatch: '+str(p))
        base=d['cnv_mask']; onh=d['onh_mask']; edge=d['onh_edge_mask']; vessel=d['vasculature_mask']
        spacing=np.array([d['bscan_um'],d['aline_um']]); reviewed=d['reviewed']
        refs.append(dict(**fingerprint(p),revision=d['revision'],kind='human_enface'))
    regions=[]
    for root in c['region_sources']:
        p=Path(root)/f'{sid}_regions.json'
        if not p.exists(): continue
        d=read(p)
        if d.get('format')!='1-cnv-region-review' or d['scan_id']!=sid or tuple(d['native_shape'])!=shape or Path(d['source_volume']).resolve()!=Path(r['source']).resolve():
            raise ValueError('Region annotation source/grid mismatch: '+str(p))
        regions=[(item,decode(item['runs'],shape)) for item in d['regions']]
        refs.append(dict(**fingerprint(p),revision=d['revision'],kind='human_classification'))
        break  # explicit priority, never copied-file modification times
    lesions,denied=resolve_regions(base,regions)
    if c['annotation_source']!='manual':
        p=Path(c['auto_proposals'])/f'{sid}.npz'; lesions=[]
        if p.exists():
            d=npz(p)
            if str(d['scan_id'].item())!=sid or tuple(d['native_shape'])!=shape or Path(str(d['source_volume'].item())).resolve()!=Path(r['source']).resolve():
                raise ValueError('Automatic proposal source/grid mismatch')
            key='core' if c['annotation_source']=='automatic_core' else 'footprint'
            mask=np.asarray(d[key],bool)
            if mask.shape!=shape: raise ValueError('Automatic mask grid mismatch')
            parts,n=label(mask & ~denied)
            lesions=[(f'candidate_{k:03d}',parts==k,c['annotation_source']) for k in range(1,n+1)]
            refs.append(dict(**fingerprint(p),kind=c['annotation_source'],revision=0))
    union=blank.copy()
    for _,m,_ in lesions: union|=m
    return dict(lesions=lesions,onh=onh,onh_edge=edge,vessel=vessel,union=union,
                denied=denied,spacing=spacing,refs=refs,reviewed=reviewed)
