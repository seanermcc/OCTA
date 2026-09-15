"""Compatibility entry point: the active v6 GUI is in ../review."""
from pathlib import Path
import runpy,sys
if __name__ == '__main__':
    review=Path(__file__).resolve().parents[1]/'review'
    sys.path.insert(0,str(review))
    runpy.run_path(str(review/'viewer.py'),run_name='__main__')
