"""Training images: 3-B-scan averages read from the source ``.mat`` volumes.

The review packs store **single, unaveraged** B-scans for GUI display, while
inference runs on ``average_bscans(imgs, bscan_avg=3)``.  Training on the pack
images and running on averaged ones would be exactly the train/inference
mismatch CLAUDE.md warns about, so the training images are rebuilt from each
labelled B-scan's source volume.

One bulk read per volume: HDF5 chunks span the whole B-scan axis, so reading
one B-scan decompresses the same chunks as reading the volume (a per-B-scan
loop measured ~1500x slower).  Every volume actually read is printed and
recorded in the cache manifest, and :func:`assert_not_pack_images` gives the
loud check that no pack image quietly stood in for an average.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

from octa.volio import ProcessedVolume, find_retina_band
from octa.segment import detect_orientation
from eight_surface.segment import prepare_bscan
from eight_surface.volume import average_bscans

BSCAN_AVG = 3
MANIFEST_NAME = "tensor_manifest.csv"


@dataclass(frozen=True)
class TensorMeta:
    scan_id: str
    bscan: int
    height: int
    width: int
    bscan_avg: int
    n_averaged: int
    band_lo: int
    band_hi: int
    vitreous_at_high_index: bool
    source: str


def source_path(seg_dir, scan_id: str) -> Path:
    """The ``.mat`` volume a segmented scan came from."""
    with np.load(Path(seg_dir) / f"{scan_id}.npz", allow_pickle=False) as data:
        return Path(str(data["source"][0]))


def averaged_bscans(source, wanted, bscan_avg: int = BSCAN_AVG):
    """``{bscan: (averaged canonical image, n_averaged)}``, from one bulk read.

    Reproduces the volume pipeline exactly: ``prepare_bscan`` on every B-scan
    in the averaging neighbourhood, then the shipped ``average_bscans`` mean,
    including its edge clipping at the ends of the volume.
    """
    wanted = sorted({int(b) for b in wanted})
    if not wanted:
        return {}, None
    with ProcessedVolume(source) as volume:
        full = volume.read_volume(channel="struct")
        profile = full.mean(axis=(0, 1))
        lo, hi, _stale = find_retina_band(profile)
        vitreous_at_high_index = detect_orientation(profile)
        band = full[:, :, lo:hi]
        n_b = band.shape[0]
        if wanted[0] < 0 or wanted[-1] >= n_b:
            raise AssertionError(
                f"{source}: requested B-scans {wanted[0]}..{wanted[-1]} outside "
                f"a volume of {n_b}")
        back, fwd = (bscan_avg - 1) // 2, bscan_avg // 2
        out = {}
        for b in wanted:
            start, stop = max(0, b - back), min(n_b, b + fwd + 1)
            imgs = np.stack([prepare_bscan(band[i], vitreous_at_high_index)
                             for i in range(start, stop)])
            avg = average_bscans(imgs, bscan_avg)[b - start]
            out[b] = (avg.astype(np.float32), stop - start)
    meta = {"band_lo": int(lo), "band_hi": int(hi),
            "vitreous_at_high_index": bool(vitreous_at_high_index)}
    return out, meta


def cache_path(cache_dir, scan_id: str, bscan: int) -> Path:
    return Path(cache_dir) / f"{scan_id}_b{int(bscan):04d}.npz"


def build_cache(records, seg_dir, cache_dir, bscan_avg: int = BSCAN_AVG,
                overwrite: bool = False, verbose: bool = True):
    """Build (or reuse) one averaged image per labelled B-scan.

    Returns the metadata for every requested record, in label order.  Raises if
    any requested B-scan is missing afterwards -- there is no fallback path.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    wanted: dict[str, list[int]] = {}
    for record in records:
        wanted.setdefault(record["scan_id"], []).append(int(record["bscan"]))

    metas: dict[tuple[str, int], TensorMeta] = {}
    volumes_read: list[str] = []
    for number, scan_id in enumerate(sorted(wanted), 1):
        bscans = sorted(set(wanted[scan_id]))
        todo = [b for b in bscans
                if overwrite or not cache_path(cache_dir, scan_id, b).exists()]
        for b in sorted(set(bscans) - set(todo)):
            metas[(scan_id, b)] = read_meta(cache_path(cache_dir, scan_id, b))
        if not todo:
            if verbose:
                print(f"  [{number}/{len(wanted)}] {scan_id}: "
                      f"{len(bscans)} cached, source volume not read")
            continue
        source = source_path(seg_dir, scan_id)
        if verbose:
            print(f"  [{number}/{len(wanted)}] {scan_id}: reading {source}")
        images, band = averaged_bscans(source, todo, bscan_avg=bscan_avg)
        volumes_read.append(str(source))
        for b in todo:
            image, n_avg = images[b]
            meta = TensorMeta(
                scan_id=scan_id, bscan=int(b), height=int(image.shape[0]),
                width=int(image.shape[1]), bscan_avg=int(bscan_avg),
                n_averaged=int(n_avg), band_lo=band["band_lo"],
                band_hi=band["band_hi"],
                vitreous_at_high_index=band["vitreous_at_high_index"],
                source=str(source))
            np.savez_compressed(
                cache_path(cache_dir, scan_id, b), image=image,
                **{k: np.array([v]) for k, v in asdict(meta).items()})
            metas[(scan_id, b)] = meta
        if verbose:
            print(f"      built {len(todo)} averaged B-scans "
                  f"(bscan_avg={bscan_avg})")

    if verbose:
        print(f"  source volumes read this run: {len(volumes_read)}")
        for path in volumes_read:
            print(f"      {path}")
    missing = [(r["scan_id"], r["bscan"]) for r in records
               if (r["scan_id"], int(r["bscan"])) not in metas]
    if missing:
        raise AssertionError(f"no averaged image was built for {missing}")
    return [metas[(r["scan_id"], int(r["bscan"]))] for r in records]


def load_image(cache_dir, scan_id: str, bscan: int) -> np.ndarray:
    path = cache_path(cache_dir, scan_id, bscan)
    if not path.exists():
        raise AssertionError(
            f"{path} missing: build_cache must run before the dataset is used; "
            "there is deliberately no pack-image fallback")
    with np.load(path, allow_pickle=False) as data:
        return data["image"].astype(np.float32)


def read_meta(path) -> TensorMeta:
    with np.load(Path(path), allow_pickle=False) as data:
        def get(key):
            value = data[key][0]
            return value.item() if hasattr(value, "item") else value
        return TensorMeta(
            scan_id=str(get("scan_id")), bscan=int(get("bscan")),
            height=int(get("height")), width=int(get("width")),
            bscan_avg=int(get("bscan_avg")), n_averaged=int(get("n_averaged")),
            band_lo=int(get("band_lo")), band_hi=int(get("band_hi")),
            vitreous_at_high_index=bool(get("vitreous_at_high_index")),
            source=str(get("source")))


def write_manifest(metas, cache_dir) -> Path:
    path = Path(cache_dir) / MANIFEST_NAME
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(metas[0])))
        writer.writeheader()
        for meta in metas:
            writer.writerow(asdict(meta))
    return path


def pack_images(pack_dir) -> dict:
    """Single unaveraged B-scans from the review packs -- for checks only."""
    out = {}
    for path in sorted(Path(pack_dir).glob("*_pack.npz")):
        with np.load(path, allow_pickle=False) as pack:
            scan_id = str(pack["scan_id"][0])
            for k, bscan in enumerate(pack["bscan_index"].astype(int)):
                out[(scan_id, int(bscan))] = pack["images"][k].astype(np.float32)
    return out


def assert_not_pack_images(cache_dir, pack_dir, records) -> int:
    """Loud check that the cache holds averages, not the raw pack B-scans.

    Same geometry (asserted), different pixels (asserted): a silent fallback to
    the pack image would make the two bit-identical.
    """
    packs = pack_images(pack_dir)
    checked = 0
    for record in records:
        key = (record["scan_id"], int(record["bscan"]))
        if key not in packs:
            continue
        cached = load_image(cache_dir, *key)
        raw = packs[key]
        if cached.shape != raw.shape:
            raise AssertionError(
                f"{key}: cached image {cached.shape} != pack image {raw.shape}")
        if np.array_equal(cached, raw):
            raise AssertionError(
                f"{key}: cached training image is bit-identical to the "
                "unaveraged pack image -- the averaging pass did not run")
        checked += 1
    if checked == 0:
        raise AssertionError("no cached image could be compared with a pack image")
    return checked
