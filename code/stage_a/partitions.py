"""Freeze the animal partition after the coverage census, before any fitting."""
import argparse
import json
from pathlib import Path
from collections import Counter
import numpy as np
from .common import DEFAULT, write_json, fingerprint, digest

ANIMALS = {
    "train": ["TS165", "TS241", "TS250", "TS267", "TS305"],
    "validation": ["TS169", "TS325", "TS336"],
    "test": ["TS247", "TS283", "TS328"],
}


def validate_partition(manifest, partition):
    if digest({k:v for k,v in manifest.items() if k!="dataset_id"}) != manifest["dataset_id"]:
        raise ValueError("Dataset identity changed")
    if "partition_id" in partition and digest({k:v for k,v in partition.items() if k!="partition_id"}) != partition["partition_id"]:
        raise ValueError("Frozen partition identity changed")
    animals = [a for values in partition["animals"].values() for a in values]
    if len(animals) != len(set(animals)):
        raise ValueError("Animal leakage")
    if set(animals) != {r["animal"] for r in manifest["records"]}:
        raise ValueError("Animal assignment incomplete")
    if partition["dataset_id"] != manifest["dataset_id"]:
        raise ValueError("Partition belongs to another dataset")
    for split, members in partition["animals"].items():
        expected = sorted(r["key"] for r in manifest["records"] if r["animal"] in members)
        if partition["keys"][split] != expected:
            raise ValueError("Sample assignment violates animal groups")


def freeze(out):
    out=Path(out)
    path=out/"partitions.json"
    if path.exists():
        raise FileExistsError("Partitions are frozen; do not reshuffle")
    m=json.loads((out/"manifest.json").read_text())
    stats={}
    keys={}
    for split, animals in ANIMALS.items():
        rows=[r for r in m["records"] if r["animal"] in animals]
        keys[split]=sorted(r["key"] for r in rows)
        stats[split]=dict(decisions=len(rows),eligible_bscans=sum(r["eligible"] for r in rows),
            surface_columns=np.sum([r["eligible_columns_by_surface"] for r in rows],axis=0).tolist(),
            eligible_qc=dict(Counter(r["qc_group"] for r in rows if r["eligible"])))
        if not all(stats[split]["surface_columns"]):
            raise ValueError(f"No evidence for one surface in {split}")
    p=dict(dataset_id=m["dataset_id"],manifest=fingerprint(out/"manifest.json"),
        animals=ANIMALS,keys=keys,coverage=stats,
        rationale="Coverage-only choice, before predictions. Train retains the only WT animal and the largest corrected animal (TS267). Validation has independent high-QC negative tissue (TS169) and low/medium-QC remote tissue (TS325). Test includes broad high/medium/low-QC evidence from TS247 and independent medium-QC TS283. Rejected-only TS336 is validation and TS328 is test. All eight boundaries have evidence in all three partitions.",
        repeatability_policy="Any future repeat maps to the original source animal and inherits its partition; no pair data read. Do not infer animal from blind aliases. No repeatability target enters this dataset version.",
        limitations="Five training animals, two validation animals with corrected evidence, two test animals with corrected evidence. One WT animal (TS165), training only: no independent WT generalization estimate. TS247/TS267 dominate raw counts; training samples animals uniformly and reporting includes animal-macro results.",
        final_test_locked=True)
    validate_partition(m,p)
    p["partition_id"]=digest(p)
    write_json(path,p)
    print(json.dumps(stats,indent=2))


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--data",type=Path,default=DEFAULT)
    freeze(p.parse_args().data)
