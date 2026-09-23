"""Batched lateral overlap inference; independent of supervision and v6."""
import numpy as np
import torch
from models import starts,structural_patch
@torch.inference_mode()
def infer_structural(model,volume,stats,device,batch_size=8):
    model.eval();height,depth,width=volume.shape
    total=np.zeros((height,width),np.float32);den=np.zeros_like(total)
    win=np.maximum(np.hanning(256),.001).astype('float32')
    coordinates=[(row,x) for row in range(height) for x in starts(width)]
    for first in range(0,len(coordinates),batch_size):
        group=coordinates[first:first+batch_size]
        inputs=np.stack([structural_patch(volume,row,x,stats) for row,x in group])
        tensor=torch.from_numpy(inputs).to(device)
        with torch.autocast(device_type=device.type,enabled=device.type=='cuda'):
            predictions=model(tensor).sigmoid().float().cpu().numpy()
        if not np.isfinite(predictions).all():raise FloatingPointError('Nonfinite structural prediction')
        for (row,x),score in zip(group,predictions):
            total[row,x:x+256]+=score*win;den[row,x:x+256]+=win
    if not (den>0).all():raise RuntimeError('Uncovered native A-lines')
    return total/den
