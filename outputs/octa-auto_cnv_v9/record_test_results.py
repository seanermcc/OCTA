from common import *
import subprocess
results=[]
for name in ('test_core.py','test_candidates.py','test_loss.py'):
 r=subprocess.run('call "D:\\Anaconda\\Scripts\\activate.bat" octa && python -B "'+str(HERE/name)+'"',shell=True,cwd=HERE,capture_output=True,text=True,env=dict(os.environ,PYTHONIOENCODING='utf-8'))
 results.append(dict(test=name,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr,source=fingerprint(HERE/name)))
 if r.returncode:write(HERE/'verification/SYNTHETIC_TESTS.json',dict(passed=False,results=results));raise RuntimeError(name+' failed')
write(HERE/'verification/SYNTHETIC_TESTS.json',dict(passed=True,tests=10,results=results))
print('Recorded 10 passing synthetic tests')
