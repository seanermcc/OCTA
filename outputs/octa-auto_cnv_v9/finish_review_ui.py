"""Add correction-list navigation and update the user entry guide."""
from common import *
p=HERE/'gallery/index.html';s=p.read_text(encoding='utf8')
if 'value="review_m2"' not in s:s=s.replace('<option value="hidden">Down-ranked candidates</option>','<option value="hidden">Down-ranked candidates</option><option value="review_m2">Review Model 2 flags</option>')
p.write_text(s,encoding='utf8')
p=HERE/'gallery/app.js';s=p.read_text(encoding='utf8')
s=s.replace("$('filter').value==='zero'?", "$('filter').value==='review_m2'?!!reviewRecords[a.scan_id]?.review_model2:$('filter').value==='zero'?",1) if "$('filter').value==='review_m2'" not in s else s
p.write_text(s,encoding='utf8')
p=HERE/'START_HERE.md';s=p.read_text(encoding='utf8')
if 'WEB_REVIEW_GUIDE' not in s:s=s.replace('Double-click **OPEN_GALLERY.cmd**.','Double-click **OPEN_GALLERY.cmd**. The preview now includes disk-saved **Confirm Model 1**, **Confirm Model 2 adjusted**, and **Review Model 2** checkboxes. See **WEB_REVIEW_GUIDE.md** for their meaning and the next training/audit plan.',1)
s=s.replace('No model has been chosen, and no correction GUI or new correction round has been started.','No model has been chosen. The web confirmation round is enabled; correction flags are saved for a later GUI queue. Retraining never starts automatically.')
p.write_text(s,encoding='utf8')
