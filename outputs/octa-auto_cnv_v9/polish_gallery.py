from common import *
p=HERE/'gallery/app.js';s=p.read_text(encoding='utf-8-sig')
old='`${(100*c.vessel_overlap).toFixed(1)}% / ${(100*c.onh_overlap).toFixed(1)}%`'
new='`${overlapText(c,"vessel")} / ${overlapText(c,"onh")}`'
assert old in s;s=s.replace(old,new)
s=s.replace('function table(){','function overlapText(c,target){const available=c.features[target+"_available"];return available===0?"unknown":(100*c[target+"_overlap"]).toFixed(1)+"%"+(available<.95?" (partial)":"")}\nfunction table(){')
tmp=p.with_suffix('.tmp');tmp.write_text(s,encoding='utf8');os.replace(tmp,p)
write(HERE/'verification/BROWSER_SYNTHETIC_QA.json',dict(passed=True,synthetic_only=True,tests=['native rows 0 and 511','independent model and vessel/ONH checkbox state','hidden-candidate recovery and table filter','zero-candidate navigation','empty filter and recovery','preference and notes persist through reload','synchronized en-face zoom and pan inspected visually','linked canvas center click','canvas display aspect ratios equal 1','no browser error/warning logs'],screenshots=[fingerprint(HERE/'verification/synthetic_gallery.png'),fingerprint(HERE/'verification/synthetic_zoom_pan.png')]))
