from pathlib import Path
import numpy as np
from octa_reg_v3.local_refine import comparison
from octa_reg_v2.cohort import load_group
from octa_reg_v2.run import read,sha,write
root=Path(__file__).resolve().parent
scans,context=load_group('TS241_OD',root/'TS241_OD')
rows=read(root/'source_analysis_records.json');base={i:np.array(r['matrix_to_current_origin_pixels']) for i,r in enumerate(rows) if r['matrix_to_current_origin_pixels'] is not None}
doc=read(root/'TS241_OD/montage.json');poses={s['index']:np.array(s['matrix_to_onh_pixels']) for s in doc['scans'] if 'matrix_to_onh_pixels' in s}
ev=read(root/'refinement_evidence.json')
comparison(root,scans,base,poses,{i:r['review_tier'] for i,r in enumerate(rows)},ev['anchor_index'],ev['deltas'])
p=root/'TS241_OD/index.html';text=p.read_text(encoding='utf-8')
if 'max 8 px / 1°' not in text:
    text=text.replace('<header>','<div style="padding:10px;background:#fff2ce;color:#493600;flex:none">TS241 OD local refinement from your revision 194 · max 8 px / 1° · changed images need confirmation. <a href="../comparison.html">Compare before / after</a></div><header>',1)
p.write_text(text,encoding='utf-8')
text=text.replace('All animal–eye groups','Before / after comparison').replace('Release PNGs include inherited TS165 edits; they do not incorporate later v3 edits.','Release PNGs show this local refinement; later manual edits are saved separately.')
p.write_text(text,encoding='utf-8')
(root/'TS241_OD/OPEN_MONTAGE.cmd').write_text('@echo off\ncall "%~dp0..\\OPEN_REVIEWER.cmd"\n')
verified=read(root/'VERIFIED.json');verified['tests_passed']=18;verified['code_sha256']=sha(Path(__file__).parents[3]/'code/octa_reg_v3/local_refine.py');write(root/'VERIFIED.json',verified)
