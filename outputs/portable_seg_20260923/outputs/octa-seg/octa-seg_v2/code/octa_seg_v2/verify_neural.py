"""Neural checks in a separate process from CPU/Qt."""
import torch
from .common import *
from .train import balanced_loss
from octa_seg_v1.model import StateNet

def run():
    torch.manual_seed(7);net=StateNet();f=torch.randn(1,8,27,64);v=torch.zeros(1,64,dtype=torch.bool)
    logits=net(f,v);logits.retain_grad();t=torch.full((1,8,64),-1);rel=t.clone();rel[:,2,12:30]=0;rel[:,2,40:50]=1
    loss=balanced_loss(logits,t,rel);loss.backward()
    assert logits.grad[:,:,0].abs().sum()==0
    assert logits.grad[:,2,1,12:30].abs().sum()>0
    assert logits.grad[:,2,1,:12].abs().sum()==0
    assert torch.isfinite(loss)
    protocol=read(V1/'models/protocol.json');fold=next(f for f in protocol['folds'] if f['name']=='ALL_LABELLED')
    ck=torch.load(fold['initialization'],map_location='cpu',weights_only=True)
    parent_manifest=read(V1/'data/manifest.json')['parent'];parent=read(parent_manifest['path'])
    parent_eligible=sorted({r['animal'] for r in parent['records'] if r.get('eligible') and sum(r.get('eligible_columns_by_surface',[]))>0})
    own=initialize()['position_eligible_animals'];seen=sorted(set(own)|set(parent_eligible))
    state_seen=set()
    for r in read(V1/'data/manifest.json')['records']:
        with np.load(r['cache']['path'],allow_pickle=False) as d:
            if (d['trace_target']>=0).any() or (d['reliability_target']>=0).any():state_seen.add(r['animal'])
    write(OUT/'tests/neural_verification.json',dict(loss=float(loss.detach()),unknown_trace_has_zero_gradient=True,regional_negative_has_no_position_loss=True,architecture='existing StateNet; position branch detached'))
    write(OUT/'checkpoint_ancestry.json',dict(current_position=initialize()['checkpoints'][0],current_eligible_animals=own,
       parent_checkpoint=fingerprint(fold['initialization']),parent_checkpoint_keys=list(ck),parent_data_manifest=parent_manifest,
       parent_eligible_animals=parent_eligible,seen_position_animals_at_least=seen,state_eligible_training_animals=sorted(state_seen),
       scan_status=[dict(scan_id=s,animal=s.split('_')[0],position_seen=s.split('_')[0] in seen,state_seen=s.split('_')[0] in state_seen) for s in SCANS],
       claim='No animal-excluded validation: latest model uses all eligible labels; inventory membership alone was not used'))
    print('Neural loss and checkpoint ancestry checks passed',flush=True)

if __name__=='__main__':run()
