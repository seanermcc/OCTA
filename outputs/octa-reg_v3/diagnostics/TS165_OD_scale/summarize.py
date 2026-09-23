from pathlib import Path
import json,hashlib
import numpy as np
from scipy.ndimage import map_coordinates
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).parent;root=P.parents[3]
paths=sorted((root/'outputs/octa-reg_v1/prepared').glob('TS165_OD*.npz'))
fits=json.loads((P/'refined_fits.json').read_text());widths=json.loads((P/'width_measurements.json').read_text())
def fit(a,b):return np.array(next(r for r in fits if r['a']==a and r['b']==b)['matrix'])
origin=np.array([177.,115.]);normal=np.array([.83,-.56]);normal/=np.linalg.norm(normal)
maps={9:np.eye(3),1:fit(1,9),8:fit(8,9),7:fit(8,9)@fit(7,8)}
fig,axes=plt.subplots(1,4,figsize=(12,5.3))
for ax,n in zip(axes,[1,7,8,9]):
    inv=np.linalg.inv(maps[n]);c=origin@inv[:2,:2].T+inv[:2,2];nn=inv[:2,:2]@normal;nn/=np.linalg.norm(nn);tt=np.array([-nn[1],nn[0]])
    yy,xx=np.mgrid[-60:60,-45:45];coords=c+xx[:,:,None]*nn+yy[:,:,None]*tt
    im=np.load(paths[n-1])['enface'];crop=map_coordinates(im,coords.reshape(-1,2)[:,::-1].T,order=1,cval=np.nan).reshape(120,90)
    lo,hi=np.nanpercentile(im,[2,98]);ax.imshow(crop,cmap='gray',vmin=lo,vmax=hi,extent=[-45,45,60,-60]);ax.axhline(0,color='#d97706',lw=1)
    ax.set_title(f'Scan {n}');ax.set_xlabel('Native pixels');ax.set_xticks([-40,-20,0,20,40]);ax.set_yticks([-60,-30,0,30,60]);ax.set_aspect('equal')
fig.suptitle('Same large vessel: native-size crops, rotation only',fontsize=17)
fig.text(.5,.02,'Approximate corresponding segment; identical pixel scale. Dark band includes the projected vessel/shadow.',ha='center',fontsize=10)
fig.tight_layout(rect=[0,.05,1,.92]);fig.savefig(P/'native_vessel_comparison.png',dpi=160)
reviewpath=root/'outputs/octa-reg_v2/all_samples/TS165_OD/human_review.json';review=json.loads(reviewpath.read_text())
audit=dict(review_revision=review['revision'],review_sha256=hashlib.sha256(reviewpath.read_bytes()).hexdigest(),scans=[])
for p in paths:
    j=json.loads(p.with_suffix('.json').read_text());m=np.array(review['fields'][p.stem]['matrix_to_onh_pixels'])
    audit['scans'].append(dict(scan_id=p.stem,prepared_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),native_shape=np.load(p)['enface'].shape,transform_singular_values=np.linalg.svd(m[:2,:2],compute_uv=False).tolist(),lateral_calibration=j['calibration'],source=j['source']))
(P/'source_audit.json').write_text(json.dumps(audit,indent=2))
(P/'matched_width_profiles.png').write_bytes((P/'width_profiles_1_9.png').read_bytes())
lines=['# TS165 OD vessel-size check — 2026-09-22','',
'Read-only analysis of the ten native prepared images and current v2 review revision '+str(review['revision'])+'. No montage, human decisions, masks, or calibration were changed.','',
'## Findings','',
'The width discrepancy is present in the source en-face projections. All ten are 512 x 512, and every saved placement has unit singular values: the reviewer rotates/translates without scan-specific zoom. The shared lateral calibration is approximate, not independently validated per acquisition. The processed MATLAB file inspected (scan 9) contains only the two 512 x 512 x 1024 image channels, without an optical magnification setting.','',
'Matched structural dark-band widths at half local contrast (not anatomical vessel diameter):','',
'| Comparison | Sites | First scan, px | Second scan, px | Second / first |','|---|---:|---:|---:|---:|']
for a,b in [(1,9),(8,9),(7,8),(4,7)]:
    rs=[r for r in widths if r['a']==a and r['b']==b]
    def span(key):return f'{min(r[key] for r in rs):.1f}–{max(r[key] for r in rs):.1f}'
    lines.append(f'| {a} vs {b} | {len(rs)} | {span("source_width_px")} | {span("target_width_px")} | {span("ratio")} |')
lines.extend(['','The 4 vs 7 comparison concerns the narrower central trunk; the other pairs concern the giant trunk. Sites differ between pair comparisons, so these ranges should not be treated as identical-segment measurements across all four scans. Edge-crossing profiles were rejected.','',
'## Scale interpretation','',
'Diagnostic rotation/translation/scale fits of scan 9 against scans 1, 2, and 3 favored approximately 1.20–1.25 times enlargement of the earlier images. Scan 1 coarse correlation increased from 0.72 (rigid) to 0.86–0.87 (scale permitted); scan 3 from 0.80 to 0.89. These fits describe an effective image-scale mismatch, not calibrated optical zoom. Fine-band image correlation includes vessel edges and is not independent small-vessel validation. Trunk-excluded correlations remained modest (~0.23–0.28 for the best scan 1/3 vs 9 fits). A uniform rescale does not align every small branch.','',
'Scans 7 and 8 have similar fitted overall scale (~1.02 for 7 -> 8) but a 13–21% width difference in their overlapping giant trunk. Scan 8 and 9 giant-trunk widths differ by only ~2–6% at the sampled sites. Scan 7 is close to unit scale in its limited overlaps with 4 and 5, yet its narrower central trunk is ~6–17% broader than scan 4. Thus there is no defensible single zoom factor shared by 7–9. Projection/contrast broadening and spatial distortion remain possible explanations; acquisition optical magnification cannot be established from the available processed images alone.','',
'## Method and limitations','',
'Native structural images were used, not vessel-mask widths. Cross-vessel profiles average seven along-vessel samples, smooth at sigma 1 pixel, and measure the outer half-depth crossings relative to a linear local background. Local rotations were used to place approximately corresponding transects; widths remain in each image’s native pixels. Four scan 1/9 sites and two each for 7/8 and 8/9 are a targeted check, not an exhaustive vessel-diameter study.','',
'Automatic SIFT correspondences were mostly sparse, clustered, or false; pair_fits.json is exploratory output and its scales are NOT accepted measurements. Similarity fits are diagnostic only and were never written into the registration. Low-scoring fits and trial failures remain recorded for transparency. Full-frame montage quality must not be inferred from a large-trunk correlation alone.','',
'Files: native_vessel_comparison.png (equal pixel-scale visual); width_profiles_1_9.png (transects/profiles); width_measurements.json (coordinates and measured widths); source_audit.json (source hashes and saved rigid-transform checks).'])
(P/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print('Wrote report, equal-scale comparison, and source audit; review revision',review['revision'])
