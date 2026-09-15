"""Evaluate a frozen split; model, shipped auto, or available stored v2 outputs."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from .common import DEFAULT,OUT,output_dir,write_json,write_csv,fingerprint
from .data import Dataset
from .train import load_checkpoint
from .inference import prediction,test_guard
from .metrics import evaluate


def run(args):
    root=Path(args.data)
    m=json.loads((root/"manifest.json").read_text())
    test_guard(m,args.split,args.final_test_protocol,args.checkpoint)
    data=Dataset(root,args.split,eligible_only=False)
    out=output_dir(args.out)
    if (out/"metrics.json").exists():
        raise FileExistsError("Choose a new evaluation version")
    device=args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    torch.set_num_threads(4)
    model=None
    if args.predictor=="model":
        if not args.checkpoint:
            raise ValueError("Model evaluation requires --checkpoint")
        model,ck=load_checkpoint(args.checkpoint,device)
        if ck["identity"]!=data.identity:
            raise ValueError("Checkpoint belongs to different data/cache partition")
        model.eval()
    targets={}; preds={}; provenance={}; failures={}
    records=data.records[:args.limit] if args.limit else data.records
    for r in records:
        with np.load(r["targets"],allow_pickle=False) as t:
            targets[r["key"]]={k:t[k].copy() for k in t.files}
        t=targets[r["key"]]
        entry=data.cache["entries"][r["key"]]
        if model is not None:
            try:
                with np.load(entry["file"]["path"],allow_pickle=False) as c:
                    pred=prediction(model,c["x"],t["scope"],t["shadow"],device,args.entropy_threshold)
                pred["rows"]-=entry["label_offset"]
                preds[r["key"]]=pred
            except (RuntimeError,ValueError) as exc:
                failures[r["key"]]=str(exc)  # Metrics still count missing predictions.
        elif args.predictor=="stored-auto":
            preds[r["key"]]=dict(rows=t["stored_auto"],retained=np.broadcast_to(t["scope"]&~t["shadow"],t["valid"].shape).copy())
        else:
            path=OUT/"auto_seg_8layer_v2/segmented"/f"{r['scan_id']}.npz"
            if path.exists():
                with np.load(path,allow_pickle=False) as seg:
                    if list(seg["surface_names"].astype(str))!=m["surface_names"] or list(seg["retina_band"])!=m["sources"][r["scan_id"]]["label_band"]:
                        raise ValueError("Stored v2 label geometry/contract mismatch")
                    rows=seg["surfaces"][r["bscan"]]
                preds[r["key"]]=dict(rows=rows,retained=np.broadcast_to(t["scope"]&~t["shadow"],t["valid"].shape).copy())
                provenance[str(path)]=fingerprint(path)
            else:
                failures[r["key"]]="No stored v2 prediction; counted as missing"
        if r["key"] in preds:
            pred=preds[r["key"]]
            np.savez_compressed(out/f"{r['key']}.npz",**pred)
    report=evaluate(records,targets,preds,m["sources"],args.gross_um)
    report.update(dataset_id=m["dataset_id"],partition_id=data.partitions["partition_id"],
        split=args.split,predictor=args.predictor,checkpoint=fingerprint(args.checkpoint) if args.checkpoint else None,
        failures=failures,baseline_sources=provenance,
        scope="Stage A eligible columns; no CNV core/buffer supervision",
        baseline_overlap="Historical v2 decisions used overlapping human examples; it is a practical comparator, not an independently trained held-out model.")
    # Risk/coverage curves are diagnostic candidates; no fitted threshold here.
    if model is not None:
        curves=[]
        for threshold in (.5,.7,.8,.9,.95,.99,1.0):
            selected={k:{**p,"retained":p["retained"]&(p["entropy"]<=threshold)} for k,p in preds.items()}
            curve=evaluate(records,targets,selected,m["sources"],args.gross_um)
            curves.extend(dict(entropy_threshold=threshold,**s) for s in curve["summary"] if s["axis"]=="pooled" and s["mode"]=="retained")
        write_csv(out/"risk_coverage.csv",curves)
    write_json(out/"metrics.json",report)
    write_csv(out/"metrics.csv",report["summary"])
    write_csv(out/"historical_secondary_bscan_metrics.csv",report["per_bscan"])
    write_csv(out/"decision_coverage.csv",report["decisions"])
    print(f"Evaluated {len(records)} {args.split} decisions; {len(failures)} missing/failed predictions")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,default=DEFAULT)
    p.add_argument("--split",choices=["train","validation","test"],default="validation")
    p.add_argument("--predictor",choices=["model","stored-auto","v2"],default="model")
    p.add_argument("--checkpoint",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--device")
    p.add_argument("--entropy-threshold",type=float)
    p.add_argument("--gross-um",type=float,default=25)
    p.add_argument("--final-test-protocol",type=Path)
    p.add_argument("--limit",type=int)
    run(p.parse_args())
