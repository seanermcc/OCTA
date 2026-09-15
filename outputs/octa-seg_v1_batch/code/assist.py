"""Second CPU lane, opposite scan order; one shared GPU and per-scan locks."""
from batch import *
from qc import aggregate
check_dependencies();m=manifest();logs=OUT/'logs';logs.mkdir(exist_ok=True)
write(OUT/'assistant_runner.json',dict(pid=os.getpid(),started=time.time(),order='reverse',gpu_workers=1))
for i,r in enumerate(reversed(m['scans'])):
    sid=r['scan_id']
    if (directory(sid)/'qc_complete.json').exists():continue
    for action in ('prepare','infer','export','qc'):
        write(OUT/'assistant_status.json',dict(status='running',scan=sid,stage=action,number=i+1,total=len(m['scans'])))
        print('Second CPU lane',i+1,action,sid,flush=True)
        logpath=logs/f'{sid}_{action}.log'
        with logpath.open('a',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,'-u',str(Path(__file__).with_name('batch.py')),action,'--scan',sid],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            write(OUT/'failures'/f'{sid}.json',dict(scan_id=sid,stage=action,exit_code=result.returncode,log=str(logpath),investigated=False));break
    else:(OUT/'failures'/f'{sid}.json').unlink(missing_ok=True)
    aggregate()
aggregate()
from ratings import compare
compare()
write(OUT/'assistant_status.json',dict(status='finished'))
