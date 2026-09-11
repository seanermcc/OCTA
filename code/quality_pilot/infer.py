"""Unmodified frozen-v1 native inference on just the two new volumes."""
import gc
import torch
from .common import *
from octa_seg_v1.predict import one,state_model
from octa_seg_v1.train import load_position
from octa.volio import ProcessedVolume
from eight_surface.segment import detect_orientation

def run():
    initialize();torch.set_num_threads(4)
    net,_=load_position(FROZEN/'models/ALL_LABELLED/position.pt');states=state_model('ALL_LABELLED')
    for sid in SCANS[4:]:
        out=OUT/'volumes'/sid
        if (out/'neural_complete.json').exists():continue
        p=read(out/'prepared.json');verify(p['source']);g=npz(out/'geometry.npz')
        with ProcessedVolume(p['source']['path']) as v:full=v.read_volume()
        vhi=bool(detect_orientation(full.mean(axis=(0,1))));assert vhi==bool(g['vitreous_high'])
        for b in range(len(full)):
            dest=out/'neural'/f'b{b:04d}.npz'
            if not dest.exists():
                result,_=one(net,states,full[b],vhi,g['vessel'][b]);save(dest,**result)
            if b%64==0:print('Frozen v1 inference',sid,b+1,'/',len(full),flush=True)
        atomic_json(out/'neural_complete.json',dict(scan_id=sid,bscans=len(full),model='octa-seg_v1',training=False))
        del full;gc.collect();torch.cuda.empty_cache()

if __name__=='__main__':run()
