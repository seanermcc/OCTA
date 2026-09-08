"""Experimental native-coordinate inference with reason-coded withholding."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from eight_surface.config import SURFACE_NAMES,LAYER_DEFS
from eight_surface.segment import detect_orientation
from octa.volio import ProcessedVolume
from .common import DEFAULT,output_dir,write_json,fingerprint,verify,digest
from .geometry import preprocess,to_disk_rows,PREPROCESS
from .model import decode
from .train import load_checkpoint

REASONS={"outside_scope":1,"shadow":2,"missing":4,"crossing":8,"uncertainty":16}


def prediction(model,x,scope,shadow,device="cpu",entropy_threshold=None):
    with torch.no_grad():
        logits,_=model(torch.from_numpy(np.asarray(x,np.float32)).unsqueeze(0).to(device))
        r,e=decode(logits)
    rows,entropy=r[0].cpu().numpy(),e[0].cpu().numpy()
    reason=np.zeros(rows.shape,np.uint8)
    reason[:,~np.asarray(scope,bool)] |= REASONS["outside_scope"]
    reason[:,np.asarray(shadow,bool)] |= REASONS["shadow"]
    reason[~np.isfinite(rows)] |= REASONS["missing"]
    # No enforced gap and no cumulative displacement of other surfaces.
    cross=np.isfinite(rows[:-1]) & np.isfinite(rows[1:]) & (rows[:-1]>rows[1:])
    reason[:-1][cross] |= REASONS["crossing"]
    reason[1:][cross] |= REASONS["crossing"]
    if entropy_threshold is not None:
        reason[entropy>entropy_threshold] |= REASONS["uncertainty"]
    return dict(rows=rows,entropy=entropy,retained=reason==0,reason_bits=reason)


def thickness(rows,retained,px_um):
    result={}
    for name,top,bottom in LAYER_DEFS:
        i,j=SURFACE_NAMES.index(top),SURFACE_NAMES.index(bottom)
        good=retained[i]&retained[j]&np.isfinite(rows[i])&np.isfinite(rows[j])&(rows[j]>=rows[i])
        result[name]=np.where(good,(rows[j]-rows[i])*px_um,np.nan).astype(np.float32)
    return result


def test_guard(data,split,protocol,checkpoint=None):
    if split!="test":
        return
    if protocol is None:
        raise ValueError("Final-test animals locked: supply finalized protocol after scientific criteria are fixed")
    p=json.loads(Path(protocol).read_text())
    if not p.get("criteria_finalized") or p.get("dataset_id")!=data["dataset_id"]:
        raise ValueError("Final-test protocol not finalized for this dataset")
    if set(p.get("surface_thresholds",{}))!=set(SURFACE_NAMES):
        raise ValueError("Final-test protocol requires all eight surface thresholds")
    if checkpoint and p.get("checkpoint_sha256")!=fingerprint(checkpoint)["sha256"]:
        raise ValueError("Final-test protocol does not freeze this checkpoint")


def volume(args):
    torch.set_num_threads(4)
    root=Path(args.data)
    m=json.loads((root/"manifest.json").read_text())
    parts=json.loads((root/"partitions.json").read_text())
    src=m["sources"][args.scan_id]
    split=next(s for s,animals in parts["animals"].items() if src["metadata"]["animal"] in animals)
    test_guard(m,split,args.final_test_protocol,args.checkpoint)
    device=args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    model,ck=load_checkpoint(args.checkpoint,device)
    model.eval()
    if ck["identity"]["dataset_id"]!=m["dataset_id"] or ck["identity"]["preprocessing"]!=PREPROCESS:
        raise ValueError("Checkpoint/dataset/preprocessing mismatch")
    out=output_dir(args.out)
    verify(src["source"]); verify(src["scope_hash"]); verify(src["segmentation"])
    with np.load(src["scope_path"],allow_pickle=False) as d:
        scope=d["allowed"]
    with np.load(src["segmentation"]["path"],allow_pickle=False) as d:
        shadow=d["shadow"]
    job=dict(source=src["source"],checkpoint=fingerprint(args.checkpoint),scope=src["scope_hash"],
        shadow_source=src["segmentation"],preprocessing=PREPROCESS,scan_id=args.scan_id,
        dataset_id=m["dataset_id"],entropy_threshold=args.entropy_threshold)
    job_id=digest(job)
    summary=out/"inference.json"
    if summary.exists() and json.loads(summary.read_text())["job_id"]!=job_id:
        raise ValueError("Inference output belongs to a different source/model/config")
    with ProcessedVolume(src["source"]["path"]) as v:
        full=v.read_volume()
    if list(full.shape)!=src["native_shape"] or shadow.shape!=full.shape[:2]:
        raise ValueError("Inference source geometry mismatch")
    vhi=bool(detect_orientation(full.mean(axis=(0,1))))
    todo=list(range(full.shape[0]))
    if args.limit_bscans:
        todo=todo[:args.limit_bscans]
    done=[]
    for b in todo:
        path=out/f"b{b:04d}.npz"
        if path.exists():
            with np.load(path,allow_pickle=False) as d:
                if str(d["job_id"])!=job_id:
                    raise ValueError("Stale inference chunk")
            done.append(b); continue
        x,_,_=preprocess(full[b],vhi)
        pred=prediction(model,x,scope[b],shadow[b],device,args.entropy_threshold)
        bands=thickness(pred["rows"],pred["retained"],1.12)
        tmp=path.with_suffix(".writing.npz")
        np.savez_compressed(tmp,canonical_rows=pred["rows"],
            disk_rows=to_disk_rows(pred["rows"],full.shape[2],vhi),
            retained_rows=np.where(pred["retained"],pred["rows"],np.nan),
            entropy=pred["entropy"],reason_bits=pred["reason_bits"],retained=pred["retained"],
            scope=scope[b],shadow=shadow[b],surface_names=np.array(SURFACE_NAMES),
            thickness_names=np.array(list(bands)),experimental_thickness_um=np.stack(list(bands.values())),
            validated_thickness_um=np.full((len(bands),full.shape[1]),np.nan,np.float32),
            validated=np.array(False),job_id=np.array(job_id),bscan=np.array(b),
            vitreous_high=np.array(vhi),native_shape=np.array(full.shape),axial_um=np.array(1.12),
            decoder_displacement_px=np.zeros_like(pred["rows"]))
        tmp.replace(path)
        done.append(b)
        if b%32==0:
            print(f"{args.scan_id}: {b+1}/{len(todo)}",flush=True)
    write_json(summary,dict(job=job,job_id=job_id,completed_bscans=done,
        full_volume_complete=len(done)==full.shape[0],experimental=True,validated=False,
        orientation_detected=vhi,reason_bits=REASONS,
        note="Raw predictions may include CNV context. Scope/shadow/crossing/optional entropy mask experimental measurements; validated measurements unavailable until promotion. Entropy is not calibrated. Shadow mask is the frozen classical segmentation artifact, not learned local visibility."))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,default=DEFAULT)
    p.add_argument("--checkpoint",type=Path,required=True)
    p.add_argument("--scan-id",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--device")
    p.add_argument("--entropy-threshold",type=float)
    p.add_argument("--final-test-protocol",type=Path)
    p.add_argument("--limit-bscans",type=int)
    volume(p.parse_args())
