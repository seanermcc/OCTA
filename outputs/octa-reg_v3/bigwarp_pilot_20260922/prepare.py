"""Read-only audit and BigWarp image-pair preparation; does not fit a warp."""
from pathlib import Path
import hashlib, json, itertools
import numpy as np
from scipy.ndimage import map_coordinates
from PIL import Image, ImageDraw
from octa_reg_v2.review_server import analysis_inputs, current, analysis_records

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT/'outputs/octa-reg_v2/all_samples'
PREP = ROOT/'outputs/octa-reg_v1/prepared'
GROUPS = [f'TS{n}_{eye}' for n in (165,169,241,247) for eye in ('OD','OS')]
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, v): p.write_text(json.dumps(v, indent=2), encoding='utf-8')

def load_image(sid, hashes):
    meta=PREP/f'{sid}.json'; p=meta.with_suffix('.npz'); info=read(meta)
    assert sha(p)==info['prepared_sha256'], sid
    for source, expected in info['input_hashes'].items():
        assert sha(Path(source))==expected, source
        hashes[source]=expected
    hashes[str(meta)]=sha(meta); hashes[str(p)]=sha(p)
    with np.load(p) as z:
        im=z['enface'].copy(); valid=np.isfinite(im)&~z['registration_blocked']
        assert im.shape==(512,512) and np.allclose(z['spacing'],1460/512)
    lo,hi=np.percentile(im[valid],[2,98])
    im=np.clip((np.nan_to_num(im,nan=lo)-lo)/max(hi-lo,1e-6),0,1)
    return im,valid

def main():
    if (OUT/'manifest.json').exists(): raise RuntimeError('Already prepared; use a fresh folder for new revisions')
    hashes={}; groups=[]; cards=[]
    yy,xx=np.mgrid[0:512,0:512]; grid=np.stack([xx.ravel(),yy.ravel(),np.ones(xx.size)])
    for group in GROUPS:
        src=SOURCE/group; folder=OUT/group; folder.mkdir(exist_ok=True)
        for name in ('montage.json','human_review.json'): hashes[str(src/name)]=sha(src/name)
        doc=read(src/'montage.json'); review=current(src,doc)
        selected=analysis_inputs(src)['records']
        write(folder/'review_snapshot.json',review)
        write(folder/'all_review_records.json',analysis_records(doc,review))
        info={s['scan_id']:s for s in doc['scans']}
        candidates=[]
        for a,b in itertools.combinations(selected,2):
            ma=np.array(a['matrix_to_current_origin_pixels']); mb=np.array(b['matrix_to_current_origin_pixels'])
            tr=np.linalg.inv(mb)@ma; q=tr@grid[:,::64]
            overlap=float(np.mean((q[0]>=0)&(q[0]<=511)&(q[1]>=0)&(q[1]<=511)))
            if overlap<.25: continue
            candidates.append(dict(moving=a['scan_id'],target=b['scan_id'],overlap_fraction_approx=overlap,
                same_date=info[a['scan_id']]['date']==info[b['scan_id']]['date'],
                moving_to_target_native=tr.tolist()))
        candidates.sort(key=lambda p:(not p['same_date'],-p['overlap_fraction_approx']))
        write(folder/'overlap_candidates.json',candidates)
        item=dict(group=group,revision=review['revision'],supported=len(selected),
                  candidate_pairs=len(candidates),saved_at=review.get('saved_at'))
        if candidates:
            pair=candidates[0]; a,va=load_image(pair['moving'],hashes); b,vb=load_image(pair['target'],hashes)
            # Export to the target native 512-square frame, retaining exact composition.
            inverse=np.linalg.inv(np.array(pair['moving_to_target_native']))
            q=inverse@grid
            warped=map_coordinates(a,[q[1],q[0]],order=1,mode='constant',cval=0).reshape(512,512)
            valid=map_coordinates(va.astype(float),[q[1],q[0]],order=0,mode='constant',cval=0).reshape(512,512)>.5
            warped[~valid]=0; target=b.copy(); target[~vb]=0
            for name,im in [('moving_manual_aligned',warped),('target',target),('moving_valid',valid),('target_valid',vb)]:
                Image.fromarray(np.round(im*255).astype('uint8')).save(folder/f'{name}.tif')
            common=valid&vb
            pair['baseline_intensity_correlation']=float(np.corrcoef(warped[common],b[common])[0,1])
            pair['selection']='Largest supported same-date geometric overlap; not a diagnosis of distortion or a quality ranking'
            pair['coordinate_contract']='TIFF x=column,y=row, unit=pixel. Target native frame. moving_manual_aligned is rigid-resampled moving. Residual warp W composes as target-native=W(inv(M_target) @ M_moving @ moving-native); world=M_target @ target-native. Do not apply original rigid placement twice.'
            pair['status']='Prepared only; no landmarks supplied, no warp estimated, no improvement claimed'
            write(folder/'pair.json',pair); item['pair']=pair
            overlay=np.stack([warped,target,target],axis=-1)
            card=Image.new('RGB',(512,548),'white');card.paste(Image.fromarray((overlay*255).astype('uint8')),(0,36))
            ImageDraw.Draw(card).text((8,8),f'{group} rev {review["revision"]}: moving red / target cyan',fill='black')
            card.save(folder/'baseline_overlay.png');cards.append(card)
        groups.append(item)
        print(group, 'revision',review['revision'],'supported',len(selected),'pairs',len(candidates),flush=True)
    # Detect concurrent edits rather than silently mixing review revisions.
    for path, expected in hashes.items(): assert sha(Path(path))==expected, f'Source changed: {path}'
    sheet=Image.new('RGB',(512*4,548*2),'white')
    for i,card in enumerate(cards): sheet.paste(card,((i%4)*512,(i//4)*548))
    sheet.save(OUT/'baseline_contact_sheet.png')
    write(OUT/'manifest.json',dict(groups=groups,source_hashes=hashes,
        source_unchanged_verified=True,warps_applied=False,script_sha256=sha(Path(__file__))))

if __name__=='__main__': main()
