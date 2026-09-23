"""Publish v3 reviewer, exact selected CNV outlines, and independent audits."""
import argparse,collections,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from octa_reg_v2.cohort_report import render_group,audit
from octa_reg_v2.run import ROOT,read,write,sha
from .inputs import OUT
from .review_server import current,analysis_records
from .provenance import verify_model_sources

def publish(root=OUT,partial=False):
    manifest=read(root/'inputs/manifest.json');groups=read(root/'run_plan.json')['groups'];summaries=[]
    for group in groups:
        folder=root/group;registration=read(folder/'review_registration.json')
        summary=render_group(folder,groups);summaries.append(summary)
        doc=read(folder/'montage.json');doc['summary']['version']='octa-reg_v3'
        doc['inherited_review']=registration['inherited_review']
        for scan,cnv in zip(doc['scans'],registration['cnv_sources']):
            assert scan['scan_id']==cnv['scan_id'];scan['cnv']=cnv
            with np.load(root/'inputs'/(scan['scan_id']+'.npz')) as z:mask=z['cnv']
            if mask.any():
                rgba=np.zeros((512,512,4),np.uint8)
                edge=mask&~ndi.binary_erosion(mask,iterations=2)
                rgba[mask]=(255,69,203,22);rgba[edge]=(255,69,203,240)
                Image.fromarray(rgba).save(folder/'assets'/f"{scan['index']:03d}_cnv.png")
                scan['cnv_image']=f"assets/{scan['index']:03d}_cnv.png"
        write(folder/'montage.json',doc)
        (folder/'data.js').write_text('window.MONTAGE='+json.dumps(doc,allow_nan=False)+';',encoding='utf8')
        for name in ('cohort_viewer.js','cohort_viewer.html'):
            shutil.copyfile(Path(__file__).with_name(name),folder/('index.html' if name.endswith('.html') else name))
        carried=registration['inherited_review']
        note=f"Saved v2 human placements and categories preserved, revision {carried['revision']}. Whole montage confirmed: {carried['montage_confirmed']}." if carried else 'Automatic v3 proposals; human review is pending.'
        (folder/'REPORT.md').write_text(f"# {group} · octa-reg_v3\n\n{note}\n\nThree graph priorities tested after multiscale feature matching, alternative pose searches, and joint large/small vessel refinement. CNV locations provide bounded supporting evidence; cross-date CNV shapes are not forced to match.\n\nSee `pair_evidence.json` for attempted candidates and margins, `registration.json` for graph trial objectives and CNV provenance, and `../REPORT.md` for limitations.\n\nNative rigid geometry retained. Anatomical NSEW is unconfirmed. Magenta overlays show selected v9 CNVs; source and confirmation status appear for each field.\n",encoding='utf8')
        (folder/'OPEN_MONTAGE.cmd').write_text('@echo off\ncall "%~dp0..\\OPEN_REVIEWER.cmd" '+group+'\n')
        review=current(folder,doc)
        if carried:
            rows=analysis_records(doc,review)
            for a,b in zip(rows,carried['records']):
                assert a['review_tier']==b['review_tier'] and a['placement_confirmed']==b['placement_confirmed']
                assert a['notes']==b['notes'] and a['matrix_to_current_origin_pixels']==b['matrix_to_current_origin_pixels']
    result=audit(root,partial=partial)
    for p,h in manifest['source_hashes'].items():assert sha(p)==h,'Source changed: '+p
    totals={k:sum(s[k] for s in summaries) for k in ('total','supported','uncertain','unlocalized','excluded')}
    cards=''.join(f'<a href="{s["group"]}/index.html"><img src="{s["group"]}/with_uncertain.png"><h2>{s["group"].replace("_"," ")}</h2><p>{s["supported"]} supported · {s["uncertain"]} flagged</p></a>' for s in summaries)
    (root/'index.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>octa-reg_v3</title><style>body{{font:16px system-ui;color:#163b49;background:#edf2f4;margin:35px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:20px}}a{{color:inherit;text-decoration:none}}main a{{background:white;padding:20px;border-radius:12px}}img{{width:100%;height:230px;object-fit:contain}}p{{max-width:1000px;line-height:1.6}}</style><h1>octa-reg_v3 · Retinal montage review</h1><p>{totals['total']} scans · {len(groups)} eyes · {totals['supported']} supported · {totals['uncertain']} flagged · {totals['unlocalized']} unlocalized · {totals['excluded']} excluded</p><p>TS165 OD and OS preserve your saved placements and flagged categories. Other eyes contain new automatic proposals. Pink outlines show selected v9 CNVs; toggle them within each montage. Dates are pooled, and anatomical NSEW remains unconfirmed.</p><p><a href="REPORT.md">Run report</a> · <a href="REVIEW_GUIDE.md">Review and saving guide</a></p><main>{cards}</main></html>''',encoding='utf8')
    write(root/'summary.json',dict(version='octa-reg_v3',groups=summaries,totals=totals,cnv_sources=manifest['cnv_counts']))
    source_hashes=dict(manifest['source_hashes'])
    source_hashes.update(verify_model_sources(root,manifest))
    for g in groups:source_hashes.update(read(root/g/'cache_context.json')['sources'])
    write(root/'PUBLICATION.json',dict(version='octa-reg_v3',verification=result,source_hashes=source_hashes,
        code_hashes={str(p):sha(p) for p in Path(__file__).parent.glob('*') if p.is_file()},
        registrations={g:sha(root/g/'registration.json') for g in groups}))
    print(json.dumps(dict(totals=totals,verification=result)),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--partial',action='store_true');a=ap.parse_args();publish(a.output,a.partial)
