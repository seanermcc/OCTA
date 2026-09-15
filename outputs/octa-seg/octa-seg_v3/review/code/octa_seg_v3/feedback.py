"""Read-only event interpretation. Only label_gui.py writes annotation journals."""
import numpy as np
import hashlib
import json
from octa.labels import apply_stroke, stroke_support, enforce_order

CONTRACT = 'whole-bscan-confirmation-1'
STATE_KEYS = ('positions', 'trace', 'reliability', 'anatomy', 'drawn', 'taper', 'displaced', 'excluded', 'region')


def state_digest(r):
    h = hashlib.sha256()
    for key in STATE_KEYS:
        a = np.ascontiguousarray(r[key])
        h.update(key.encode()); h.update(str(a.shape).encode()); h.update(str(a.dtype).encode())
        h.update(a.tobytes())
    return h.hexdigest()


def geometry(r, offset, depth):
    """Ignore explicitly denied/ambiguous proposals when checking measurable geometry."""
    z = r['positions']
    exception = (r['trace'] == 0) | (r['reliability'] == 0) | (r['anatomy'] == 0) | r['excluded'][None]
    finite = np.isfinite(z)
    valid = finite & (z >= offset) & (z <= offset + depth - 1)
    for k in range(len(z)):
        for j in range(k):
            pair = finite[k] & finite[j] & ~exception[k] & ~exception[j]
            crossing = pair & (z[k] < z[j] + 1)
            valid[k, crossing] = False
            valid[j, crossing] = False
    return valid, ~valid & ~exception


def anchored_order(z, active, touched, trace, anatomy, excluded):
    """Keep active values; move only colliding available neighbors in touched columns.

    Do not clamp neighbors at image edges: impossible geometry remains explicit.
    Hidden display curves still participate; absent/no-trace curves do not.
    """
    initial = touched & ~excluded & np.isfinite(z[active])
    for direction in (-1, 1):
        pending = initial.copy()
        anchor = z[active].copy()
        for k in range(active + direction, len(z) if direction > 0 else -1, direction):
            available = np.isfinite(z[k]) & (trace[k] != 0) & (anatomy[k] != 0)
            limit = anchor + direction
            colliding = direction * (z[k] - limit) < 0
            moved = pending & available & colliding
            z[k, moved] = limit[moved]
            anchor[moved] = z[k, moved]
            pending &= ~available | colliding
            if not pending.any():
                break
    return z


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
    # Display continuity is independent of revision-specific training approval.
    display_reliable = np.zeros(shape, bool)
    excluded = np.zeros(width, bool)
    region = np.full(width, -1, np.int8)
    region_revision = np.full(width, -1, int)
    metadata = dict(categories=[], for_review=False, especially_ambiguous=False,
                    data_role='development', completed=False, notes='', blinded=False)
    strokes = 0
    confirmation = None
    had_confirmation = False
    geometry_revision = None
    for revision, event in enumerate(events):
        action = event['action']
        if action == 'case_metadata':
            if 'data_role' in event['values'] and event['values']['data_role'] != metadata['data_role']:
                if had_confirmation:
                    approved[:] = False
                    confirmation = None
                geometry_revision = event.get('id', 'legacy-' + str(revision))
            metadata.update(event['values'])
            continue
        if action == 'confirm_bscan':
            if event.get('contract') != CONTRACT:
                raise ValueError('Unknown whole-B-scan confirmation contract')
            effective_rel = np.where((region[None] >= 0) & (region_revision[None] > rel_revision), region[None], reliability).astype(np.int8)
            current = dict(positions=z, trace=trace, reliability=effective_rel, anatomy=anatomy,
                           drawn=drawn, taper=taper, displaced=displaced, excluded=excluded, region=region)
            valid, problems = geometry(current, offset, depth)
            if (event.get('state_digest') != state_digest(current) or event.get('scope') != [n, width]
                    or problems.any() or event.get('geometry_revision') != geometry_revision):
                raise ValueError('Confirmation does not match the full current geometry/state revision')
            snapshot = event.get('snapshot', {})
            for key in STATE_KEYS:
                arr = np.asarray(snapshot.get(key), dtype=current[key].dtype)
                if arr.shape != current[key].shape or not np.array_equal(arr, current[key], equal_nan=True):
                    raise ValueError('Confirmation snapshot differs from event replay: ' + key)
            approved = valid & (trace != 0) & (effective_rel != 0) & (anatomy != 0) & ~excluded[None]
            if not np.array_equal(np.asarray(snapshot.get('approved'), bool), approved):
                raise ValueError('Confirmation approved mask differs from explicit exceptions')
            confirmation = event
            display_reliable = approved.copy()
            had_confirmation = True
            continue
        if event.get('semantics', 1) >= 2:
            # Every substantive event invalidates the whole approval, even a no-op mark.
            if had_confirmation:
                approved[:] = False
            confirmation = None
        geometry_revision = event.get('id', 'legacy-' + str(revision))
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
            if event.get('semantics', 1) >= 2:
                blocked = (trace[k] == 0) | (anatomy[k] == 0) | excluded | ~np.isfinite(before[k])
                allowed_joins = joins.copy()
                for direction, edge in ((-1, explicit[0]), (1, explicit[-1])):
                    for x in range(edge + direction, width if direction > 0 else -1, direction):
                        if blocked[x]:
                            if direction < 0: allowed_joins[:x+1] = False
                            else: allowed_joins[x:] = False
                            break
                z[k, ~support & ~allowed_joins] = before[k, ~support & ~allowed_joins]
                joins = allowed_joins
            before_order = z.copy()
            if event.get('semantics', 1) >= 2:
                # NaN joins stay absent; drawing cannot erase unrelated finite values.
                z[k, ~support & ~np.isfinite(z[k])] = before[k, ~support & ~np.isfinite(z[k])]
                active_changed = ~np.isclose(z[k], before[k], atol=1e-6, rtol=0, equal_nan=True)
                z = anchored_order(z, k, support | active_changed, trace, anatomy, excluded)
            elif np.isfinite(z).all():
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
            if event.get('semantics', 1) < 3:
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
                display_reliable[k, span] = False
                trace[k, span] = reliability[k, span] = -1
                rel_revision[k, span] = -1
                reviewed[k, span] = False
            elif action == 'reset_boundary':
                display_reliable[k, span] = False
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
    approved &= ~forbidden
    if not had_confirmation:
        approved &= ~displaced
    result = dict(positions=z, trace=trace, reliability=reliability, anatomy=anatomy,
                drawn=drawn, taper=taper, displaced=displaced, reviewed=reviewed,
                approved=approved, display_reliable=display_reliable,
                excluded=excluded, region=region, metadata=metadata,
                n_strokes=strokes, confirmation=confirmation, geometry_revision=geometry_revision,
                review_status='Confirmed' if confirmation else 'Needs reconfirmation' if had_confirmation else 'Draft')
    result['valid_geometry'], result['unresolved'] = geometry(result, offset, depth)
    return result


def position_targets(resolved, shadow, valid_geometry):
    """Prepared for a future importer; unknown/ambiguous traces are never hard targets."""
    r = resolved
    eligible = r['drawn'] & ~r['displaced'] & (r['trace'] == 1) & (r['anatomy'] != 0)
    eligible &= ~r['excluded'][None] & ~np.asarray(shadow)[None] & valid_geometry
    trace, reliability = r['trace'].copy(), r['reliability'].copy()
    trace[(trace == 1) & r['excluded'][None]] = -1
    reliability[(reliability == 1) & r['excluded'][None]] = -1
    approved = r['approved'] & np.isfinite(r['positions']) & (r['trace'] != 0) & (r['reliability'] != 0) & (r['anatomy'] != 0)
    approved &= ~r['excluded'][None] & ~np.asarray(shadow)[None] & valid_geometry
    if r.get('confirmation'):
        trace[approved] = reliability[approved] = 1
    return dict(reliable_manual=eligible & (r['reliability'] == 1),
                ambiguous_manual=eligible & (r['reliability'] != 1),
                approved_position=approved,
                trace=trace, reliability=reliability, anatomy=r['anatomy'].copy())


def training_targets(record, baseline, offset, depth, shadow, role='development'):
    """Authoritative importer: role-gated NEW whole-confirmed pool, never implicit NPZ labels."""
    r = resolve(record['events'][:record['cursor']], baseline, offset, depth)
    if record.get('pinned_data_role'):
        r['metadata']['data_role'] = record['pinned_data_role']
    confirmation = r.get('confirmation')
    if confirmation:
        for key in ('reviewer_id', 'scan_id', 'bscan', 'model_id', 'source'):
            if confirmation.get(key) != record.get(key):
                raise ValueError('Confirmed snapshot identity differs from journal: ' + key)
        if confirmation.get('boundary_names') != record.get('boundary_names', confirmation['boundary_names']):
            raise ValueError('Confirmed boundary definitions differ from journal')
    targets = position_targets(r, shadow, r['valid_geometry'])
    eligible = (record.get('training_eligible') is True and not record['scan_id'].startswith('SYNTHETIC')
                and r['metadata']['data_role'] == role and role in ('development', 'assessment')
                and r['confirmation'] is not None)
    targets['approved_position'] &= eligible
    targets['reliable_manual'] &= eligible
    targets['ambiguous_manual'] &= eligible
    targets['ambiguous_candidate'] = (r['reliability'] == 0) & (r['trace'] != 0) & (r['anatomy'] != 0)
    targets['ambiguous_candidate'] &= np.isfinite(r['positions']) & ~r['excluded'][None] & ~np.asarray(shadow)[None] & eligible
    targets['ambiguous_candidate'] &= (r['positions'] >= offset) & (r['positions'] <= offset+depth-1)
    targets.update(positions=r['positions'], drawn=r['drawn'], joined=r['taper'], displaced=r['displaced'],
                   review_status=r['review_status'], eligible=eligible)
    if not eligible:
        for key in ('trace', 'reliability', 'anatomy'):
            targets[key][:] = -1
    return targets
