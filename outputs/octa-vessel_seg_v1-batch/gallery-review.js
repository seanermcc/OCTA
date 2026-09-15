(() => {
  'use strict';
  const key = 'octa-vessel-v1-gallery-flags-v1';
  const figures = [...document.querySelectorAll('main figure')];
  const ids = new Set(figures.map(f => f.querySelector('figcaption').textContent.trim()));
  let flags = {}, storageOK = true;
  try { flags = JSON.parse(localStorage.getItem(key) || '{}'); } catch (_) { storageOK = false; }
  if (!flags || typeof flags !== 'object' || Array.isArray(flags)) flags = {};
  const style = document.createElement('style');
  style.textContent = `body{margin:0;padding:20px;color:#e9eef5;font-family:system-ui}h1{font-size:24px;margin:0 0 10px}main{grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:12px}figure{margin:0;background:#232833;border:2px solid transparent;border-radius:10px;overflow:hidden}figure.flagged{border-color:#f7bd59}figure img{display:block}figcaption{padding:10px;overflow-wrap:anywhere}.flag-controls{display:flex;gap:10px;padding:0 10px 12px;flex-wrap:wrap}.flag-controls label{padding:9px;background:#353d4c;border-radius:6px;cursor:pointer;font-size:14px}.flag-controls input{accent-color:#ffbf55;width:18px;height:18px;vertical-align:middle;margin-right:7px}.review-toolbar{position:sticky;top:0;z-index:2;background:#171b23f5;padding:12px 0;display:flex;gap:10px;flex-wrap:wrap;align-items:center}button,select,input[type=search]{font:inherit;padding:9px;border:1px solid #6c7789;border-radius:6px;background:#293342;color:white}button{cursor:pointer}#review-save{width:100%;font-size:13px;color:#b8c9dc}#review-count{font-weight:600}figure[hidden]{display:none}.review-note{color:#bec9d8;font-size:14px}`;
  document.head.append(style);
  const toolbar = document.createElement('section');
  toolbar.className = 'review-toolbar';
  toolbar.innerHTML = `<label>Show <select id="review-filter"><option value="all">All scans</option><option value="flagged">Any flag</option><option value="onh">ONH present</option><option value="vessel">Vessel issue</option></select></label><input id="review-search" type="search" placeholder="Search animal, date, scan…" aria-label="Search scans"><button id="review-export">Export review queue</button><button id="review-import">Import saved queue</button><input id="review-file" type="file" accept=".json,application/json" hidden><span id="review-count"></span><div id="review-save" role="status" aria-live="polite"></div>`;
  document.querySelector('main').before(toolbar);
  const note = document.createElement('p');
  note.className = 'review-note';
  note.textContent = 'Flag thumbnails directly. Both flags can be selected. Unflagged scans are not approved labels. Selections save in this browser; export the queue when finished to keep a portable copy for GUI correction.';
  toolbar.before(note);
  const status = document.getElementById('review-save');
  const filter = document.getElementById('review-filter');
  const search = document.getElementById('review-search');
  function update() {
    let total=0,onh=0,vessel=0,shown=0;
    figures.forEach(f => {
      const id=f.dataset.scanId, r=flags[id] || {}, any=!!(r.onh_present || r.vessel_issue);
      total+=any; onh+=!!r.onh_present; vessel+=!!r.vessel_issue;
      f.classList.toggle('flagged',any);
      f.querySelector('[data-flag="onh_present"]').checked=!!r.onh_present;
      f.querySelector('[data-flag="vessel_issue"]').checked=!!r.vessel_issue;
      f.hidden=!(id.toLowerCase().includes(search.value.toLowerCase()) && (filter.value==='all' || filter.value==='flagged' && any || filter.value==='onh' && r.onh_present || filter.value==='vessel' && r.vessel_issue));
      shown+=!f.hidden;
    });
    document.getElementById('review-count').textContent=`${total} flagged · ${onh} ONH · ${vessel} vessel · ${shown}/${figures.length} shown`;
  }
  function save() {
    try { localStorage.setItem(key,JSON.stringify(flags)); storageOK=true; }
    catch (_) { storageOK=false; }
    status.textContent=storageOK ? 'Selections saved in this browser. Export review queue to save a file for the correction GUI.' : 'Browser saving unavailable. Export review queue before closing this page to preserve your flags.';
  }
  figures.forEach(f => {
    const id=f.querySelector('figcaption').textContent.trim(); f.dataset.scanId=id;
    f.querySelector('a').target='_blank'; f.querySelector('a').rel='noopener';
    const controls=document.createElement('div'); controls.className='flag-controls';
    for (const [field,label] of [['onh_present','ONH present'],['vessel_issue','Vessel issue']]) {
      const wrapper=document.createElement('label'), input=document.createElement('input');
      input.type='checkbox';input.dataset.flag=field;input.setAttribute('aria-label',`${label}: ${id}`);
      input.addEventListener('change',()=>{ flags[id]={...flags[id],[field]:input.checked,updated_at:new Date().toISOString()};save();update(); });
      wrapper.append(input,document.createTextNode(label));controls.append(wrapper);
    }
    f.append(controls);
  });
  filter.addEventListener('change',update); search.addEventListener('input',update);
  document.getElementById('review-export').onclick=()=>{
    const scans=[...ids].filter(id=>flags[id]?.onh_present || flags[id]?.vessel_issue).map(id=>({scan_id:id,onh_present:!!flags[id].onh_present,vessel_issue:!!flags[id].vessel_issue,updated_at:flags[id].updated_at}));
    const data={format:'octa-vessel-gallery-flags-v1',batch:'octa-vessel_seg_v1-batch',exported_at:new Date().toISOString(),purpose:'thumbnail triage only; not segmentation approval or training labels',scans};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='octa-vessel-v1-review-queue.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
    status.textContent=`Export requested: ${scans.length} flagged scans. Keep the downloaded JSON file for the correction queue.`;
  };
  const file=document.getElementById('review-file');
  document.getElementById('review-import').onclick=()=>file.click();
  file.onchange=async()=>{
    try {
      if (!file.files.length) return;
      const data=JSON.parse(await file.files[0].text());
      if(data.format!=='octa-vessel-gallery-flags-v1' || !Array.isArray(data.scans)) throw Error('Not a gallery queue file');
      const imported={};
      for(const r of data.scans) {
        if(!ids.has(r.scan_id) || typeof r.onh_present!=='boolean' || typeof r.vessel_issue!=='boolean') throw Error('Invalid scan or flags');
        imported[r.scan_id]={onh_present:r.onh_present,vessel_issue:r.vessel_issue,updated_at:r.updated_at};
      }
      Object.assign(flags,imported);save();update();status.textContent+=' Imported flags merged with current selections.';
    } catch(e) {status.textContent=`Import failed: ${e.message}. Current selections retained.`;}
    file.value='';
  };
  update();
  status.textContent=storageOK ? 'Selections restored from this browser. Export review queue when finished.' : 'Browser saving unavailable; export before closing.';
})();
