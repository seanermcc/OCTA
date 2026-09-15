"""Small 2-D U-Net with eight depth-distribution heads and seven closed bands."""
import torch
from torch import nn
from torch.nn import functional as F


def block(a,b):
    return nn.Sequential(nn.Conv2d(a,b,3,padding=1),nn.GroupNorm(4,b),nn.SiLU(),
                         nn.Conv2d(b,b,3,padding=1),nn.GroupNorm(4,b),nn.SiLU())


class BoundaryUNet(nn.Module):
    def __init__(self,base=8):
        super().__init__()
        if base%4:
            raise ValueError("base must be divisible by four")
        self.base=base
        self.enc=nn.ModuleList([block(1,base),block(base,2*base),block(2*base,4*base)])
        self.bridge=block(4*base,8*base)
        self.dec=nn.ModuleList([block(12*base,4*base),block(6*base,2*base),block(3*base,base)])
        self.boundary=nn.Conv2d(base,8,1)
        self.region=nn.Conv2d(base,7,1)

    def forward(self,x):
        skip=[]
        for encoder in self.enc:
            x=encoder(x)
            skip.append(x)
            x=F.avg_pool2d(x,2)
        x=self.bridge(x)
        for decoder,s in zip(self.dec,reversed(skip)):
            x=decoder(torch.cat([F.interpolate(x,size=s.shape[-2:],mode="bilinear",align_corners=False),s],1))
        return self.boundary(x),self.region(x)


def decode(logits):
    p=logits.softmax(2)
    depths=torch.arange(logits.shape[2],device=logits.device,dtype=logits.dtype)[None,None,:,None]
    rows=(p*depths).sum(2)
    entropy=-(p*p.clamp_min(1e-12).log()).sum(2)/torch.log(torch.tensor(float(logits.shape[2]),device=logits.device))
    return rows,entropy


def losses(logits,regions,rows,valid,region_target,region_weight=.1,sigma=2.0):
    """No visibility loss: legacy global flags do not support local classes."""
    good=valid.bool()
    if not good.any():
        raise ValueError("No supervised boundary targets")
    if not torch.isfinite(rows[good]).all() or ((rows[good]<0)|(rows[good]>logits.shape[2]-1)).any():
        raise ValueError("Eligible target is non-finite or out of image")
    clean=torch.where(good,rows,torch.zeros_like(rows))
    depths=torch.arange(logits.shape[2],device=logits.device)[None,None,:,None]
    target=torch.exp(-.5*((depths-clean[:,:,None,:])/sigma)**2)
    target=target/target.sum(2,keepdim=True).clamp_min(1e-12)
    ce=-(target*logits.log_softmax(2)).sum(2)
    pred,_=decode(logits)
    l1=F.smooth_l1_loss(pred,clean,reduction="none")
    # Equal weight to each supervised surface within this image.
    counts=good.sum((0,2)); supported=counts>0
    loss_per=((ce+.05*l1)*good).sum((0,2))/counts.clamp_min(1)
    boundary=loss_per[supported].mean()
    has_region=region_target.ne(-100)
    region=(F.cross_entropy(regions,region_target,ignore_index=-100,reduction="sum")/has_region.sum().clamp_min(1)) if has_region.any() else regions.sum()*0
    total=boundary+region_weight*region
    return total,dict(boundary=float(boundary.detach()),region=float(region.detach()))
