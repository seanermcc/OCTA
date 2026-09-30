from pathlib import Path
p=Path('code/reviewer_compare/viewer.html')
s=p.read_text(encoding='utf-8')
def replace(old,new):
    global s
    assert s.count(old)==1,(old[:100],s.count(old))
    s=s.replace(old,new)
replace('<div class="panes"><div class="pane">','''<div class="note" id="cnvControls">
<div class="toolbar" style="margin:0 0 6px"><b>Saved CNV annotations</b><label><input id="cnvRegions" type="checkbox" checked> CNV regions</label><label><input id="cnvEdges" type="checkbox" checked> CNV edges</label><label><input id="cnvLead" type="checkbox" checked> Lead CNV</label><label><input id="cnvShichu" type="checkbox" checked> Shichu CNV</label><label><input id="layers" type="checkbox" checked> Retinal boundaries</label></div>
<div>CNV colors: <b style="color:var(--cyan)">lead cyan</b> · <b style="color:var(--pink)">Shichu pink</b>. Shaded band = marked lateral extent (full depth). Edge: solid = marked reliable; dashed = unreliable; dotted = not traceable.</div>
<div class="muted">CNV overlays show saved drawings, including drafts and excluded areas; they are independent of the retinal comparison scope and are not included in the distance scores.</div>
<div id="cnvStatus" style="margin-top:6px"></div></div>
<div class="panes"><div class="pane">''')
replace('<script src="data.js"></script><script>','<script src="data.js"></script><script src="cnv.js"></script><script>')
replace("function update(){if(!current)return;", "function update(){if(!current)return;cnvSummary();")
replace("const kk=boundary()<0?names.map((_,i)=>i):[boundary()],reviewers=who==='both'?['lead','shichu']:[who];", "const kk=!$('layers').checked?[]:boundary()<0?names.map((_,i)=>i):[boundary()],reviewers=who==='both'?['lead','shichu']:[who];drawCnvRegions(g,reviewers,w,h,sx);")
replace(" if(who!=='both'&&!current.reviewers[who])", " drawCnvEdges(g,reviewers,sx,sy);\n if(who!=='both'&&!current.reviewers[who])")
replace("const lo=zs.length?Math.min(...zs):0", "for(const r of Object.values(current.reviewers))for(const z of r.cnv?.edge||[])if(z!=null&&z>=current.offset&&z<current.offset+current.depth)zs.push(z-current.offset);const lo=zs.length?Math.min(...zs):0")
replace("}).join('   |   ')}", "}).join('   |   ');$('hover').textContent+=' · '+cnvHover(x)}")
replace("['boundary','highlights','context','overlayToggle']", "['boundary','highlights','context','overlayToggle','cnvRegions','cnvEdges','cnvLead','cnvShichu','layers']")
replace("c.height=Math.max(a.height,b.height)+100", "c.height=Math.max(a.height,b.height)+148")
replace("g.drawImage(a,0,100);g.drawImage(b,a.width,100);", "g.font='12px system-ui';g.fillText('CNV: regions '+($('cnvRegions').checked?'on':'off')+' / edges '+($('cnvEdges').checked?'on':'off')+' | Lead cyan '+($('cnvLead').checked?'on':'off')+' / Shichu pink '+($('cnvShichu').checked?'on':'off')+' | solid: marked reliable; dashed: unreliable; dotted: not traceable',20,104);g.fillText(['lead','shichu'].map(who=>who+': '+(current.reviewers[who]?.cnv?.status||'no review')).join(' | '),20,128);g.drawImage(a,0,148);g.drawImage(b,a.width,148);")
replace("current.id+'_comparison.png'", "current.id+'_cnv_comparison.png'")
replace('CNV footprints, CNV edge and Hyper_Ref paint are outside these scores.', 'CNV regions and CNV edges are displayed separately from these scores. Regions are lateral spans, not tissue masks. CNV edge coordinates and uncertainty are read from each reviewer’s saved journal; drafts are labeled. Hyper_Ref paint is not displayed.')
p.write_text(s,encoding='utf-8')
