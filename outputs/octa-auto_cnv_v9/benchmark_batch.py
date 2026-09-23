"""Synthetic throughput measurement; no datasets, labels, or fit outputs changed."""
import time,torch,json
from models import UNet,masked_loss
torch.set_num_threads(4);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
for batch in (1,4):
 net=UNet(30).cuda();opt=torch.optim.AdamW(net.parameters(),lr=.001);scaler=torch.amp.GradScaler('cuda',init_scale=1024);x=torch.randn(batch,30,256,256,device='cuda');y=(torch.rand(batch,256,256,device='cuda')>.95).float();k=torch.ones_like(y)
 torch.cuda.synchronize();start=time.time()
 for step in range(12):
  opt.zero_grad(set_to_none=True)
  for _ in range(4//batch):
   with torch.autocast('cuda',dtype=torch.float16):z=net(x);loss=masked_loss(z,y,k,1)/(4//batch)
   scaler.scale(loss).backward()
  scaler.step(opt);scaler.update()
 torch.cuda.synchronize();print(json.dumps(dict(microbatch=batch,effective_batch=4,seconds_per_optimizer_step=(time.time()-start)/12,peak_bytes=torch.cuda.max_memory_allocated())),flush=True)
 del net,opt,x,y,k;torch.cuda.empty_cache()
