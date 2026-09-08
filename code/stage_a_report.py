"""Summarize Stage A frozen preparation without touching repeatability data."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
from stage_a.common import DEFAULT,OUT,verify,write_json,write_csv,fingerprint
from eight_surface.config import SURFACE_NAMES

root=DEFAULT
m=json.loads((root/"manifest.json").read_text())
cache=json.loads((root/"cache_manifest.json").read_text())
part=json.loads((root/"partitions.json").read_text())
before=json.loads((OUT/"stage_a/20260908_v1/environment_before.json").read_text())
after=json.loads((root/"environment_after.json").read_text())
changes={k:[before["packages"].get(k),v] for k,v in after["packages"].items() if before["packages"].get(k)!=v}
for name in ("numpy","scipy","h5py","matplotlib","pandas","skimage"):
    assert before[name]==after[name],name
for fp in m["inputs"].values():
    verify(fp)
for r in m["records"]:
    verify(r["label"])
    verify(r["targets_fingerprint"])
    verify(cache["entries"][r["key"]]["file"])
for src in m["sources"].values():
    for key in ("source","segmentation","pack","scope_hash","footprint"):
        if src[key]: verify(src[key])
    assert Path(src["qc"]["source"]).resolve()==Path(src["source"]["path"]).resolve()
reasons=Counter()
for r in m["records"]: reasons.update(r["reason_counts"])
summary=dict(dataset_id=m["dataset_id"],partition_id=part["partition_id"],
    first_round_labels_unchanged=len(m["records"]),packs_unchanged=len(m["sources"]),
    footprints_unchanged=sum(s["footprint"] is not None for s in m["sources"].values()),
    source_qc_join_verified=True,cache_count=len(cache["entries"]),
    cache_missing=cache["missing"],pack_source_pixels_exact=all(e["pack_pixels_exact"] for e in cache["entries"].values()),
    targets_contained=all(e["eligible_targets_contained"] for e in cache["entries"].values()),
    footprint_status=dict(Counter("missing" if not s["footprint"] else "positive" if s["footprint_positive"] else "empty" for s in m["sources"].values())),
    missing_footprints=[sid for sid,s in m["sources"].items() if not s["footprint"]],
    reason_counts=dict(reasons),environment_changes=changes,
    scientific_versions_unchanged=True,repeatability_data_read=False,
    eligible_bscan_count=sum(r["eligible"] for r in m["records"]),
    eligible_volume_count=len({r["scan_id"] for r in m["records"] if r["eligible"]}),
    total_eligible_boundary_columns=sum(sum(r["eligible_columns_by_surface"]) for r in m["records"]))
write_json(root/"integrity_and_environment.json",summary)
counts=[]
for animal in sorted({r["animal"] for r in m["records"]}):
    rr=[r for r in m["records"] if r["animal"]==animal]
    split=next(s for s,aa in part["animals"].items() if animal in aa)
    counts.append(dict(animal=animal,split=split,decisions=len(rr),
        corrected=sum(r["verdict"]=="corrected" for r in rr),eligible_bscans=sum(r["eligible"] for r in rr),
        **{name:sum(r["eligible_columns_by_surface"][k] for r in rr) for k,name in enumerate(SURFACE_NAMES)}))
write_csv(root/"animal_coverage.csv",counts)
print(json.dumps(summary,indent=2))
