"""Frozen vessel/ONH context, never CNV truth or a geometry gate."""
from common import *
import importlib.util
spec=importlib.util.spec_from_file_location('v9_export_loader',EXPORT/'load_masks.py')
loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
CHANNELS=['vessel_mask','onh_mask','vessel_available','onh_available','vessel_reviewed','onh_reviewed','vessel_uncertain','onh_uncertain','vessel_brush_touched','onh_brush_touched','saved_manual_source']
def build_context(z,r):
 shape=(512,512);zero=np.zeros(shape,bool)
 if z is None:
  return np.zeros((len(CHANNELS),*shape),np.float32),dict(source='missing',vessel_available=False,onh_available=False,vessel_reviewed=False,onh_reviewed=False)
 if r['excluded_from_analysis']:raise ValueError('Context export excludes acquisition from analysis')
 vessel=z['vessel_mask'];onh=z['onh_mask'];vu=z.get('vessel_region_excluded',zero);ou=z.get('onh_region_excluded',zero)
 vr=bool(r['vessel_reviewed']);orr=bool(r['onh_reviewed'])
 # A reviewed empty ONH can establish absence; empty automatic/draft cannot.
 va=np.ones(shape,bool)&~vu
 oa=np.full(shape,orr or bool(onh.any()),bool)&~ou
 arr=[vessel&va,onh&oa,va,oa,np.full(shape,vr)&va,np.full(shape,orr)&oa,vu,ou,z.get('vasculature_brush_touched',zero),z.get('onh_brush_touched',zero),np.full(shape,r['selection']=='saved_manual')]
 return np.stack(arr).astype('float32'),dict(source=r['selection'],vessel_available=True,onh_available=bool(oa.any()),vessel_reviewed=vr,onh_reviewed=orr,onh_visibility=r['onh_visibility'],notes=r['notes'],excluded_from_analysis=False,mask_sha256=r['masks_sha256'],source_sha256=r['source_sha256'],revision=r['revision'],vessel_uncertain_pixels=int(vu.sum()),onh_uncertain_pixels=int(ou.sum()),vessel_brush_pixels=int(arr[8].sum()),onh_brush_pixels=int(arr[9].sum()),claim='provenance-qualified context; drafts and untouched automatic pixels are not exhaustive truth')
def load_context(a):
 try:z,r=loader.load_masks(a['scan_id'],a['source'])
 except KeyError:return build_context(None,None)
 if str(z['scan_id'])!=a['scan_id'] or str(z['source_sha256'])!=r['source_sha256']:raise ValueError('Context identity/hash mismatch')
 return build_context(z,r)
