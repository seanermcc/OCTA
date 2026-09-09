"""Exact state pruning and a sparse closed-set graph for the same joint optimum.

A feasible joint solution is an upper bound. Independent smooth-path dynamic
programs supply a lower bound conditional on every state. A state is removed
only when that lower bound exceeds the incumbent, with a numerical allowance.
The remaining ordered depth states form a nonuniform closed-set graph.
"""
import numpy as np
from scipy.ndimage import minimum_filter1d


def constant_incumbent(cost, minimum, maximum):
    """Best feasible four horizontal paths, a valid joint upper bound."""
    unary = cost.sum(2)
    depth = cost.shape[1]
    value = unary[0].copy()
    parents = []
    for k in range(1, 4):
        parent = np.full(depth, -1, int)
        next_value = np.full(depth, np.inf)
        for z in range(depth):
            lo, hi = max(0, z - maximum[k-1]), z - minimum[k-1] + 1
            if hi > lo:
                previous = lo + np.argmin(value[lo:hi])
                next_value[z] = unary[k, z] + value[previous]
                parent[z] = previous
        value = next_value; parents.append(parent)
    endpoint = int(np.argmin(value))
    rows = [endpoint]
    for parent in parents[::-1]:
        rows.append(int(parent[rows[-1]]))
    rows = np.broadcast_to(np.array(rows[::-1])[:, None], (4, cost.shape[2])).copy()
    if not np.isfinite(value[endpoint]) or np.any(rows < 0):
        raise ValueError("No feasible horizontal incumbent")
    return rows, float(value[endpoint])


def conditional_bounds(cost, max_step):
    """Exact independent-path lower bound given a row at an A-line."""
    left = np.empty_like(cost); right = np.empty_like(cost)
    left[:, :, 0] = cost[:, :, 0]
    for x in range(1, cost.shape[2]):
        left[:, :, x] = cost[:, :, x] + minimum_filter1d(left[:, :, x-1], 2*max_step+1,
            axis=1, mode="constant", cval=np.inf)
    right[:, :, -1] = cost[:, :, -1]
    for x in range(cost.shape[2]-2, -1, -1):
        right[:, :, x] = cost[:, :, x] + minimum_filter1d(right[:, :, x+1], 2*max_step+1,
            axis=1, mode="constant", cval=np.inf)
    optimum = left[:, :, -1].min(1)
    return left + right - cost + (optimum.sum() - optimum)[:, None, None]


def exact_graph_cut(cost, minimum, maximum, max_step=2, *, return_diagnostics=False):
    import maxflow
    from stage_a_decoder import validate_cost, dp_project
    cost, minimum, maximum = validate_cost(cost, minimum, maximum, max_step)
    incumbent, upper = constant_incumbent(cost, minimum, maximum)
    candidate = np.floor(dp_project(cost, minimum, maximum, max_step) + .5).astype(int)
    gaps = np.diff(candidate, axis=0)
    if (np.all(gaps >= minimum[:, None]) and np.all(gaps <= maximum[:, None])
            and np.all(np.abs(np.diff(candidate, axis=1)) <= max_step)):
        value = float(cost[np.arange(4)[:, None], candidate, np.arange(cost.shape[2])].sum())
        if value < upper:
            incumbent, upper = candidate, value
    lower = conditional_bounds(cost, max_step)
    allowed = lower <= upper + 1e-7 * max(1., abs(upper))
    # Keep the incumbent explicitly against platform-dependent summation error.
    allowed[np.arange(4)[:, None], incumbent, np.arange(cost.shape[2])] = True
    states, nodes, weights = {}, {}, []
    total, width = 0, cost.shape[2]
    for k in range(4):
        for x in range(width):
            z = np.flatnonzero(allowed[k, :, x])
            if not len(z):
                raise AssertionError("Pruning removed every feasible state")
            states[k, x] = z
            nodes[k, x] = np.arange(total, total + len(z), dtype=np.int64)
            unary = cost[k, z, x]
            weights.append(np.r_[unary[0], np.diff(unary)])
            total += len(z)
    weights = np.concatenate(weights)
    infinity = float(np.abs(weights).sum() + 1.)
    source, sink = np.maximum(-weights, 0), np.maximum(weights, 0)
    edges_a, edges_b = [], []
    def arc(a, b):
        if len(a):
            edges_a.append(a); edges_b.append(b)
    def imply(k, x, target_k, target_x, shift):
        z = states[k, x] + shift
        index = np.searchsorted(states[target_k, target_x], z)
        valid = (index > 0) & (index < len(states[target_k, target_x]))
        arc(nodes[k, x][valid], nodes[target_k, target_x][index[valid]])
        sink[nodes[k, x][index == len(states[target_k, target_x])]] += infinity
    for k in range(4):
        for x in range(width):
            n = nodes[k, x]
            source[n[0]] += infinity
            arc(n[1:], n[:-1])
            if x:
                imply(k, x, k, x-1, -max_step)
            if x+1 < width:
                imply(k, x, k, x+1, -max_step)
            if k < 3:
                imply(k, x, k+1, x, int(minimum[k]))
            if k:
                imply(k, x, k-1, x, -int(maximum[k-1]))
    a = np.concatenate(edges_a) if edges_a else np.array([], np.int64)
    b = np.concatenate(edges_b) if edges_b else np.array([], np.int64)
    graph = maxflow.Graph[float](total, len(a))
    ids = graph.add_nodes(total)
    graph.add_edges(a, b, np.full(len(a), infinity), np.zeros(len(a)))
    graph.add_grid_tedges(ids, source, sink)
    graph.maxflow()
    selected = ~graph.get_grid_segments(ids)
    rows = np.empty((4, width), int)
    for k in range(4):
        for x in range(width):
            count = int(selected[nodes[k, x]].sum())
            if count == 0:
                raise AssertionError("Empty surface prefix")
            rows[k, x] = states[k, x][count-1]
    gaps = np.diff(rows, axis=0)
    if (np.any(gaps < minimum[:, None]) or np.any(gaps > maximum[:, None])
            or np.any(np.abs(np.diff(rows, axis=1)) > max_step)):
        raise AssertionError("Sparse graph violated a hard constraint")
    energy = float(cost[np.arange(4)[:, None], rows, np.arange(width)].sum())
    if energy > upper + 1e-6 * max(1., abs(upper)):
        raise AssertionError("Minimum cut is worse than its feasible incumbent")
    diagnostics = dict(original_states=int(cost.size), retained_states=total,
        pruned_fraction=1-total/cost.size, incumbent_energy=upper, optimum_energy=energy,
        exact_pruning=True)
    return (rows.astype(float), diagnostics) if return_diagnostics else rows.astype(float)
