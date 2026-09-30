"""Descriptive agreement audit of saved Hyper_Ref paint; writes reports only."""
import json
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt, binary_erosion
from PIL import Image, ImageDraw, ImageFont
from build import PROJECT, digest

OUT=PROJECT/'outputs/reviewer_comparison'
REPORT=OUT/'hyper_assessment'
REPORT.mkdir(exist_ok=True)
data=json.loads((OUT/'data.js').read_text(encoding='utf-8').removeprefix('window.COMPARISON = ').rstrip().removesuffix(';'))
for source in data['provenance']['sources']:
    assert digest(source['path'])==source['sha256'],source['path']

def mask(r):
    h=r['hyper_ref']; m=np.zeros(np.prod(h['shape']),bool)
    for lo,hi in h['runs']:m[lo:hi]=True
    return m.reshape(h['shape'])

def counts(a,b):
    na,nb=int(a.sum()),int(b.sum()); overlap=int((a&b).sum()); union=na+nb-overlap
    return dict(lead_px=na,shichu_px=nb,overlap_px=overlap,union_px=union,
                lead_only_px=na-overlap,shichu_only_px=nb-overlap,
                dice=2*overlap/(na+nb) if na+nb else None,
                iou=overlap/union if union else None,
                lead_covered=overlap/na if na else None,shichu_covered=overlap/nb if nb else None)

def pooled(rows,key):
    vals={k:sum(r[key][k] for r in rows) for k in ['lead_px','shichu_px','overlap_px','union_px','lead_only_px','shichu_only_px']}
    a,b,i,u=(vals[k] for k in ['lead_px','shichu_px','overlap_px','union_px'])
    vals.update(dice=2*i/(a+b) if a+b else None,iou=i/u if u else None,
                lead_covered=i/a if a else None,shichu_covered=i/b if b else None)
    return vals

font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
panels=[];rows=[]
for c in data['cases']:
    if len(c['reviewers'])!=2:continue
    ra,rb=c['reviewers']['lead'],c['reviewers']['shichu']; a,b=mask(ra),mask(rb)
    assert a.shape==b.shape==(c['depth'],c['width'])
    region_a=np.asarray(ra['cnv']['region'],bool);region_b=np.asarray(rb['cnv']['region'],bool)
    providers=[Path(p['path']) for p in data['provenance']['sources'] if p['kind']=='provider' and Path(p['path']).parent.name==c['scan_id']]
    assert len(providers)==1
    with np.load(providers[0],allow_pickle=False) as z:shadow=np.asarray(z['shadow'][c['bscan']],bool)
    confirmed=ra['cnv']['confirmed'] and rb['cnv']['confirmed']
    usable=~(np.asarray(ra['excluded'],bool)|np.asarray(rb['excluded'],bool)|shadow)
    shared=usable&region_a&region_b&confirmed
    row=dict(case=c['id'],scan=c['scan_id'],bscan=c['bscan'],both_lesion_confirmed=confirmed,
             raw=counts(a,b),shared_cnv_usable=counts(a&shared[None],b&shared[None]),
             shared_cnv_columns=int(shared.sum()),
             lead_outside_own_region_px=int(a[:,~region_a].sum()),
             shichu_outside_own_region_px=int(b[:,~region_b].sum()),
             lead_unusable_px=int(a[:,~usable].sum()),shichu_unusable_px=int(b[:,~usable].sum()))
    if a.any() and b.any():
        # Descriptive tolerance only. Lateral field width is approximate.
        da=distance_transform_edt(~a,sampling=(1.12,1460/c['width']))
        db=distance_transform_edt(~b,sampling=(1.12,1460/c['width']))
        row['near_5um']=dict(lead_near_shichu_px=int((a&(db<=5)).sum()),
                              shichu_near_lead_px=int((b&(da<=5)).sum()))
    rows.append(row)
    yy=np.nonzero(a|b)[0]
    y0=max(0,int(yy.min())-35) if yy.size else 0
    y1=min(c['depth'],int(yy.max())+36) if yy.size else c['depth']
    gray=np.asarray(Image.open(OUT/c['image']).convert('RGB'))[y0:y1]
    panel=Image.new('RGB',(c['width']*3,y1-y0+62),'#101925');d=ImageDraw.Draw(panel)
    label=c['scan_id'].replace('_OD_',' ')+' | B'+str(c['bscan'])
    d.text((8,4),label,fill='white',font=font)
    d.text((8,27),f"Lead cyan | {a.sum():,} px",fill='#60e8f7',font=small)
    d.text((c['width']+8,27),f"Shichu pink | {b.sum():,} px",fill='#fa96df',font=small)
    dice=row['raw']['dice']
    d.text((2*c['width']+8,27),f"Overlap yellow | Dice {dice:.3f}" if dice is not None else 'No paint',fill='#ffe169',font=small)
    for k in range(3):
        rgb=gray.astype(float).copy()
        groups=[(a,(96,232,247))] if k==0 else [(b,(250,150,223))] if k==1 else [(a&~b,(96,232,247)),(b&~a,(250,150,223)),(a&b,(255,225,105))]
        for m,col in groups:
            mm=m[y0:y1];edge=(m&~binary_erosion(m))[y0:y1]
            rgb[mm]=.6*rgb[mm]+.4*np.array(col);rgb[edge]=col
        panel.paste(Image.fromarray(rgb.astype(np.uint8)),(k*c['width'],52))
    panel.save(REPORT/(c['id']+'.png'));panels.append(panel)

for page in range(0,len(panels),3):
    pack=panels[page:page+3]; canvas=Image.new('RGB',(1536,sum(p.height for p in pack)+16*(len(pack)-1)),'#253249')
    y=0
    for p in pack:canvas.paste(p,(0,y));y+=p.height+16
    canvas.save(REPORT/f'gallery_{page//3+1}.png')

report=dict(snapshot=data['summary']['created'],matched_bscans=len(rows),
            both_lesion_confirmed=sum(r['both_lesion_confirmed'] for r in rows),
            raw=pooled(rows,'raw'),shared_cnv_usable=pooled(rows,'shared_cnv_usable'),
            equal_bscan_mean_dice=float(np.mean([r['raw']['dice'] for r in rows if r['raw']['dice'] is not None])),
            rows=rows)
report['near_5um']={k:sum(r.get('near_5um',{}).get(k,0) for r in rows) for k in ['lead_near_shichu_px','shichu_near_lead_px']}
report['inventory']={who:dict(saved=sum(who in c['reviewers'] for c in data['cases']),
    with_paint=sum(c['reviewers'].get(who,{}).get('hyper_ref',{}).get('pixels',0)>0 for c in data['cases'])) for who in ['lead','shichu']}
(REPORT/'assessment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
