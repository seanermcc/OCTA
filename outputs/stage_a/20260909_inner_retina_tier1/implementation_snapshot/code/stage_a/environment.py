"""Record the activated scientific environment without importing the GUI."""
import importlib.metadata as md
import json
import os
from pathlib import Path
import subprocess
import sys

if os.environ.get("CONDA_DEFAULT_ENV") != "octa":
    raise RuntimeError("Activate conda octa before Python")
out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
if out.exists():
    raise FileExistsError(out)
packages = {d.metadata["Name"]: d.version for d in md.distributions()}
payload = {"python": sys.version, "executable": sys.executable,
           "packages": packages,
           "gpu": subprocess.check_output(["nvidia-smi"], text=True)}
for name in ("numpy", "scipy", "h5py", "matplotlib", "pandas", "skimage"):
    mod = __import__(name)
    payload[name] = mod.__version__
import numpy as np
payload["numpy_dot"] = int(np.dot([1, 2], [3, 4]))
if "torch" in packages:
    import torch
    payload["torch_cuda"] = torch.version.cuda
    payload["cuda_available"] = torch.cuda.is_available()
    if torch.cuda.is_available():
        payload["cuda_compute"] = float((torch.ones(8, device="cuda") ** 2).sum())
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(out)
