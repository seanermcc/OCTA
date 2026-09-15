"""Measure allocation overhead on the output drive without modifying artifacts."""
from common import *
import ctypes,shutil,math

if __name__=='__main__':
    values=[ctypes.c_ulong() for _ in range(4)]
    ok=ctypes.windll.kernel32.GetDiskFreeSpaceW(str(HERE.anchor),*[ctypes.byref(v) for v in values])
    if not ok:raise ctypes.WinError()
    cluster=values[0].value*values[1].value
    rows=[]
    for folder in HERE.iterdir():
        if not folder.is_dir():continue
        files=list(p for p in folder.rglob('*') if p.is_file())
        rows.append(dict(folder=folder.name,files=len(files),logical_bytes=sum(p.stat().st_size for p in files),
            estimated_allocated_bytes=sum(math.ceil(p.stat().st_size/cluster)*cluster for p in files)))
    result=dict(cluster_bytes=cluster,free_bytes=shutil.disk_usage(HERE).free,folders=rows)
    write(HERE/'verification/storage_audit.json',result);print(json.dumps(result),flush=True)
