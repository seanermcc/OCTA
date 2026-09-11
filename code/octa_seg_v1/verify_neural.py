"""Checkpoint reproducibility and neural/data identities, separate Torch process."""
import json
import platform
import torch
import numpy as np
from .common import *
from .train import load_position
from .model import StateNet

def run():
    torch.set_num_threads(2)
    p=json.loads((OUT/"models/protocol.json").read_text());checks=[]
    x=torch.rand(1,1,64,32)
    for fold in p["folds"]:
        path=OUT/"models"/fold["name"]/"position.pt"
        a,ck=load_position(path,"cpu");b,_=load_position(path,"cpu")
        with torch.no_grad():assert torch.equal(a(x)[0],b(x)[0])
        assert ck["step"]==fold["steps"]
        if fold["evaluation"]:
            assert ck["fold"]["initialization"]=="random"
            assert not (set(ck["fold"]["training"])&set(fold["evaluation"]+fold["calibration"]))
        for name in ("states.pt","states_no_vessels.pt"):
            s=torch.load(path.parent/name,map_location="cpu",weights_only=True)
            assert s["step"]==p["state_steps"]
            assert s["protocol_id"]==digest(p)
            net=StateNet();net.load_state_dict(s["model"])
            assert all(torch.isfinite(v).all() for v in s["model"].values())
            checks.append(dict(fold=fold["name"],checkpoint=name,step=s["step"],fingerprint=fingerprint(path.parent/name)))
        checks.append(dict(fold=fold["name"],checkpoint="position.pt",step=ck["step"],reload_exact=True,fingerprint=fingerprint(path)))
    write_json(OUT/"verification/checkpoints.json",dict(checks=checks,torch=torch.__version__,python=platform.python_version(),numpy=np.__version__,
        gpu=torch.cuda.get_device_name() if torch.cuda.is_available() else None,position_reload_exact=True))
    progress("checkpoint verification passed",checkpoints=len(checks))

if __name__=="__main__":run()
