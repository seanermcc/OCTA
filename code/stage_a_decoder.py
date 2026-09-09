"""Four-surface decoder experiments, outside the resumable stage_a package.

Graph construction follows Li/Wu/Chen/Sonka (TPAMI 2006): minimum closed sets
with differences of on-surface costs and directed hard implication arcs.
https://pmc.ncbi.nlm.nih.gov/articles/PMC2646122/
PyMaxflow supplies min-cut; this module does not implement a max-flow solver.
https://pmneila.github.io/PyMaxflow/maxflow.html
"""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from scipy.special import logsumexp

from stage_a.common import DEFAULT, output_dir, write_json, write_csv, verify, fingerprint
from stage_a_inner_retina import SURFACES, evaluate, sensitivity


def validate_cost(cost, minimum, maximum, max_step):
    cost = np.asarray(cost, np.float64)
    minimum, maximum = np.asarray(minimum), np.asarray(maximum)
    if cost.ndim != 3 or cost.shape[0] != 4 or not np.isfinite(cost).all():
        raise ValueError("Expected finite [4, depth, A-line] costs")
    if minimum.shape != (3,) or maximum.shape != (3,):
        raise ValueError("Exactly three separation intervals are required")
    if (np.any(minimum < 1) or np.any(maximum < minimum)
            or np.any(minimum != np.floor(minimum)) or np.any(maximum != np.floor(maximum))
            or not np.isfinite(minimum).all() or not np.isfinite(maximum).all()):
        raise ValueError("Separation bounds must be finite positive integers with min <= max")
    if int(max_step) != max_step or max_step < 0 or cost.shape[1] <= minimum.sum():
        raise ValueError("Infeasible depth range or invalid lateral step")
    return cost, minimum.astype(int), maximum.astype(int)


def pava(values):
    """Equal-weight least-squares projection onto the nondecreasing cone."""
    levels, counts = [], []
    for value in np.asarray(values, float):
        levels.append(float(value)); counts.append(1)
        while len(levels) > 1 and levels[-2] > levels[-1]:
            count = counts[-2] + counts[-1]
            value = (levels[-2] * counts[-2] + levels[-1] * counts[-1]) / count
            levels[-2:] = [value]; counts[-2:] = [count]
    return np.repeat(levels, counts)


def dp_project(cost, minimum, maximum, max_step=2):
    from octa.surfaces import dp_surface
    cost, minimum, maximum = validate_cost(cost, minimum, maximum, max_step)
    raw = np.stack([dp_surface(c, max_step=max_step) for c in cost]).astype(float)
    offsets = np.r_[0, np.cumsum(minimum)]
    top_limit = cost.shape[1] - 1 - offsets[-1]
    projected = np.stack([np.clip(pava(raw[:, x] - offsets), 0, top_limit) + offsets
                          for x in range(cost.shape[2])], axis=1)
    # This control enforces minimum separations only, as specified in the brief.
    # The projection is L-infinity nonexpansive, retaining the input step bound.
    if np.any(np.diff(projected, axis=0) < minimum[:, None] - 1e-8):
        raise AssertionError("Projection failed minimum separation")
    if np.any(np.abs(np.diff(projected, axis=1)) > max_step + 1e-8):
        raise AssertionError("Projection failed lateral step constraint")
    return projected


def graph_cut(cost, minimum, maximum, max_step=2, *, prune=False):
    """Joint optimum; optional exact pruning is a separate performance control."""
    if prune:
        from stage_a_decoder_sparse import exact_graph_cut
        return exact_graph_cut(cost, minimum, maximum, max_step)
    return graph_cut_full(cost, minimum, maximum, max_step)


def graph_cut_full(cost, minimum, maximum, max_step=2):
    import maxflow
    cost, minimum, maximum = validate_cost(cost, minimum, maximum, max_step)
    n, depth, width = cost.shape
    weights = np.concatenate([cost[:, :1], np.diff(cost, axis=1)], axis=1)
    infinity = float(np.abs(weights).sum() + 1.)
    graph = maxflow.Graph[float](cost.size, 6 * cost.size)
    nodes = graph.add_grid_nodes(cost.shape)
    source = np.maximum(-weights, 0)
    sink = np.maximum(weights, 0)
    source[:, 0] += infinity  # Every surface chooses at least row zero.

    def imply(a, b):
        a, b = np.ascontiguousarray(a.ravel()), np.ascontiguousarray(b.ravel())
        graph.add_edges(a, b, np.full(a.size, infinity), np.zeros(a.size))

    imply(nodes[:, 1:], nodes[:, :-1])  # Selected rows form a prefix.
    if width > 1:
        if max_step == 0:
            imply(nodes[:, :, :-1], nodes[:, :, 1:])
            imply(nodes[:, :, 1:], nodes[:, :, :-1])
        elif max_step < depth:
            imply(nodes[:, max_step:, :-1], nodes[:, :-max_step, 1:])
            imply(nodes[:, max_step:, 1:], nodes[:, :-max_step, :-1])
    for k, (lo, hi) in enumerate(zip(minimum, maximum)):
        imply(nodes[k, :-lo], nodes[k + 1, lo:])
        sink[k, depth - lo:] += infinity  # Top cannot demand a row beyond depth.
        if hi < depth:
            imply(nodes[k + 1, hi:], nodes[k, :-hi])
    graph.add_grid_tedges(nodes, source, sink)
    graph.maxflow()
    selected = ~graph.get_grid_segments(nodes)
    rows = selected.sum(axis=1) - 1
    separation = np.diff(rows, axis=0)
    if (np.any(rows < 0) or np.any(separation < minimum[:, None])
            or np.any(separation > maximum[:, None])
            or np.any(np.abs(np.diff(rows, axis=1)) > max_step)):
        raise AssertionError("Minimum cut violated a hard constraint")
    return rows.astype(float)


def fit(args):
    from eight_surface.labels import load_label
    from stage_a_inner_retina_audit import manual_valid, permitted_records
    m = json.loads((args.data / "manifest.json").read_text())
    p = json.loads((args.data / "partitions.json").read_text())
    verify(p["manifest"])
    records = permitted_records(m, p)
    animals = set(args.animals or p["animals"]["train"])
    if not animals.issubset(set(p["animals"]["train"] + p["animals"]["validation"])):
        raise ValueError("Cannot fit constraints from locked or unknown animals")
    values, fps, counts = [[] for _ in range(3)], [], [0, 0, 0]
    for r in records:
        if r["animal"] not in animals:
            continue
        verify(r["label"])
        label = load_label(r["label"]["path"])
        valid = manual_valid(label)
        for k in range(3):
            good = valid[k] & valid[k + 1]
            thickness = label["surfaces"][k + 1] - label["surfaces"][k]
            if np.any(good & (thickness <= 0)):
                raise ValueError("Manually supported surfaces cross; audit those labels before fitting bounds")
            if good.any():
                values[k].extend(thickness[good].tolist()); counts[k] += 1
        fps.append(r["label"])
    details = []
    for k, name in enumerate(("RNFL", "GCL", "IPL")):
        if not values[k]:
            raise ValueError(f"No manually drawn pair for {name}")
        q01, median, q99 = np.quantile(values[k], [.01, .5, .99])
        lower_margin, upper_margin = args.margin_fraction * q01, args.margin_fraction * q99
        lo, hi = max(1, int(np.floor(q01 - lower_margin))), int(np.ceil(q99 + upper_margin))
        details.append(dict(layer=name, n_columns=len(values[k]), n_bscans=counts[k],
            q01_px=float(q01), median_px=float(median), q99_px=float(q99),
            lower_widening_px=float(lower_margin), upper_widening_px=float(upper_margin),
            minimum_px=lo, maximum_px=hi))
    out = output_dir(args.out)
    write_json(out / "constraints.json", dict(surface_names=list(SURFACES),
        minimum=[d["minimum_px"] for d in details], maximum=[d["maximum_px"] for d in details],
        max_step=2, details=details, animals=sorted(animals), labels=fps,
        method=f"Manual pair thickness q01/q99: lower endpoint reduced and upper endpoint increased by {100 * args.margin_fraction:g}% of that endpoint; integer bounds rounded outward, minimum one pixel. The margin is relative to each endpoint so a wide upper tail does not collapse the lower bound.",
        margin_fraction=args.margin_fraction, published_values_used=False,
        final_test_used=bool(p.get("authorization", {}).get("former_test_animals_released"))))
    print(json.dumps(details, indent=2))


def run_evaluation(args):
    import torch
    from stage_a.data import Dataset
    from stage_a.train import load_checkpoint
    from stage_a.model import decode
    from stage_a.inference import prediction
    from stage_a_inner_train import load as load_inner
    if args.split not in ("train", "validation"):
        raise ValueError("Final-test animals are locked")
    torch.set_num_threads(2)
    data = Dataset(args.data, args.split, eligible_only=not args.include_unlabelled_decisions)
    if not args.include_unlabelled_decisions:
        data.records = [r for r in data.records if sum(r["eligible_columns_by_surface"][:4]) > 0]
    ck = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    loader = load_inner if ck.get("format") == "inner-retina-experiment-v1" else load_checkpoint
    model, ck = loader(args.checkpoint, device)
    if any(ck["identity"].get(k) != v for k, v in data.identity.items()):
        raise ValueError("Checkpoint and frozen data differ")
    model.eval()
    bound = json.loads(args.constraints.read_text()) if args.constraints else None
    methods = args.methods.split(",")
    implementation = dict(decoder=fingerprint(Path(__file__)),
                          exact_pruning=fingerprint(Path(__file__).with_name("stage_a_decoder_sparse.py")))
    if any(m not in ("soft", "dp_project", "graph_cut") for m in methods):
        raise ValueError("Unknown decoder")
    if any(m != "soft" for m in methods) and bound is None:
        raise ValueError("Constrained decoding requires measured bounds")
    out = output_dir(args.out)
    targets, predictions, movement = {}, {m: {} for m in methods}, []
    for method in methods:
        directory = output_dir(out / method)
        if any(directory.iterdir()):
            raise FileExistsError("Choose a new evaluation directory")
    for number, r in enumerate(data.records, 1):
        entry = data.cache["entries"][r["key"]]
        with np.load(r["targets"], allow_pickle=False) as d:
            t = {k: d[k].copy() for k in d.files}
        targets[r["key"]] = t
        with np.load(entry["file"]["path"], allow_pickle=False) as d:
            x = d["x"]
        with torch.no_grad():
            logits, _ = model(torch.from_numpy(x).unsqueeze(0).to(device))
            raw_rows, entropy = decode(logits)
        full_raw = raw_rows[0].cpu().numpy()
        raw, entropy = full_raw[:4], entropy[0].cpu().numpy()[:4]
        costs = (-logits[:, :4].log_softmax(2))[0].detach().cpu().numpy()
        base = np.zeros(raw.shape, np.uint8)
        base[:, ~t["scope"]] |= 1
        base[:, t["shadow"]] |= 2
        base[~np.isfinite(raw)] |= 4
        full_cross = full_raw[:-1] > full_raw[1:]
        full_flags = np.zeros(full_raw.shape, np.uint8)
        full_flags[:-1][full_cross] |= 8; full_flags[1:][full_cross] |= 8
        original = base | full_flags[:4]
        for method in methods:
            started = time.monotonic()
            if method == "soft":
                rows = raw.copy(); reasons = original.copy()
            else:
                func = dp_project if method == "dp_project" else graph_cut
                rows = func(costs, bound["minimum"], bound["maximum"], bound["max_step"])
                reasons = base.copy()
            displacement = rows - raw
            changed = np.abs(displacement) > .5
            moved = np.abs(displacement)[changed]
            crossing = np.any(rows[:-1] > rows[1:], axis=0)
            pred = dict(rows=(rows - entry["label_offset"]).astype(np.float32),
                retained=reasons == 0, reason_bits=reasons, entropy=entropy,
                raw_reason_bits=original, decoder_displacement_px=displacement.astype(np.float32))
            predictions[method][r["key"]] = pred
            np.savez_compressed(out / method / f"{r['key']}.npz", **pred)
            movement.append(dict(key=r["key"], animal=r["animal"], method=method,
                crossing_alines=int(crossing.sum()), n_alines=len(crossing),
                changed_boundary_columns=int(changed.sum()), n_boundary_columns=int(changed.size),
                moved_median_px=float(np.median(moved)) if moved.size else 0.,
                moved_p95_px=float(np.quantile(moved, .95)) if moved.size else 0.,
                mean_entropy_changed=float(entropy[changed].mean()) if changed.any() else None,
                mean_entropy_unchanged=float(entropy[~changed].mean()) if (~changed).any() else None,
                elapsed_s=time.monotonic() - started))
        print(f"Decoded {number}/{len(data.records)}: {r['key']}", flush=True)
    metrics = []
    for method in methods:
        for scenario, selected in sensitivity(data.records):
            report = evaluate(selected, targets, predictions[method], data.manifest["sources"])
            metrics.extend(dict(decoder=method, sensitivity=scenario, **r) for r in report["summary"])
            write_json(out / method / f"metrics_{scenario}.json", report)
    write_csv(out / "metrics.csv", metrics)
    write_csv(out / "movement.csv", movement)
    write_json(out / "evaluation_meta.json", dict(checkpoint=fingerprint(args.checkpoint),
        constraints=None if args.constraints is None else fingerprint(args.constraints),
        identity=data.identity, split=args.split, methods=methods, final_test_used=False,
        n_bscans=len(data.records), include_unlabelled_decisions=args.include_unlabelled_decisions,
        scope="Four reported surfaces; the unchanged soft baseline preserves crossing flags involving all heads emitted by its checkpoint.",
        constraint_policy="Scope, shadow and missing-data reasons preserved; crossing recomputed after constrained estimation. Raw crossing reasons remain separately recorded.",
        implementation=implementation, graph_algorithm="One joint closed-set minimum cut; optional pruning is not enabled by default"))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--data", type=Path, default=DEFAULT)
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--animals", nargs="+")
    f.add_argument("--margin-fraction", type=float, default=.2)
    e = sub.add_parser("evaluate")
    e.add_argument("--data", type=Path, default=DEFAULT)
    e.add_argument("--split", choices=("train", "validation"), default="validation")
    e.add_argument("--checkpoint", type=Path, required=True)
    e.add_argument("--constraints", type=Path)
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--methods", default="soft,dp_project,graph_cut")
    e.add_argument("--device")
    e.add_argument("--include-unlabelled-decisions", action="store_true",
                   help="Also infer decisions without manual targets; not part of the default accuracy cohort")
    a = p.parse_args()
    fit(a) if a.command == "fit" else run_evaluation(a)
