"""Run/resume this exact release, with a Windows exclusive process lock."""
import argparse,msvcrt,os,traceback
from common import *

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',nargs='?',default='all',choices=['all','audit','train','infer','report','gallery','verify'])
    args=parser.parse_args()
    lock=(HERE/'run.lock').open('a+b')
    lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise RuntimeError('A release runner is already active; do not launch a second copy')
    try:
        steps=['audit','train','infer','report','gallery','verify','report'] if args.stage=='all' else [args.stage]
        for stage in steps:
            if stage=='audit':from audit import main as call
            elif stage=='train':from training import main as call
            elif stage=='infer':from inference import main as call
            elif stage=='report':from report import main as call
            elif stage=='gallery':from gallery import main as call
            else:from verify import main as call
            call()
        progress('complete' if args.stage=='all' else args.stage+'_finished')
    except Exception as exc:
        # Make the storage stop visible even when the conservative reserve prevents regular writes.
        state=dict(stage='stopped',updated=now(),error=str(exc),resume='RUN_OR_RESUME.cmd',traceback=traceback.format_exc())
        try:write_json(HERE/'progress.json',state)
        except Exception:print(json.dumps(state),flush=True)
        raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
