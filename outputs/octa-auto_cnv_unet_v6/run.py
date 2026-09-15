"""Reproducible bounded pilot; stop on failed preflight and resume checkpoints."""
from common import *
import subprocess

def run():
    for script in ['dataset.py','verify.py','source_check.py','train.py','evaluate.py','seed_sensitivity.py','patterns.py','report.py','verify_release.py','finalize.py']:
        progress('Running stage',script=script)
        result=subprocess.run([sys.executable,'-u',str(HERE/script)],cwd=HERE)
        if result.returncode:
            progress('Stage failed',script=script,returncode=result.returncode)
            raise SystemExit(result.returncode)
    progress('Pilot complete')

if __name__=='__main__':run()
