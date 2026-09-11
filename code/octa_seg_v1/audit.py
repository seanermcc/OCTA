"""Read-only audit; freeze derived training arrays, never human label files."""
from collections import Counter
from types import SimpleNamespace
import json
import subprocess
import time
import numpy as np
from eight_surface import provenance as P
from eight_surface.labels import load_label
from eight_surface.config import SURFACE_NAMES
from cnv_review_v1.data import load_enface
from .common import *

def targets(label, shadow, height, offset):
    vis, rel = P.record_visibility(label), P.record_reliability(label)
    # Legacy true booleans are defaults, not positive judgements. Explicit
    # negative global flags remain useful even for rejected/no-position records.
    trace = np.full(vis.shape, -1, np.int8)
    reliability = np.full(vis.shape, -1, np.int8)
    trace[vis == P.MARK_YES] = 1; trace[vis == P.MARK_NO] = 0
    reliability[rel == P.MARK_YES] = 1; reliability[rel == P.MARK_NO] = 0
    valid = P.local_position_valid(label, "strict") & np.isfinite(label["surfaces"])
    valid &= (label["surfaces"] >= 0) & (label["surfaces"] <= height - 1)
    valid &= ~shadow[None]
    if label["verdict"] != "corrected":
        valid[:] = False
    # Position evidence and state judgments are separate. A stroke normally
    # writes an affirmative local_visibility mark in the GUI, but does NOT
    # manufacture reliability where that tri-state mark remains unknown.
    excluded = np.broadcast_to(label["region_excluded"], vis.shape).copy()
    # Preserve explicit negatives in excluded images, but never infer positives.
    trace[excluded & (trace == 1)] = -1
    reliability[excluded & (reliability == 1)] = -1
    return dict(rows=(label["surfaces"] + offset).astype(np.float32), valid=valid,
                trace_target=trace, reliability_target=reliability, excluded=excluded,
                visibility=vis, reliability=rel, displaced=label["local_displaced"],
                drawn=label["local_drawn"], taper=label["local_taper"])

def run():
    start = time.monotonic()
    if (OUT / "data/manifest.json").exists():
        progress("audit already frozen"); return
    m = json.loads((PREVIOUS / "data/manifest.json").read_text())
    cache = json.loads((PREVIOUS / "data/cache_manifest.json").read_text())
    chosen = {r["key"]: Path(r["label"]["path"]) for r in m["records"]}
    extras = []
    # Latest isolated GUI saves supersede by identity, with every source retained
    # in the census. Do not recursively treat history copies as new decisions.
    for folder in (ROOT / "outputs/eight_surface/labels", ROOT / "outputs/stage_a/20260909_full_labeled_cohort/manual_review_36/labels", ROOT / "outputs/cnv_review_v1/surface_labels"):
        for path in folder.glob("*.npz"):
            lab = load_label(path); key = f"{lab['scan_id']}_b{lab['bscan']:04d}"
            if key not in chosen:
                extras.append(dict(path=str(path), key=key, reason="no previously verified image cache; quarantined pending geometry import"))
            else:
                chosen[key] = path
    # The two latest linked-GUI records have source/crop provenance rather than
    # an older pack-cache entry. Validate that geometry and read their native
    # source once; they must not disappear just because the old importer had
    # never encountered their B-scan numbers.
    extra_data = {}
    from octa.volio import ProcessedVolume
    from eight_surface.segment import detect_orientation
    from stage_a.geometry import preprocess, label_offset
    for sid in sorted({x["key"].rsplit("_b",1)[0] for x in extras}):
        src=m["sources"][sid]
        with ProcessedVolume(src["source"]["path"]) as volume: full=volume.read_volume()
        vhi=bool(detect_orientation(full.mean(axis=(0,1))))
        offset=label_offset(src["label_band"],full.shape[2],vhi)
        with np.load(src["segmentation"]["path"] if "segmentation" in src else ROOT/"outputs/eight_surface/segmented"/f"{sid}.npz",allow_pickle=False) as seg:
            shadow=seg["shadow"]
        for item in [e for e in extras if e["key"].rsplit("_b",1)[0]==sid]:
            path=Path(item["path"]);lab=load_label(path);b=lab["bscan"]
            ctx_path=ROOT/"outputs/cnv_review_v1/surface_context"/f"{item['key']}.json"
            ctx=json.loads(ctx_path.read_text())
            if Path(ctx["source_volume"]).resolve()!=Path(src["source"]["path"]).resolve() or ctx["retina_band"]!=src["label_band"] or not ctx["canonical_vitreous_at_depth_zero"]:
                raise ValueError("New linked label geometry mismatch")
            x,_,_=preprocess(full[b],vhi)
            extra_data[item["key"]]=dict(x=x,label_offset=np.array(offset),vitreous_high=np.array(vhi),shadow=shadow[b],scope=np.ones(full.shape[1],bool))
            m["records"].append(dict(key=item["key"],scan_id=sid,bscan=b,animal=src["metadata"]["animal"]))
            chosen[item["key"]]=path
            item["reason"]="imported after fresh native orientation and GUI source/crop validation"
        del full
    records, audit, source_masks = [], [], {}
    for sid, src in m["sources"].items():
        scan = SimpleNamespace(scan_id=sid, native_shape=tuple(src["native_shape"][:2]),
            source_volume=Path(src["source"]["path"]), retina_band=tuple(src["label_band"]))
        cnv, vessel, onh, edge, prov, label_path = load_enface(scan, ROOT / "outputs/cnv_labels", ROOT / "outputs/eight_surface/vasculature_proposals")
        dest = OUT / "data/footprints" / f"{sid}.npz"
        save_npz(dest, vessel=vessel, cnv=cnv, onh=onh, onh_edge=edge)
        source_masks[sid] = dict(path=str(dest), fingerprint=fingerprint(dest), vessel=prov,
            enface_label=fingerprint(label_path) if label_path else None,
            vessel_columns=int(vessel.sum()), cnv_columns=int(cnv.sum()), axis_order="B-scan,A-line; native; no depth")
    for r in m["records"]:
        key = r["key"]; path = chosen[key]; label = load_label(path)
        if key in extra_data:
            d=extra_data[key];old=d
            entry=dict(source=m["sources"][r["scan_id"]]["source"],geometry="fresh source orientation plus linked-GUI source/crop provenance")
        else:
            entry = cache["entries"][key]; verify(entry["file"])
            d = load_npz(entry["file"]["path"])
            old = load_npz(r["targets"])
        src = m["sources"][r["scan_id"]]
        t = targets(label, old["shadow"], src["label_band"][1]-src["label_band"][0], int(d["label_offset"]))
        footprints = load_npz(source_masks[r["scan_id"]]["path"])
        dest = OUT / "data/cache" / f"{key}.npz"
        save_npz(dest, x=d["x"], **t, shadow=old["shadow"], vessel=footprints["vessel"][r["bscan"]],
            cnv=footprints["cnv"][r["bscan"]], original_scope=old.get("original_stage_a_scope",old["scope"]),
            label_offset=d["label_offset"], vitreous_high=d["vitreous_high"])
        rec = dict(key=key, scan_id=r["scan_id"], bscan=r["bscan"], animal=r["animal"],
            verdict=label["verdict"], label=fingerprint(path), cache=fingerprint(dest),
            image_provenance=entry, local_provenance_available=label["local_provenance_available"],
            format=label["label_format_version"], positions=t["valid"].sum(1).tolist())
        records.append(rec)
        for k,name in enumerate(SURFACE_NAMES):
            audit.append(dict(key=key, animal=r["animal"], boundary=name, verdict=label["verdict"],
                format=label["label_format_version"], path=str(path),
                not_traceable=int((t["trace_target"][k]==0).sum()), traceable=int((t["trace_target"][k]==1).sum()),
                unreliable=int((t["reliability_target"][k]==0).sum()), reliable=int((t["reliability_target"][k]==1).sum()),
                unknown_trace=int((t["trace_target"][k]<0).sum()), unknown_reliability=int((t["reliability_target"][k]<0).sum()),
                positions=int(t["valid"][k].sum()), image_excluded=int(label["region_excluded"].sum()),
                displaced=int(label["local_displaced"][k].sum()), taper=int(label["local_taper"][k].sum()),
                visible_global=bool(label["surface_visible"][k]), reliable_global=bool(label["surface_reliable"][k])))
    history = {}
    for rev in ("8dc00a6", "8e8ceee", "HEAD"):
        p = subprocess.run(["git","show",f"{rev}:code/eight_surface/label_gui.py"], capture_output=True,text=True,encoding="utf-8")
        history[rev] = [line for line in p.stdout.splitlines() if "right-drag" in line or 'return "visible" if ctrl' in line or 'return "reliable" if ctrl' in line]
    census = dict(records=len(records), animals=dict(Counter(r["animal"] for r in records)),
        formats=dict(Counter(r["format"] for r in records)), verdicts=dict(Counter(r["verdict"] for r in records)),
        counts={key:sum(r[key] for r in audit) for key in ("not_traceable","traceable","unreliable","reliable","positions","unknown_trace","unknown_reliability")},
        supplemental_records=extras, runtime_s=time.monotonic()-start)
    write_csv(OUT / "data/label_audit.csv", audit)
    write_json(OUT / "data/gesture_history.json", history)
    write_json(OUT / "data/census.json", census)
    manifest = dict(version="octa-seg_v1", records=records, sources=m["sources"], footprints=source_masks,
        parent=fingerprint(PREVIOUS / "data/manifest.json"), surface_names=SURFACE_NAMES,
        position_policy="strict direct local stroke, corrected, non-displaced, non-excluded, visible/reliable not denied, in-image, not shadowed",
        state_policy="explicit tri-state and negative whole-boundary judgments only; rejected negatives retained; no positives inferred from drawing or missing flags",
        original_labels_immutable=True, future_feedback="reviewer/surface_labels and reviewer/estimate_feedback; v2 only")
    manifest["dataset_id"] = digest(manifest)
    write_json(OUT / "data/manifest.json", manifest)
    progress("audit frozen", **census)

if __name__ == "__main__": run()
