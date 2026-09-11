"""Single-process resumable release runner. Completed versions are immutable."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from .common import *

def verify_completed():
    manifest=json.loads((OUT/"COMPLETE.json").read_text())
    for fp in manifest["artifacts"]:verify(fp)
    print("Completed octa-seg_v1 artifacts verified; no retraining or overwrite.",flush=True)

def activated(args,env,**kwargs):
    # Fresh activation in each child also retains the environment's DLL search
    # setup. Use the lab's supported Command Prompt entry point consistently.
    command="call D:\\Anaconda\\Scripts\\activate.bat octa && "+subprocess.list2cmdline(["python",*args])
    return subprocess.run(["cmd","/d","/c",command],env=env,cwd=ROOT,**kwargs)

def run(finalize=False):
    OUT.mkdir(parents=True,exist_ok=True)
    lock=(OUT/"run.lock").open("a+b")
    lock.seek(0);lock.write(b"0");lock.flush();lock.seek(0)
    import msvcrt
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise RuntimeError("An octa-seg_v1 release runner is already active; inspect progress.json before resuming")
    try:
        if (OUT/"COMPLETE.json").exists():verify_completed();return
        prepared=(OUT/"READY_TO_FINALIZE.json").exists()
        env=os.environ.copy();env["PYTHONPATH"]=str(ROOT/"code")
        env["OMP_NUM_THREADS"]="1";env["MKL_NUM_THREADS"]="1"
        stages=[("audit",[]),("train",[]),("predict",["labels"]),("evaluate",[]),("predict",["volumes"]),
                ("export",[]),("queue",[]),("report",[]),("verify_neural",[]),("verify",[]),("verify_gui",[])]
        if prepared:stages=[]
        for module,args in stages:
            if module=="audit" and (OUT/"data/manifest.json").exists():continue
            if module=="train" and len(list((OUT/"models").glob("*/complete.json")))==5:continue
            if module=="predict" and args==["labels"]:
                count=len(json.loads((OUT/"data/manifest.json").read_text())["records"])
                if len(list((OUT/"predictions/labels").glob("*/*/*.npz")))==count*10:continue
            if module=="evaluate" and (OUT/"evaluation/complete.json").exists():continue
            if module=="predict" and args==["volumes"] and len(list((OUT/"volumes").glob("*/neural_complete.json")))==4:continue
            if module=="export" and (OUT/"reports/volumes.json").exists():continue
            if module=="queue" and (OUT/"review_packs/queue.json").exists():continue
            if module=="report" and (OUT/"START_HERE.md").exists() and (OUT/"IMPLEMENTATION.md").exists():continue
            progress("release runner",module=module)
            activated(["-m",f"octa_seg_v1.{module}",*args],env,check=True)
        directory(OUT/"verification")
        for name,tests in (("contract",["octa_seg_v1.test_contract"]),("neural",["octa_seg_v1.test_neural"]),
                           ("reviewer",["octa_seg_v1.test_reviewer","cnv_review_v1.test_review"])):
            if prepared:continue
            result=activated(["-m","unittest",*tests,"-v"],env,capture_output=True,text=True)
            (OUT/"verification"/f"tests_{name}.txt").write_text(result.stdout+result.stderr,encoding="utf-8")
            if result.returncode:raise RuntimeError(f"{name} verification failed")
        if not prepared:
            write_json(OUT/"READY_TO_FINALIZE.json",dict(automated_checks_passed=True,
                pending="Inspect representative images and offscreen reviewer preview, then run release --finalize",
                inspection_artifacts=[fingerprint(OUT/"START_HERE.md"),fingerprint(OUT/"reports/review_overview.png"),fingerprint(OUT/"verification/reviewer_preview.png")]))
        if not finalize:
            progress("release prepared for final artifact inspection");return
        for fp in json.loads((OUT/"READY_TO_FINALIZE.json").read_text())["inspection_artifacts"]:verify(fp)
        codefiles=[]
        for package in ("octa_seg_v1","cnv_review_v1","eight_surface","octa","stage_a"):
            codefiles.extend((ROOT/"code"/package).glob("*.py"))
        codefiles.extend([ROOT/"code/label_gui.py",ROOT/"AGENTS.md",ROOT/"README.md",ROOT/"PIPELINE.md"])
        for path in codefiles:
            dest=OUT/"code_snapshot"/path.relative_to(ROOT);directory(dest.parent);shutil.copy2(path,dest)
        # Runtime GUI feedback remains mutable. All scientific release artifacts
        # and the source snapshot are frozen with full hashes.
        selected=[]
        for directory_name in ("models","calibration","data","features","predictions","volumes",
                               "review_packs","reports","evaluation","verification","code_snapshot",
                               "development_rejected_state_assumption"):
            selected.extend(p for p in (OUT/directory_name).rglob("*") if p.is_file() and p.suffix!=".pyc")
        selected.extend([OUT/"launch_config.json",OUT/"OPEN_OCTA_SEG_V1.cmd",OUT/"START_HERE.md",OUT/"IMPLEMENTATION.md"])
        progress("release complete",model="octa-seg_v1",status="experimental; learned reliability validation failed")
        write_json(OUT/"COMPLETE.json",dict(version="octa-seg_v1",created=time.strftime("%Y-%m-%dT%H:%M:%S"),
            release_status="experimental review release",artifacts=[fingerprint(p) for p in sorted(set(selected))]))
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--finalize",action="store_true")
    run(p.parse_args().finalize)
