'use strict';
const {summary:S, scans, groups} = window.MONTAGE;
const $ = s => document.querySelector(s), C = $('#view'), ctx = C.getContext('2d');
const clone = x => JSON.parse(JSON.stringify(x));
const images = new Map(), history = [], dayColors = new Map();
let mode = 'representative', tool = 'pan', selected = null, alpha = 1, blink = false;
let zoom = 1, pan = [0,0], drag = null, ready = false, saving = false, dirty = false, generation = 0;
let review = {fields:{}, decisions:{}, montage_confirmed:false, onh_override:null}, revision = 0, baseFingerprint = '';
let notesTimer=null, notesCheckpoint=false;
const endpoint = '/api/review/'+encodeURIComponent(S.group);
const days = [...new Set(scans.map(s=>s.day_label || '?'))];
const enabledDays = new Set(days);
const eligible = scans.filter(s=>s.tier!=='excluded');
const record = s => review.fields[s.scan_id];
const tier = s => review.decisions[s.scan_id]?.tier || s.tier;
const active = () => eligible.filter(s=>tier(s)!=='excluded');
const flagged = s => ['uncertain','unlocalized'].includes(tier(s));
const pose = s => record(s)?.matrix_to_onh_pixels || s.matrix_to_onh_pixels;
const confirmed = s => tier(s)!=='excluded' && record(s)?.status === 'confirmed';
const onhCenter = () => S.canvas_origin.map((v,i)=>v+(review.onh_override || [0,0])[i]);
const onhKnown = () => review.onh_override !== null || S.origin_kind !== 'unresolved';
function setONH(p){review.onh_override=p.map((v,i)=>v-S.canvas_origin[i]);review.montage_confirmed=false;}
const visible = s => enabledDays.has(s.day_label || '?') && (tier(s)==='supported' ? $('#supportedToggle').checked : tier(s)!=='excluded' && $('#uncertainToggle').checked);
const apply = (m,p) => [m[0][0]*p[0]+m[0][1]*p[1]+m[0][2],m[1][0]*p[0]+m[1][1]*p[1]+m[1][2]];
const canvasPose = s => {const m=pose(s);if(!m)return null;const n=clone(m);n[0][2]+=S.canvas_origin[0];n[1][2]+=S.canvas_origin[1];return n;};
const corners = s => {const m=canvasPose(s);return m?[[5,5],[507,5],[507,507],[5,507]].map(p=>apply(m,p)):[];};
const angle = m => Math.atan2(m[1][0],m[0][0])*180/Math.PI;
function rotate(m,degrees){const center=apply(m,[256,256]),r=degrees*Math.PI/180,c=Math.cos(r),s=Math.sin(r);return [[c,-s,center[0]-256*c+256*s],[s,c,center[1]-256*s-256*c],[0,0,1]];}
function edited(s){return !!record(s) && JSON.stringify(pose(s))!==JSON.stringify(s.matrix_to_onh_pixels);}
function checkpoint(){history.push(clone(review));if(history.length>50)history.shift();$('#undo').disabled=false;}
function mutate(fn){if(!ready)return;checkpoint();fn();changed();}
function changed(){generation++;dirty=true;status();details();draw();save();}
function setPose(s,m){review.fields[s.scan_id]={matrix_to_onh_pixels:clone(m),status:'draft'};review.montage_confirmed=false;}
function saveMessage(text,error=false){$('#saveStatus').textContent=text;$('#saveStatus').classList.toggle('error',error);}
async function save(){
  if(!ready || saving || !dirty)return;
  saving=true;const version=generation;
  saveMessage('Saving review…');
  try{
    const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...review,revision,base_fingerprint:baseFingerprint})});
    const result=await response.json();if(!response.ok)throw Error(result.error || 'Save failed');
    revision=result.revision;dirty=generation!==version;
    saveMessage('Saved to disk · revision '+revision+' · '+new Date(result.saved_at).toLocaleTimeString());
    saving=false;if(dirty)save();
  }catch(error){saving=false;saveMessage('NOT SAVED: '+error.message+' Use Retry save or Export review JSON.',true);}
}
async function loadReview(){
  try{
    const response=await fetch(endpoint);const data=await response.json();if(!response.ok)throw Error(data.error || 'Cannot load review');
    if(!data.supports_review_categories)throw Error('Restart the reviewer server to enable review categories.');
    review={fields:data.fields,decisions:data.decisions || {},montage_confirmed:data.montage_confirmed,onh_override:data.onh_override ?? null};revision=data.revision;baseFingerprint=data.base_fingerprint;ready=true;
    saveMessage(revision?'Loaded saved review · revision '+revision:'Ready · changes save to disk automatically');
  }catch(error){saveMessage('Review saving unavailable. Open OPEN_REVIEWER.cmd and reload. '+error.message,true);}
  status();details();fit();
}
$('#title').textContent=S.group.replace('_',' ')+' · Retinal montage';document.title=S.group+' · octa-reg_v2';
$('#supportedLabel').textContent=`Show supported (${S.supported})`;
$('#uncertainLabel').textContent=`Show flagged / uncertain (${S.uncertain+S.unlocalized})`;
$('#origin').textContent=S.origin_kind==='reviewed_onh'?'Origin: reviewed visible ONH':S.origin_kind==='estimated_onh'?'Origin: estimated ONH':'ONH unresolved · reference-field coordinates';
for(const group of groups){const option=document.createElement('option');option.value=group;option.textContent=group.replace('_',' ');option.selected=group===S.group;$('#group').append(option);}
$('#group').onchange=e=>location.href='../'+encodeURIComponent(e.target.value)+'/index.html';
days.sort((a,b)=>{const rank=x=>x==='pre'?-2:x==='wt'?-1:x.startsWith('d')?+x.slice(1):999;return rank(a)-rank(b);});
for(const [i,day] of days.entries()){
  const color=`hsl(${i*137.5%360} 55% 42%)`;dayColors.set(day,color);
  const label=document.createElement('label');label.className='day';label.style.setProperty('--day',color);
  const items=scans.filter(s=>(s.day_label || '?')===day);
  label.title=[...new Set(items.map(s=>`${s.date}: ${s.nominal_day_label || day}; ${s.day_basis || ''}`))].join('\n');
  const input=document.createElement('input');input.type='checkbox';input.checked=true;input.dataset.day=day;
  input.onchange=()=>{input.checked?enabledDays.add(day):enabledDays.delete(day);status();details();fit();};
  label.append(input,document.createTextNode(day));$('#dayLegend').append(label);
}
const lists={};
for(const [tier,title] of [['supported','Overlap / supported'],['uncertain','Flagged / uncertain'],['unlocalized','Unlocalized native fields'],['excluded','Excluded']]){
  const holder=document.createElement(tier==='excluded'?'details':'div');holder.id='list-'+tier;
  holder.innerHTML=tier==='excluded'?`<summary>${title} (${S.excluded})</summary>`:`<div class="group-title">${title}</div>`;
  $('#scanLists').append(holder);lists[tier]=holder;
  holder.ondragover=e=>{if(ready&&tier!=='unlocalized'){e.preventDefault();holder.classList.add('drop-hover');}};
  holder.ondragleave=()=>holder.classList.remove('drop-hover');
  holder.ondrop=e=>{e.preventDefault();holder.classList.remove('drop-hover');const id=e.dataTransfer.getData('text/plain');const s=scans.find(s=>s.scan_id===id);if(s&&tier!=='unlocalized')moveTier(s,tier);};
}
for(const s of scans){
  const row=document.createElement('div');row.className='scan';row.id='scan-'+s.index;row.tabIndex=0;row.setAttribute('role','button');
  row.onclick=()=>choose(s.index);row.onkeydown=e=>{if(e.key==='Enter'){choose(s.index);e.preventDefault();}};lists[s.tier].append(row);
  row.draggable=s.tier!=='excluded';row.ondragstart=e=>startScanDrag(e,s);
  if(s.image){const im=new Image();im.onload=draw;im.src=s.image;images.set(s.index,im);}
}
function canConfirmMontage(){return ready && mode==='all' && enabledDays.size===days.length && $('#supportedToggle').checked && $('#uncertainToggle').checked && active().every(s=>tier(s)!=='supported'||pose(s));}
function status(){
  $('#exportReview').disabled=!ready;
  $('#moveONH').disabled=!ready;$('#resetONH').disabled=!ready||review.onh_override===null;
  const originText=review.onh_override!==null?'Origin: manually placed ONH':S.origin_kind==='reviewed_onh'?'Origin: reviewed visible ONH':S.origin_kind==='estimated_onh'?'Origin: estimated ONH':'ONH unresolved · reference-field coordinates';
  $('#origin').textContent=originText;$('#onhStatus').textContent=originText+(review.onh_override!==null?` · offset x ${review.onh_override[0].toFixed(1)}, y ${review.onh_override[1].toFixed(1)} px`:'');
  const enabled=active().filter(s=>visible(s)&&pose(s)), n=active().filter(confirmed).length;
  const ns=scans.filter(s=>tier(s)==='supported').length,nf=scans.filter(flagged).length,ne=scans.filter(s=>tier(s)==='excluded').length;
  $('#stats').innerHTML=`<div><b>${ns}</b><span>supported</span></div><div><b>${nf}</b><span>flagged</span></div><div><b>${ne}</b><span>excluded</span></div><div><b>${n}/${active().length}</b><span>confirmed</span></div>`;
  $('#supportedLabel').textContent=`Show supported (${ns})`;$('#uncertainLabel').textContent=`Show flagged / uncertain (${nf})`;
  lists.excluded.querySelector('summary').textContent=`Excluded (${ne}) · select to restore, or drag onto montage`;
  $('#visibleStatus').textContent=`${enabled.length} placed fields enabled · ${enabledDays.size}/${days.length} days · ${eligible.filter(s=>visible(s)&&!pose(s)).length} unlocalized`;
  $('#coverageNote').textContent=`Original automatic coverage: supported ${S.supported_coverage_mm2.toFixed(2)} mm²; with proposals ${S.proposed_coverage_mm2.toFixed(2)} mm². These totals are not recalculated for filters or manual edits.`;
  $('#montageStatus').textContent=review.montage_confirmed?'✓ Montage confirmed':'Montage not confirmed';
  $('#montageStatus').classList.toggle('badge',review.montage_confirmed);
  $('#confirmMontage').disabled=!canConfirmMontage()||review.montage_confirmed;
  $('#unconfirmMontage').disabled=!ready||!review.montage_confirmed;
  $('#confirmHelp').textContent=canConfirmMontage()?`Confirm saves this review: ${ns} supported, ${nf} flagged, ${ne} excluded. Flagged scans stay flagged; confirmation does not promote them.`:'Use Review all fields before confirming. Flagged and excluded decisions are preserved for analysis.';
  for(const s of scans){
    const row=$('#scan-'+s.index),t=tier(s);if(row.parentElement!==lists[t])lists[t].append(row);row.hidden=t!=='excluded'&&!visible(s);row.classList.toggle('selected',s.index===selected);
    const state=t==='excluded'?'Excluded':flagged(s)?(confirmed(s)?'Flagged · pose confirmed':'Flagged · needs review'):confirmed(s)?'✓ Confirmed':edited(s)?'Adjusted · needs confirmation':s.reference?'Reference field':'Needs confirmation';
    row.innerHTML=`<span class="num">${String(s.index+1).padStart(2,'0')}</span><span>${s.day_label || '?'} · ${s.date} · scan ${s.scan_no}<small>${state}${review.decisions[s.scan_id]?.notes?' · note saved':''}</small></span><i class="dot ${t}"></i>`;
  }
  lists.supported.classList.toggle('hidden',!$('#supportedToggle').checked);
  lists.uncertain.classList.toggle('hidden',!$('#uncertainToggle').checked);
  lists.unlocalized.classList.toggle('hidden',!$('#uncertainToggle').checked||!scans.some(s=>tier(s)==='unlocalized'));
}
function moveTier(s,next){
  if(!ready)return;
  if(s.tier==='excluded'&&next!=='excluded'){saveMessage('Original source exclusion is locked; it has no prepared placement.',true);return;}
  if(next==='supported'&&!pose(s)){saveMessage('Place this field before moving it to supported.',true);return;}
  if(tier(s)===next)return;
  mutate(()=>{review.decisions[s.scan_id]={tier:next,notes:review.decisions[s.scan_id]?.notes || ''};if(record(s))record(s).status='draft';review.montage_confirmed=false;});
  if(next==='supported')$('#supportedToggle').checked=true;else if(next==='uncertain')$('#uncertainToggle').checked=true;else lists.excluded.open=true;
  choose(s.index);
}
function startScanDrag(e,s){
  e.dataTransfer.setData('text/plain',s.scan_id);
  e.dataTransfer.setData('application/x-octa-scan',s.scan_id);
  e.dataTransfer.effectAllowed='move';
}
function restoreExcluded(s,point=null){
  if(!ready||!s||tier(s)!=='excluded')return;
  if(s.tier==='excluded'){saveMessage('Original source exclusion remains locked.',true);return;}
  const m=pose(s)?clone(pose(s)):[[1,0,0],[0,1,0],[0,0,1]];
  if(point||!pose(s)){
    const r=C.getBoundingClientRect(),p=point||[(r.width/2-pan[0])/zoom,(r.height/2-pan[1])/zoom];
    const center=apply(m,[256,256]);
    m[0][2]+=p[0]-S.canvas_origin[0]-center[0];m[1][2]+=p[1]-S.canvas_origin[1]-center[1];
  }
  enabledDays.add(s.day_label||'?');
  document.querySelectorAll('[data-day]').forEach(e=>e.checked=enabledDays.has(e.dataset.day));
  $('#uncertainToggle').checked=true;
  mutate(()=>{review.decisions[s.scan_id]={tier:'uncertain',notes:review.decisions[s.scan_id]?.notes||''};setPose(s,m);});
  choose(s.index);tool='move';updateTool();if(!point)fit();else draw();
}
function choose(index){selected=index;alpha=1;$('#opacity').value=1;tool='pan';updateTool();status();details();draw();}
function details(){
  const s=scans[selected];const hasPose=!!s&&!!pose(s)&&tier(s)!=='excluded';
  $('#reviewControls').classList.toggle('hidden',!s);
  if(s){$('#reviewTier').value=tier(s)==='unlocalized'?'uncertain':tier(s);$('#reviewTier').disabled=!ready||s.tier==='excluded';$('#reviewNotes').value=review.decisions[s.scan_id]?.notes || '';$('#reviewNotes').disabled=!ready;$('#originalTier').textContent='Automatic category: '+s.tier+(s.tier==='excluded'?' (source exclusion locked)':' · manual category overrides it for analysis');}
  $('#editControls').classList.toggle('hidden',!hasPose);
  $('#localizeControls').classList.toggle('hidden',!s || !!pose(s) || tier(s)==='excluded');
  $('#localize').disabled=!ready;
  if(!s){$('#detail').innerHTML='<b>Select a field to inspect</b><p class="note">Flagged fields already have best-guess placements. Select one to confirm it or adjust its pose.</p>';return;}
  $('#detail').replaceChildren();const title=document.createElement('b');title.textContent=`Field ${String(s.index+1).padStart(2,'0')} · ${s.day_label} · ${s.date} · scan ${s.scan_no}`;$('#detail').append(title);
  if(tier(s)==='excluded'){
    const help=document.createElement('p');help.className='note';
    help.textContent=s.tier==='excluded'?'This scan was excluded in the source data; its original exclusion is preserved.':'Restore its last placement, or drag this scan row or preview onto the montage. It returns as flagged and needs confirmation; other fields keep their confirmations.';
    $('#detail').append(help);
    if(s.tier!=='excluded'){const restore=document.createElement('button');restore.id='restoreExcluded';restore.textContent='Restore to montage';restore.disabled=!ready;restore.onclick=()=>restoreExcluded(s);$('#detail').append(restore);}
  }
  for(const reason of s.reasons || []){const p=document.createElement('p');p.className='warning';p.textContent=reason;$('#detail').append(p);}
  const evidence=document.createElement('p');evidence.className='note';evidence.textContent=`${s.links || 0} automatic overlap links${s.best_dice!=null?' · best Dice '+s.best_dice.toFixed(2):''}. ${s.reference?'Reference origin stays fixed when this field is edited. ':''}Fit agreement is not independent accuracy.`;$('#detail').append(evidence);
  if(s.image){const img=document.createElement('img');img.src=s.image;img.alt='Selected native retinal field';img.draggable=tier(s)==='excluded'&&s.tier!=='excluded';if(img.draggable){img.title='Drag onto the montage to restore this field';img.style.cursor='grab';img.ondragstart=e=>startScanDrag(e,s);}$('#detail').append(img);}
  if(hasPose){
    const enabled=ready&&visible(s);for(const id of ['confirmField','unconfirmField','moveMode','rotateMode','rotateLeft','rotateRight','angle','resetField'])$('#'+id).disabled=!enabled;
    $('#confirmField').disabled=!enabled||confirmed(s);$('#unconfirmField').disabled=!enabled||!confirmed(s);
    $('#fieldStatus').textContent=!visible(s)?'Hidden by filters':confirmed(s)?'✓ Field confirmed':edited(s)?'Adjusted · needs confirmation':'Automatic pose · needs confirmation';
    const m=pose(s),o=review.onh_override || [0,0];$('#angle').value=angle(m).toFixed(2);$('#pose').textContent=`Current origin offset: x ${(m[0][2]-o[0]).toFixed(1)}, y ${(m[1][2]-o[1]).toFixed(1)} px · angle ${angle(m).toFixed(2)}°`;
  }
}
function bounds(){const points=scans.filter(visible).flatMap(corners);if(onhKnown())points.push(onhCenter());if(!points.length)return [0,0,...S.canvas_size];const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);return [Math.min(...xs)-45,Math.min(...ys)-45,Math.max(...xs)+45,Math.max(...ys)+45];}
function fit(){const r=C.getBoundingClientRect(),[x0,y0,x1,y1]=bounds();zoom=Math.max(.001,Math.min((r.width-60)/(x1-x0),(r.height-210)/(y1-y0)));pan=[(r.width-(x1-x0)*zoom)/2-x0*zoom,(r.height-(y1-y0)*zoom)/2-y0*zoom];draw();}
function order(){
  // A filtered visit must not disappear just because another day's scan was chosen as representative.
  if(mode!=='representative'||enabledDays.size!==days.length)return scans.filter(s=>visible(s)&&pose(s)).map(s=>s.index).reverse();
  return [...new Set([...S.draw_order,...S.uncertain_representative_indices.slice().reverse(),...scans.filter(s=>edited(s)||review.decisions[s.scan_id]).map(s=>s.index)])].filter(i=>visible(scans[i]));
}
function field(index,opacity=1){
  const s=scans[index],im=images.get(index),m=canvasPose(s);if(!visible(s)||!m||!im?.complete||!im.naturalWidth)return;
  ctx.save();ctx.transform(m[0][0],m[1][0],m[0][1],m[1][1],m[0][2],m[1][2]);
  ctx.globalAlpha=opacity;ctx.drawImage(im,5,5,502,502,5,5,502,502);ctx.globalAlpha=1;
  ctx.strokeStyle=flagged(s)?'#db892a':confirmed(s)?'#28b57e':dayColors.get(s.day_label)||'#537380';
  ctx.lineWidth=(index===selected?3:1.3)/zoom;ctx.setLineDash(flagged(s)?[7/zoom,4/zoom]:[]);ctx.strokeRect(5,5,502,502);ctx.setLineDash([]);
  ctx.font=`${12/zoom}px system-ui`;ctx.lineWidth=3/zoom;ctx.strokeStyle='#243a45';const label=String(index+1).padStart(2,'0')+' '+s.day_label;
  ctx.strokeText(label,14,491);ctx.fillStyle='#ffe09c';ctx.fillText(label,14,491);ctx.restore();
}
function draw(){
  const box=C.getBoundingClientRect(),dpr=devicePixelRatio||1;C.width=Math.round(box.width*dpr);C.height=Math.round(box.height*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#eef2f4';ctx.fillRect(0,0,box.width,box.height);ctx.translate(...pan);ctx.scale(zoom,zoom);
  ctx.fillStyle='white';ctx.fillRect(0,0,...S.canvas_size);
  for(const i of order())if(i!==selected)field(i,flagged(scans[i])?.82:1);
  if(selected!==null&&!blink)field(selected,alpha);
  if(mode==='footprints')for(const s of scans){if(!visible(s)||!pose(s))continue;const ps=corners(s);ctx.beginPath();ctx.moveTo(...ps[0]);ps.slice(1).forEach(p=>ctx.lineTo(...p));ctx.closePath();ctx.strokeStyle=dayColors.get(s.day_label);ctx.lineWidth=1.5/zoom;ctx.stroke();}
  if(onhKnown()){ctx.beginPath();ctx.arc(...onhCenter(),(tool==='onh'?9:5)/zoom,0,2*Math.PI);ctx.strokeStyle='#ffb521';ctx.lineWidth=2/zoom;ctx.stroke();}
  if(selected!==null&&visible(scans[selected])&&pose(scans[selected])&&tool==='rotate'){const p=apply(canvasPose(scans[selected]),[256,256]);ctx.strokeStyle='#24cde0';ctx.lineWidth=2/zoom;ctx.beginPath();ctx.arc(...p,7/zoom,0,2*Math.PI);ctx.stroke();}
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.strokeStyle='#3b5560';ctx.fillStyle='#3b5560';ctx.lineWidth=2;
  const bar=500/S.spacing_um*zoom;ctx.beginPath();ctx.moveTo(22,92);ctx.lineTo(22+bar,92);ctx.stroke();ctx.font='11px system-ui';ctx.fillText('500 µm, approximate',22,108);
}
function updateTool(){for(const k of ['pan','move','rotate'])$('#'+k+'Mode').classList.toggle('active',tool===k);$('#moveONH').classList.toggle('active',tool==='onh');$('#moveONH').textContent=tool==='onh'?'Done moving ONH':'Move ONH';$('#onhHelp').classList.toggle('hidden',tool!=='onh');C.style.cursor=tool==='pan'?'grab':tool==='move'?'move':'crosshair';}
function setMode(next){mode=next;for(const k of ['representative','all','footprints'])$('#'+k).classList.toggle('active',k===mode);status();draw();}
function setDays(all){enabledDays.clear();if(all)days.forEach(d=>enabledDays.add(d));document.querySelectorAll('[data-day]').forEach(e=>e.checked=all);status();details();fit();}
for(const m of ['representative','all','footprints'])$('#'+m).onclick=()=>setMode(m);
for(const k of ['pan','move','rotate'])$('#'+k+'Mode').onclick=()=>{tool=k;updateTool();draw();};
$('#fit').onclick=fit;$('#clear').onclick=()=>choose(null);
$('#reviewTier').onchange=e=>moveTier(scans[selected],e.target.value);
$('#reviewNotes').onfocus=()=>notesCheckpoint=false;
$('#reviewNotes').oninput=e=>{const s=scans[selected];if(!s||!ready)return;if(!notesCheckpoint){checkpoint();notesCheckpoint=true;}review.decisions[s.scan_id]={tier:tier(s)==='unlocalized'?'uncertain':tier(s),notes:e.target.value};review.montage_confirmed=false;generation++;dirty=true;status();saveMessage('Notes pending save…');clearTimeout(notesTimer);notesTimer=setTimeout(save,400);};
$('#reviewNotes').onblur=()=>{clearTimeout(notesTimer);save();};
$('#moveONH').onclick=()=>{tool=tool==='onh'?'pan':'onh';updateTool();draw();};
$('#resetONH').onclick=()=>mutate(()=>{review.onh_override=null;review.montage_confirmed=false;});
$('#daysAll').onclick=()=>setDays(true);$('#daysNone').onclick=()=>setDays(false);
for(const id of ['supportedToggle','uncertainToggle'])$('#'+id).onchange=()=>{tool='pan';updateTool();status();details();fit();};
$('#opacity').oninput=e=>{alpha=+e.target.value;draw();};
$('#reviewAll').onclick=()=>{$('#supportedToggle').checked=true;$('#uncertainToggle').checked=true;setDays(true);setMode('all');fit();};
$('#confirmMontage').onclick=()=>{if(canConfirmMontage())mutate(()=>review.montage_confirmed=true);};
$('#unconfirmMontage').onclick=()=>mutate(()=>review.montage_confirmed=false);
$('#confirmField').onclick=()=>mutate(()=>{const s=scans[selected];review.fields[s.scan_id]={matrix_to_onh_pixels:clone(pose(s)),status:'confirmed'};});
$('#unconfirmField').onclick=()=>mutate(()=>{const s=scans[selected];review.fields[s.scan_id]={matrix_to_onh_pixels:clone(pose(s)),status:'draft'};review.montage_confirmed=false;});
function rotateSelected(degrees){const s=scans[selected];if(!s||!ready||!visible(s)||!Number.isFinite(degrees))return;mutate(()=>setPose(s,rotate(pose(s),degrees)));}
$('#rotateLeft').onclick=()=>rotateSelected(angle(pose(scans[selected]))-1);
$('#rotateRight').onclick=()=>rotateSelected(angle(pose(scans[selected]))+1);
$('#angle').onchange=e=>{if(e.target.value.trim())rotateSelected(+e.target.value);else details();};
$('#resetField').onclick=()=>mutate(()=>{delete review.fields[scans[selected].scan_id];review.montage_confirmed=false;});
$('#localize').onclick=()=>mutate(()=>{const r=C.getBoundingClientRect();setPose(scans[selected],[[1,0,(r.width/2-pan[0])/zoom-S.canvas_origin[0]-256],[0,1,(r.height/2-pan[1])/zoom-S.canvas_origin[1]-256],[0,0,1]]);});
$('#undo').onclick=()=>{if(!ready||!history.length)return;review=history.pop();$('#undo').disabled=!history.length;changed();};
$('#retrySave').onclick=()=>{if(!ready)loadReview();else if(dirty)save();else if(!saving)saveMessage('All changes are already saved. Nothing to retry.');};
function exportPayload(){
  const effective={},rows=[];
  for(const s of scans){
    const t=tier(s);let m=null;
    if(t!=='excluded'&&pose(s)){m=clone(pose(s));const o=review.onh_override || [0,0];m[0][2]-=o[0];m[1][2]-=o[1];effective[s.scan_id]=m;}
    rows.push({scan_id:s.scan_id,automatic_tier:s.tier,review_tier:t,tier_source:review.decisions[s.scan_id]?'manual':'automatic',notes:review.decisions[s.scan_id]?.notes || '',placement_confirmed:confirmed(s),eligible_for_primary_analysis:review.montage_confirmed&&t==='supported'&&!!m,matrix_to_current_origin_pixels:m});
  }
  return {...review,schema:'octa-reg-v2-human-review-3',group:S.group,base_fingerprint:baseFingerprint,revision,unsaved:dirty||saving,analysis_records:rows,effective_matrices_to_onh_pixels:effective,coordinate_system:'fields use original automatic frame; effective matrices use current ONH/reference origin',analysis_policy:'Confirmed montage required; supported only by default; flagged opt-in; excluded never included.'};
}
$('#exportReview').onclick=()=>{const blob=new Blob([JSON.stringify(exportPayload(),null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=S.group+'-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
function world(e){const r=C.getBoundingClientRect();return [(e.clientX-r.left-pan[0])/zoom,(e.clientY-r.top-pan[1])/zoom];}
C.ondragover=e=>{if(ready&&Array.from(e.dataTransfer.types).includes('application/x-octa-scan')){e.preventDefault();e.dataTransfer.dropEffect='move';}};
C.ondrop=e=>{const id=e.dataTransfer.getData('application/x-octa-scan');const s=scans.find(s=>s.scan_id===id);if(s&&tier(s)==='excluded'){e.preventDefault();restoreExcluded(s,world(e));}};
function inside(s,p){const m=canvasPose(s);if(!m)return false;const x=p[0]-m[0][2],y=p[1]-m[1][2],u=m[0][0]*x+m[1][0]*y,v=m[0][1]*x+m[1][1]*y;return u>=5&&u<=507&&v>=5&&v<=507;}
function hit(p){const ids=order().filter(i=>i!==selected);if(selected!==null)ids.push(selected);return ids.reverse().find(i=>visible(scans[i])&&inside(scans[i],p));}
C.onwheel=e=>{e.preventDefault();const r=C.getBoundingClientRect(),p=[e.clientX-r.left,e.clientY-r.top],next=Math.min(7,Math.max(.01,zoom*Math.exp(-e.deltaY*.001)));pan=p.map((v,i)=>v-(v-pan[i])*next/zoom);zoom=next;draw();};
C.onpointerdown=e=>{
  if(e.button!==0)return;C.focus();C.setPointerCapture(e.pointerId);const p=world(e),s=scans[selected];
  if(ready&&tool==='onh'){drag={client:[e.clientX,e.clientY],tool:'onh',moved:false,before:clone(review)};return;}
  const editing=ready&&tool!=='pan'&&s&&visible(s)&&pose(s)&&inside(s,p);
  drag={start:p,client:[e.clientX,e.clientY],pan:pan.slice(),m:editing?clone(pose(s)):null,index:selected,tool:editing?tool:'pan',moved:false,before:clone(review)};
  if(editing){drag.center=apply(canvasPose(s),[256,256]);drag.startAngle=Math.atan2(p[1]-drag.center[1],p[0]-drag.center[0]);}
};
C.onpointermove=e=>{
  if(!drag)return;const dx=e.clientX-drag.client[0],dy=e.clientY-drag.client[1];if(!drag.moved&&Math.hypot(dx,dy)<3)return;
  drag.moved=true;
  if(drag.tool==='onh')setONH(world(e));
  else if(drag.tool==='pan')pan=[drag.pan[0]+dx,drag.pan[1]+dy];
  else{let m=clone(drag.m);if(drag.tool==='move'){m[0][2]+=dx/zoom;m[1][2]+=dy/zoom;}else{const p=world(e);m=rotate(m,angle(m)+(Math.atan2(p[1]-drag.center[1],p[0]-drag.center[0])-drag.startAngle)*180/Math.PI);}setPose(scans[drag.index],m);}
  draw();
};
function finishDrag(cancel=false){if(!drag)return;const d=drag;drag=null;if(d.tool!=='pan'&&d.moved){if(cancel){review=d.before;draw();return;}history.push(d.before);if(history.length>50)history.shift();$('#undo').disabled=false;changed();}}
C.onpointerup=e=>{if(!drag)return;if(drag.tool==='onh'){setONH(world(e));drag.moved=true;finishDrag();return;}const wasClick=!drag.moved,p=world(e);finishDrag();if(wasClick){const i=hit(p);if(i!==undefined)choose(i);}};
C.onpointercancel=()=>finishDrag(true);C.onlostpointercapture=()=>finishDrag();
window.addEventListener('resize',fit);
window.addEventListener('keydown',e=>{
  if(['INPUT','BUTTON','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;
  if(e.code==='Space'){e.preventDefault();blink=true;draw();}
  if(e.key==='Escape'){finishDrag(true);tool='pan';updateTool();draw();}
  if(tool==='move'&&selected!==null&&ready&&visible(scans[selected])&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){
    e.preventDefault();const step=e.shiftKey?10:1,s=scans[selected],m=clone(pose(s));m[0][2]+=e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0;m[1][2]+=e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0;mutate(()=>setPose(s,m));
  }
});
window.addEventListener('keyup',e=>{if(e.code==='Space'){blink=false;draw();}});
window.addEventListener('blur',()=>{blink=false;finishDrag();draw();});
window.addEventListener('beforeunload',e=>{if(dirty||saving){e.preventDefault();e.returnValue='Review changes are not saved yet.';}});
status();fit();loadReview();

