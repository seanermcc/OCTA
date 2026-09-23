"""Continuation of this compute job; publish only after all 14 scheduled fits finish."""
from common import *
import subprocess
def run():
 while not (HERE/'COMPUTE_COMPLETE.json').exists():
  if (HERE/'COMPUTE_FAILED.json').exists():raise RuntimeError('Compute stage failed; inspect COMPUTE_FAILED.json')
  time.sleep(10)
 for args in ['freeze_scoring.py','deliver.py','verify_release.py --final','verify_controlled_comparison.py']:
  subprocess.run('call "D:\\Anaconda\\Scripts\\activate.bat" octa && python -B '+args,shell=True,cwd=HERE,check=True)
 write(HERE/'AUTOMATED_STAGES_COMPLETE.json',dict(at=time.time(),training_delivery_data_checks=True,browser_final_qa_pending=True))
if __name__=='__main__':
 try:run()
 except Exception as exc:write(HERE/'FINALIZATION_FAILED.json',dict(error=repr(exc),at=time.time()));raise
