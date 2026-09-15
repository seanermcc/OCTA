"""Bounded companion worker; does not alter the full group's completion status."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'code'))
from longitudinal_assessment import OUT, initialize, write

for sid in [s for s in initialize()['scans'] if s.startswith('TS328_')]:
    for action in ('prepare', 'infer', 'export', 'verify'):
        write(OUT/'ts328_status.json', dict(scan=sid, stage=action, status='running'))
        print(action, sid, flush=True)
        subprocess.run([sys.executable, str(Path(__file__).with_name('longitudinal_assessment.py')), action, '--scan', sid], check=True)
write(OUT/'ts328_status.json', dict(status='complete', scans=5))
