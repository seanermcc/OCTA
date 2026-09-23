"""Make actual changes visible without presenting unchanged pairs as corrections."""
from pathlib import Path
import json
import numpy as np
from PIL import Image

out=Path(__file__).resolve().parent
rows=json.loads((out/'results.json').read_text())
checks=[]
for row in rows:
    g=row['group']
    a=np.array(Image.open(out/g/'before.png'));b=np.array(Image.open(out/g/'after.png'))
    changed=np.any(a!=b,axis=2)
    checks.append(dict(group=g,identical=bool(np.array_equal(a,b)),changed_pixels=int(changed.sum()),
                       max_channel_difference=int(np.abs(a.astype(int)-b.astype(int)).max())))
    # Identical cyan channels verify that the target stays fixed in the overlay.
    assert np.array_equal(a[:,:,1:],b[:,:,1:])
    assert (row['selected']=='baseline')==np.array_equal(a,b)
(out/'DISPLAY_CHECK.json').write_text(json.dumps(checks,indent=2))
data=json.dumps([dict(group=r['group'],model=r['selected']) for r in rows if r['selected']!='baseline'])
unchanged=''.join(f'<li><b>{r["group"]}</b>: no correction applied. <a href="{r["group"]}/before.png">View original overlap</a> · <a href="{r["group"]}/OPEN_PAIR_IN_FIJI.ijm">Fiji helper</a></li>' for r in rows if r['selected']=='baseline')
page='''<!doctype html><html><head><meta charset="utf-8"><title>Warp changes · magnified comparison</title><style>
body{font:17px system-ui;background:#17232b;color:#eef5f8;margin:24px;max-width:1250px}a{color:#8ee3f2}button,select,input{font:inherit;padding:8px;margin:4px}button{cursor:pointer}canvas{width:min(100%,800px);height:auto;border:1px solid #71838d;cursor:crosshair;display:block;background:#000}#state{font-size:24px;font-weight:700;color:#ffd084}p{max-width:950px}li{margin:14px 0}.note{padding:14px;background:#2b3d49}label{display:inline-block}summary{cursor:pointer;padding:15px;background:#2b3d49}
</style></head><body><h1>What actually changed</h1>
<p class="note"><b>Only TS241 OD and TS247 OD were changed.</b> The six other “after” images in the previous page were identical to their “before” images. They are now listed separately below.</p>
<p>Choose a changed pair, then use <b>Play before/after</b> to alternate images in the same position. The cyan target stays fixed; the red moving image changes. Look for separated red/cyan vessel edges becoming aligned. A visible change does not by itself prove a better registration.</p>
<label>Changed pair <select id="group"><option>TS247_OD</option><option>TS241_OD</option></select></label>
<label>View <select id="mode"><option value="overlay">Red/cyan overlap</option><option value="moving">Moving image only</option></select></label>
<div><button id="before">Show BEFORE</button><button id="after">Show AFTER</button><button id="play">Play before/after</button></div>
<label>Zoom <select id="zoom"><option value="1">1× whole image</option><option value="2" selected>2×</option><option value="3">3×</option></select></label>
<label>Horizontal <input id="cx" type="range" min="0" max="512" value="256"></label>
<label>Vertical <input id="cy" type="range" min="0" max="512" value="320"></label>
<p id="state">AFTER · TS247 OD · 2×</p><canvas id="view" width="800" height="800" aria-label="Magnified before and after image"></canvas>
<p id="detail"></p><p>Use the position sliders to inspect different vessels. Both frames use the same crop, brightness and magnification. Nothing here saves or approves a correction.</p>
<details><summary>Six unchanged pairs — no before/after difference expected</summary>UNCHANGED</details>
<p><a href="REPORT.md">Full measurements, limitations and Fiji instructions</a></p>
<script>
const records=DATA;let after=true,timer=null;const cache={};const $=s=>document.getElementById(s);const context=$('view').getContext('2d');
for(const r of records){cache[r.group]={};for(const [key,file] of Object.entries({before:'before.png',after:'after.png',rawBefore:'manual_moving.tif',rawAfter:'proposed_moving.tif'})){if(key.startsWith('raw'))continue;const im=new Image();im.onload=draw;im.src=r.group+'/'+file;cache[r.group][key]=im}}
function draw(){const g=$('group').value,im=cache[g][after?'after':'before'];if(!im.complete||!im.naturalWidth)return;const zoom=+$('zoom').value,size=512/zoom,x=Math.max(0,Math.min(512-size,+$('cx').value-size/2)),y=Math.max(0,Math.min(512-size,+$('cy').value-size/2));context.drawImage(im,x,y,size,size,0,0,800,800);if($('mode').value==='moving'){const pixels=context.getImageData(0,0,800,800);for(let i=0;i<pixels.data.length;i+=4)pixels.data[i+1]=pixels.data[i+2]=pixels.data[i];context.putImageData(pixels,0,0)}$('state').textContent=(after?'AFTER':'BEFORE')+' · '+g.replace('_',' ')+' · '+zoom+'×';$('detail').textContent=g==='TS247_OD'?'TS247 OD: affine + smooth local warp. Median reserved-match error 26.4 → 1.0 px. Draft only.':'TS241 OD: affine correction. Median reserved-match error 17.1 → 3.0 px. Draft only.'}
function stop(){clearInterval(timer);timer=null;$('play').textContent='Play before/after'}
$('before').onclick=()=>{stop();after=false;draw()};$('after').onclick=()=>{stop();after=true;draw()};$('play').onclick=()=>{if(timer){stop();return}timer=setInterval(()=>{after=!after;draw()},900);$('play').textContent='Pause'};
for(const id of ['group','mode','zoom','cx','cy'])$(id).oninput=draw;document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});draw();
</script></body></html>'''.replace('UNCHANGED',unchanged).replace('DATA',data)
(out/'index.html').write_text(page,encoding='utf-8')
print(json.dumps(checks,indent=2))
