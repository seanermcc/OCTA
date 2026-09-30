from pathlib import Path
p=Path('code/reviewer_compare/viewer.html')
s=p.read_text(encoding='utf-8')
def replace(old,new):
    global s
    assert s.count(old)==1,(old[:100],s.count(old))
    s=s.replace(old,new)
replace('<div class="panes"><div class="pane">','''<div class="note" id="hyperControls">
<div class="toolbar" style="margin:0 0 6px"><b>Hyperreflective dots (Hyper_Ref)</b><label><input id="hyperLead" type="checkbox" checked> Lead dots</label><label><input id="hyperShichu" type="checkbox" checked> Shichu dots</label></div>
<div>Exact saved paint: <b style="color:var(--cyan)">lead cyan</b> · <b style="color:var(--pink)">Shichu pink</b>, with outlined edges and translucent fill. Toggle either reviewer independently of CNV.</div>
<div class="muted">Includes saved drafts; image-excluded portions are dimmed. No dots marked does not establish absence. Painted-pixel totals are not dot counts. These overlays are outside the retinal distance scores.</div>
<div id="hyperStatus" style="margin-top:6px"></div></div>
<div class="panes"><div class="pane">''')
replace('cnvSummary();const messages=', 'cnvSummary();hyperSummary();const messages=')
replace('drawCnvEdges(g,reviewers,sx,sy);','drawCnvEdges(g,reviewers,sx,sy);drawHyper(g,reviewers,sx,sy,w,h);')
replace("'cnvShichu','layers']", "'cnvShichu','layers','hyperLead','hyperShichu']")
replace('const lo=zs.length?Math.min(...zs):0', 'for(const r of Object.values(current.reviewers))if(r.hyper_ref?.bounds)zs.push(r.hyper_ref.bounds[1],r.hyper_ref.bounds[3]);const lo=zs.length?Math.min(...zs):0')
replace('Hyper_Ref paint is not displayed.', 'Hyper_Ref shows the exact saved brush footprints, with separate reviewer toggles. The lesion confirmation status covers CNV and Hyper_Ref together; draft paint is explicitly identified. Painted pixels are not a count of individual dots.')
replace('Math.max(a.height,b.height)+148','Math.max(a.height,b.height)+198')
replace('g.drawImage(a,0,148);g.drawImage(b,a.width,148);', "g.fillText('Hyperreflective dots: '+['lead','shichu'].map(who=>who+' '+(hyperEnabled(who)?'on':'off')+' / '+(current.reviewers[who]?.hyper_ref?.pixels??0)+' painted pixels').join(' | ')+' | retinal boundaries '+($('layers').checked?'on':'off'),20,151);g.fillText(['lead','shichu'].map(who=>who+': '+(current.reviewers[who]?.hyper_ref?.status||'no review')).join(' | '),20,176);g.drawImage(a,0,198);g.drawImage(b,a.width,198);")
replace("current.id+'_cnv_comparison.png'", "current.id+'_annotations_comparison.png'")
p.write_text(s,encoding='utf-8')
