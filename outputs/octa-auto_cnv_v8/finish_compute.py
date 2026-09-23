"""Run only the remaining frozen comparison steps after both fixed fits finish."""
from common import *
import subprocess,threading
def run():
    required=[HERE/'data/inputs.json',HERE/'model1/complete.json',HERE/'model2/complete.json']
    deadline=time.time()+4*3600
    while not all(p.exists() for p in required):
        failed=[p for p in (HERE/'model1/FAILED.json',HERE/'model2/FAILED.json') if p.exists()]
        if failed:raise RuntimeError('Training stopped: '+str(failed))
        if time.time()>deadline:raise TimeoutError('Full preparation or fixed fits not complete')
        time.sleep(5)
    def execute(name,*args):subprocess.run([sys.executable,'-B',str(HERE/name),*args],check=True,cwd=HERE)
    execute('predict.py','--model','2')
    execute('preservation.py','--after')
    execute('finalize.py')
    execute('figures.py')
    from viewer import ThreadingHTTPServer,Handler
    from viewer_checks import run as check_viewer
    server=ThreadingHTTPServer(('127.0.0.1',8768),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:check_viewer()
    finally:server.shutdown();server.server_close();thread.join()
    write(HERE/'READY_FOR_BROWSER_QA.json',dict(complete=True,comparison_cases=30,all_http_checks_passed=True))
    progress('Compute and all-case API verification complete; browser QA ready')
if __name__=='__main__':
    try:run()
    except Exception as e:write(HERE/'FINISH_FAILED.json',dict(error=repr(e),time=time.time()));raise
