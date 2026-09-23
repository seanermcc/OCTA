"""Resumable complete compute stage. Release lock is released by OS on crash."""
from common import *
from audit import freeze
from prepare import run as prepare
from training import train,predict
def run():
 m=freeze()
 from novelty_supplement import run as complete_novelty
 complete_novelty();prepare();protocol=read(HERE/'data/protocol.json');records=m['records']
 for f in protocol['folds']:
  ev=[r['acquisition'] for r in records if r['animal'] in f['evaluation_animals']]
  for model in (1,2):
   name=f"outer{f['fold']}_m{model}";train(name,model,f['train_animals']);predict(name,ev)
  for j,inner in enumerate(f['inner']):
   name=f"outer{f['fold']}_inner{j}_m2";train(name,2,inner['train_animals']);predict(name,[r['acquisition'] for r in records if r['animal'] in inner['candidate_animals']])
 for model in (1,2):
  name=f'final_m{model}';train(name,model,m['animals']);predict(name,read(HERE/'data/selection.json')['acquisitions'])
 write(HERE/'COMPUTE_COMPLETE.json',dict(at=time.time(),fits=14,selected=len(read(HERE/'data/selection.json')['acquisitions'])))
if __name__=='__main__':
 try:
  with RunLock():run()
 except Exception as e:
  write(HERE/'COMPUTE_FAILED.json',dict(error=repr(e),at=time.time()));raise
