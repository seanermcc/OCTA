"""Small full-field U-Net with independently masked vessel/ONH objectives."""
import torch
from torch import nn
from torch.nn import functional as F
import numpy as np
from scipy import ndimage

class Block(nn.Sequential):
    def __init__(self,cin,cout):
        super().__init__(nn.Conv2d(cin,cout,3,padding=1,bias=False),nn.GroupNorm(4,cout),nn.SiLU(),
                         nn.Conv2d(cout,cout,3,padding=1,bias=False),nn.GroupNorm(4,cout),nn.SiLU())

class Model(nn.Module):
    def __init__(self):
        super().__init__()
        widths=[8,16,32,64,128]
        self.enc=nn.ModuleList([Block(1,8)]+[Block(a,b) for a,b in zip(widths[:-1],widths[1:])])
        self.dec=nn.ModuleList([Block(a+b,b) for a,b in zip(widths[:0:-1],widths[-2::-1])])
        self.head=nn.Conv2d(8,2,1)
    def forward(self,x):
        skips=[]
        for i,block in enumerate(self.enc):
            if i:x=F.max_pool2d(x,2)
            x=block(x);skips.append(x)
        for block,skip in zip(self.dec,skips[-2::-1]):
            x=F.interpolate(x,size=skip.shape[-2:],mode='bilinear',align_corners=False)
            x=block(torch.cat([x,skip],1))
        return self.head(x)

def masked_loss(logits,pos,neg):
    """Area-pooled positive/negative weights; unknown pixels have zero gradient.

    Each available sign contributes equally within each image/target. Positive
    and negative native pixels in a 2x2 block retain separate mass, rather than
    turning the whole block into a hard pseudo-label. No unmasked Dice term.
    """
    dims=(-2,-1)
    pc=pos.sum(dims);nc=neg.sum(dims)
    pl=(F.softplus(-logits)*pos).sum(dims)/pc.clamp_min(1e-8)
    nl=(F.softplus(logits)*neg).sum(dims)/nc.clamp_min(1e-8)
    terms=(pc>0).float()+(nc>0).float()
    per=(pl*(pc>0)+nl*(nc>0))/terms.clamp_min(1)
    active=terms>0
    return (per*active).sum()/active.sum().clamp_min(1)

def native_prob(raw,shape=(512,512)):
    return F.interpolate(torch.as_tensor(raw,dtype=torch.float32)[None],size=shape,
                         mode='bilinear',align_corners=False)[0].numpy()

def resolved_masks(prob,thresholds,min_onh_area):
    vessel=prob[0]>=thresholds[0];onh=prob[1]>=thresholds[1]
    if min_onh_area:
        labels,n=ndimage.label(onh)
        sizes=np.bincount(labels.ravel());keep=sizes>=min_onh_area;keep[0]=False
        onh=keep[labels]
    return np.stack([vessel & ~onh,onh])

def confusion(pred,pos,neg):
    return dict(tp=int((pred&pos).sum()),fn=int((~pred&pos).sum()),fp=int((pred&neg).sum()),tn=int((~pred&neg).sum()))

def scored(counts):
    tp,fn,fp,tn=[counts[k] for k in ['tp','fn','fp','tn']]
    n=tp+fn+fp+tn
    return dict(**counts,scored_pixels=n,positive_pixels=tp+fn,negative_pixels=fp+tn,
        dice=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,
        specificity=tn/(tn+fp) if tn+fp else None,iou=tp/(tp+fp+fn) if tp+fp+fn else None)
