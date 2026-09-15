"""Re-render diagnostic overlays with wrapped titles; metrics/predictions unchanged."""
from pathlib import Path
import runpy
import sys
import textwrap
from matplotlib.axes import Axes
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
original=Axes.set_title
def set_title(self,label,*args,**kwargs):
    label='\n'.join(textwrap.fill(line,150) for line in str(label).splitlines())
    return original(self,label,*args,**kwargs)
Axes.set_title=set_title
sys.argv=['stage_a_review.py','--split','validation','--eval',str(HERE/'dev_seed20260908/eval_validation'),
    '--out',str(HERE/'dev_seed20260908/review_validation'),'--worst','4']
runpy.run_path(str(ROOT/'code/stage_a_review.py'),run_name='__main__')
