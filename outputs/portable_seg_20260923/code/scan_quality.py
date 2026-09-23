#!/usr/bin/env python3
"""Independent acquisition-quality measurements for every processed OCT scan.

These measurements deliberately do not use automatic retinal surfaces:

1. signal/contrast -- retinal-band intensity above the vitreous noise floor;
2. continuity -- adjacent-B-scan agreement and slow-axis stripe energy;
3. repeat agreement -- registered structural similarity to other acquisitions
   of the same animal, eye, and session.

The output keeps the component measurements separate.  It does not manufacture
an unvalidated composite "quality score" or a good/bad threshold.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_segment import load_candidates, resolve_volumes_path, scan_id_for  # noqa: E402
from octa.volio import ProcessedVolume, VolumeReadError  # noqa: E402


EPS = 1e-6
FINGERPRINT_SIZE = 128


def _mad(x: np.ndarray, axis=None) -> np.ndarray:
    med = np.nanmedian(x, axis=axis, keepdims=True)
    return 1.4826 * np.nanmedian(np.abs(x - med), axis=axis)


def _block_mean(a: np.ndarray, size: int = FINGERPRINT_SIZE) -> np.ndarray:
    """Area-average a 2-D image to at most size x size."""
    sy = max(1, a.shape[0] // size)
    sx = max(1, a.shape[1] // size)
    ny, nx = a.shape[0] // sy, a.shape[1] // sx
    a = a[:ny * sy, :nx * sx]
    return a.reshape(ny, sy, nx, sx).mean(axis=(1, 3)).astype(np.float32)


def _standardize_rows(img: np.ndarray) -> np.ndarray:
    med = np.median(img, axis=1, keepdims=True)
    scale = _mad(img, axis=1)[:, None]
    return np.clip((img - med) / np.maximum(scale, EPS), -6, 6)


def _adjacent_correlations(img: np.ndarray) -> np.ndarray:
    a, b = img[:-1], img[1:]
    a = a - a.mean(axis=1, keepdims=True)
    b = b - b.mean(axis=1, keepdims=True)
    den = np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
    return np.divide((a * b).sum(axis=1), den,
                     out=np.zeros_like(den), where=den > EPS)


def _stripe_fraction(img: np.ndarray) -> float:
    """Fraction of slow-axis projection power above 1/16 cycles/B-scan."""
    row_signal = np.median(img, axis=1) if img.ndim == 2 else np.asarray(img)
    # Remove broad anatomy without importing segmentation or scipy.
    residual = _slow_axis_residual(row_signal)
    power = np.abs(np.fft.rfft(residual - residual.mean())) ** 2
    freq = np.fft.rfftfreq(residual.size)
    useful = freq > 0
    high = freq >= (1.0 / 16.0)
    return float(power[high].sum() / max(power[useful].sum(), EPS))


def _slow_axis_residual(signal: np.ndarray, width: int = 17) -> np.ndarray:
    signal = np.asarray(signal, dtype=np.float64)
    smooth = np.convolve(np.pad(signal, width // 2, mode="edge"),
                         np.ones(width) / width, mode="valid")
    return signal - smooth


def _read_noise(v: ProcessedVolume, lo: int, hi: int) -> tuple[np.ndarray, str]:
    """Read a 48-pixel vitreous window, choosing the longer outside-tissue side."""
    nd = v.shape[2]
    left, right = lo, nd - hi
    if right >= left and right >= 24:
        stop = nd - 4
        start = max(hi + 4, stop - 48)
        return v.read_volume(depth_slice=slice(start, stop)), "high_depth"
    stop = max(4, lo - 4)
    start = max(0, stop - 48)
    return v.read_volume(depth_slice=slice(start, stop)), "low_depth"


def measure_one(row: dict, bands: dict[str, tuple[int, int]]) -> tuple[dict, np.ndarray | None]:
    sid = scan_id_for(row)
    out = {
        "scan_id": sid, "animal": row.get("animal", ""),
        "eye": row.get("eye", ""), "day_label": row.get("day_label", ""),
        "days_post_laser": row.get("days_post_laser", ""),
        "session_date": row.get("session_date", ""),
        "scan_no": row.get("scan_no", ""), "acq_time": row.get("acq_time", ""),
        "status": "failed", "error": "", "elapsed_s": "",
    }
    path = resolve_volumes_path(row)
    if path is None:
        out["error"] = "could not resolve processedVolumes.mat"
        return out, None
    if sid not in bands:
        out["error"] = "retina band unavailable; rerun with a compatible band CSV"
        return out, None

    lo, hi = bands[sid]
    t0 = time.time()
    try:
        with ProcessedVolume(path) as v:
            tissue = v.read_volume(depth_slice=slice(lo, hi))
            noise, noise_side = _read_noise(v, lo, hi)

        # Signal/contrast: robust scan value plus spatial coverage.  The
        # per-position contrast uses the upper tissue quartile so dark ONL and
        # lesions do not masquerade as global acquisition failure.
        noise_floor = float(np.median(noise))
        noise_sigma = float(_mad(noise.ravel()))
        tissue_p75 = np.percentile(tissue, 75, axis=2)
        local_contrast = tissue_p75 - np.median(noise, axis=2)
        contrast = float(np.median(local_contrast))
        cnr = contrast / max(noise_sigma, EPS)
        low_signal_frac = float(np.mean(local_contrast < 3.0 * max(noise_sigma, EPS)))

        # Structural en-face projection for motion and repeat agreement.
        enface = np.percentile(tissue, 75, axis=2).astype(np.float32)
        norm = _standardize_rows(enface)
        adj = _adjacent_correlations(norm)
        discontinuity = 1.0 - adj
        # Axial motion is invisible after depth projection.  Track the robust
        # tissue centroid for every B-scan before collapsing depth, then score
        # abrupt jumps and stripe-like high-frequency variation along the slow
        # axis.  This is the raw-data counterpart of surface roughness.
        depth_profiles = np.median(tissue, axis=1)
        base = np.percentile(depth_profiles, 10, axis=1, keepdims=True)
        weights = np.maximum(depth_profiles - base, 0.0)
        depth_index = np.arange(tissue.shape[2], dtype=np.float32)[None, :]
        centroids = (weights * depth_index).sum(axis=1) / np.maximum(weights.sum(axis=1), EPS)
        centroid_jumps = np.abs(np.diff(centroids))
        centroid_residual = _slow_axis_residual(centroids)
        brightness_rows = np.median(enface, axis=1)
        brightness_residual = _slow_axis_residual(brightness_rows)
        # Preserve broad anatomy for between-acquisition matching.  Row-wise
        # standardisation is useful for detecting striping but removes exactly
        # the slow-axis structure needed to decide whether two repeats overlap.
        fp_scale = float(_mad(enface.ravel()))
        fingerprint = _block_mean(np.clip(
            (enface - np.median(enface)) / max(fp_scale, EPS), -6, 6))

        out.update({
            "status": "ok", "source": str(path), "retina_lo": lo,
            "retina_hi": hi, "noise_window_side": noise_side,
            "noise_floor": round(noise_floor, 6),
            "noise_sigma_mad": round(noise_sigma, 6),
            "retina_vitreous_contrast": round(contrast, 6),
            "retina_cnr": round(cnr, 6),
            "low_signal_frac": round(low_signal_frac, 6),
            "adjacent_bscan_corr_median": round(float(np.median(adj)), 6),
            "bscan_discontinuity_p95": round(float(np.percentile(discontinuity, 95)), 6),
            "brightness_stripe_power_frac": round(_stripe_fraction(enface), 6),
            "brightness_stripe_mad": round(float(_mad(brightness_residual)), 6),
            "axial_centroid_jump_median_px": round(float(np.median(centroid_jumps)), 6),
            "axial_centroid_jump_p95_px": round(float(np.percentile(centroid_jumps, 95)), 6),
            "axial_centroid_residual_p95_px": round(float(np.percentile(np.abs(centroid_residual), 95)), 6),
            "axial_centroid_stripe_power_frac": round(_stripe_fraction(centroids), 6),
            "elapsed_s": round(time.time() - t0, 2),
        })
        return out, fingerprint
    except (VolumeReadError, Exception):
        out["error"] = traceback.format_exc(limit=5)
        out["elapsed_s"] = round(time.time() - t0, 2)
        return out, None


def _registered_corr(a: np.ndarray, b: np.ndarray, max_shift: int = 24) -> tuple[float, int, int]:
    """Translation-register two fingerprints and return overlap correlation."""
    h = min(a.shape[0], b.shape[0]); w = min(a.shape[1], b.shape[1])
    a, b = a[:h, :w], b[:h, :w]
    aa = a - a.mean(); bb = b - b.mean()
    cross = np.fft.ifft2(np.fft.fft2(aa) * np.conj(np.fft.fft2(bb))).real
    yy, xx = np.unravel_index(np.argmax(cross), cross.shape)
    dy = int(yy if yy <= h // 2 else yy - h)
    dx = int(xx if xx <= w // 2 else xx - w)
    dy = int(np.clip(dy, -max_shift, max_shift)); dx = int(np.clip(dx, -max_shift, max_shift))
    ay0, ay1 = max(0, dy), min(h, h + dy)
    by0, by1 = max(0, -dy), min(h, h - dy)
    ax0, ax1 = max(0, dx), min(w, w + dx)
    bx0, bx1 = max(0, -dx), min(w, w - dx)
    av = a[ay0:ay1, ax0:ax1].ravel(); bv = b[by0:by1, bx0:bx1].ravel()
    if av.size < 256 or np.std(av) < EPS or np.std(bv) < EPS:
        return math.nan, dy, dx
    return float(np.corrcoef(av, bv)[0, 1]), dy, dx


def add_repeat_agreement(rows: list[dict], fingerprints: dict[str, np.ndarray]) -> None:
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["animal"], r["eye"], r["session_date"]), []).append(r)
    for members in groups.values():
        valid = [r for r in members if r["scan_id"] in fingerprints]
        for r in members:
            peers = [p for p in valid if p["scan_id"] != r["scan_id"]]
            r["repeat_group_n"] = len(valid)
            r["repeat_peer_n"] = len(peers)
            r["repeat_corr_median"] = ""
            r["repeat_corr_best"] = ""
            r["repeat_disagreement"] = ""
            r["repeat_comparable"] = ""
            r["repeat_best_peer"] = ""
            r["repeat_registration_shift_px"] = ""
            if r["scan_id"] not in fingerprints or not peers:
                continue
            scored = []
            for p in peers:
                corr, dy, dx = _registered_corr(fingerprints[r["scan_id"]], fingerprints[p["scan_id"]])
                if np.isfinite(corr):
                    scored.append((corr, p["scan_id"], dy, dx))
            if not scored:
                continue
            scored.sort(reverse=True)
            vals = np.array([x[0] for x in scored])
            best = scored[0]
            r["repeat_corr_median"] = round(float(np.median(vals)), 6)
            r["repeat_corr_best"] = round(float(best[0]), 6)
            # A low best correlation usually means the acquisitions sampled
            # different retinal locations, not that either scan is poor.  Keep
            # the observed correlations but expose whether disagreement is a
            # valid QC measurement; do not turn non-overlap into a failure.
            comparable = bool(best[0] >= 0.30)
            r["repeat_comparable"] = comparable
            if comparable:
                r["repeat_disagreement"] = round(float(1.0 - np.median(vals)), 6)
            r["repeat_best_peer"] = best[1]
            r["repeat_registration_shift_px"] = round(float(math.hypot(best[2], best[3])), 3)


def add_human_review(rows: list[dict], label_dir: Path) -> None:
    """Attach existing GUI scan-level verdict counts as validation, not inputs."""
    counts: dict[str, dict[str, int]] = {}
    if label_dir.is_dir():
        for path in label_dir.glob("*.npz"):
            try:
                d = np.load(path, allow_pickle=False)
                sid = str(d["scan_id"][0])
                verdict = str(d["verdict"][0]).lower()
                if sid.startswith("slab_") or verdict not in {"accepted", "corrected", "rejected"}:
                    continue
                c = counts.setdefault(sid, {"accepted": 0, "corrected": 0, "rejected": 0})
                c[verdict] += 1
            except Exception:
                continue
    for r in rows:
        c = counts.get(r["scan_id"], {"accepted": 0, "corrected": 0, "rejected": 0})
        total = sum(c.values())
        r["human_review_n"] = total
        r["human_accepted_n"] = c["accepted"]
        r["human_corrected_n"] = c["corrected"]
        r["human_rejected_n"] = c["rejected"]
        r["human_reject_frac"] = round(c["rejected"] / total, 6) if total else ""


def add_legacy_context(rows: list[dict], v1_path: Path, v2_path: Path) -> None:
    """Attach retired confidence proxies for comparison, never as QC inputs."""
    def read(path: Path) -> dict[str, dict]:
        if not path.exists(): return {}
        with path.open(newline="", encoding="utf-8-sig") as f:
            return {r["scan_id"]: r for r in csv.DictReader(f)}
    v1, v2 = read(v1_path), read(v2_path)
    for r in rows:
        sid = r["scan_id"]
        r["legacy_quality_confidence_v1"] = v1.get(sid, {}).get("quality_confidence", "")
        r["segmentation_support_proxy_v2"] = v2.get(sid, {}).get("quality_confidence", "")
        r["legacy_shadow_frac"] = v2.get(sid, {}).get("shadow_frac", "")


def load_bands(path: Path) -> dict[str, tuple[int, int]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {r["scan_id"]: (int(r["retina_lo"]), int(r["retina_hi"]))
                for r in csv.DictReader(f) if r.get("retina_lo") and r.get("retina_hi")}


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", default="../outputs/scan_index.csv")
    ap.add_argument("--bands", default="../outputs/quality_scores_v2.csv")
    ap.add_argument("--legacy-v1", default="../outputs/quality_scores.csv")
    ap.add_argument("--out", default="../outputs/scan_quality_metrics.csv")
    ap.add_argument("--cache", default="../outputs/scan_quality_fingerprints.npz")
    ap.add_argument("--labels", default="../outputs/labels")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--scan-id", action="append", default=[])
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    out_path, cache_path = Path(args.out), Path(args.cache)
    candidates = load_candidates(Path(args.index), None)
    if args.scan_id:
        wanted = set(args.scan_id)
        candidates = [r for r in candidates if scan_id_for(r) in wanted]
    if args.limit: candidates = candidates[:args.limit]
    bands = load_bands(Path(args.bands))

    old_rows: dict[str, dict] = {}
    fingerprints: dict[str, np.ndarray] = {}
    if args.resume and out_path.exists():
        with out_path.open(newline="", encoding="utf-8-sig") as f:
            old_rows = {r["scan_id"]: r for r in csv.DictReader(f) if r.get("status") == "ok"}
    if args.resume and cache_path.exists():
        d = np.load(cache_path, allow_pickle=False)
        fingerprints = {k: d[k] for k in d.files}

    rows = []
    for i, row in enumerate(candidates, 1):
        sid = scan_id_for(row)
        if sid in old_rows and sid in fingerprints:
            result = old_rows[sid]
            print(f"[{i}/{len(candidates)}] {sid}: cached", flush=True)
        else:
            print(f"[{i}/{len(candidates)}] {sid}", flush=True)
            result, fp = measure_one(row, bands)
            if fp is not None: fingerprints[sid] = fp
            print(f"  {result['status']} ({result.get('elapsed_s', '')} s)", flush=True)
        rows.append(result)
        add_repeat_agreement(rows, fingerprints)
        write_csv(out_path, rows)
        np.savez_compressed(cache_path, **fingerprints)

    add_repeat_agreement(rows, fingerprints)
    add_human_review(rows, Path(args.labels))
    add_legacy_context(rows, Path(args.legacy_v1), Path(args.bands))
    write_csv(out_path, rows)
    meta = {"metric_version": "1-independent-acquisition-qc", "rows": len(rows),
            "definitions": {
                "signal": "retinal P75 intensity minus vitreous median; CNR divides by vitreous MAD",
                "continuity": "adjacent structural-enface row correlation, discontinuity P95, and high-frequency stripe power",
                "repeat": "translation-registered structural-enface correlation to same animal/eye/session peers",
            }}
    out_path.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {out_path} ({len(rows)} rows)")
    return 0 if all(r["status"] == "ok" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
