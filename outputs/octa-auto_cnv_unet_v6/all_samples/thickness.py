"""Automatic-only v6 maps, with the existing v5 paint behavior."""
from common import *
def limits(values):
    valid=values[np.isfinite(values)]
    lo,hi=np.percentile(valid,[2,98]) if len(valid) else (0.,1.)
    return float(lo),float(max(hi,lo+1))
def paint_filled(old,stroke):
    from scipy.ndimage import binary_fill_holes
    old_holes=binary_fill_holes(old)&~old
    painted=old|binary_fill_holes(stroke)
    return painted|(binary_fill_holes(painted)&~painted&~old_holes)
