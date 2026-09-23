"""Gate the six existing major-vessel proposals by connected-band geometry.

Reads the frozen baseline proposals; never writes human annotations. The gate
only removes pixels. It cannot invent continuity across unsupported gaps.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from skimage import measure, morphology

from vasculature_baseline import (
    DEFAULT_OUT as BASELINE_OUT, ROOT, SCAN_IDS, display_image,
    file_hash, load_label, metrics, plt,
)

DEFAULT_OUT = ROOT / "outputs/vasculature_baseline/20260909_major_vessels_shape_gate"
PARAMETERS = dict(min_area=600, min_length=80., min_width=6.,
                  min_slenderness=5., min_terminal_length=35.)


def skeleton_graph(skeleton):
    """Weighted 8-neighbor graph in a component's small bounding box."""
    coords = np.argwhere(skeleton)
    ids = np.full(skeleton.shape, -1, dtype=int)
    ids[skeleton] = np.arange(len(coords))
    rows, cols, weights = [], [], []
    for dy, dx in ((0, 1), (1, -1), (1, 0), (1, 1)):
        yy, xx = coords[:, 0]+dy, coords[:, 1]+dx
        inside = (yy >= 0) & (xx >= 0) & (yy < ids.shape[0]) & (xx < ids.shape[1])
        source = np.flatnonzero(inside)
        target = ids[yy[inside], xx[inside]]
        good = target >= 0
        a, b = source[good], target[good]
        rows.extend(a); cols.extend(b); weights.extend([np.hypot(dy, dx)]*len(a))
        rows.extend(b); cols.extend(a); weights.extend([np.hypot(dy, dx)]*len(a))
    return coo_matrix((weights, (rows, cols)), shape=(len(coords), len(coords))).tocsr(), coords


def path_span(skeleton):
    """Two-sweep geodesic diameter lower bound; handles bends and trees."""
    graph, coords = skeleton_graph(skeleton)
    if len(coords) < 2:
        return 0.
    distances = dijkstra(graph, indices=0, directed=False)
    farthest = int(np.argmax(np.where(np.isfinite(distances), distances, -1)))
    distances = dijkstra(graph, indices=farthest, directed=False)
    return float(np.max(distances[np.isfinite(distances)]))


def prune_terminal_spurs(component, min_terminal_length=35., min_width=6.):
    """Remove short/narrow terminal side branches by their own geometry.

    Internal paths between junctions remain intact. A nearest-original-centerline
    assignment removes the spur's footprint without dilating a retained vessel.
    One pass avoids repeatedly eroding a real branching tree from its tips.
    """
    skeleton = morphology.skeletonize(component)
    width = 2*ndi.distance_transform_edt(component)
    degree = ndi.convolve(skeleton.astype(np.int16), np.ones((3, 3), np.int16),
                          mode="constant")-skeleton
    junctions = skeleton & (degree >= 3)
    paths, count = ndi.label(skeleton & ~junctions, structure=np.ones((3, 3)))
    remove = np.zeros(component.shape, bool)
    pruned = []
    for i in range(1, count+1):
        path = paths == i
        if not np.any(path & (degree == 1)):
            continue
        if not np.any(ndi.binary_dilation(path) & junctions):
            continue  # whole isolated vessels are judged by the component gate
        length = path_span(path)
        typical_width = float(np.median(width[path]))
        if length < min_terminal_length or typical_width < min_width:
            remove |= path
            pruned.append(dict(length_px=length, median_width_px=typical_width))
    if not remove.any():
        return component.copy(), pruned
    nearest = ndi.distance_transform_edt(~skeleton, return_distances=False,
                                        return_indices=True)
    rejected_footprint = remove[tuple(nearest)]
    return component & ~rejected_footprint, pruned


def shape_gate(mask, *, min_area=600, min_length=80., min_width=6.,
               min_slenderness=5., min_terminal_length=35.):
    mask = np.asarray(mask)
    if mask.ndim != 2 or mask.dtype != bool:
        raise ValueError("Expected a boolean 2D candidate mask")
    result = np.zeros_like(mask)
    audit = []
    original_components = measure.label(mask, connectivity=2)
    for region in measure.regionprops(original_components):
        # Padding makes the distance transform treat all bounding-box boundaries
        # consistently, including a vessel touching the crop's edge.
        component = np.pad(region.image, 1)
        clean, spurs = prune_terminal_spurs(component, min_terminal_length, min_width)
        local_result = np.zeros_like(clean)
        subcomponents = measure.label(clean, connectivity=2)
        children = []
        for child in measure.regionprops(subcomponents):
            child_mask = subcomponents == child.label
            skeleton = morphology.skeletonize(child_mask)
            length = path_span(skeleton)
            widths = 2*ndi.distance_transform_edt(child_mask)[skeleton]
            width = float(np.median(widths)) if len(widths) else 0.
            slenderness = length/max(width, 1.)
            failures = []
            if child.area < min_area:
                failures.append("small area")
            if length < min_length:
                failures.append("short centerline")
            if width < min_width:
                failures.append("thin band")
            if slenderness < min_slenderness:
                failures.append("compact shape")
            keep = not failures
            if keep:
                local_result |= child_mask
            children.append(dict(area_px=int(child.area), length_px=length,
                                 median_width_px=width, length_to_width=slenderness,
                                 kept=keep, rejection_reasons=failures))
        y0, x0, y1, x1 = region.bbox
        result[y0:y1, x0:x1] |= local_result[1:-1, 1:-1]
        audit.append(dict(component_id=int(region.label), bbox=list(region.bbox),
                          input_area_px=int(region.area), pruned_terminal_branches=spurs,
                          components_after_pruning=children))
    return result, audit


def rgba(mask, onh=None):
    overlay = np.zeros((*mask.shape, 4))
    overlay[mask] = [.1, .65, 1., .60]
    if onh is not None:
        overlay[onh] = [.2, 1., .4, .6]
    return overlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE_OUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.out.resolve()
    if out == args.baseline.resolve():
        raise ValueError("Use a separate output folder to preserve baseline comparisons")
    out.mkdir(parents=True, exist_ok=True)
    (out / "proposals").mkdir(exist_ok=True)
    rows, records, component_audit = [], [], {}
    for scan_id in SCAN_IDS:
        source_path = args.baseline / "proposals" / f"{scan_id}_proposal.npz"
        source_hash = file_hash(source_path)
        with np.load(source_path, allow_pickle=False) as data:
            before = data["predicted_vasculature_mask"]
            border = data["unassessed_border_mask"]
            onh = data["human_onh_exclusion_mask"]
            threshold = float(data["threshold"][0])
        with np.load(args.baseline / "projections" / f"{scan_id}.npz", allow_pickle=False) as data:
            im = data["structural_enface"]
        label_path = ROOT / "outputs/cnv_labels" / f"{scan_id}_cnv.npz"
        label_hash = file_hash(label_path) if label_path.exists() else None
        label = load_label(label_path) if label_path.exists() else None
        after, audit = shape_gate(before, **PARAMETERS)
        assert not np.any(after & ~before)
        assert not after[border | onh].any()
        component_audit[scan_id] = audit
        row = dict(scan_id=scan_id, pixels_before=int(before.sum()),
                   pixels_after=int(after.sum()), removed_pixels=int((before & ~after).sum()),
                   components_before=int(measure.label(before, connectivity=2).max()),
                   components_after=int(measure.label(after, connectivity=2).max()),
                   baseline_sha256=source_hash, label_sha256=label_hash,
                   baseline_threshold=threshold,
                   vessel_reviewed=bool(label and label["reviewed_targets"][1]))
        if row["vessel_reviewed"]:
            valid = ~onh
            truth = label["vasculature_mask"]
            row["before"] = metrics(before, truth, valid)
            row["after"] = metrics(after, truth, valid)
            row["removed_unlabeled_pixels"] = int((before & ~after & ~truth & valid).sum())
            row["removed_human_vessel_pixels"] = int((before & ~after & truth & valid).sum())
            row["retained_human_overlap_fraction"] = row["after"]["tp"]/max(row["before"]["tp"], 1)
        rows.append(row)
        records.append(dict(scan_id=scan_id, im=im, before=before, after=after, onh=onh))
        np.savez_compressed(out / "proposals" / f"{scan_id}_proposal.npz",
                            predicted_vasculature_mask=after,
                            rejected_from_baseline_mask=before & ~after,
                            unassessed_border_mask=border,
                            human_onh_exclusion_mask=onh,
                            scan_id=np.array([scan_id]),
                            method=np.array(["major-vessel-shape-gate-v2"]),
                            parameters_json=np.array([json.dumps(PARAMETERS)]),
                            baseline_path=np.array([str(source_path.resolve())]),
                            baseline_sha256=np.array([source_hash]),
                            code_sha256=np.array([file_hash(__file__)]),
                            provenance=np.array(["automatic shape-gated proposal; not a human label"]),
                            axis_order=np.array(["B-scan,A-line"]),
                            human_reviewed=np.array([False]))
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        for ax in axes:
            ax.imshow(display_image(im), cmap="gray", vmin=0, vmax=1)
            ax.axis("off")
        axes[0].set_title("Original")
        axes[1].imshow(rgba(before, onh)); axes[1].set_title("Previous proposal")
        axes[2].imshow(rgba(after, onh)); axes[2].set_title("Continuous-band shape gate")
        fig.suptitle(scan_id + " | green = existing human ONH mask", fontsize=10)
        fig.tight_layout()
        fig.savefig(out / f"{scan_id}.png", dpi=130)
        plt.close(fig)
        if file_hash(source_path) != source_hash or (label_hash and file_hash(label_path) != label_hash):
            raise RuntimeError("An input changed during the comparison; rerun for consistent results")
    (out / "metrics.json").write_text(json.dumps(rows, indent=2))
    (out / "component_audit.json").write_text(json.dumps(component_audit, indent=2))
    (out / "parameters.json").write_text(json.dumps(PARAMETERS, indent=2))
    for mode in ("after", "removed"):
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        for rec, ax in zip(records, axes.flat):
            ax.imshow(display_image(rec["im"]), cmap="gray", vmin=0, vmax=1)
            overlay = rgba(rec["after"], rec["onh"])
            if mode == "removed":
                overlay[rec["before"] & ~rec["after"]] = [1., .4, .05, .75]
            ax.imshow(overlay)
            ax.set_title(rec["scan_id"], fontsize=9)
            ax.axis("off")
        fig.suptitle("Major vessels after the shape gate\nBlue = kept; " +
                     ("orange = removed; " if mode == "removed" else "") +
                     "green = existing human ONH mask", fontsize=13)
        fig.tight_layout()
        fig.savefig(out / ("overview.png" if mode == "after" else "changes.png"), dpi=140)
        plt.close(fig)
    report = [
        "# Major-vessel shape gate — same six scans", "",
        "The new gate removes many small, compact and thin candidate regions while retaining "
        "long vessel bands. The same six saved input masks and the original contrast threshold "
        "(0.18) were used; no contrast parameters were retuned. Original proposals and human "
        "labels remain unchanged. These new files are automatic proposals for review.", "",
        "![Shape-gated proposals](overview.png)", "",
        "[See removed regions in orange](changes.png)", "",
        "## The rule", "",
        "Each surviving connected region must have at least 600 pixels of area, an estimated "
        "centerline span of at least 80 pixels, a median centerline width of at least 6 pixels, "
        "and a centerline-length/width ratio of at least 5. The length follows the band through "
        "curves and branches instead of judging only its bounding-box shape. This keeps a "
        "branching vessel tree from being rejected merely because its overall outline is round. "
        "With the nominal 1460-um field, 6 pixels is about 17 um and 80 pixels about 228 um; "
        "these are pilot cleanup settings, not validated biological cutoffs.", "",
        "A single pass also removes terminal side branches shorter than 35 pixels or narrower "
        "than 6 pixels. Interior paths between junctions are retained, followed by another "
        "connected-component check. A weighted skeleton graph supplies a two-sweep estimate "
        "of centerline span. Pixel ownership is assigned to the nearest original centerline "
        "point when pruning a spur. The gate only removes existing candidate pixels; it does "
        "not fill gaps or invent vessel continuity. Median width is a component criterion, "
        "not a guarantee that every local cross-section is at least six pixels wide.", "",
        "## What changed", "",
        "| Scan | Connected regions before | After | Removed pixels |",
        "|---|---:|---:|---:|",
    ]
    for row in rows:
        report.append(f"| {row['scan_id']} | {row['components_before']} | "
                      f"{row['components_after']} | {row['removed_pixels']:,} |")
    report += ["", f"Across the six scans, connected regions went from "
               f"{sum(r['components_before'] for r in rows)} to "
               f"{sum(r['components_after'] for r in rows)}, and "
               f"{sum(r['removed_pixels'] for r in rows):,} candidate pixels were removed. "
               "Fewer regions is a description of cleanup, not proof that every removed region "
               "was false. In particular, short real vessel fragments at the image edge may "
               "also be removed; the clipped upper-left vessel on TS267 is an example.", "",
               "## Comparison against your two saved vessel masks", "",
               "| Eye | Dice before -> after | Precision before -> after | Recall before -> after | Previously matched vessel pixels retained |",
               "|---|---:|---:|---:|---:|"]
    for row in rows:
        if not row["vessel_reviewed"]:
            continue
        a, b = row["before"], row["after"]
        eye = row["scan_id"].split("_")[1]
        report.append(f"| TS165 {eye} | {a['dice']:.3f} -> {b['dice']:.3f} | "
                      f"{a['precision']:.3f} -> {b['precision']:.3f} | "
                      f"{a['recall']:.3f} -> {b['recall']:.3f} | "
                      f"{100*row['retained_human_overlap_fraction']:.1f}% |")
    report += ["", "Precision improves on both labeled scans; recall drops slightly and mean "
               "Dice is essentially unchanged. Both masks are from TS165 and already informed "
               "baseline development, so this is a development comparison, not independent "
               "validation. Existing human ONH exclusions are reused identically in before/after "
               "measurements and shown in green. The unassessed outer ten pixels still count as "
               "misses where a human painted vessels. The four other scans have no reviewed "
               "vessel mask and therefore no measured accuracy here.", "",
               "## Remaining errors", "",
               "Round/compact islands between vessels are largely removed in these examples. "
               "Long acquisition borders and some elongated lesion artifacts still pass the "
               "band rule. The bottom border in TS305/TS325, the right-side seam in TS165 OS, "
               "and the horizontal lesion/streak regions in TS267 show this limitation. A shape "
               "gate cannot distinguish two structures that both look like long thick bands. "
               "Some real short fragments and smaller branches are removed as well. Existing "
               "gaps and width errors are not repaired by this cleanup.", "",
               "## Verification and files", "",
               "Six behavioral tests check rejection of round/short/thin regions, preservation "
               "of straight and curved bands and branching trees, removal of an isolated round "
               "blob and a short attached spur, and preservation of unsupported gaps. These "
               "synthetic checks verify the intended operation; they do not establish animal "
               "segmentation accuracy. Saved-array checks verify native grids, removal-only "
               "behavior, exclusions, and unchanged human/baseline files.", "",
               "`parameters.json` contains the shared settings. `component_audit.json` records "
               "geometry and rejection reasons for every original candidate region. "
               "`metrics.json` records comparison measurements. `proposals/*_proposal.npz` "
               "stores the new mask, removed mask, exclusions, original-proposal path/hash and "
               "explicit automatic provenance. No human-label or training directory is written.", "",
               "### Individual before/after comparisons", ""]
    for rec in records:
        report.append(f"- [{rec['scan_id']}]({rec['scan_id']}.png)")
    report += ["", "Reproduce after activating `octa`: `python code/vasculature_shape_gate.py`. "
               "Run the geometry checks with `python -m unittest discover -s code -p "
               "test_vasculature_shape_gate.py -v`."]
    (out / "START_HERE.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(rows, indent=2), flush=True)


if __name__ == "__main__":
    main()
