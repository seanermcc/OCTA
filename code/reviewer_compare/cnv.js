/* Saved CNV annotations: independent of retinal eligibility and distance scores. */
const cnvColors = {lead:'#60e8f7', shichu:'#fa96df'};
function cnvEnabled(who) { return $('cnv'+(who==='lead'?'Lead':'Shichu')).checked; }
function cnvEdgeCode(c, x) {
  return c.edge_state[x]===3 ? 3 : c.edge_unreliable[x] ? 2 : c.edge_state[x];
}
function cnvEdgeLabel(c, x) {
  return ['no drawn edge','marked reliable','unreliable','not traceable'][cnvEdgeCode(c,x)] || 'unknown';
}
function cnvSummary() {
  $('cnvStatus').innerHTML=['lead','shichu'].map(who=>{
    const r=current.reviewers[who],c=r?.cnv;
    if(!c) return `<span><b>${who==='lead'?'Lead':'Shichu'}:</b> ${r?'CNV data unavailable — refresh snapshot':'No saved review'}</span>`;
    const n=c.region.filter(Boolean).length;
    const drawn=c.edge.filter((z,x)=>z!=null&&c.edge_state[x]>0).length;
    const unclear=c.edge_state.filter((s,x)=>s===2||s===3||c.edge_unreliable[x]).length;
    return `<span><b style="color:${cnvColors[who]}">${who==='lead'?'Lead':'Shichu'}:</b> ${esc(c.status)} · region ${n} A-lines · edge ${drawn} A-lines · unclear marks ${unclear}${!n?' · no region marked':''}</span>`;
  }).join('<br>');
}
function drawCnvRegions(g, reviewers, w, h, sx) {
  if(!$('cnvRegions').checked) return;
  for(const who of reviewers) {
    const c=current.reviewers[who]?.cnv;
    if(!c||!cnvEnabled(who)) continue;
    const rail=who==='lead'?13:28;
    for(let lo=0;lo<current.width;) {
      if(!c.region[lo]){lo++;continue;}
      let hi=lo+1;while(hi<current.width&&c.region[hi])hi++;
      const x0=sx(lo-.5),x1=sx(hi-.5);
      g.save();g.fillStyle=cnvColors[who];g.globalAlpha=.10;
      g.fillRect(x0,0,x1-x0,h-23);g.globalAlpha=.85;
      g.strokeStyle=cnvColors[who];g.lineWidth=1;g.setLineDash([4,4]);
      g.beginPath();g.moveTo(x0,0);g.lineTo(x0,h-23);g.moveTo(x1,0);g.lineTo(x1,h-23);g.stroke();
      g.setLineDash([]);g.lineWidth=4;g.beginPath();g.moveTo(x0,rail);g.lineTo(x1,rail);g.stroke();
      g.font='11px system-ui';g.fillText(who+' CNV',Math.max(3,x0+4),rail+12);g.restore();
      lo=hi;
    }
  }
}
function drawCnvEdges(g, reviewers, sx, sy) {
  if(!$('cnvEdges').checked) return;
  for(const who of reviewers) {
    const r=current.reviewers[who],c=r?.cnv;
    if(!c||!cnvEnabled(who))continue;
    // Draw contiguous runs with a shared dash phase; never bridge erased gaps or states.
    for(let lo=0;lo<current.width;) {
      const z=c.edge[lo],code=cnvEdgeCode(c,lo);
      if(z==null||code===0||z<current.offset||z>current.offset+current.depth-1){lo++;continue;}
      let hi=lo+1;
      while(hi<current.width&&c.edge[hi]!=null&&cnvEdgeCode(c,hi)===code&&
            !!r.excluded[hi]===!!r.excluded[lo]&&c.edge[hi]>=current.offset&&c.edge[hi]<=current.offset+current.depth-1)hi++;
      g.save();g.globalAlpha=r.excluded[lo] ? .45 : 1;g.lineCap='round';
      g.setLineDash(code===2?[7,5]:code===3?[1,5]:[]);
      g.beginPath();
      if(hi===lo+1){g.moveTo(sx(lo-.4),sy(z-current.offset));g.lineTo(sx(lo+.4),sy(z-current.offset));}
      else {g.moveTo(sx(lo),sy(z-current.offset));for(let x=lo+1;x<hi;x++)g.lineTo(sx(x),sy(c.edge[x]-current.offset));}
      g.strokeStyle='#08111e';g.lineWidth=5;g.stroke();g.strokeStyle=cnvColors[who];g.lineWidth=2.7;g.stroke();g.restore();lo=hi;
    }
  }
}
function cnvHover(x) {
  return ['lead','shichu'].filter(who=>cnvEnabled(who)&&current.reviewers[who]?.cnv).map(who=>{
    const r=current.reviewers[who],c=r.cnv,z=c.edge[x];
    return `${who} CNV: ${c.region[x]?'inside region':'outside marked region'}; edge ${z==null?'—':fmt(z,1)+' px'}, ${cnvEdgeLabel(c,x)}${r.excluded[x]?'; image excluded':''}`;
  }).join(' | ');
}

// Hyper_Ref brush footprints are crop-relative raster pixels, unlike CNV edge depths.
const hyperCache = new WeakMap();
function hyperEnabled(who) { return $('hyper'+(who==='lead'?'Lead':'Shichu')).checked; }
function hyperSummary() {
  $('hyperStatus').innerHTML=['lead','shichu'].map(who=>{
    const r=current.reviewers[who],h=r?.hyper_ref;
    const message=!r?'No saved review':!h?'Dot data unavailable — refresh snapshot':
      `${esc(h.status)} · ${h.pixels? h.pixels.toLocaleString()+' painted pixels':'no dots marked'}`;
    return `<span><b style="color:${cnvColors[who]}">${who==='lead'?'Lead':'Shichu'}:</b> ${message}</span>`;
  }).join('<br>');
}
function hyperMaskCanvas(r, who) {
  const h=r.hyper_ref;
  if(hyperCache.has(h))return hyperCache.get(h);
  const [height,width]=h.shape,mask=new Uint8Array(height*width);
  for(const [lo,hi] of h.runs)mask.fill(1,lo,hi);
  const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
  const g=canvas.getContext('2d'),im=g.createImageData(width,height);
  const rgb=who==='lead'?[96,232,247]:[250,150,223];
  for(const [lo,hi] of h.runs)for(let p=lo;p<hi;p++) {
    const x=p%width,y=Math.floor(p/width);
    const edge=x===0||x===width-1||y===0||y===height-1||!mask[p-1]||!mask[p+1]||!mask[p-width]||!mask[p+width];
    im.data.set(rgb,p*4);im.data[p*4+3]=Math.round((edge?240:85)*(r.excluded[x] ? .45 : 1));
  }
  g.putImageData(im,0,0);hyperCache.set(h,canvas);return canvas;
}
function drawHyper(g, reviewers, sx, sy, w, h) {
  g.save();g.beginPath();g.rect(0,0,w,h-23);g.clip();g.imageSmoothingEnabled=false;
  for(const who of reviewers) {
    const r=current.reviewers[who];
    if(!hyperEnabled(who)||!r?.hyper_ref?.pixels)continue;
    const mask=hyperMaskCanvas(r,who);
    g.drawImage(mask,sx(-.5),sy(0),sx(current.width-.5)-sx(-.5),sy(current.depth)-sy(0));
  }
  g.restore();
}
