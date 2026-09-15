"""Durable two-lane batch supervisor; one GPU, final audit and safe resumption."""
from batch import *
from concurrent.futures import ThreadPoolExecutor,as_completed
from qc import aggregate

def process(r):
    sid=r['scan_id'];logs=OUT/'logs';logs.mkdir(exist_ok=True)
    actions=['qc'] if (directory(sid)/'qc_complete.json').exists() else ['prepare','infer','export','qc']
    for action in actions:
        t=time.time();print(action,sid,flush=True)
        logpath=logs/f'{sid}_{action}.log'
        with logpath.open('a',encoding='utf-8') as log:
            code=subprocess.run([sys.executable,'-u',str(Path(__file__).with_name('batch.py')),action,'--scan',sid],stdout=log,stderr=subprocess.STDOUT).returncode
        write(OUT/'stage_timings'/f'{sid}_{action}.json',dict(scan_id=sid,stage=action,started=t,elapsed_s=time.time()-t,returncode=code))
        if code:
            failure=dict(scan_id=sid,stage=action,exit_code=code,log=str(logpath),investigated=False)
            write(OUT/'failures'/f'{sid}.json',failure);return failure
    (OUT/'failures'/f'{sid}.json').unlink(missing_ok=True)
    return None

def main():
    import msvcrt
    lock=OUT/'locks/supervisor.lock';lock.parent.mkdir(exist_ok=True)
    with lock.open('a+b') as f:
        if f.tell()==0:f.write(b'0');f.flush()
        f.seek(0)
        try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:print('Batch supervisor is already running. No duplicate launched.');return
        write(OUT/'supervisor.json',dict(pid=os.getpid(),started=time.time(),status='running',cpu_lanes=2,gpu_lanes=1))
        check_dependencies();m=manifest();todo=m['scans']
        for attempt in range(2):
            failures=[]
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures={pool.submit(process,r):r for r in todo}
                for future in as_completed(futures):
                    r=futures[future]
                    try:failure=future.result()
                    except Exception:
                        log=OUT/'logs'/f'{r["scan_id"]}_supervisor.log';log.write_text(traceback.format_exc(),encoding='utf-8');failure=dict(scan_id=r['scan_id'],stage='supervisor',exit_code=1,log=str(log),investigated=False);write(OUT/'failures'/f'{r["scan_id"]}.json',failure)
                    if failure:failures.append(r)
                    aggregate();counts=read(OUT/'counts.json');write(OUT/'supervisor.json',dict(pid=os.getpid(),status='running',attempt=attempt+1,**counts));print(counts,flush=True)
            if not failures:break
            todo=failures
        aggregate()
        from ratings import compare
        compare()
        if read(OUT/'counts.json')['completed']==len(m['scans']):
            from final_audit import audit
            audit()
        write(OUT/'supervisor.json',dict(pid=os.getpid(),status='complete' if (OUT/'FINAL_VERIFIED.json').exists() else 'needs_failure_investigation',**read(OUT/'counts.json')))

if __name__=='__main__':main()
