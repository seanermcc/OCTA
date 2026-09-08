"""Frozen dataset loading; cached targets and images, no live human-label reads."""
import json
from pathlib import Path
import numpy as np
import torch
from .common import verify,digest,fingerprint
from .partitions import validate_partition
from .geometry import PREPROCESS
from .eligibility import region_targets


class Dataset:
    def __init__(self,path,split="train",eligible_only=True):
        self.path=Path(path)
        self.manifest=json.loads((self.path/"manifest.json").read_text())
        self.partitions=json.loads((self.path/"partitions.json").read_text())
        self.cache=json.loads((self.path/"cache_manifest.json").read_text())
        validate_partition(self.manifest,self.partitions)
        verify(self.partitions["manifest"])
        if self.cache["dataset_id"]!=self.manifest["dataset_id"] or self.cache["preprocessing"]!=PREPROCESS:
            raise ValueError("Cache/dataset preprocessing identity mismatch")
        self.records=[r for r in self.manifest["records"] if r["key"] in self.partitions["keys"][split] and (r["eligible"] or not eligible_only)]
        if not self.records:
            raise ValueError("Empty partition")
        missing=[r["key"] for r in self.records if r["key"] not in self.cache["entries"]]
        if missing:
            raise FileNotFoundError(f"Missing caches: {missing}")
        for r in self.records:
            verify(self.cache["entries"][r["key"]]["file"])
            verify(r["targets_fingerprint"])
        self.identity=dict(dataset_id=self.manifest["dataset_id"],partition_id=self.partitions["partition_id"],
            preprocessing=PREPROCESS,cache_manifest=fingerprint(self.path/"cache_manifest.json"))
        self.animals=sorted({r["animal"] for r in self.records})

    def __len__(self):
        return len(self.records)

    def sample(self,index,device="cpu",flip=False):
        r=self.records[index]
        entry=self.cache["entries"][r["key"]]
        with np.load(entry["file"]["path"],allow_pickle=False) as d:
            if str(d["cache_key"])!=entry["cache_key"]:
                raise ValueError("Tensor cache key mismatch")
            x,rows,valid=d["x"],d["rows"],d["valid"]
        if flip:
            x,rows,valid=x[...,::-1].copy(),rows[...,::-1].copy(),valid[...,::-1].copy()
        region=region_targets(rows,valid,x.shape[1])
        return tuple(torch.from_numpy(a.copy()).unsqueeze(0).to(device) for a in (x,rows,valid,region))
