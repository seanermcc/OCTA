// Offline execution check for the generated HTML; no browser or network access.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const folder = process.argv[2];
const html = fs.readFileSync(path.join(folder, 'v1_manual_v2.html'), 'utf8');
const nodes = {};
for (const match of html.matchAll(/<([\w-]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)) {
  const [tag, kind, id] = match;
  nodes[id] = {value:tag.match(/\bvalue="([^"]*)"/)?.[1] || '', checked:/\bchecked\b/.test(tag),
    style:{}, classList:{toggle(){},add(){}}, dataset:{}, textContent:'',innerHTML:'',
    addEventListener(event, fn){this[event]=fn;}, showModal(){this.open=true;},close(){this.open=false;}};
  if (kind === 'select') nodes[id].value = html.slice(match.index).match(/<option value="([^"]+)"/)?.[1];
}
const saved = {};
const context = vm.createContext({window:{},document:{getElementById:id=>nodes[id],
  body:{classList:{toggle(){}}},documentElement:{style:{setProperty(){}}}},
  localStorage:{getItem:key=>saved[key]||null,setItem:(key,value)=>saved[key]=value},setTimeout(){}});
vm.runInContext(fs.readFileSync(path.join(folder, 'manual-gallery-data.js'),'utf8'), context);
vm.runInContext(html.match(/<script>\s*([\s\S]*?)<\/script>/)[1], context);
const records = context.window.RELEASE.items;
const cards = () => [...nodes.grid.innerHTML.matchAll(/<article\b[\s\S]*?<\/article>/g)].map(m=>m[0]);
assert.equal(cards().length,314);
assert.deepEqual([...nodes.grid.innerHTML.matchAll(/<h2[^>]*>(.*?)<\/h2>/g)].map(m=>m[1].match(/(\d+) scans/)[1]), ['58','27','229']);
for (const card of cards()) {
  const sid = card.match(/data-scan="([^"]+)"/)[1];
  const record = records.find(i=>i.scan_id===sid);
  const panels = [...card.matchAll(/class="view-label">([^<]+)</g)].map(m=>m[1].split(' · ')[0]);
  assert.deepEqual(panels, record.manual?['v1','Manual','v2']:['v1','v2']);
}
nodes.filter.value='pending'; nodes.filter.onchange(); assert.equal(cards().length,27);
assert(cards().every(c=>!c.includes('Manual · latest')));
nodes.filter.value='manual'; nodes.filter.onchange(); assert.equal(cards().length,58);
nodes.search.value='TS165_OS_2025-04-29_WT_s06_123911'; nodes.search.oninput(); assert.equal(cards().length,1);
nodes.search.value='no-such-scan'; nodes.search.oninput(); assert.equal(cards().length,0);
nodes.search.value=''; nodes.filter.value='excluded'; nodes.filter.onchange(); assert.equal(cards().length,2);
assert(cards().every(c=>c.includes('Excluded — no prediction')));
nodes.filter.value='all'; nodes.filter.onchange();
const archived = fs.readFileSync(path.join(folder,'index_archived_20260915.html'),'utf8');
assert(!/Final model|New model|new model|final model/.test(archived));
assert(archived.includes('v2 · all eligible labels'));
console.log('PASS: 314 cards; 58 triple / 256 double panels; group order 58 / 27 / 229; filters, search, exclusions, archived v2 naming.');
