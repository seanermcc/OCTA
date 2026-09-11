"""Load structural/OCTA data for linked en-face CNV annotation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from octa.volio import ProcessedVolume, VolumeReadError, find_retina_band

from .config import CASCADE_VERSION, SURFACE_NAMES
from .segment import detect_orientation, prepare_bscan


@dataclass
class CnvScan:
    scan_id: str
    segmentation_path: Path
    source_volume: Path
    structural_band: np.ndarray  # stored orientation [B-scan, A-line, depth]
    structural_enface: np.ndarray
    octa_enface: np.ndarray
    surfaces: np.ndarray  # canonical cropped [B-scan, surface, A-line]
    confidence: np.ndarray
    shadow: np.ndarray
    surface_names: tuple[str, ...]
    px_um: float
    retina_band: tuple[int, int]
    vitreous_at_high_index: bool
    animal: str = ""
    eye: str = ""
    day_label: str = ""
    days_post_laser: str = ""
    session_date: str = ""

    @property
    def native_shape(self) -> tuple[int, int]:
        return tuple(int(x) for x in self.structural_band.shape[:2])

    def structural_bscan(self, index: int) -> np.ndarray:
        return prepare_bscan(
            self.structural_band[int(index)], self.vitreous_at_high_index)


def _scalar(data, key: str, default="") -> str:
    return str(data[key][0]) if key in data.files else default


def _streamed_depth_profile(dataset, block_depth: int = 16) -> np.ndarray:
    """Mean vs depth without holding the complete 2-GB volume in memory.

    The HDF5 chunks have depth extent one, so stepping through depth blocks
    touches each compressed chunk once.  This is unlike the forbidden
    per-B-scan loop, which repeatedly decompresses the same chunks.
    """
    n_depth = int(dataset.shape[2])
    profile = np.empty(n_depth, dtype=np.float64)
    for lo in range(0, n_depth, block_depth):
        hi = min(n_depth, lo + block_depth)
        block = np.asarray(dataset[:, :, lo:hi], dtype=np.float32)
        profile[lo:hi] = block.mean(axis=(0, 1), dtype=np.float64)
    return profile


def _mean_db_array(volume: np.ndarray, block_depth: int = 24) -> np.ndarray:
    total = np.zeros(volume.shape[:2], dtype=np.float64)
    for lo in range(0, volume.shape[2], block_depth):
        block = np.asarray(volume[:, :, lo:lo + block_depth], dtype=np.float32)
        total += np.log10(np.maximum(block, 1e-3)).sum(axis=2, dtype=np.float64)
    return (20.0 * total / volume.shape[2]).astype(np.float32)


def _mean_db_dataset(dataset, depth_slice: slice,
                     block_depth: int = 16) -> np.ndarray:
    start = 0 if depth_slice.start is None else int(depth_slice.start)
    stop = int(dataset.shape[2]) if depth_slice.stop is None else int(depth_slice.stop)
    total = np.zeros(dataset.shape[:2], dtype=np.float64)
    count = 0
    for lo in range(start, stop, block_depth):
        hi = min(stop, lo + block_depth)
        block = np.asarray(dataset[:, :, lo:hi], dtype=np.float32)
        total += np.log10(np.maximum(block, 1e-3)).sum(axis=2, dtype=np.float64)
        count += hi - lo
    if count < 1:
        raise ValueError("projection depth range is empty")
    return (20.0 * total / count).astype(np.float32)


def read_scan(segmentation_path: str | Path) -> CnvScan:
    """Read one current eight-boundary scan for linked annotation.

    Surface arrays are never used to construct either projection.  They are
    loaded only for the linked B-scan overlay.  Orientation is re-detected from
    the structural data as required by the project contract; the stored
    orientation flag is deliberately ignored.
    """
    seg_path = Path(segmentation_path)
    with np.load(seg_path, allow_pickle=False) as seg:
        version = _scalar(seg, "cascade_version", "unknown")
        if version != CASCADE_VERSION:
            raise ValueError(
                f"{seg_path.name} uses cascade {version!r}; expected {CASCADE_VERSION!r}")
        scan_id = _scalar(seg, "scan_id", seg_path.stem)
        source = Path(_scalar(seg, "source"))
        surface_names = tuple(str(x) for x in seg["surface_names"])
        if surface_names != tuple(SURFACE_NAMES):
            raise ValueError(
                f"{seg_path.name} surfaces do not match the current eight-boundary "
                "definition")
        surfaces = np.asarray(seg["surfaces"], dtype=np.float32)
        confidence = (np.asarray(seg["confidence"], dtype=np.float32)
                      if "confidence" in seg.files
                      else np.full(surfaces.shape, np.nan, dtype=np.float32))
        shadow = (np.asarray(seg["shadow"], dtype=bool)
                  if "shadow" in seg.files
                  else np.zeros(surfaces.shape[::2], dtype=bool))
        px_um = float(seg["px_um"][0]) if "px_um" in seg.files else 1.12
        stored_band = (tuple(int(x) for x in seg["retina_band"])
                       if "retina_band" in seg.files else None)
        metadata = {
            key: _scalar(seg, key) for key in
            ("animal", "eye", "day_label", "days_post_laser", "session_date")
        }
    if not source.is_file():
        raise FileNotFoundError(f"source volume not found: {source}")

    with ProcessedVolume(source) as volume:
        if volume.angio is None:
            raise VolumeReadError(
                f"{source.name} has no frame_OCTAAvg channel; linked structural/OCTA "
                "annotation requires both channels")
        if tuple(volume.angio.shape[:2]) != tuple(volume.struct.shape[:2]):
            raise VolumeReadError(
                f"structural grid {volume.struct.shape[:2]} and OCTA grid "
                f"{volume.angio.shape[:2]} do not align")
        profile = _streamed_depth_profile(volume.struct)
        detected_lo, detected_hi, _unused = find_retina_band(profile)
        vitreous_at_high_index = detect_orientation(profile)
        lo, hi = stored_band or (detected_lo, detected_hi)
        if not (0 <= lo < hi <= volume.struct.shape[2]):
            raise ValueError(
                f"stored retina band {(lo, hi)} is outside structural depth "
                f"0..{volume.struct.shape[2]}")
        structural_band = volume.read_volume(
            channel="struct", depth_slice=slice(lo, hi))
        structural_enface = _mean_db_array(structural_band)
        octa_enface = _mean_db_dataset(volume.angio, slice(lo, hi))

    native_shape = tuple(int(x) for x in structural_band.shape[:2])
    expected_surfaces = (native_shape[0], len(surface_names), native_shape[1])
    if surfaces.shape != expected_surfaces:
        raise ValueError(
            f"surface shape {surfaces.shape} does not match volume grid "
            f"{expected_surfaces}")
    if confidence.shape != surfaces.shape:
        raise ValueError("confidence must have the same shape as surfaces")
    if shadow.shape != native_shape:
        raise ValueError("shadow must have shape [B-scan, A-line]")

    return CnvScan(
        scan_id=scan_id,
        segmentation_path=seg_path,
        source_volume=source,
        structural_band=structural_band,
        structural_enface=structural_enface,
        octa_enface=octa_enface,
        surfaces=surfaces,
        confidence=confidence,
        shadow=shadow,
        surface_names=surface_names,
        px_um=px_um,
        retina_band=(lo, hi),
        vitreous_at_high_index=vitreous_at_high_index,
        **metadata,
    )
