"""Read-only replay and targets for manual lesion annotations, outside the layer stack."""
import hashlib
import json
import numpy as np

CONTRACT = 'cnv-lesion-review-1'
DEFINITION_VERSION = 'cnv-lesion-tentative-1'
DEFINITIONS = {
    'status': 'tentative; revise after inspecting manual examples, before training',
    'CNV region': 'Manual lateral lesion extent; full-depth B-scan columns, not a tissue mask.',
    'CNV edge': 'Bottom of the dark outer-retinal lesion, above the RPE, within the CNV lesion.',
    'Hyper_Ref': 'Hyperreflective dots within the CNV lesion, above and separate from the RPE.',
}
# Add future definitions here; keep historical entries immutable.
DEFINITION_VERSIONS = {DEFINITION_VERSION: DEFINITIONS}
ACTIONS = {'cnv_region', 'cnv_edge', 'cnv_edge_mark', 'hyper_ref'}


def empty(width, depth):
    return dict(cnv_region=np.zeros(width, bool), cnv_edge=np.full(width, np.nan, np.float32),
                cnv_edge_state=np.zeros(width, np.uint8), cnv_edge_unreliable=np.zeros(width, bool),
                hyper_ref=np.zeros((depth, width), bool))


def runs(mask):
    edges = np.flatnonzero(np.diff(np.r_[False, np.asarray(mask, bool), False]))
    return np.column_stack((edges[::2], edges[1::2])).tolist()


def snapshot(state):
    return dict(cnv_region=runs(state['cnv_region']),
                cnv_edge=np.where(np.isfinite(state['cnv_edge']), state['cnv_edge'], None).tolist(),
                cnv_edge_state=state['cnv_edge_state'].tolist(),
                cnv_edge_unreliable=state['cnv_edge_unreliable'].tolist(),
                hyper_ref_runs=runs(state['hyper_ref'].ravel()), shape=list(state['hyper_ref'].shape))


def digest(state):
    return hashlib.sha256(json.dumps(snapshot(state), sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def brush_mask(points, shape, diameter):
    """Continuous round brush in native image pixels; independent of display zoom/stretch."""
    points = np.asarray(points, float)
    if points.ndim != 2 or points.shape[1] != 2 or not len(points) or not np.isfinite(points).all():
        raise ValueError('Invalid Hyper_Ref brush path')
    if not np.isfinite(diameter) or not 1 <= diameter <= 150:
        raise ValueError('Invalid brush diameter')
    height, width = shape
    if ((points < 0).any() or (points[:, 0] > width - 1).any() or (points[:, 1] > height - 1).any()):
        raise ValueError('Brush path outside the native B-scan')
    result = np.zeros(shape, bool)
    radius = diameter / 2.
    for a, b in zip(points, np.vstack((points[1:], points[-1:]))):
        lo = np.maximum(0, np.floor(np.minimum(a, b) - radius).astype(int))
        hi = np.minimum([width, height], np.ceil(np.maximum(a, b) + radius).astype(int) + 1)
        yy, xx = np.mgrid[lo[1]:hi[1], lo[0]:hi[0]]
        d = b - a
        t = np.clip(((xx-a[0])*d[0] + (yy-a[1])*d[1]) / max(float(d @ d), 1e-12), 0, 1)
        result[lo[1]:hi[1], lo[0]:hi[0]] |= (xx-a[0]-t*d[0])**2 + (yy-a[1]-t*d[1])**2 <= radius**2
    return result


def apply(state, event, offset):
    if event.get('lesion_definition') not in DEFINITION_VERSIONS:
        raise ValueError('Unsupported lesion definition; explicit migration is required')
    width = len(state['cnv_region'])
    depth = state['hyper_ref'].shape[0]
    lo, hi = event['lo'], event['hi']
    if not 0 <= lo < hi <= width:
        raise ValueError('Invalid lesion A-line span')
    action = event['action']
    erase = event.get('erase', False)
    if not isinstance(erase, bool):
        raise ValueError('Invalid eraser state')
    if action == 'cnv_region':
        state['cnv_region'][lo:hi] = not erase
    elif action == 'cnv_edge':
        if erase:
            state['cnv_edge'][lo:hi] = np.nan
            state['cnv_edge_state'][lo:hi] = 0
            state['cnv_edge_unreliable'][lo:hi] = False
        else:
            xs, ys = np.asarray(event['xs'], float), np.asarray(event['ys'], float)
            if (xs.ndim != 1 or ys.shape != xs.shape or not len(xs) or not np.isfinite(xs).all()
                    or not np.isfinite(ys).all() or (xs < 0).any() or (xs > width-1).any()
                    or (ys < offset).any() or (ys > offset+depth-1).any()):
                raise ValueError('Invalid CNV edge stroke')
            # Last value in each visited column wins; interpolate only within this stroke.
            columns = dict(zip(np.rint(xs).astype(int).tolist(), ys.tolist()))
            x = np.array(sorted(columns))
            if lo != x[0] or hi != x[-1] + 1:
                raise ValueError('CNV edge span differs from its stroke')
            state['cnv_edge'][lo:hi] = np.interp(np.arange(lo, hi), x, [columns[k] for k in x])
            state['cnv_edge_state'][lo:hi] = 2 if event.get('unreliable', False) else 1
            state['cnv_edge_unreliable'][lo:hi] = event.get('unreliable', False)
    elif action == 'cnv_edge_mark':
        mark = event['mark']
        codes = {'unreliable': 2, 'not_traceable': 3, 'reliable': 1, 'traceable': 1,
                 'clear_marks': 1, 'absent': 0, 'reset_boundary': 0}
        if mark not in codes:
            raise ValueError('Unsupported CNV edge mark')
        code = codes[mark]
        current = state['cnv_edge_state'][lo:hi]
        uncertain = state['cnv_edge_unreliable'][lo:hi]
        finite = np.isfinite(state['cnv_edge'][lo:hi])
        if mark == 'reliable':  # Reliability alone cannot restore a no-trace interval.
            uncertain[:] = False
            current[current == 2] = np.where(finite[current == 2], 1, 0)
        elif mark == 'unreliable':
            uncertain[:] = True
            current[current != 3] = 2
        elif code == 1:
            if mark == 'clear_marks':
                uncertain[:] = False
            current[:] = np.where(finite, np.where(uncertain, 2, 1), 0)
        else:
            current[:] = code
        if code == 0:
            state['cnv_edge'][lo:hi] = np.nan
            uncertain[:] = False
    elif action == 'hyper_ref':
        points = np.column_stack((event['xs'], np.asarray(event['ys'], float) - offset))
        footprint = brush_mask(points, state['hyper_ref'].shape, event['diameter'])
        state['hyper_ref'][footprint] = not erase
    else:
        raise ValueError('Unsupported lesion action')


def outside_region(state):
    return (~state['cnv_region'] & (np.isfinite(state['cnv_edge']) |
            (state['cnv_edge_state'] != 0) | state['hyper_ref'].any(axis=0)))


def targets(state, eligible, excluded, shadow, vessel=None):
    """Completed empty paint is negative inside the reviewed CNV region; drafts are masked."""
    usable = ~np.asarray(excluded) & ~np.asarray(shadow) & bool(eligible)
    inside = usable & state['cnv_region']
    edge_state = state['cnv_edge_state']
    edge_usable = usable if vessel is None else usable & ~np.asarray(vessel, bool)
    return dict(cnv_region=state['cnv_region'].copy(), cnv_region_known=usable,
                cnv_edge=state['cnv_edge'].copy(), cnv_edge_state=edge_state.copy(),
                cnv_edge_unreliable=state['cnv_edge_unreliable'].copy(),
                cnv_edge_known=edge_usable & (state['cnv_region'] | (edge_state == 1)) & (edge_state < 2),
                cnv_edge_valid=edge_usable & (edge_state == 1) & np.isfinite(state['cnv_edge']),
                hyper_ref=state['hyper_ref'].copy(),
                hyper_ref_known=(inside[None] | (usable[None] & state['hyper_ref'])))
