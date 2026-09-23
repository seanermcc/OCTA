"""GPU-only inference; never import plotting or Qt in this process."""
import gc
import torch
from .common import *
from octa_seg_v1.predict import one,state_model
from octa_seg_v1.train import load_position
from octa.volio import ProcessedVolume
from eight_surface.segment import detect_orientation

def run():
    initialize();torch.set_num_threads(4)
    net,_=load_position(V1/'models/ALL_LABELLED/position.pt');states=state_model('ALL_LABELLED')
    for sid in SCANS:
        out=ROUND/'volumes'/sid
        if not (out/'prepared.json').exists():continue
        p=read(out/'prepared.json')
        if p['reused_neural'] or (out/'neural_complete.json').exists():continue
        verify(p['source']);g=npz(out/'geometry.npz')
        with ProcessedVolume(p['source']['path']) as v:full=v.read_volume()
        vhi=bool(detect_orientation(full.mean(axis=(0,1))));assert vhi==bool(g['vitreous_high'])
        for b in range(512):
            dest=out/'neural'/f'b{b:04d}.npz'
            if not dest.exists():result,_=one(net,states,full[b],vhi,g['vessel'][b]);save(dest,**result)
            if b%64==0:print('v2 frozen model',sid,b+1,flush=True)
        write(out/'neural_complete.json',dict(scan_id=sid,bscans=512,training=False,checkpoints=initialize()['checkpoints']))
        del full;gc.collect();torch.cuda.empty_cache()

if __name__=='__main__':run()
