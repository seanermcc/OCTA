"""Check exact pruned cuts against saved unpruned development predictions."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import torch
from stage_a.common import DEFAULT, write_json, output_dir
from stage_a.data import Dataset
from stage_a.train import load_checkpoint
from stage_a_decoder_sparse import exact_graph_cut


def run(args):
    torch.set_num_threads(2)
    data = Dataset(DEFAULT, "validation", eligible_only=False)
    lookup = {r["key"]: r for r in data.records}
    if any(key not in lookup for key in args.keys):
        raise ValueError("Only permitted validation decisions can be benchmarked")
    model, _ = load_checkpoint(args.checkpoint, args.device); model.eval()
    bound = json.loads(args.constraints.read_text())
    out = output_dir(args.out)
    results = []
    for key in args.keys:
        entry = data.cache["entries"][key]
        with np.load(entry["file"]["path"], allow_pickle=False) as d:
            x = d["x"]
        with torch.no_grad():
            logits, _ = model(torch.from_numpy(x).unsqueeze(0).to(args.device))
            cost = (-logits[:, :4].log_softmax(2))[0].cpu().numpy()
        started = time.monotonic()
        rows, info = exact_graph_cut(cost, bound["minimum"], bound["maximum"], 2, return_diagnostics=True)
        info.update(key=key, elapsed_s=time.monotonic()-started)
        previous = args.previous / f"{key}.npz"
        if previous.exists():
            with np.load(previous, allow_pickle=False) as d:
                old = np.rint(d["rows"] + entry["label_offset"]).astype(int)
            energy = float(np.asarray(cost, float)[np.arange(4)[:, None], old, np.arange(cost.shape[2])].sum())
            if abs(energy - info["optimum_energy"]) > 1e-5:
                raise AssertionError("Pruned and original full graphs disagree on the optimal energy")
            info.update(unpruned_energy=energy, rows_exactly_equal=bool(np.array_equal(rows, old)))
        np.savez_compressed(out / f"{key}.npz", canonical_rows=rows, cost=cost)
        results.append(info)
        write_json(out / "results.json", results)
        print(json.dumps(info), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--constraints", type=Path, required=True)
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--keys", nargs="+", required=True)
    p.add_argument("--device", default="cpu")
    run(p.parse_args())
