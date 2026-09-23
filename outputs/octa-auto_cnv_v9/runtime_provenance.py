import torch,platform,sys,os
from common import write,HERE
from v6_model import UNet
write(HERE/'reports/runtime.json',dict(python=sys.version,platform=platform.platform(),conda_environment=os.environ.get('CONDA_DEFAULT_ENV'),torch=torch.__version__,cuda_runtime=torch.version.cuda,cudnn=torch.backends.cudnn.version(),device=torch.cuda.get_device_name(0),device_memory_bytes=torch.cuda.get_device_properties(0).total_memory,training_threads=4,precision='CUDA float16 autocast with float32 parameters and GradScaler',microbatch=4,effective_batch=4,backbone_widths=[16,32,64,128,256],parameters={str(c):sum(p.numel() for p in UNet(c).parameters()) for c in (19,30)}))
print('Recorded training runtime and parameter counts')
