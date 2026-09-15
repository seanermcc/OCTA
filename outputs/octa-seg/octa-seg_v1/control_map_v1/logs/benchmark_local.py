from pathlib import Path
import os,sys,time,json
sys.path.insert(0,str(Path.cwd()/'code'))
handles=[]
if os.name=='nt': handles.append(os.add_dll_directory(str(Path(os.environ['CONDA_PREFIX'])/'Library/bin')))
import numpy as np
from control_map_v1 import DEFAULTS
from control_map_v1.masks import local_screen
x=np.random.default_rng(1).normal(240,10,(512,512)).astype(np.float32)
t=time.perf_counter()
y=local_screen(x,np.ones_like(x,bool),(1460/512,1460/512),DEFAULTS)
print(json.dumps(dict(synthetic_native_grid_seconds=time.perf_counter()-t,resolved_pixels=int(y['resolved'].sum()))))
