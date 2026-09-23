"""Fresh-weight footprint models. No axial lesion segmentation."""
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from scipy import ndimage as ndi
from v6_model import UNet

class StructuralCNN(nn.Module):
    def __init__(self):
        super().__init__(); widths=[16,32,64,128]
        self.stages=nn.ModuleList();self.attention=nn.ModuleList()
        for i,w in enumerate(widths):
            self.stages.append(nn.Sequential(nn.Conv2d(5 if i==0 else widths[i-1],w,3,stride=1 if i==0 else 2,padding=1,bias=False),nn.GroupNorm(8,w),nn.SiLU(),nn.Conv2d(w,w,3,padding=1,bias=False),nn.GroupNorm(8,w),nn.SiLU()))
            self.attention.append(nn.Conv2d(w,1,1))
        self.head=nn.Sequential(nn.Conv1d(sum(widths),64,3,padding=1),nn.GroupNorm(8,64),nn.SiLU(),nn.Conv1d(64,1,1))
    def forward(self,x,return_attention=False):
        width=x.shape[-1];seq=[];maps=[]
        for stage,attention in zip(self.stages,self.attention):
            x=stage(x);weights=attention(x).float().softmax(dim=2).to(x.dtype)
            seq.append(F.interpolate((x*weights).sum(2),size=width,mode='linear',align_corners=False))
            if return_attention:maps.append(weights.float())
        logits=self.head(torch.cat(seq,1))[:,0]
        return (logits,maps) if return_attention else logits

def masked_loss(logits,target,known,model=1):
    """Unknown logits and targets are sanitized before arithmetic; zero gradient."""
    k=known.bool();y=torch.where(k,target.float(),0);z=torch.where(k,logits.float(),0)
    dims=tuple(range(1,z.ndim));n=k.sum(dims);valid=n>0
    if not valid.any():return z.sum()*0
    weight=torch.where(y>0,1.,2. if model==1 else 1.)
    bce=(F.binary_cross_entropy_with_logits(z,y,reduction='none')*weight*k).sum(dims)/n.clamp_min(1)
    p=z.sigmoid()*k;y=y*k;positive=y.sum(dims)>0
    dice=1-(2*(p*y).sum(dims)+1)/(p.sum(dims)+y.sum(dims)+1)
    dice_term=torch.where(positive,dice,0) if model==1 else dice
    return (bce+(0.5 if model==1 else 1.)*dice_term)[valid].mean()

def neighbors(row,n=512):return np.clip(np.arange(row-2,row+3),0,n-1)
def starts(length,size=256,stride=128):
    if length<size:raise ValueError('Native dimension smaller than patch')
    return sorted(set(range(0,length-size+1,stride))|{length-size})
def structural_patch(volume,row,x,stats):
    a=np.asarray(volume[neighbors(row,volume.shape[0]),:,x:x+256],dtype=np.float32)
    return np.clip((a-stats['center'])/stats['scale'],-8,8)

@torch.inference_mode()
def infer_structural(model,volume,stats,device):
    model.eval();h,d,w=volume.shape;total=np.zeros((h,w),np.float32);den=np.zeros_like(total)
    win=np.maximum(np.hanning(256),.001).astype('float32')
    for row in range(h):
        for x in starts(w):
            inp=torch.from_numpy(structural_patch(volume,row,x,stats)[None]).to(device)
            with torch.autocast(device_type=device.type,enabled=device.type=='cuda'):
                score=model(inp).sigmoid().float().cpu().numpy()[0]
            if not np.isfinite(score).all():raise FloatingPointError('Nonfinite structural output')
            total[row,x:x+256]+=score*win;den[row,x:x+256]+=win
    assert (den>0).all()
    return total/den

def filter_mask(raw):
    """Fixed provisional policy; reasons retain every removed pixel."""
    raw=np.asarray(raw,bool)
    opened=ndi.binary_opening(raw,structure=np.array([[0,1,0],[1,1,1],[0,1,0]],bool),border_value=0)
    components,n=ndi.label(opened,structure=np.ones((3,3)))
    sizes=np.bincount(components.ravel());small=np.zeros_like(raw)
    for i in range(1,n+1):
        if sizes[i]<64:small|=components==i
    filtered=opened&~small;reason=np.zeros(raw.shape,np.uint8);reason[raw&~opened]=1;reason[small]=2
    removed,nremoved=ndi.label(raw&~filtered,structure=np.ones((3,3)))
    records=[]
    for i in range(1,nremoved+1):
        m=removed==i;ys,xs=np.where(m)
        records.append(dict(id=i,pixels=int(m.sum()),opening_pixels=int((m&(reason==1)).sum()),below_64_pixels=int((m&(reason==2)).sum()),bbox=[int(ys.min()),int(xs.min()),int(ys.max()+1),int(xs.max()+1)]))
    assert np.array_equal(raw,filtered|(reason>0)) and not (filtered&(reason>0)).any()
    return dict(raw_mask=raw,filtered_mask=filtered,opened_mask=opened,removed_labels=removed.astype('int32'),removal_reason=reason),records
