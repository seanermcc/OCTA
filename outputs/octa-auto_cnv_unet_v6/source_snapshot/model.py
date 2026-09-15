"""Random-initialized four-downsample compact CNV U-Net."""
import torch
from torch import nn
from torch.nn import functional as F

class Block(nn.Sequential):
    def __init__(self,inputs,outputs):
        super().__init__(nn.Conv2d(inputs,outputs,3,padding=1,bias=False),nn.GroupNorm(8,outputs),nn.SiLU(),
                         nn.Conv2d(outputs,outputs,3,padding=1,bias=False),nn.GroupNorm(8,outputs),nn.SiLU())

class UNet(nn.Module):
    def __init__(self,channels):
        super().__init__()
        widths=[16,32,64,128,256]
        self.encoder=nn.ModuleList([Block(channels if i==0 else widths[i-1],w) for i,w in enumerate(widths)])
        self.up=nn.ModuleList([nn.ConvTranspose2d(a,b,2,stride=2) for a,b in zip(widths[:0:-1],widths[-2::-1])])
        self.decoder=nn.ModuleList([Block(2*w,w) for w in widths[-2::-1]])
        self.head=nn.Conv2d(16,1,1)

    def forward(self,x):
        skip=[]
        for i,enc in enumerate(self.encoder):
            x=enc(x)
            if i<4: skip.append(x);x=F.max_pool2d(x,2)
        for up,dec,s in zip(self.up,self.decoder,reversed(skip)):
            x=dec(torch.cat([up(x),s],1))
        return self.head(x)[:,0]

def masked_loss(logits,target,known):
    """Per-tile BCE; Dice only for known positive tiles; unknown tiles omitted."""
    known=known.float(); target=target.float(); n=known.sum((1,2)); valid=n>0
    if not valid.any(): return logits.sum()*0
    bce=(F.binary_cross_entropy_with_logits(logits,target,reduction='none')*known).sum((1,2))/n.clamp_min(1)
    prob=logits.sigmoid()*known; truth=target*known
    positive=truth.sum((1,2))>0
    dice=1-(2*(prob*truth).sum((1,2))+1)/(prob.sum((1,2))+truth.sum((1,2))+1)
    return (bce+torch.where(positive,dice,0))[valid].mean()

@torch.inference_mode()
def infer(model,array,device,batch_size=4):
    """Native 256 tiles at 128 stride, positive Hann weights including FOV edges."""
    import numpy as np
    model.eval(); h,w=array.shape[-2:]; size=256;stride=128
    ys=sorted(set(list(range(0,h-size+1,stride))+[h-size])); xs=sorted(set(list(range(0,w-size+1,stride))+[w-size]))
    coords=[(y,x) for y in ys for x in xs]
    weights=np.maximum(np.outer(np.hanning(size),np.hanning(size)),.001).astype('float32')
    total=np.zeros((h,w),np.float32);denom=total.copy()
    for start in range(0,len(coords),batch_size):
        group=coords[start:start+batch_size]
        tensor=torch.from_numpy(np.stack([array[:,y:y+size,x:x+size] for y,x in group])).to(device)
        with torch.autocast(device_type=device.type,enabled=device.type=='cuda'):
            p=model(tensor).sigmoid().float().cpu().numpy()
        for (y,x),v in zip(group,p):
            total[y:y+size,x:x+size]+=v*weights;denom[y:y+size,x:x+size]+=weights
    assert (denom>0).all()
    return total/denom
