"""Read-only event interpretation. Only label_gui.py writes annotation journals."""
import numpy as np
from octa.labels import apply_stroke, stroke_support, enforce_order


def resolve(events, baseline, offset, depth):
    """Canonical depth coordinates; exact strokes, joins and displacements remain separate."""
    z = np.asarray(baseline, np.float32).copy()
    shape = z.shape
    n, width = shape
    trace = np.full(shape, -1, np.int8)
    reliability = np.full(shape, -1, np.int8)
    rel_revision = np.full(shape, -1, int)
    anatomy = np.full(shape, -1, np.int8)  # -1 unknown; 0 judged absent/interrupted; 1 present
    drawn = np.zeros(shape, bool)
    taper = np.zeros(shape, bool)
    displaced = np.zeros(shape, bool)
    reviewed = np.zeros(shape, bool)
    approved = np.zeros(shape, bool)
    excluded = np.zeros(width, bool)
    region = np.full(width, -1, np.int8)
    region_revision = np.full(width, -1, int)
    metadata = dict(categories=[], for_review=False, especially_ambiguous=False,
                    data_role='development', completed=False, notes='', blinded=False)
    strokes = 0
    for revision, event in enumerate(events):
        action = event['action']
        if action == 'case_metadata':
            metadata.update(event['values'])
            continue
        lo, hi = int(event['lo']), int(event['hi'])
        if not 0 <= lo < hi <= width:
            raise ValueError('Invalid native A-line interval')
        ks = event.get('boundaries', list(range(n)))
        if any(k < 0 or k >= n for k in ks):
            raise ValueError('Invalid boundary index')
        span = slice(lo, hi)
        if action == 'unreliable_region':
            region[span] = 0
            region_revision[span] = revision
            approved[:, span] = False
            continue
        if action == 'clear_region':
            region[span] = -1
            region_revision[span] = -1
            continue
        if action in ('exclude_image', 'clear_exclusion'):
            excluded[span] = action == 'exclude_image'
            if action == 'exclude_image':
                approved[:, span] = False
            continue
        if action == 'stroke':
            k = ks[0]
            drawing_reliability = event.get('drawing_reliability')
            if drawing_reliability not in (None, 'reliable', 'unreliable'):
                raise ValueError('Invalid drawing reliability mode')
            xs, ys = np.asarray(event['xs']), np.asarray(event['ys'])
            if not len(xs) or len(xs) != len(ys) or not np.isfinite(xs).all() or not np.isfinite(ys).all():
                raise ValueError('Invalid stroke')
            support, joins = stroke_support(width, xs, event['taper'])
            before = z.copy()
            z[k] = apply_stroke(z[k], xs, np.clip(ys, offset, offset + depth - 1), event['taper'])
            # The historic offset-splice cannot repair a NaN base. Direct human
            # points can: replace only the explicitly drawn interval in that case.
            cols = np.clip(np.rint(xs).astype(int), 0, width - 1)
            unique, inverse = np.unique(cols, return_inverse=True)
            yy = np.bincount(inverse, weights=ys) / np.bincount(inverse)
            explicit = np.flatnonzero(support)
            z[k, explicit] = np.clip(np.interp(explicit, unique, yy), offset, offset + depth - 1)
            before_order = z.copy()
            if np.isfinite(z).all():
                z = enforce_order(z).astype(np.float32)
            else:
                # Same downward-only constraint, skipping absent numerical proposals.
                for j in range(1, n):
                    for earlier in range(j):
                        pair = np.isfinite(z[earlier]) & np.isfinite(z[j])
                        z[j, pair] = np.maximum(z[j, pair], z[earlier, pair] + 1)
            moved = ~np.isclose(z, before_order, atol=1e-6, rtol=0, equal_nan=True)
            changed = ~np.isclose(z, before, atol=1e-6, rtol=0, equal_nan=True)
            reviewed[changed] = False
            approved[changed] = False
            reliability[changed & (reliability == 1)] = -1
            rel_revision[changed & (reliability == -1)] = -1
            drawn[k] |= support
            taper[k] |= joins
            taper &= ~drawn
            displaced |= moved
            displaced[k, support & ~moved[k]] = False
            trace[k, support] = 1
            # New GUI modes are explicit judgments on exact human strokes only.
            # Missing mode retains the original semantics of existing journals.
            if drawing_reliability is not None:
                direct = support & ~moved[k]
                reliability[k, direct] = int(drawing_reliability == 'reliable')
                rel_revision[k, direct] = revision
            # A drawn best guess does not silently clear an anatomical-absence judgment.
            approved[k, support] = False
            strokes += 1
            continue
        for k in ks:
            if action in ('not_traceable', 'unreliable', 'absent', 'clear_marks', 'reset_boundary'):
                approved[k, span] = False
            if action == 'not_traceable':
                trace[k, span] = 0
            elif action == 'traceable':
                trace[k, span] = 1
            elif action == 'unreliable':
                reliability[k, span] = 0
                rel_revision[k, span] = revision
            elif action == 'reliable':
                # Ctrl+Alt restores reliability only, exactly as in the original editor.
                reliability[k, span] = 1
                rel_revision[k, span] = revision
            elif action == 'absent':
                anatomy[k, span] = 0
            elif action == 'clear_absence':
                anatomy[k, span] = -1
            elif action == 'clear_marks':
                trace[k, span] = reliability[k, span] = -1
                rel_revision[k, span] = -1
                reviewed[k, span] = False
            elif action == 'reset_boundary':
                z[k, span] = baseline[k, span]
                for plane in (drawn, taper, displaced, reviewed, approved):
                    plane[k, span] = False
                trace[k, span] = reliability[k, span] = anatomy[k, span] = -1
                rel_revision[k, span] = -1
            elif action in ('reviewed', 'approve_position'):
                cc = np.asarray(event['columns'].get(str(k), []), int)
                yy = np.asarray(event['positions'].get(str(k), []), float)
                if len(cc) != len(yy) or np.any((cc < lo) | (cc >= hi)) or not np.isfinite(yy).all():
                    raise ValueError('Invalid position-specific review')
                cc = cc[np.isclose(z[k, cc], yy, atol=1e-4, rtol=0)]
                if action == 'reviewed':
                    trace[k, cc] = reliability[k, cc] = 1
                    rel_revision[k, cc] = revision
                    reviewed[k, cc] = True
                else:
                    approved[k, cc] = True
                    trace[k, cc] = 1
            else:
                raise ValueError(f'Unknown annotation action: {action}')
    use_region = (region[None] >= 0) & (region_revision[None] > rel_revision)
    reliability = np.where(use_region, region[None], reliability).astype(np.int8)
    forbidden = (trace == 0) | (anatomy == 0) | excluded[None]
    approved &= ~forbidden & ~displaced
    return dict(positions=z, trace=trace, reliability=reliability, anatomy=anatomy,
                drawn=drawn, taper=taper, displaced=displaced, reviewed=reviewed,
                approved=approved, excluded=excluded, region=region, metadata=metadata,
                n_strokes=strokes)


def position_targets(resolved, shadow, valid_geometry):
    """Prepared for a future importer; unknown/ambiguous traces are never hard targets."""
    r = resolved
    eligible = r['drawn'] & ~r['displaced'] & (r['trace'] == 1) & (r['anatomy'] != 0)
    eligible &= ~r['excluded'][None] & ~np.asarray(shadow)[None] & valid_geometry
    trace, reliability = r['trace'].copy(), r['reliability'].copy()
    trace[(trace == 1) & r['excluded'][None]] = -1
    reliability[(reliability == 1) & r['excluded'][None]] = -1
    return dict(reliable_manual=eligible & (r['reliability'] == 1),
                ambiguous_manual=eligible & (r['reliability'] != 1),
                approved_position=r['approved'] & ~r['excluded'][None] & ~np.asarray(shadow)[None] & valid_geometry,
                trace=trace, reliability=reliability, anatomy=r['anatomy'].copy())
