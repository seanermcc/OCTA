"""Versioned U-Net position branch plus separate traceability/reliability heads.

The state branch sees local depth evidence around the position distribution,
its uncertainty and lateral context. It cannot send gradients to the position
branch. Thus negative state-only records never become positional supervision.
"""
import torch
from torch import nn
from torch.nn import functional as F
from stage_a.model import BoundaryUNet, decode

FEATURES = 27

def evidence(logits, x):
    p = logits.float().softmax(2)
    rows, entropy = decode(logits.float())
    h = logits.shape[2]
    offsets = torch.tensor([-24,-16,-12,-8,-6,-4,-2,-1,0,1,2,4,6,8,12,16,24],device=x.device)
    at = (rows[:,:,None] + offsets[None,None,:,None]).round().long().clamp(0,h-1)
    samples = torch.gather(x.float().expand(-1,8,-1,-1),2,at)
    depth = torch.arange(h,device=x.device)[None,None,:,None]
    sd = ((p*(depth-rows[:,:,None]).square()).sum(2)).sqrt()/h
    features = torch.cat([samples, rows[:,:,None]/h, entropy[:,:,None],
                          sd[:,:,None], p.amax(2)[:,:,None]],2)
    # + two local contrast summaries, native normalized intensity statistics,
    # + vessel channel, boundary ID, and explicit constant (27 total).
    features = torch.cat([features, (samples.amax(2)-samples.amin(2))[:,:,None],
        (samples[:,:,9:]-samples[:,:,:8]).abs().mean(2,keepdim=True),
        x.float().mean(2)[:,None].expand(-1,8,-1,-1),
        x.float().std(2)[:,None].expand(-1,8,-1,-1),
        torch.zeros_like(rows[:,:,None]),
        torch.arange(8,device=x.device)[None,:,None,None].expand(x.shape[0],-1,1,x.shape[-1])/7],2)
    assert features.shape[2] == FEATURES
    return features, rows, entropy

class StateNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Conv1d(FEATURES,32,7,padding=3), nn.SiLU(),
            nn.Conv1d(32,32,7,padding=6,dilation=2),nn.SiLU(),
            nn.Conv1d(32,16,7,padding=12,dilation=4),nn.SiLU(),nn.Conv1d(16,2,1))
    def forward(self, features, vessel, use_vessels=True):
        z = features.clone()
        z[:,:,25] = vessel[:,None].float() if use_vessels else 0
        b,k,c,w=z.shape
        return self.net(z.reshape(b*k,c,w)).reshape(b,k,2,w)

def state_loss(logits, trace, reliable, vessel, use_vessels=True):
    target = torch.stack([trace,reliable],2).float()
    weight = (target>=0).float()
    if use_vessels:
        defaults = torch.zeros_like(reliable,dtype=torch.bool)
        defaults[:,1:] = vessel[:,None].bool()
        defaults &= reliable<0
        target[:,:,1] = torch.where(defaults,0,target[:,:,1])
        weight[:,:,1] = torch.where(defaults,.2,weight[:,:,1])
    clean = target.clamp(0,1)
    loss = F.binary_cross_entropy_with_logits(logits,clean,reduction="none")
    # Balance positive/negative evidence per output so abundant unknown or
    # vessel defaults cannot make withholding everything an easy objective.
    terms=[]
    for k in range(8):
        for head in range(2):
            for value in (0,1):
                w=weight[:,k,head]*(clean[:,k,head]==value)
                if w.sum()>0:
                    terms.append((loss[:,k,head]*w).sum()/w.sum().clamp_min(1))
    return torch.stack(terms).mean() if terms else logits.sum()*0
