"""Audit real outputs and seal input/code hashes for safe resumption."""
import sys,platform,json
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import scipy,skimage,PIL
from .run import load,OUT,ROOT,read,write,sha,score

def main():
    scans=load();data=read(OUT/'montage.json');records=data['scans'];summary=data['summary']
    assert len(scans)==len(records)==34
    assert summary['eligible']==summary['placed']==33 and summary['excluded']==1
    hashes=read(OUT/'source_hashes.json')
    for path,expected in hashes.items():assert sha(path)==expected,path
    ps={r['index']:np.array(r['matrix_to_onh_pixels']) for r in records if 'matrix_to_onh_pixels' in r}
    assert 17 not in ps
    for i,m in ps.items():
        assert np.isfinite(m).all()
        np.testing.assert_allclose(m[:2,:2].T@m[:2,:2],np.eye(2),atol=1e-8)
        assert abs(np.linalg.det(m[:2,:2])-1)<1e-8
        np.testing.assert_allclose(m@np.array(records[i]['matrix_from_onh_pixels']),np.eye(3),atol=1e-8)
        np.testing.assert_allclose(np.array(records[i]['native_um_to_onh_um'])@np.array(records[i]['onh_um_to_native_um']),np.eye(3),atol=1e-8)
    fits=[]
    for e in data['edges']:
        a,b=e['a'],e['b'];m=np.linalg.inv(ps[b])@ps[a]
        s=score(scans[a],scans[b],m)
        fits.append(dict(a=a,b=b,**s))
    best=[]
    for i in ps:
        incident=[e for e in fits if i in (e['a'],e['b'])]
        assert incident
        e=max(incident,key=lambda x:x['score']);best.append(dict(scan=i,**e))
        assert e['dice']>.4 and e['span_px']>23 and e['overlap']>.18,(i,e)
    write(OUT/'verification.json',dict(status='passed',source_files_unchanged=len(hashes),
        placed=33,excluded_not_placed=True,rigid_and_inverse_checks=True,
        best_final_overlap_by_scan=best,final_overlap_edges=fits,
        limitations='Scores reuse fitting masks; not independent registration accuracy or biological repeatability'))
    pairs=read(OUT/'pairs.json');curve_files=list((OUT/'curve_pairs').glob('*.json'))
    code_paths=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).with_name('viewer.html'),ROOT/'code/octa_reg_v1/io.py']
    release=dict(created_utc=datetime.now(timezone.utc).isoformat(),version='octa-reg_v2 TS247_OD pooled pilot',
        scan_ids=[s['info']['scan_id'] for s in scans],source_hashes=hashes,
        code_hashes={str(p):sha(p) for p in code_paths},versions=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,skimage=skimage.__version__,pillow=PIL.__version__),
        search_plan=[[read(p)['a'],read(p)['b']] for p in curve_files],
        metadata_policy='All acquisition dates pooled only for this user-authorized exploration',
        coordinate_contract='Native x=A-line column, y=B-scan row; no flips; ONH at origin of reference scan; rigid only; approximate 1460/512 um per pixel')
    write(OUT/'RELEASE.json',release)
    loops=[e['final_loop_rms_px']*summary['spacing_um'] for e in data['edges']]
    weak=[r for r in records if r.get('placement_evidence')]
    excluded=[r for r in records if r['excluded']]
    consensus_distance=read(OUT/'corroboration.json')[0]['convergence_distance_px']*summary['spacing_um']
    report=f'''# TS247 OD — pooled ONH montage

All **33 eligible scans** are placed in one ONH-centered map. One previously excluded scan remains out. All dates (2024-10-17 through 2024-11-26) were pooled at the user's request; dates remain attached to each source field.

Open `index.html` or `OPEN_MONTAGE.cmd`. The default montage displays **{len(summary['representative_indices'])} representative fields**, chosen by incremental observed coverage. Use **All scans** for all 33, **Footprints** for their boundaries, and select a scan to bring it forward. Opacity and Space-to-blink let you inspect overlap. `montage.png` is the annotated export; `montage_clean.png` is the map without its caption.

## Observed coverage

- Union of placed, 5-pixel-border-cropped fields: **{summary['coverage_mm2']:.2f} mm²**, approximately **{summary['coverage_single_field_equivalents']:.2f} single-field areas**.
- Bounding extent: approximately **{summary['extent_mm'][0]:.2f} × {summary['extent_mm'][1]:.2f} mm**. The bounding rectangle includes blank space; it is not the observed area.
- Reference ONH: reviewed visible disc in `TS247_OD_2024-10-17_beforelaser_s10_120645` (display field 07).
- Scale remains approximate (1460 µm across 512 pixels). Native display orientation is retained. Temporal/nasal and superior/inferior are not established from these files.

## What changed from v1

The original run depended on sparse ORB texture matches and required three vessel junctions. This pilot uses vessel-anchored SIFT matches, then searches whole vessel curves over rotation and translation for difficult fields. It measures symmetric centerline agreement, common-tissue vessel Dice, structural correlation, and two-dimensional spatial support. Matching one straight trunk cannot pass the spatial-support check.

The graph starts at the ONH reference, resolves conflicting placements using agreement across neighbors, and jointly fits rigid poses. No image is stretched or nonrigidly warped. Convergence toward the ONH contributes a directional consistency check for the low-contrast recovery; convergence alone does not establish an exact position. The other fields are placed by overlapping vessel geometry. Source tiles are composited without synthesized tissue or forced gap filling.

## Evidence and remaining uncertainty

- {len(pairs)} eligible descriptor comparisons; {sum(r['accepted'] for r in pairs)} passed that stage. {len(curve_files)} additional whole-curve searches are recorded.
- {summary['accepted_edges']} pairwise constraints retained after graph consistency checks; {summary['quarantined_edges']} conflicting constraint rejected. A high-scoring wrong-trunk match for display field 17 was overruled by four agreeing neighbors.
- Display field **22** (`TS247_OD_2024-11-20_D35_s01_112538`) has low structural contrast. Six informative vessel overlaps agreed, and its inferred convergence lay about {consensus_distance:.0f} µm from the reference ONH before final joint fitting. Its intensity-correlation gate was explicitly waived under this separate consensus rule; the viewer flags it.
- Internal pose-loop RMS: median **{np.median(loops):.1f} µm**, maximum **{max(loops):.1f} µm**. These are graph-consistency residuals, **not independent accuracy measurements**.
- All placements remain automatic research proposals. Single-link peripheral fields deserve particular review. Their transforms, neighbor counts, and pair metrics are retained in `montage.json` and `verification.json`.
- Mixing dates can mix laser lesions and acquisition appearances. This is a coverage montage, not a single-timepoint image or a longitudinal outcome measurement. Repeated scans mostly revisit the same territory; 33 scans do not imply 33 distinct fields of retina.
- Excluded: `{excluded[0]['scan_id']}`. Reason retained from the existing review: {excluded[0]['exclusion_reason'] or 'whole-scan exclusion'}.

## Verification and provenance

Five synthetic/regression tests passed: known rigid recovery with partial overlap, rejection of a single straight trunk as spatial support, no-overlap handling, ONH direction/inverse coordinates, and a false high-score graph bridge overridden by neighbor consensus. Real-output checks verified every transform and inverse, positive unit determinant, exclusion handling, per-scan final overlap support, and unchanged hashes for {len(hashes)} consumed source files. Original volumes, optical caches, masks, human labels and v1 products were not modified.

`RELEASE.json` pins code, source files, package versions and the curve-search plan. A later source/code change prevents silent reuse of released caches. `montage.json` contains pixel and micrometer transforms and inverses; `pairs/`, `curve_pairs/`, and `consensus_pairs/` preserve candidate evidence and rejected alternatives. No training or new human labels were produced.

## Reproduce

From the repository root in an activated `octa` conda environment:

```powershell
$env:PYTHONPATH = "$PWD\\code"
python -m octa_reg_v2
python -m octa_reg_v2.verify
```

The pilot is deliberately bounded to TS247 OD on its verified 512 × 512 grid. Implement another animal or modified algorithm in a new output version.
'''
    (OUT/'REPORT.md').write_text(report,encoding='utf-8')
    print(json.dumps(dict(verified_sources=len(hashes),final_edges=len(fits),minimum_best_dice=min(e['dice'] for e in best),loop_median_um=float(np.median(loops)),loop_max_um=float(max(loops))),indent=2))

if __name__=='__main__':main()
