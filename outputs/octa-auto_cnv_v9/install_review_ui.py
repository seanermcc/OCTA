"""Apply the isolated review controls to the existing gallery."""
from common import *

p=HERE/'gallery/index.html';s=p.read_text(encoding='utf8')
section='''<section class="confirmation" aria-label="CNV confirmation">
<h2>Confirm this scan</h2>
<p>Check the whole scan for missing or extra CNVs and outline errors. Zero candidates confirms no CNV. Model 2 confirmation applies to the adjusted set, even when hidden raw candidates are recovered.</p>
<div class="confirmation-options">
<label><input id="confirmM1" type="checkbox" disabled>Confirm Model 1 CNVs</label>
<label><input id="confirmM2" type="checkbox" disabled>Confirm Model 2 adjusted CNVs</label>
<label><input id="reviewM2" type="checkbox" disabled>Review Model 2</label>
</div>
<p>“Review Model 2” flags this scan for GUI correction and clears its Model 2 confirmation. Unchecked means unconfirmed.</p>
<input id="reviewNotes" maxlength="4000" placeholder="Optional correction notes (saved when you leave the field)" aria-label="CNV review notes" disabled>
<span id="reviewSaved" role="status" aria-live="polite">Loading saved review…</span>
<p id="reviewConflict"></p><p id="reviewProgress"></p>
<details><summary>Export review decisions</summary><button id="exportReviews">Export confirmations JSON</button><button id="exportReviewQueue">Export Model 2 correction list</button><p>Decisions save automatically to disk. Confirmation and correction flags do not start training.</p></details>
</section>
'''
if 'id="confirmM1"' not in s:
 s=s.replace('<div class="controls">',section+'<div class="controls">',1)
 s=s.replace('<script src="app.js"></script>','<script src="review.js"></script><script src="app.js"></script>')
 p.write_text(s,encoding='utf8')
p=HERE/'gallery/app.js';s=p.read_text(encoding='utf8')
if 'initReview();' not in s:
 s=s.replace("if(!visible.length){$('identity')","if(!visible.length){clearReview();$('identity')")
 s=s.replace("async function load(sid){let mine=++token;","async function load(sid){clearReview();let mine=++token;")
 s=s.replace("buildOverlays();table();draw();await loadBscan();","buildOverlays();table();draw();openReview(sid);await loadBscan();")
 s+='\ninitReview();\n'
 p.write_text(s,encoding='utf8')
p=HERE/'gallery/style.css';s=p.read_text(encoding='utf8')
if '.confirmation-options' not in s:
 s+='''\n.confirmation{padding:14px 16px;background:#142738;border:1px solid #416379;border-radius:8px;margin:12px 0}
.confirmation p{font-size:12px;max-width:1050px}.confirmation-options{display:flex;flex-wrap:wrap;gap:12px 24px;margin:12px 0}.confirmation-options label{font-size:14px;font-weight:600}.confirmation input[type=checkbox]{width:18px;height:18px;accent-color:#8de1bf}.confirmation input[type=text],#reviewNotes{width:min(100%,620px);margin:8px 10px 5px 0}#reviewSaved{font-size:12px;color:#9fdfbe}#reviewConflict{color:#ffd166}#reviewProgress{color:#c4dbe9}.confirmation details{max-width:none;margin-top:8px}.confirmation details button{margin:8px 8px 0 0}input:disabled{opacity:.6;cursor:wait}\n'''
 p.write_text(s,encoding='utf8')
print('Review controls installed')
