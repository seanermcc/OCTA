"""Two independent numerical workers; atomic per-acquisition records and locks."""
from common import *
import subprocess
jobs=[]
for worker in range(2):
    log=dest(HERE/f'worker_{worker}.log').open('a',encoding='utf-8')
    jobs.append((subprocess.Popen([sys.executable,'-B','-u',str(HERE/'batch.py'),'--worker',str(worker),'--workers','2'],cwd=HERE,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0),log))
codes=[]
for process,log in jobs:codes.append(process.wait());log.close()
from batch import status
status(read(HERE/'inventory.json'))
raise SystemExit(max(codes))
