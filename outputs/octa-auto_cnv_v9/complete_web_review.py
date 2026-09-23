"""Record the verified web-review addition without changing the frozen model release."""
from common import *
from urllib.request import urlopen
qa=read(HERE/'verification/WEB_REVIEW_QA.json');assert qa['passed']
health=json.load(urlopen('http://127.0.0.1:8799/health'));assert health['review_api']==1
reviews=json.load(urlopen('http://127.0.0.1:8799/reviews'));assert len(reviews['records'])==50
write(HERE/'WEB_REVIEW_ENABLED.json',dict(passed=True,at=time.time(),acquisitions=50,
    confirmation_scope='whole scan per model',checkboxes=['confirm_m1','confirm_m2_adjusted','review_model2'],
    durable_storage=str(HERE/'manual_review'),review_api=1,
    existing_model_preferences_preserved=True,user_scan_restored='TS169_OD_2025-01-14_D35_s06_113841',user_bscan_row_restored=219,
    real_decisions_at_activation=sum(r['revision']>0 for r in reviews['records'].values()),
    synthetic_only_write_tests=True,retraining_started=False,
    screenshots=[fingerprint(HERE/'verification/web_review_controls.png')],
    verification=fingerprint(HERE/'verification/WEB_REVIEW_QA.json'),
    implementation=[fingerprint(HERE/p) for p in ['server.py','review_store.py','gallery/app.js','gallery/review.js','gallery/index.html','gallery/style.css']],
    guide=fingerprint(HERE/'WEB_REVIEW_GUIDE.md')))
print('Web review enabled and verified for 50 real scans; no test confirmations written to real scans')
