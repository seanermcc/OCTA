"""Synthetic optimizer/scaler/RNG round trip; isolated from human records."""
import sys,random,copy,torch,numpy as np
from common import HERE,dest,write
torch.set_num_threads(2)
torch.manual_seed(267);torch.cuda.manual_seed_all(267);random.seed(267);rng=np.random.default_rng(267)
net=torch.nn.Sequential(torch.nn.Conv2d(2,4,3,padding=1),torch.nn.Dropout(.2),torch.nn.Conv2d(4,1,1)).cuda();opt=torch.optim.AdamW(net.parameters(),lr=.001);scaler=torch.amp.GradScaler('cuda',init_scale=1024)
def step():
 opt.zero_grad(set_to_none=True);x=torch.from_numpy(rng.normal(size=(4,2,16,16)).astype('float32')).cuda()
 with torch.autocast('cuda',dtype=torch.float16):loss=net(x).float().square().mean()
 scaler.scale(loss).backward();scaler.step(opt);scaler.update();return float(loss)
step();cp=copy.deepcopy(dict(model=net.state_dict(),optimizer=opt.state_dict(),scaler=scaler.state_dict(),cpu=torch.get_rng_state(),gpu=torch.cuda.get_rng_state_all(),sampler=rng.bit_generator.state))
p=dest(HERE/'verification/synthetic_resume.pt');torch.save(cp,p);expected_loss=step();expected=copy.deepcopy(net.state_dict());restored=torch.load(p,weights_only=False,map_location='cpu');net.load_state_dict(restored['model']);opt.load_state_dict(restored['optimizer']);scaler.load_state_dict(restored['scaler']);torch.set_rng_state(restored['cpu']);torch.cuda.set_rng_state_all(restored['gpu']);rng.bit_generator.state=restored['sampler'];actual_loss=step()
assert expected_loss==actual_loss and all(torch.equal(expected[k],v) for k,v in net.state_dict().items())
write(HERE/'verification/RESUME_QA.json',dict(passed=True,exact_next_update_equal=True,optimizer_scaler_sampler_torch_cuda_rng_restored=True,synthetic=True))
print('Exact synthetic next-update resume verified')
