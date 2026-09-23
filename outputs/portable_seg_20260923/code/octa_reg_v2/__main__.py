"""Reproduce the bounded TS247 OD pilot, with deterministic cached searches."""
import shutil
from pathlib import Path
from . import run,complete,corroborate,assemble
from .curves import match

def searches(scans,plan):
    for a,b in plan:
        path=run.OUT/'curve_pairs'/f'{a:02d}_{b:02d}.json'
        if not path.exists():
            r=dict(a=a,b=b,**match(scans[a],scans[b]));run.write(path,r)
            print('curve search',a,b,r['accepted'],flush=True)

run.main()
scans=run.load()
searches(scans,[(0,6),(1,6),(2,6),(3,6),(4,6),(6,7)])
complete.main()
searches(scans,[(0,5),(0,9),(0,22)])
corroborate.main()
assemble.main()
shutil.copyfile(Path(__file__).with_name('viewer.html'),run.OUT/'index.html')
