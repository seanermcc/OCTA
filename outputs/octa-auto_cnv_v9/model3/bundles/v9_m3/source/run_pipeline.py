from common import *
from freeze_inputs import run as freeze
from prepare import prepare_case
from training import train,predict
from candidates import make_examples
import shutil,torch,subprocess

def prepare(a):
 sid=a['scan_id'];old=HERE.parent/'cache'/sid
 if old.exists() and not (HERE/'cache'/sid).exists():
  # Copy derived immutable arrays only. Human annotation providers stay read-only.
  shutil.copytree(old,dest(HERE/'cache'/sid))
 return prepare_case(a)

def run():
 # Preserve the inference backend policy even when every fit is reused on resume.
 torch.backends.cudnn.benchmark=False
 torch.backends.cudnn.deterministic=True
 with RunLock():
  m=freeze();protocol=read(HERE/'data/protocol.json');acquisitions=read(HERE/'data/selection.json')['acquisitions']
  for i,r in enumerate(m['records']):
   prepare(r['acquisition'])
   progress('Prepare training inputs',completed=i+1,total=len(m['records']))
  train('final_m3',2,m['animals'])
  examples=[]
  for f in protocol['folds']:
   name=f"scorer_fold{f['fold']}";ev=[r for r in m['records'] if r['animal'] in f['evaluation_animals']]
   train(name,2,f['train_animals']);predict(name,[r['acquisition'] for r in ev]);examples+=make_examples(name,ev)
  write(HERE/'development/scorer_examples.json',dict(records=examples))
  # Fit CPU BLAS in a separate interpreter: torch and this environment's
  # scientific stack load different OpenMP runtimes into a shared process.
  subprocess.run([sys.executable,'-B',str(HERE/'fit_candidate_scorer.py')],check=True)
  for i,a in enumerate(acquisitions):
   prepare(a)
   progress('Prepare full cohort',completed=i+1,total=len(acquisitions))
  predict('final_m3',acquisitions)
  # Frozen parent model, copied only for the comparison runner; no re-training.
  parent=HERE.parent/'fits/final_m2';target=HERE/'fits/parent_m2'
  for name in ('complete.json','normalization.json'):
   if not (target/name).exists():shutil.copyfile(parent/name,dest(target/name))
  predict('parent_m2',acquisitions)
  write(HERE/'COMPUTE_COMPLETE.json',dict(training_acquisitions=101,positive=73,negative=28,regions=156,inference_acquisitions=len(acquisitions),models=['v9_m2','v9_m3']))
  from publish import run as publish
  publish()

if __name__=='__main__':run()
