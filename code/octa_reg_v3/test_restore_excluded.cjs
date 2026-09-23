// Exercise the shipped restoration functions without touching a real review.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
for (const version of ['v2','v3']) {
  const source = fs.readFileSync(`code/octa_reg_${version}/cohort_viewer.js`, 'utf8');
  const fn = source.slice(source.indexOf('function restoreExcluded('), source.indexOf('function choose('));
  const fixture = () => {
    const m = [[0,-1,350],[1,0,20],[0,0,1]];
    const s={scan_id:'restored',tier:'supported',day_label:'d7'};
    const els={'#uncertainToggle':{checked:false}}, day={dataset:{day:'d7'},checked:false};
    const review={fields:{restored:{matrix_to_onh_pixels:m,status:'confirmed'},other:{matrix_to_onh_pixels:[[1,0,40],[0,1,80],[0,0,1]],status:'confirmed'}},decisions:{restored:{tier:'excluded',notes:'keep note'}},montage_confirmed:true,onh_override:[17,19]};
    const c={ready:true,review,s,S:{canvas_origin:[100,200]},zoom:2,pan:[10,20],enabledDays:new Set(),tool:'pan',saved:0,
      C:{getBoundingClientRect:()=>({width:800,height:600})},document:{querySelectorAll:()=>[day]},$:s=>els[s],
      clone:x=>JSON.parse(JSON.stringify(x)),tier:s=>review.decisions[s.scan_id]?.tier||s.tier,
      pose:s=>review.fields[s.scan_id]?.matrix_to_onh_pixels,
      apply:(m,p)=>[m[0][0]*p[0]+m[0][1]*p[1]+m[0][2],m[1][0]*p[0]+m[1][1]*p[1]+m[1][2]],
      mutate:f=>{f();c.saved++;},setPose:(s,m)=>{review.fields[s.scan_id]={matrix_to_onh_pixels:m,status:'draft'};review.montage_confirmed=false;},
      choose:()=>{},updateTool:()=>{},fit:()=>{},draw:()=>{},saveMessage:()=>{}};
    vm.createContext(c);vm.runInContext(fn,c);return c;
  };
  let c=fixture(), prior=JSON.stringify(c.review.fields.other), m=JSON.stringify(c.review.fields.restored.matrix_to_onh_pixels);
  c.restoreExcluded(c.s);
  assert.equal(JSON.stringify(c.review.fields.restored.matrix_to_onh_pixels),m);
  assert.equal(c.review.decisions.restored.tier,'uncertain');assert.equal(c.review.decisions.restored.notes,'keep note');
  assert.equal(c.review.fields.restored.status,'draft');assert.equal(c.review.montage_confirmed,false);
  assert.equal(JSON.stringify(c.review.fields.other),prior);assert.deepEqual(c.review.onh_override,[17,19]);
  assert(c.enabledDays.has('d7'));assert.equal(c.tool,'move');assert.equal(c.saved,1);
  c=fixture();c.restoreExcluded(c.s,[700,800]);
  assert.deepEqual(c.apply(c.review.fields.restored.matrix_to_onh_pixels,[256,256]),[600,600]);
  assert.equal(c.review.fields.restored.matrix_to_onh_pixels[0][1],-1);
  c=fixture();c.s.tier='excluded';m=JSON.stringify(c.review);c.restoreExcluded(c.s,[700,800]);
  assert.equal(JSON.stringify(c.review),m);assert.equal(c.saved,0);
  c=fixture();delete c.review.fields.restored;c.restoreExcluded(c.s);
  assert.deepEqual(c.apply(c.review.fields.restored.matrix_to_onh_pixels,[256,256]),[95,-60]);
  c=fixture();c.ready=false;c.restoreExcluded(c.s);assert.equal(c.saved,0);
  console.log(version+': restore, drop geometry, rotation, notes, confirmations, ONH, filters, source lock, unplaced and readiness checks passed');
}
