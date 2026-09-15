"""Read the established thickness engine; never infer missing layer boundaries."""
from common import *
import engine

LAYERS = tuple(engine.LAYERS)
PREVIOUS = ROOT/'outputs/octa-auto_cnv_v3'

def review_config():
    config = read(LONG/'v2/launch_config.json')
    config['manual_sources'] = [str(PREVIOUS/'review/surface_labels'),
        str(Path(config['output'])/'surface_labels'), *config['manual_sources']]
    config['output'] = str(HERE/'review')
    return config

def load_thickness(sid):
    engine.HERE = HERE/'viewer_cache'
    volume = engine.Volume(volume_path(sid), review_config())
    # Mode 0 keeps the engine's shadow, explicit-unreliability and geometry guards.
    return volume.maps[0][0].copy(), volume.metadata()

def limits(values):
    valid = values[np.isfinite(values)]
    lo, hi = np.percentile(valid, [2, 98]) if len(valid) else (0., 1.)
    return float(lo), float(max(hi, lo+1))

def paint_filled(old, stroke):
    """Fill newly closed brush loops, preserving holes deliberately erased earlier."""
    from scipy.ndimage import binary_fill_holes
    old_holes = binary_fill_holes(old) & ~old
    # A deliberately closed new loop fills even an older hollow annotation.
    painted = old | binary_fill_holes(stroke)
    newly_enclosed = binary_fill_holes(painted) & ~painted & ~old_holes
    return painted | newly_enclosed
