"""Explicit resumable GPU inference or CPU export for a trained round variant."""
import argparse
from .common import *

def infer(round_name,mode):
    import torch
    import gc
    from octa_seg_v1.train import load_position
    from octa_seg_v1.model import StateNet
    from octa_seg_v1.predict import one
    from octa.volio import ProcessedVolume
    from eight_surface.segment import detect_orientation
    models=OUT/round_name/'models'/mode;trained=read(models/'trained.json')
    for key in ('states','position'):verify(trained[key])
    output=OUT/round_name/'variants'/mode
    mm=dict(checkpoints=[trained['position'],trained['states']],position_mode=mode,protocol=trained['protocol'],comparison=str(ROUND),model_fitting='development; all-label ancestry')
    write(output/'model_manifest.json',mm)
    net,_=load_position(models/'position.pt');states=StateNet().cuda().eval();states.load_state_dict(torch.load(models/'states.pt',map_location='cpu',weights_only=True)['model']);torch.set_num_threads(4)
    for sid in SCANS:
        out=output/'volumes'/sid;original=ROUND/'volumes'/sid;p=read(original/'prepared.json');p['reused_neural']=None
        if not (out/'prepared.json').exists():write(out/'prepared.json',p);save(out/'geometry.npz',**npz(original/'geometry.npz'));save(out/'alignment.npz',**npz(original/'alignment.npz'))
        if (out/'neural_complete.json').exists():continue
        verify(p['source']);g=npz(out/'geometry.npz')
        with ProcessedVolume(p['source']['path']) as v:full=v.read_volume()
        vhi=bool(detect_orientation(full.mean(axis=(0,1))));assert vhi==bool(g['vitreous_high'])
        for b in range(512):
            dest=out/'neural'/f'b{b:04d}.npz'
            if not dest.exists():result,_=one(net,states,full[b],vhi,g['vessel'][b]);save(dest,**result)
            if b%128==0:print(round_name,mode,sid,b,flush=True)
        write(out/'neural_complete.json',dict(n_bscans=512,model_manifest=mm));del full;gc.collect();torch.cuda.empty_cache()

def export(round_name,mode):
    output=OUT/round_name/'variants'/mode
    from .export import run as run_export
    from .report import run as report
    from .compare import compare
    run_export(output);report(output)
    trained=read(OUT/round_name/'models'/mode/'trained.json')
    snapshot=next(p.parent for p in (OUT/'datasets').glob('*/manifest.json') if read(p)['dataset_id']==trained['protocol']['dataset_id'])
    compare(snapshot,output)
    write(output/'COMPLETE.json',dict(model=fingerprint(output/'model_manifest.json'),volumes=SCANS,
          claim='candidate round for assessment; no automatic provider promotion'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['infer','export']);p.add_argument('round');p.add_argument('--positions',choices=['frozen','manual','approved'],default='frozen');a=p.parse_args()
    if Path(a.round).name!=a.round or not a.round.startswith('round_') or a.round=='round_000':raise ValueError('Choose a new round_NNN')
    (infer if a.stage=='infer' else export)(a.round,a.positions)
