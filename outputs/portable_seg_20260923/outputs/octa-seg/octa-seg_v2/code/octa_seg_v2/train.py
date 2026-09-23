"""Explicit between-round batches. Frozen-position reliability first; resumable."""
import argparse
import random
import torch
from .common import *
from octa_seg_v1.model import StateNet,evidence
from octa_seg_v1.train import load_position
from stage_a.geometry import preprocess
from stage_a.model import losses
from octa.volio import ProcessedVolume
from eight_surface.segment import detect_orientation

def atomic_torch(path,data):
    path=writable(path);tmp=path.with_suffix('.tmp.pt');torch.save(data,tmp);tmp.replace(path)

def balanced_loss(logits,t,rel):
    # No inferred vessel labels. Mean each supported boundary/head/sign independently.
    target=torch.stack([t,rel],2).float();loss=torch.nn.functional.binary_cross_entropy_with_logits(logits,target.clamp(0,1),reduction='none');terms=[]
    for k in range(8):
        for h in range(2):
            for sign in (0,1):
                mask=target[:,k,h]==sign
                if mask.any():terms.append(loss[:,k,h][mask].mean())
    return torch.stack(terms).mean() if terms else logits.sum()*0

def run(snapshot,round_name,steps=300,positions='frozen'):
    if not round_name.startswith('round_') or round_name=='round_000' or Path(round_name).name!=round_name:raise ValueError('Choose a new round_NNN')
    m=read(Path(snapshot)/'manifest.json');out=OUT/round_name
    if (out/'COMPLETE.json').exists():raise ValueError('Round is frozen')
    for r in m['records']:verify(r['targets'])
    train=[r for r in m['records'] if r['role']=='training']
    support={str(v):sum(np.any(npz(r['targets']['path'])['reliability_target']==v) for r in train) for v in (0,1)}
    protocol=dict(dataset_id=m['dataset_id'],steps=steps,position_mode=positions,seed=20260910,state_lr=.0003,position_lr=.00003,
        positions_first_frozen=True,assessment_used_for_fitting=False,ancestry='all-label initialization; development only',new_review_regions_by_reliability_sign=support)
    if positions!='frozen' and not any(npz(r['targets']['path'])['manual_valid'].any() or (positions=='approved' and npz(r['targets']['path'])['approved_valid'].any()) for r in train):
        write(out/'position_training_status.json',dict(status='no_new_eligible_positions',position_mode=positions,provider_preserved=True));return
    if min(support.values(),default=0)<2:
        write(out/'training_status.json',dict(status='collect_feedback',protocol=protocol,provider_preserved='round_000',
           reason='Need affirmative and negative reliability evidence in at least two distinct new reviewed B-scans each; no model trained.'))
        print('Preserving current provider: insufficient balanced new feedback',support,flush=True);return
    pid=digest(protocol);mode_dir=out/'models'/positions
    if (mode_dir/'protocol.json').exists() and read(mode_dir/'protocol.json')!=protocol:raise ValueError('Resume protocol changed')
    write(mode_dir/'protocol.json',protocol);torch.set_num_threads(4);torch.manual_seed(20260910);rng=random.Random(20260910)
    pos,_=load_position(V1/'models/ALL_LABELLED/position.pt');pos.eval()
    records=[];data={};features={}
    # Build native normalized feedback inputs in a separate derived cache.
    for sid in sorted({r['scan_id'] for r in m['records']}):
        wanted=[r for r in m['records'] if r['scan_id']==sid];missing=[r for r in wanted if not (out/'training_cache'/f'{r["key"]}.npz').exists()]
        if missing:
            prep=read(ROUND/'volumes'/sid/'prepared.json');verify(prep['source'])
            with ProcessedVolume(prep['source']['path']) as v:full=v.read_volume()
            vhi=bool(detect_orientation(full.mean(axis=(0,1))));g=npz(ROUND/'volumes'/sid/'geometry.npz')
            for r in missing:
                x,_,_=preprocess(full[r['bscan']],vhi);t=npz(r['targets']['path'])
                save(out/'training_cache'/f'{r["key"]}.npz',x=x,vessel=g['vessel'][r['bscan']],**t)
            del full
        for r in wanted:
            cache=npz(out/'training_cache'/f'{r["key"]}.npz');data[r['key']]=cache
            if r['role']=='training':records.append(r)
    for r in m['baseline_replay']:
        verify(r['cache']);d=npz(r['cache']['path']);d['manual_valid']=d['valid'];d['approved_valid']=np.zeros_like(d['valid']);data[r['key']]=d;records.append(dict(r,role='training',events=[]))
    for key,d in data.items():
        with torch.no_grad():
            x=torch.from_numpy(d['x'][None]).cuda();logits,_=pos(x);f,_,_=evidence(logits,x);features[key]=f[0].detach().cpu().numpy()
    groups={a:[r for r in records if r['animal']==a] for a in sorted({r['animal'] for r in records})}
    states=StateNet().cuda();states.load_state_dict(torch.load(V1/'models/ALL_LABELLED/states.pt',map_location='cpu',weights_only=True)['model'])
    opt=torch.optim.AdamW(states.parameters(),lr=protocol['state_lr']);start=0;history=[];path=mode_dir/'states.pt'
    if path.exists():
        ck=torch.load(path,map_location='cpu',weights_only=True)
        if ck['protocol_id']!=pid:raise ValueError('Incompatible state resume')
        states.load_state_dict(ck['model']);opt.load_state_dict(ck['optimizer']);start=ck['step'];history=ck['history'];rng.setstate(ck['rng'])
    for step in range(start,steps):
        r=rng.choice(groups[rng.choice(list(groups))]);d=data[r['key']]
        t=d['trace_target'].copy();rel=d['reliability_target'].copy()
        # Pick a reviewed region first, so strip width cannot weight sampling frequency.
        es=[e for e in r.get('events',[]) if e['action'] not in ('clear_region','clear_boundary','clear_exclusion')]
        if es:
            e=rng.choice(es);mask=np.zeros(512,bool);mask[e['lo']:e['hi']]=True;t[:,~mask]=-1;rel[:,~mask]=-1
        f=torch.from_numpy(features[r['key']][None]).cuda();v=torch.from_numpy(d['vessel'][None]).cuda()
        opt.zero_grad(set_to_none=True);loss=balanced_loss(states(f,v),torch.from_numpy(t[None]).cuda(),torch.from_numpy(rel[None]).cuda())
        if not torch.isfinite(loss):raise FloatingPointError('State loss')
        loss.backward();torch.nn.utils.clip_grad_norm_(states.parameters(),5);opt.step()
        if (step+1)%50==0 or step+1==steps:
            history.append(dict(step=step+1,loss=float(loss.detach())))
            atomic_torch(path,dict(model=states.state_dict(),optimizer=opt.state_dict(),step=step+1,history=history,protocol_id=pid,rng=rng.getstate(),dataset_id=m['dataset_id']))
            print('Frozen-position state training',step+1,flush=True)
    # Always preserve a frozen-position comparison before optional positional fitting.
    atomic_torch(mode_dir/'frozen_position.pt',dict(model=pos.state_dict(),protocol_id=pid,parent=initialize()['checkpoints'][0]))
    if positions!='frozen':
        eligible=[r for r in records if data[r['key']]['manual_valid'].any() or (positions=='approved' and data[r['key']]['approved_valid'].any())]
        pos.train();popt=torch.optim.AdamW(pos.parameters(),lr=protocol['position_lr']);pstart=0;ppath=mode_dir/'position.pt'
        if ppath.exists():
            ck=torch.load(ppath,map_location='cpu',weights_only=True)
            if ck['protocol_id']!=pid:raise ValueError('Incompatible position resume')
            pos.load_state_dict(ck['model']);popt.load_state_dict(ck['optimizer']);pstart=ck['step'];rng.setstate(ck['rng'])
        pgroups={a:[r for r in eligible if r['animal']==a] for a in sorted({r['animal'] for r in eligible})}
        for step in range(pstart,steps):
            r=rng.choice(pgroups[rng.choice(list(pgroups))]);d=data[r['key']];valid=d['manual_valid']|(d['approved_valid'] if positions=='approved' else False)
            center=int(rng.choice(np.flatnonzero(valid.any(0)).tolist()));lo=int(np.clip(center-64,0,384));sl=slice(lo,lo+128)
            x=torch.from_numpy(d['x'][None,...,sl].copy()).cuda();yy=torch.from_numpy(d['rows'][None,...,sl].copy()).cuda();mask=torch.from_numpy(valid[None,...,sl].copy()).cuda()
            # Sanitize unknown targets: zero weight does not neutralize NaN arithmetic.
            yy=torch.nan_to_num(yy);region=torch.full((1,1024,128),-100,device='cuda',dtype=torch.long)
            popt.zero_grad(set_to_none=True);logits,rlogits=pos(x);loss,_=losses(logits,rlogits,yy,mask,region,region_weight=0)
            if not torch.isfinite(loss):raise FloatingPointError('Position loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(pos.parameters(),5);popt.step()
            if (step+1)%50==0 or step+1==steps:atomic_torch(ppath,dict(model=pos.state_dict(),optimizer=popt.state_dict(),step=step+1,protocol_id=pid,rng=rng.getstate()))
    else:atomic_torch(mode_dir/'position.pt',dict(model=pos.state_dict(),protocol_id=pid,step=0))
    write(mode_dir/'trained.json',dict(protocol=protocol,states=fingerprint(path),position=fingerprint(mode_dir/'position.pt'),
       promotion='candidate only; compare withheld assessment before choosing provider',positions_state_score_caveat='When positions change, state features change: reassessment required; no calibration claim'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path);p.add_argument('round');p.add_argument('--steps',type=int,default=300);p.add_argument('--positions',choices=['frozen','manual','approved'],default='frozen');a=p.parse_args();run(a.snapshot,a.round,a.steps,a.positions)
