"""Prepare the existing 32-scan en-face queue with the approved shape-gated rule.

Only proposal/cache/report directories are written. Human labels are read-only.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from vasculature_baseline import (ROOT, DEFAULT_OUT as PILOT, file_hash,
                                  load_projection, vessel_evidence, make_mask,
                                  display_image, plt, load_label)
from vasculature_shape_gate import shape_gate, PARAMETERS
from eight_surface.vasculature_proposals import DEFAULT_PROPOSALS, PROPOSAL_VERSION

RUN = ROOT / "outputs/vasculature_baseline/20260909_queue32"
THRESHOLD = .18


def main():
    paths = sorted((ROOT / "outputs/eight_surface/segmented").glob("*.npz"))
    if len(paths) != 32:
        raise RuntimeError(f"Expected the existing 32-scan queue; found {len(paths)}")
    RUN.mkdir(parents=True, exist_ok=True)
    DEFAULT_PROPOSALS.mkdir(parents=True, exist_ok=True)
    (RUN / "previews").mkdir(exist_ok=True)
    labels_before = {str(p): file_hash(p) for p in (ROOT / "outputs/cnv_labels").glob("*_cnv.npz")}
    records, thumbnails = [], []
    code_hashes = {name: file_hash(ROOT / "code" / name) for name in
                   ("vasculature_baseline.py", "vasculature_shape_gate.py", "prepare_vasculature_queue.py")}
    for i, path in enumerate(paths):
        started = time.monotonic()
        scan_id = path.stem
        with np.load(path, allow_pickle=False) as seg:
            source = str(seg["source"][0])
            band = seg["retina_band"].copy()
            native_shape = tuple(seg["surfaces"].shape[::2])
        label_path = ROOT / "outputs/cnv_labels" / f"{scan_id}_cnv.npz"
        label = load_label(label_path) if label_path.exists() else None
        onh = label["onh_mask"] if label is not None else np.zeros(native_shape, bool)
        cache_root = PILOT if (PILOT / "projections" / f"{scan_id}.npz").exists() else RUN
        im = load_projection(scan_id, cache_root)
        evidence, _, _ = vessel_evidence(im)
        before = make_mask(evidence, THRESHOLD, onh)
        mask, _audit = shape_gate(before, **PARAMETERS)
        assert mask.shape == native_shape and not np.any(mask & ~before)
        out = DEFAULT_PROPOSALS / f"{scan_id}_proposal.npz"
        temporary = out.with_suffix(".writing.npz")
        np.savez_compressed(
            temporary, predicted_vasculature_mask=mask, evidence=evidence,
            scan_id=np.array([scan_id]), source_volume=np.array([source]),
            source_segmentation=np.array([str(path.resolve())]),
            retina_band=band, native_shape=np.array(native_shape),
            axis_order=np.array(["B-scan,A-line"]),
            proposal_format_version=np.array([PROPOSAL_VERSION]),
            projection_version=np.array(["1-retina-band-mean-db"]),
            human_onh_exclusion_mask=onh,
            method=np.array(["major-vessel-shape-gate-v2"]),
            threshold=np.array([THRESHOLD]), parameters_json=np.array([json.dumps(PARAMETERS)]),
            code_hashes_json=np.array([json.dumps(code_hashes)]),
            human_reviewed=np.array([False]),
            provenance=np.array(["automatic starting mask for GUI correction; not a human label"]))
        temporary.replace(out)
        previous_pilot = ROOT / "outputs/vasculature_baseline/20260909_major_vessels_shape_gate/proposals" / out.name
        if previous_pilot.exists():
            with np.load(previous_pilot, allow_pickle=False) as old:
                assert np.array_equal(old["predicted_vasculature_mask"], mask), "Pilot result changed"
        row = dict(scan_id=scan_id, vessel_pixels=int(mask.sum()), proposal=str(out),
                   projection=str(cache_root / "projections" / f"{scan_id}.npz"),
                   proposal_sha256=file_hash(out),
                   existing_vessel_reviewed=bool(label and label["reviewed_targets"][1]),
                   existing_vessel_pixels=int(label["vasculature_mask"].sum()) if label else 0,
                   seconds=round(time.monotonic()-started, 2))
        records.append(row)
        thumb = np.repeat(display_image(im)[..., None], 3, axis=2)
        thumb[mask] = thumb[mask]*.4 + np.array([.1, .65, 1.])*.6
        thumb[onh] = thumb[onh]*.4 + np.array([.2, 1., .4])*.6
        thumbnails.append(thumb)
        plt.imsave(RUN / "previews" / f"{scan_id}.png", thumb)
        (RUN / "progress.json").write_text(json.dumps(records, indent=2))
        print(f"{i+1}/32 {scan_id}: {mask.sum():,} proposed pixels", flush=True)
    for path, expected in labels_before.items():
        if file_hash(path) != expected:
            raise RuntimeError(f"Human label changed during run: {path}")
    manifest = dict(status="complete", count=len(records), threshold=THRESHOLD,
                    parameters=PARAMETERS, code_hashes=code_hashes,
                    human_label_hashes=labels_before, human_labels_unchanged=True, scans=records)
    (DEFAULT_PROPOSALS / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (RUN / "manifest.json").write_text(json.dumps(manifest, indent=2))
    for page in range(2):
        fig, axes = plt.subplots(4, 4, figsize=(16, 17))
        for rec, thumb, ax in zip(records[page*16:page*16+16], thumbnails[page*16:page*16+16], axes.flat):
            ax.imshow(thumb); ax.axis("off")
            ax.set_title(rec["scan_id"], fontsize=7)
        fig.suptitle(f"32-scan vessel starting masks: page {page+1}/2 | review required", fontsize=15)
        fig.tight_layout(); fig.savefig(RUN / f"overview_{page+1}.png", dpi=120)
        plt.close(fig)
    print("Complete: 32 automatic proposals; all existing human-label hashes unchanged.", flush=True)


if __name__ == "__main__":
    main()
