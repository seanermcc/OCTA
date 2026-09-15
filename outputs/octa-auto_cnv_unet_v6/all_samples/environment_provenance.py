"""Record the activated numerical runtime used by the frozen inference runner."""
from common import *
import platform,importlib.metadata
import torch

if __name__=='__main__':
    packages={name:importlib.metadata.version(name) for name in ('numpy','scipy','h5py','torch','pandas','PySide6','Pillow')}
    write(HERE/'verification/environment.json',dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
        conda_environment=os.environ.get('CONDA_DEFAULT_ENV'),packages=packages,cuda_runtime=torch.version.cuda,
        cudnn=torch.backends.cudnn.version(),gpu=torch.cuda.get_device_name(0),device_capability=torch.cuda.get_device_capability(0),
        inference_policy=dict(cuda=True,autocast='float16 as frozen v6 infer',cudnn_benchmark=False,cudnn_deterministic=True,torch_cpu_threads=4,tile_batch_size=4)))
