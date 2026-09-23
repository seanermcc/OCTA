"""Export every saved predicted B-scan into the existing labeling-pack format."""
import argparse
import gc
import json
from pathlib import Path

import numpy as np
from octa.volio import ProcessedVolume
from eight_surface.segment import detect_orientation, prepare_bscan
from eight_surface.review import write_review_pack
from stage_a.common import fingerprint, verify, write_json
from stage_a.geometry import label_offset


def run(args):
    root = args.run.resolve()
    queue = root / "review_queue"
    out = root / "full_volume_review"
    out.mkdir(exist_ok=True)
    manifest = json.loads((root / "data/manifest.json").read_text())
    summaries = json.loads((queue / "queue_summary.json").read_text())["volumes"]
    completed = []
    for summary in summaries:
        sid = summary["scan_id"]
        path = out / "packs" / f"{sid}_pack.npz"
        marker = out / f"{sid}.json"
        if marker.exists():
            saved = json.loads(marker.read_text())
            verify(saved["pack"])
            completed.append(saved)
            continue
        if path.exists():
            raise FileExistsError(f"Unverified pack already exists: {path}")
        src = manifest["sources"][sid]
        verify(src["source"])
        job = json.loads((queue / sid / "job.json").read_text())
        with ProcessedVolume(src["source"]["path"]) as volume:
            full = volume.read_volume(channel="struct")
        vhi = bool(detect_orientation(full.mean(axis=(0, 1))))
        offset = label_offset(src["label_band"], full.shape[2], vhi)
        if vhi != summary["orientation_detected"] or offset != summary["label_offset"]:
            raise ValueError("Fresh orientation disagrees with the completed inference")
        lo, hi = src["label_band"]
        images = np.stack([prepare_bscan(b[:, lo:hi], vhi) for b in full])
        del full
        predictions = []
        for b in range(summary["n_bscans"]):
            with np.load(queue / sid / "predictions" / f"b{b:04d}.npz", allow_pickle=False) as data:
                if str(data["job_id"]) != job["job_id"]:
                    raise ValueError("Prediction belongs to another inference job")
                predictions.append(data["candidate_rows"].astype(np.float32) - offset)
        candidates = np.stack(predictions)
        with np.load(queue / sid / "experimental_measurements.npz", allow_pickle=False) as data:
            shadow = data["shadow"].copy()
            retained = data["retained"].copy()
            entropy = data["entropy"].copy()
            np.testing.assert_allclose(candidates[:, :4] + offset, data["canonical_rows"], atol=1e-4, rtol=0)
        picked = np.arange(len(images))
        write_review_pack(path, sid, images, candidates, np.full_like(candidates, np.nan),
            shadow, picked, np.array([], int), np.zeros(len(images)), extra=dict(
                selection_role=np.full(len(images), "Full-volume browsing; automatic proposal"),
                inner_retained=retained, inner_entropy=entropy,
                prediction_checkpoint=np.array(job["job"]["checkpoint"]["path"]),
                source=np.array(src["source"]["path"]), label_offset=np.array(offset),
                full_volume=np.array(True)))
        # Check alignment against the already delivered, verified nine-image pack.
        with np.load(summary["pack"]["path"], allow_pickle=False) as small:
            indices = small["bscan_index"]
            np.testing.assert_array_equal(images[indices], small["images"])
            np.testing.assert_array_equal(candidates[indices], small["surfaces"])
        result = dict(scan_id=sid, n_bscans=len(images), first_bscan=0, last_bscan=len(images)-1,
            pack=fingerprint(path), source=src["source"], inference_job_id=job["job_id"],
            orientation_freshly_verified=True, sampled_pack_pixels_and_surfaces_identical=True,
            no_training_or_inference_repeated=True, no_manual_labels_written=True)
        write_json(marker, result)
        completed.append(result)
        del images, candidates, predictions, retained, entropy, shadow
        gc.collect()
        print(f"Full-volume pack ready: {sid}, {result['n_bscans']} B-scans", flush=True)
    write_json(out / "export_summary.json", dict(volumes=completed, total_bscans=sum(v["n_bscans"] for v in completed)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    run(parser.parse_args())
