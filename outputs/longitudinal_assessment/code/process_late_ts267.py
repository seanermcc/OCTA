"""Use the companion processing slot after TS328; scan locks protect overlap."""
from pathlib import Path
import os
import subprocess
import sys
import time
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'code'))
from longitudinal_assessment import OUT, initialize, read, write

while read(OUT/'ts328_status.json')['status'] != 'complete':
    if (OUT/'COMPLETE.json').exists(): sys.exit(0)
    time.sleep(10)
for sid in [s for s in initialize()['scans'] if s.startswith('TS267_') and '_D98_' in s]:
    for action in ('prepare', 'infer', 'export', 'verify'):
        write(OUT/'late_ts267_status.json', dict(scan=sid, stage=action, status='running'))
        print(action, sid, flush=True)
        subprocess.run([sys.executable, str(Path(__file__).with_name('longitudinal_assessment.py')), action, '--scan', sid], check=True)
write(OUT/'late_ts267_status.json', dict(status='complete', scans=2))
