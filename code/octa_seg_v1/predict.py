"""Neural inference only. Context/plots run separately to avoid Windows BLAS clash."""
import argparse
import gc
import json
import time
import numpy as np
import torch
from .common import *
from .model import StateNet, evidence
from .train import load_position
from stage_a.geometry import preprocess,label_offset
from eight_surface.segment import detect_orientation,prepare_bscan
from octa.volio import ProcessedVolume

def state_model(fold,vessel=True):
    ck=torch.load(OUT/"models"/fold/("states.pt" if vessel else "states_no_vessels.pt"),map_location="cpu",weights_only=True)
    net=StateNet().cuda().eval();net.load_state_dict(ck["model"]);return net

def probabilities():
    m=json.loads((OUT/"data/manifest.json").read_text());p=json.loads((OUT/"models/protocol.json").read_text())
    for fold in p["folds"]:
        for vessel in (True,False):
            name="vessels" if vessel else "no_vessels";net=state_model(fold["name"],vessel)
            for r in m["records"]:
                dest=OUT/"predictions/labels"/fold["name"]/name/f"{r['key']}.npz"
                if dest.exists():continue
                feat=load_npz(OUT/"features"/fold["name"]/f"{r['key']}.npz")
                with np.load(r["cache"]["path"],allow_pickle=False) as cache:d={"vessel":cache["vessel"]}
                with torch.no_grad():
                    prob=net(torch.from_numpy(feat["features"][None]).cuda(),torch.from_numpy(d["vessel"][None]).cuda(),vessel).sigmoid()[0].cpu().numpy()
                save_npz(dest,probabilities=prob,rows=feat["rows"],entropy=feat["entropy"])
            progress("label probability predictions complete",fold=fold["name"],vessels=vessel)

def one(net,states,raw,vhi,vessel):
    x,db,_=preprocess(raw,vhi)
    with torch.no_grad(),torch.autocast("cuda",dtype=torch.bfloat16):
        x=torch.from_numpy(x[None]).cuda();logits,_=net(x);feat,rows,entropy=evidence(logits,x)
        prob=states(feat,torch.from_numpy(vessel[None]).cuda(),True).float().sigmoid()
    return dict(rows=rows[0].cpu().numpy(),probabilities=prob[0].cpu().numpy(),entropy=entropy[0].cpu().numpy()),db

def volumes():
    start=time.monotonic()
    m=json.loads((OUT/"data/manifest.json").read_text())
    sids=sorted(p.stem for p in (PREVIOUS/"cnv_gui/scan_queue").glob("*.npz"))
    net,_=load_position(OUT/"models/ALL_LABELLED/position.pt");states=state_model("ALL_LABELLED")
    for sid in sids:
        out=directory(OUT/"volumes"/sid);marker=out/"neural_complete.json"
        if marker.exists():continue
        t=time.monotonic();src=m["sources"][sid];verify(src["source"])
        progress("reading full native volume",scan=sid)
        with ProcessedVolume(src["source"]["path"]) as volume:full=volume.read_volume()
        vhi=bool(detect_orientation(full.mean(axis=(0,1))))
        offset=label_offset(src["label_band"],full.shape[2],vhi)
        masks=load_npz(m["footprints"][sid]["path"])
        old=load_npz(PREVIOUS/"cnv_gui/scan_queue"/f"{sid}.npz")
        read_s=time.monotonic()-t
        # A memory-mapped crop makes CPU registration, review packs, and figures
        # resumable without another source-volume read.
        image_path=out/"images.npy"
        images=np.lib.format.open_memmap(image_path,mode="w+",dtype=np.float32,
            shape=(len(full),src["label_band"][1]-src["label_band"][0],full.shape[1]))
        infer_start=time.monotonic()
        for b in range(len(full)):
            dst=out/"neural"/f"b{b:04d}.npz"
            if dst.exists():
                db=prepare_bscan(full[b],vhi)
            else:
                result,db=one(net,states,full[b],vhi,masks["vessel"][b]);save_npz(dst,**result)
            images[b]=db[offset:offset+images.shape[1]]
            if b%64==0:images.flush();progress("full volume neural inference",scan=sid,completed=b+1,total=len(full))
        images.flush();del images
        save_npz(out/"geometry.npz",shadow=old["shadow"],vessel=masks["vessel"],cnv=masks["cnv"],
            label_offset=np.array(offset),vitreous_high=np.array(vhi),native_shape=np.array(full.shape),retina_band=np.array(src["label_band"]))
        # Neighboring rows for the hidden-position experiment use the same
        # animal-excluded network as the held-out central row. Never all-label.
        animal=src["metadata"]["animal"]
        held_net,_=load_position(OUT/"models"/animal/"position.pt");held_states=state_model(animal)
        wanted=sorted({b for r in m["records"] if r["scan_id"]==sid for b in (r["bscan"]-1,r["bscan"],r["bscan"]+1) if 0<=b<len(full)})
        for b in wanted:
            dst=OUT/"predictions/context_heldout"/sid/f"b{b:04d}.npz"
            if dst.exists():continue
            result,_=one(held_net,held_states,full[b],vhi,masks["vessel"][b]);save_npz(dst,**result)
        del held_net,held_states,full;gc.collect();torch.cuda.empty_cache()
        write_json(marker,dict(scan_id=sid,source=src["source"],n_bscans=512,read_s=read_s,
            inference_and_neighbor_s=time.monotonic()-infer_start,total_s=time.monotonic()-t,
            orientation_detected=vhi,label_offset=offset,axis_order="B-scan,boundary,A-line; full canonical depth; vitreous 0",
            position_checkpoint=fingerprint(OUT/"models/ALL_LABELLED/position.pt"),state_checkpoint=fingerprint(OUT/"models/ALL_LABELLED/states.pt")))
    progress("neural volume export complete",runtime_s=time.monotonic()-start)

if __name__=="__main__":
    torch.set_num_threads(4)
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["labels","volumes"]);a=p.parse_args()
    probabilities() if a.mode=="labels" else volumes()
