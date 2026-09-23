"""python -m control_map_v1 init|run|test|audit-figures"""
import argparse
import os
from pathlib import Path
import time
# Keep the activated environment's native math runtime on the DLL search path.
_dll_handles=[]
if os.name=="nt" and os.environ.get("CONDA_PREFIX"):
    folder=Path(os.environ["CONDA_PREFIX"])/"Library/bin"
    _dll_handles.append(os.add_dll_directory(str(folder)))
    os.environ["PATH"]=str(folder)+os.pathsep+os.environ.get("PATH","")
from .pipeline import DEFAULT_OUT,DEFAULT_BATCH,initialize,run
from .io import write


def main():
    parser=argparse.ArgumentParser(description="Preliminary read-only ONH-centered atlas")
    parser.add_argument("command",choices=["init","run","test","audit-figures"])
    parser.add_argument("--output",type=Path,default=DEFAULT_OUT)
    parser.add_argument("--batch",type=Path,default=DEFAULT_BATCH)
    parser.add_argument("--wait",action="store_true",help="Wait for FINAL_VERIFIED.json before analysis")
    parser.add_argument("--skip-batch-audit",action="store_true",
                        help="User-authorized cohort audit skip; retain per-export integrity checks")
    args=parser.parse_args()
    if args.command=="init":initialize(args.output,args.batch);return
    if args.command=="test":
        import unittest
        suite=unittest.defaultTestLoader.discover(str(Path(__file__).parent),pattern="test_*.py",top_level_dir=str(Path(__file__).parent.parent))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        initialize(args.output,args.batch)
        write(args.output/"qc/implementation_tests.json",dict(passed=result.wasSuccessful(),tests=result.testsRun,
              failures=len(result.failures),errors=len(result.errors),scope="synthetic algorithm and contract tests; not cohort scientific validation"))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    if args.command=="audit-figures":
        from .figures import audit_figures
        audit_figures(args.output);return
    initialize(args.output,args.batch)
    # Exclusive create prevents two workers from racing atomic stages or figures.
    lock=args.output/"logs/atlas.lock"
    try:
        with lock.open("x") as f:f.write(str(os.getpid()))
    except FileExistsError:raise SystemExit(f"Atlas lock exists ({lock}); inspect the recorded PID before removing a stale lock.")
    try:
        if args.wait and not args.skip_batch_audit:
            while not (args.batch/"FINAL_VERIFIED.json").exists():
                write(args.output/"logs/run_status.json",dict(status="awaiting_verified_batch",pid=os.getpid(),checked=time.time(),batch=str(args.batch)))
                time.sleep(30)
        run(args.output,args.batch,skip_batch_audit=args.skip_batch_audit)
    except Exception as exc:
        waiting=isinstance(exc,RuntimeError) and str(exc).startswith("Waiting for batch verification:")
        write(args.output/"logs/run_status.json",dict(status="awaiting_verified_batch" if waiting else "failed",error=str(exc),pid=os.getpid(),time=time.time()))
        if waiting:raise SystemExit(str(exc))
        raise
    finally:lock.unlink(missing_ok=True)


if __name__=="__main__":main()
