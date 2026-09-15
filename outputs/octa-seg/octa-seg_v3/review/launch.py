"""Working-directory-independent entry point; activated environment is required."""
from pathlib import Path
import os
import runpy
import sys

here = Path(__file__).resolve().parent
root = next((p for p in here.parents if (p / 'PIPELINE.md').is_file() and (p / 'code/octa/labels.py').is_file()), None)
if root is None:
    raise RuntimeError('Cannot locate the OCTA project from this launcher.')
if Path(os.environ.get('CONDA_PREFIX', '')).name.lower() != 'octa':
    raise RuntimeError('Activate the octa conda environment before launching.')
sys.dont_write_bytecode = True
sys.path[:0] = [str(here / 'code'), str(here.parent.parent / 'octa-seg_v2/code'), str(root / 'code')]
if '--check-paths' in sys.argv:
    from octa_seg_v3 import common
    print('Review:', common.OUT)
    print('Project:', common.ROOT)
    raise SystemExit(0)
module = 'octa_seg_v3.verify_review' if '--verify' in sys.argv else 'octa_seg_v3.gui'
if '--verify' in sys.argv: sys.argv.remove('--verify')
if '--export-targets' in sys.argv:
    sys.argv.remove('--export-targets')
    module = 'octa_seg_v3.export_targets'
runpy.run_module(module, run_name='__main__')
