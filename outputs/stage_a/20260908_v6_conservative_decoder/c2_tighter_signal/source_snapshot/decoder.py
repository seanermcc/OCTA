"""Bounded posterior relocation with monotone withholding and partial surfaces.

No normal thickness priors. Already rejected measurements never return. Every
retained subset is ordered, with a one-pixel geometric gap. Disconnected usable
intervals have independent lateral costs. Jumps and tiny islands are withheld,
not bridged or moved toward a smooth-looking answer.
"""
import numpy as np
from stage_a_readability_ordered.ordered import ordered_column, intervals, gated_raw

REASONS = dict(outside_scope=1, shadow=2, missing=4, crossing=8, uncertainty=16,
    readability=32, posterior_unsupported=64, order_infeasible=128,
    simple_entropy_signal=256, relocation_unsupported=512,
    abrupt_jump=1024, short_interval=2048, previous_version_withheld=4096)


def ordered_flags(rows, gap=1.):
    """Flags all retained pairs, including those separated by missing surfaces."""
    bad=np.zeros(rows.shape,bool)
    for i in range(len(rows)):
        for j in range(i+1,len(rows)):
            conflict=np.isfinite(rows[i])&np.isfinite(rows[j])&(rows[j]-rows[i]<gap)
            bad[i,conflict]=True; bad[j,conflict]=True
    return bad


def jump_flags(rows, allowed, limit, radius=1):
    """Mark endpoints and a small guard around jumps within a usable interval.

    No comparison is made across a rejected column. Mask growth is restricted
    to the original connected interval and never leaks over its rejected gaps.
    """
    bad=np.zeros(rows.shape,bool)
    for k in range(len(rows)):
        for start,end in intervals(allowed[k]):
            jump=np.flatnonzero(abs(np.diff(rows[k,start:end]))>limit[k])+start
            for c in jump:
                bad[k,max(start,c-radius):min(end,c+2+radius)]=True
    return bad


def prune_short(reason, minimum):
    for k in range(len(reason)):
        for a,b in intervals(reason[k]==0):
            if b-a<minimum: reason[k,a:b]|=REASONS['short_interval']


def decode(logits, raw, entropy, scope, shadow, config, gate=None, parent=None):
    logits=np.asarray(logits,np.float32); raw=np.asarray(raw,np.float32)
    entropy=np.asarray(entropy,np.float32)
    if logits.ndim!=3 or logits.shape[0]!=8 or raw.shape!=logits.shape[::2] or entropy.shape!=raw.shape:
        raise ValueError('Expected [8, depth, width] distributions and [8,width] rows/entropy')
    _,height,width=logits.shape
    if np.shape(scope)!=(width,) or np.shape(shadow)!=(width,): raise ValueError('Scope/shadow geometry')
    maximum=float(config['max_displacement_px'])
    cap=np.asarray(config['entropy_cap'],float)
    steps=np.asarray(config['max_step_px'],float)
    if maximum<0 or cap.shape!=(8,) or steps.shape!=(8,) or (steps<=0).any() or not np.isfinite(steps).all():
        raise ValueError('Invalid conservative decoder configuration')
    base=gated_raw(raw,scope,shadow)
    reason=base['reason_bits'].astype(np.uint16)
    # Preserve original per-boundary crossing withholding. Further geometric
    # exclusions consider every surviving pair, not just adjacent names.
    if parent is not None:
        if parent['retained'].shape!=raw.shape: raise ValueError('Parent geometry')
        inherited=~parent['retained']
        reason|=parent['reason_bits'].astype(np.uint16)
        reason[inherited]|=REASONS['previous_version_withheld']
    if gate is not None:
        gate=np.asarray(gate,bool)
        if gate.shape not in ((width,),raw.shape): raise ValueError('Gate shape')
        reason[~np.broadcast_to(gate,raw.shape)]|=REASONS['simple_entropy_signal']
    reason[(~np.isfinite(entropy))|(entropy>cap[:,None])]|=REASONS['posterior_unsupported']
    reason[~np.isfinite(logits).all(1)]|=REASONS['posterior_unsupported']
    safe=np.where(np.isfinite(logits),logits,-1e6)
    cost=safe.max(1,keepdims=True)-safe
    depth=np.arange(height)[None,:,None]
    # This is a data-support admissibility test, not a forced displacement cap:
    # if no sufficiently probable row is nearby, the surface is withheld.
    admissible=(abs(depth-raw[:,None,:])<=maximum)&(cost<=config['max_log_drop'])
    cost=np.where(admissible,cost,np.inf)
    reason[~admissible.any(1)]|=REASONS['relocation_unsupported']
    raw_jump=jump_flags(raw,reason==0,steps,config['jump_guard_radius'])
    reason[raw_jump]|=REASONS['abrupt_jump']
    prune_short(reason,config['min_interval_columns'])

    def solve():
        rows=np.full(raw.shape,np.nan,np.float32)
        active=reason==0
        for c in range(width):
            k=np.flatnonzero(active[:,c])
            if not len(k): continue
            selected=ordered_column(cost[k,:,c])
            if selected is None:
                reason[k,c]|=REASONS['order_infeasible']; active[k,c]=False
            else: rows[k,c]=selected
        # A hard gap for all boundaries separates independent image intervals.
        # Individual surfaces only see adjacent neighbors retained for that surface.
        for a,b in intervals(active.any(0)):
            for sweep in (range(a,b),range(b-1,a-1,-1)):
                for c in sweep:
                    k=np.flatnonzero(active[:,c])
                    if not len(k): continue
                    local=cost[k,:,c].copy()
                    for neighbor in (c-1,c+1):
                        if not a<=neighbor<b: continue
                        connected=active[k,neighbor]
                        if connected.any():
                            ii=np.flatnonzero(connected)
                            distance=abs(np.arange(height)[None,:]-rows[k[ii],neighbor,None])
                            local[ii]+=config['continuity_weight']*np.minimum(distance/steps[k[ii],None],4.)
                    selected=ordered_column(local)
                    if selected is None: raise RuntimeError('Finite penalty destroyed feasibility')
                    rows[k,c]=selected
        return rows

    # After removals, re-solve so rejected positions cannot keep influencing
    # neighboring values. Masks only shrink; exhaustion is explicit withholding.
    for iteration in range(config['max_guard_iterations']):
        before=reason.copy()
        rows=solve()
        reason[ordered_flags(rows)]|=REASONS['order_infeasible']
        reason[jump_flags(rows,reason==0,steps,config['jump_guard_radius'])]|=REASONS['abrupt_jump']
        prune_short(reason,config['min_interval_columns'])
        if np.array_equal(reason,before): break
    else:
        # Fail closed for still-changing connected image intervals rather than
        # return a curve influenced by the last discarded candidates.
        changed=(reason!=before).any(0)
        for a,b in intervals((before==0).any(0)):
            if changed[a:b].any(): reason[:,a:b]|=REASONS['abrupt_jump']
        rows=solve()
        reason[ordered_flags(rows)]|=REASONS['order_infeasible']
    retained=reason==0
    retained_rows=np.where(retained,rows,np.nan)
    if not np.isfinite(retained_rows[retained]).all(): raise AssertionError('Finite measurement invariant')
    if ordered_flags(retained_rows).any(): raise AssertionError('Retained order invariant')
    if jump_flags(retained_rows,retained,steps,0).any(): raise AssertionError('Retained jump invariant')
    if (retained&~base['retained']).any(): raise AssertionError('Original withholding rescued')
    if parent is not None and (retained&~parent['retained']).any(): raise AssertionError('Parent withholding rescued')
    if np.any(abs(retained_rows-raw)[retained]>maximum+1e-5): raise AssertionError('Unbounded relocation')
    return dict(rows=rows,retained_rows=retained_rows,retained=retained,reason_bits=reason,
        decoder_displacement_px=rows-raw,guard_iterations=iteration+1)
