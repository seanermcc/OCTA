"""Saved-data verification, manual inventory and v3 handoff."""
from common import *
from algorithm import detect,quantify,VARIANTS,RULES,grow
from eight_surface.cnv_labels import load_label
from scipy import ndimage as ndi
import csv

def table(name,rows):
 if not rows:return
 with destination(HERE/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 checks=[];rows=[];candidate_rows=[];sens=[];locations=[];screens=[]
 for v in selected():
  sid=v['scan_id'];p=HERE/'scans'/sid
  a=npz(p/'maps.npz');meta=read(p/'provenance.json');s=read(p/'summary.json')
  print('Verify',sid,flush=True)
  c,rec=detect(a);assert np.array_equal(c['candidate_labels'],a['candidate_labels']);assert len(rec)<=4
  default,diag=quantify(a,c)
  assert np.array_equal(default['deficit_percent'],a['deficit_percent'],equal_nan=True)
  assert np.isnan(a['automatic_thickness_um'][a['shadow']]).all()
  for name in VARIANTS:
   d=a[name+'__deficit_percent'];support=a[name+'__background_supported'];valid=np.isfinite(d)
   assert np.array_equal(a[name+'__core'],a['core'])
   assert np.isnan(d[~support|~np.isfinite(a['automatic_thickness_um'])|a['shadow']|a['vessel']|a['low_signal']]).all()
   b=a[name+'__background_um'];assert np.allclose(d[valid],100*(b[valid]-a['automatic_thickness_um'][valid])/b[valid],atol=1e-4)
   sens.append(dict(scan_id=sid,variant=name,candidates=len(rec),support_fraction=float(support.mean()),
    measurable_core_fraction=float(valid[a['core']].mean()) if a['core'].any() else None,
    observed_footprint_mm2=float(a[name+'__footprint'].sum()*PIXEL_MM2) if valid.any() else None,
    **{f'contour{t}_observed_mm2':float((d>=t).sum()*PIXEL_MM2) if valid.any() else None for t in (10,20,30)}))
  for r in rec:
   candidate_rows.append(dict(scan_id=sid,**{k:r[k] for k in ('id','row','col','pixels','circularity','aspect_ratio','solidity','trunk_fraction','score','priority')},joined_fragments=r.get('joined_fragments',1)))
  for r in meta['screened_regions']:
   screens.append(dict(scan_id=sid,row=r['row'],col=r['col'],pixels=r['pixels'],reasons='; '.join(r['screen_reasons'])))
  labs,n=ndi.label(a['manual_cnv'],np.ones((3,3)))
  dist=ndi.distance_transform_edt(~a['core'])*PIXEL_UM if a['core'].any() else np.full(a['core'].shape,np.inf)
  for i in range(1,n+1):
   m=labs==i;y,x=np.nonzero(m);distance=float(dist[m].min())
   locations.append(dict(scan_id=sid,manual_component=i,row=float(y.mean()),col=float(x.mean()),
     minimum_core_distance_um=distance if np.isfinite(distance) else None,location_hit_75um=distance<=75,
     exact_border_ground_truth=False))
  s['background_sufficient']=diag['sufficient'];s['core_tolerance_field_fraction']=float(grow(a['core'],75).mean());rows.append(s)
  native=next(x for x in read(LONG/'verification'/f'{sid}.json') if x['version']=='v2')
  assert native['measurements']['sha256']==sha(volume_path(sid)/'measurements.npz')
  checks.append(dict(scan_id=sid,core_reproduced=True,default_deficit_reproduced=True,background_independent=True,native_source_rows_verified=native['native_rows_verified'],units_and_missingness=True))
 table('summary.csv',rows);table('candidates.csv',candidate_rows);table('screened_evidence.csv',screens);table('sensitivity.csv',sens);table('manual_location_comparison.csv',locations)
 write(HERE/'verification/numerical_checks.json',checks)
 inventory=[];chosen={v['scan_id'] for v in selected()}
 for path in sorted((ROOT/'outputs/cnv_labels').glob('*TS267*')):
  r=load_label(path);lab,n=ndi.label(r['cnv_mask'],np.ones((3,3)))
  inventory.append(dict(scan_id=r['scan_id'],path=str(path),sha256=sha(path),reviewed=bool(r['reviewed_targets'][0]),
     cnv_pixels=int(r['cnv_mask'].sum()),connected_components=n,selected_in_pilot=r['scan_id'] in chosen,
     source_segmentation=str(r['source_segmentation']),source_volume=str(r['source_volume'])))
 table('manual_inventory.csv',inventory)
 manual='# Your saved manual annotations\n\nOriginal files remain in `G:/OCT_TreeShrew/octa/outputs/cnv_labels/`. Five TS267 files contain footprints; the sixth is an explicit reviewed absence. V3 reads matching acquisitions as cyan comparison outlines and never overwrites these files.\n\n| Acquisition | Manual work | In current pilot? | File |\n|---|---|---|---|\n'
 for r in inventory:manual+=f'| {r["scan_id"]} | '+(f'{r["connected_components"]} connected components (not necessarily separate lesions)' if r['cnv_pixels'] else 'Reviewed: no CNV')+f' | {"Yes" if r["selected_in_pilot"] else "No; different repeat"} | [{Path(r["path"]).name}]({Path(r["path"]).as_posix()}) |\n'
 manual+='\nD7 and D28 appear in the v3 viewer. Use **Saved manual outlines (cyan)** and the **Saved manual** dropdown to jump to each footprint. **OPEN_SAVED_MANUAL_D7.cmd** opens D7 directly. Different repeats are not transferred to the selected scan without registration. `manual_inventory.csv` records their source segmentation paths and hashes.\n\nFor new reference drawings, use **OPEN_MANUAL_REVIEW.cmd**: automatic footprints start hidden and no automatic region is selected. Draw region, assign Full Lesion / Normal / Other, then complete review and Save all. Keep Normal restricted to tissue actually inspected. Suggested next examples: D14 OD; the missed lower D7 footprint; and a D0 vessel or edge artifact confirmed not to be CNV. Three to five acquisitions are a useful first review set, not a statistically powered validation cohort.\n\nNew drawings save separately in `outputs/octa-auto_cnv_v3/review/regions/`. Original hand-drawn regions (no automatic seed) enter the reference comparison when the pilot is rerun. Corrections/approvals of automatic seeds remain assisted review evidence and are not counted as independent manual-location ground truth. All examples used to revise these rules are development examples; later validation needs different acquisitions/animals with upstream training exposure disclosed.\n'
 destination(HERE/'MANUAL_ANNOTATIONS.md').write_text(manual,encoding='utf-8')
 sid='TS267_OD_2025-03-05_D14_s01_104048';a=npz(HERE/'scans'/sid/'maps.npz');assert a['geometry_any'][230,85] and a['core'][230,85]
 write(HERE/'verification/D14_regression.json',dict(scan_id=sid,bscan=230,aline=85,candidate=int(a['candidate_labels'][230,85]),geometry_visible=True,thickness_unavailable=not bool(np.isfinite(a['automatic_thickness_um'][230,85])),human_label_created=False))
 count=sum(r['candidate_count'] for r in rows);hits=sum(r['location_hit_75um'] for r in locations);unsupported=sum(not r['background_sufficient'] for r in rows)
 text=f'''# octa-auto_cnv_v3

Implemented on all 17 selected TS267 acquisitions. **{count} proposals**, down from **220** in v2; each acquisition has **0–4**, with no forced minimum. Location agreement against the existing D7/D28 manual components is **{hits}/{len(locations)} within 75 um** using candidate cores alone. One lower D7 manual location remains missed; review it rather than treating the new rules as validated. D14 A-line 85 / B-scan 230 remains a proposed focus despite unavailable thickness. Default background is sufficient on **{17-unsupported}/17** scans.

## Open and use

**OPEN_OCTA_AUTO_CNV_V3.cmd** opens the integrated GUI. Saved manual outlines are cyan and selectable in the new **Saved manual** dropdown. **OPEN_SAVED_MANUAL_D7.cmd** jumps directly to existing D7 work. **OPEN_MANUAL_REVIEW.cmd** starts D14 with automatic proposals hidden for new drawings. See **MANUAL_ANNOTATIONS.md** for all six TS267 annotation files and where new work saves.

Paint, erase, redraw, split/merge, approval/rejection, undo/redo and revision checking remain integrated. Structural footprints, candidate cores and numerical contours remain separate. The **Excluded / extra evidence (not CNV)** switch exposes screened shapes and geometry failures, with reasons at the cursor; it is off by default. Those outlines are not presented as CNVs. Geometry alone cannot create a primary CNV proposal. No view is labeled OCTA because no actual OCTA projection was loaded.

## Revised rules

- Require a compact round or roughly oval focus: area >=250 native pixels, equivalent diameter <=120 pixels (~342 um), axis ratio <=2, solidity >=0.70, and Crofton circularity >=0.48. These exploratory thresholds need manual calibration.
- Favor spaces between major vessel trunks. Long connected vessel structures are separated from compact islands in the upstream vessel mask, because some small lesion-like islands were themselves labeled as vessels. A focus cannot be centered on a trunk corridor; trunk overlap is limited to 12%. This does not establish vascular anatomy from a mask.
- Require structural corroboration: at least half the focus exceeds the local structural-departure threshold. Geometry failures, automatic trace loss, and local measured thickness departures remain supporting evidence. Background support never enters detection.
- Reject diffuse, elongated, weakly supported and clipped shapes from the main list; preserve them separately for inspection. Field-edge candidates have uncertain roundness and may require manual addition.
- Nearby fragments can join only across <=50 um gaps when the inferred envelope remains rounded, compact, and off trunks. The envelope is an editing proposal, not an anatomical border.
- Typically expect 1–2 lesions; show at most four qualifying foci in the main queue. Any additional qualifying focus is explicitly retained as extra evidence, rather than silently labeled absent. No scan is assigned lesions merely to reach an expected count.

This reduces review burden but can miss small, clipped or irregular true lesions. More coverage made v2's 7/7 location figure misleading; v3 reports candidate-core area and tolerance coverage alongside hits. Sparse manual components are not confirmed independent lesion counts, and uncertain manual borders are not exact ground truth. Nominal D0 is not a confirmed negative. A saved D98 OS reviewed absence exists on repeat 5, outside this pilot's repeat 1; no performance claim is transferred across that mismatch.

## Measurement and provenance

Full retina remains ILM to outer RPE edge ×1.12 um/pixel. Signed deficit remains 100×(reference−measured)/reference. Native coordinates, missing values, vessel/shadow exclusions, six background variants and assisted-recomputation provenance are preserved. Quantitative areas describe supported measured pixels, not recovered tissue or complete lesion area.

Frozen v2 input arrays are reused with source hashes checked; v2 detector outputs and human CNV masks do not enter the v3 rules. Current matching manual annotations are read only for comparison. V1/v2 implementation and labels remain untouched. New human annotations are written only by GUI actions under this v3 folder. Automatic-seeded reviews are distinguished from newly hand-drawn reference regions. These rules were developed on TS267 examples; the upstream segmentation model also trained on TS267. Other animals remain reserved for subsequent detector evaluation. No visits are registered and no longitudinal lesion-change claim is made.

## Results and review next

`summary.csv`, `candidates.csv`, `screened_evidence.csv`, `sensitivity.csv`, `manual_location_comparison.csv` and per-scan maps/provenance contain the numerical results. `REVIEW_ATLAS.html` shows examples. `verification/` contains synthetic, editing, native-coordinate and saved-array checks. Run **RUN_PILOT.cmd** to recompute, and **VERIFY.cmd** for verification.

A few new manual examples would now be useful: D14, the missed lower D7 region, and genuine vessel/edge negatives. Draw without automatic footprints visible when possible. Review D7's five saved components as well: they exceed the usual count expectation and should not be silently collapsed into assumed lesion counts.

| Scan | v2 | v3 | Manual locations hit/available | Background support |
|---|---:|---:|---:|---:|
'''
 for r in rows:text+=f'| {r["scan_id"]} | {r["v2_candidates"]} | {r["candidate_count"]} | {r["location_hits_75um"]}/{r["reviewed_manual_components"]} | {r["supported_fraction"]:.1%} |\n'
 destination(HERE/'START_HERE.md').write_text(text,encoding='utf-8')
 atlas='<html><head><meta charset="utf-8"><style>body{font:18px system-ui;margin:32px;background:#202329;color:white}img{width:100%;max-width:1200px}a{color:cyan}</style></head><body><h1>CNV v3: rounded intervascular proposals</h1><p>Orange/red outlines: proposals. Cyan: saved manual. These are development review examples.</p>'
 for v in selected():
  if v['eye']=='OD' and v['day_label'] in ('D0','D7','D14','D28'):atlas+=f'<h2>{v["scan_id"]}</h2><img src="scans/{v["scan_id"]}/overview.png">'
 atlas+='</body></html>';destination(HERE/'REVIEW_ATLAS.html').write_text(atlas,encoding='utf-8')
 preservation={}
 for version in ('v1','v2'):
  root=ROOT/f'outputs/octa-auto_cnv_{version}'
  for name,digest in read(root/'implementation_manifest.json').items():preservation[f'{version}/{name}']=sha(root/name)==digest
 assert all(preservation.values());write(HERE/'verification/prior_versions_preserved.json',preservation)
 write(HERE/'RESULTS.json',dict(scans=17,proposals=count,previous_v2_proposals=220,location_hits=hits,manual_components=len(locations),default_background_insufficient=unsupported,human_review_pending=True))
 print('RESULTS',count,'proposals;',hits,'/',len(locations),'locations;',unsupported,'insufficient backgrounds')

if __name__=='__main__':main()
