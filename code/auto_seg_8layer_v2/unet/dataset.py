"""Assemble one training sample: input channels, targets, masks, geometry.

Composes :mod:`flatten`, :mod:`tensors` and :mod:`targets`.  Nothing here is
model-specific -- a sample is plain numpy, so Phase 2 can wrap it in whatever
``Dataset`` class it wants without touching this file.

Channel order is fixed and stated once, here:

``channels[0]``  flattened, intensity-normalised image;
``channels[1]``  the same normalised image **unflattened**, so the model can
                 recover where the flattening is locally wrong.

Every array is in *flattened, cropped* coordinates.  ``shifts`` and ``row0``
are carried on the sample so predictions can be returned to original image
coordinates -- which :func:`to_image_rows` does, and which must happen before
anything is compared with a human label or written to disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from eight_surface.config import N_SURFACES

from . import flatten as F
from . import targets as T
from . import tensors as V

# The anchor row inside the cropped window: the posterior tissue edge sits
# CROP_ABOVE rows down, leaving CROP_BELOW rows of sub-RPE below it.
ANCHOR_ROW = F.CROP_ABOVE
NORM_PERCENTILES = (1.0, 99.5)


@dataclass
class Sample:
    scan_id: str
    bscan: int
    animal: str
    channels: np.ndarray        # [2, H, W] float32
    valid_mask: np.ndarray      # [H, W] bool: real pixels, not wrapped padding
    region_ids: np.ndarray      # [H, W] int8, 0..8
    region_weight: np.ndarray   # [H, W] float32
    boundary_maps: np.ndarray   # [8, H, W] float32, each column sums to 1 or 0
    boundary_weight: np.ndarray  # [8, W] float32
    # Local measurability supervision, on a different mask from the boundary
    # head: 1 where a human said the boundary was identifiable, 0 where they
    # said it was not, and zero *weight* where nobody said anything at all.
    visibility_target: np.ndarray  # [8, W] float32
    visibility_weight: np.ndarray  # [8, W] float32
    rows: np.ndarray            # [8, W] float32, human rows in sample coords
    shifts: np.ndarray          # [W] int64
    row0: int                   # top of the crop in flattened coordinates
    raw_row0: int               # top of the unflattened channel's crop
    px_um: float
    n_surfaces_supervised: int

    @property
    def height(self) -> int:
        return self.channels.shape[1]

    @property
    def width(self) -> int:
        return self.channels.shape[2]


def normalise(image: np.ndarray, percentiles=NORM_PERCENTILES) -> np.ndarray:
    """Per-B-scan scaling to the 1st-99.5th percentile range."""
    finite = image[np.isfinite(image)]
    if finite.size == 0:
        raise AssertionError("image has no finite pixels")
    lo, hi = np.percentile(finite, list(percentiles))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        raise AssertionError(f"degenerate intensity range ({lo}, {hi})")
    out = (np.asarray(image, np.float32) - lo) / (hi - lo)
    return np.clip(out, -0.5, 1.5).astype(np.float32)


def sample_rows(rows: np.ndarray, shifts: np.ndarray, row0: int) -> np.ndarray:
    """Image-coordinate surface rows -> flattened, cropped coordinates."""
    return F.shift_rows(rows, shifts) - float(row0)


def to_image_rows(rows: np.ndarray, shifts: np.ndarray, row0: int) -> np.ndarray:
    """Flattened, cropped surface rows -> original image coordinates.

    The exact inverse of :func:`sample_rows`; call it before comparing anything
    with a human label.
    """
    return F.unshift_rows(np.asarray(rows, float) + float(row0), shifts)


def build_sample(record, image: np.ndarray, sigma: float = T.BOUNDARY_SIGMA_PX,
                 anchor_row: int = ANCHOR_ROW, above: int = F.CROP_ABOVE,
                 below: int = F.CROP_BELOW,
                 legacy_policy: str = T.DEFAULT_LEGACY_POLICY) -> Sample:
    """One sample from one ``corrected`` label and its averaged image.

    ``legacy_policy`` governs only labels written before per-A-line provenance
    existed; see :mod:`eight_surface.provenance`.  Labels that carry provenance
    are masked from it exactly, whatever the policy says.
    """
    if record["verdict"] != "corrected":
        raise AssertionError(
            f"{record['scan_id']} b{record['bscan']}: verdict "
            f"{record['verdict']!r} is not evidence and must not be built into "
            "a supervised sample")
    image = np.asarray(image, np.float32)
    human = np.asarray(record["surfaces"], float)
    if human.shape[0] != N_SURFACES:
        raise AssertionError(f"label has {human.shape[0]} surfaces, expected {N_SURFACES}")
    if image.ndim != 2 or image.shape[1] != human.shape[1]:
        raise AssertionError(
            f"image {image.shape} does not match label width {human.shape[1]}")

    normalised = normalise(image)
    # Flatten so the posterior tissue edge lands on ``anchor_row`` of the
    # flattened image; the crop is then the top ``above + below`` rows and
    # ``row0`` is 0.  Keeping row0 explicit costs nothing and keeps
    # ``to_image_rows`` correct if the window is ever moved.
    shifts = F.flatten_shifts(image, target_row=int(anchor_row))
    flat = F.apply_shifts(normalised, shifts)
    window, row0 = F.crop(flat, target_row=int(anchor_row), above=above,
                          below=below)
    # Second channel: the same normalised pixels, *not* flattened, cropped
    # around the median posterior edge so the retina is in frame.  It carries
    # its own offset because it is deliberately in different coordinates.
    raw_anchor = int(np.rint(np.median(F.posterior_edge(image))))
    raw_window, raw_row0 = F.crop(normalised, target_row=raw_anchor,
                                  above=above, below=below)
    if window.shape != raw_window.shape:
        raise AssertionError("flattened and unflattened channels differ in shape")
    # The roll is circular so the round trip stays lossless; pixels it brought
    # in from the other end of the image are not evidence about this retina, so
    # they are zeroed here and carry no loss weight below.
    valid, _ = F.crop(F.wrap_mask(normalised.shape, shifts),
                      target_row=int(anchor_row), above=above, below=below)
    window = np.where(valid, window, 0.0).astype(np.float32)

    rows = sample_rows(human, shifts, row0)
    weight_b = T.boundary_weight(record, rows=rows, height=window.shape[0],
                                 legacy_policy=legacy_policy)
    supervised = (T.surface_supervised(record, legacy_policy)
                  & (weight_b.sum(axis=1) > 0))
    if not supervised.any():
        raise AssertionError(
            f"{record['scan_id']} b{record['bscan']}: no supervised surface "
            "survived the crop")
    ids = T.region_map(rows, window.shape[0])
    weight_r = (T.region_weight(record, ids, rows=rows,
                                legacy_policy=legacy_policy)
                * valid.astype(np.float32))

    return Sample(
        scan_id=record["scan_id"], bscan=int(record["bscan"]),
        animal=record["scan_id"].split("_", 1)[0],
        channels=np.stack([window, raw_window]).astype(np.float32),
        valid_mask=valid.astype(bool),
        region_ids=ids, region_weight=weight_r.astype(np.float32),
        boundary_maps=T.boundary_maps(rows, window.shape[0], sigma=sigma),
        boundary_weight=weight_b.astype(np.float32),
        visibility_target=T.visibility_target(record).astype(np.float32),
        visibility_weight=T.visibility_weight(record).astype(np.float32),
        rows=rows.astype(np.float32), shifts=shifts, row0=int(row0),
        raw_row0=int(raw_row0), px_um=float(record["px_um"]),
        n_surfaces_supervised=int(supervised.sum()))


def build_samples(records, cache_dir, sigma: float = T.BOUNDARY_SIGMA_PX,
                  legacy_policy: str = T.DEFAULT_LEGACY_POLICY):
    """Samples for every ``corrected`` record, in label order."""
    out = []
    for record in T.supervised_records(records):
        image = V.load_image(cache_dir, record["scan_id"], record["bscan"])
        out.append(build_sample(record, image, sigma=sigma,
                                legacy_policy=legacy_policy))
    return out


def save_sample(sample: Sample, out_dir) -> Path:
    path = Path(out_dir) / f"{sample.scan_id}_b{sample.bscan:04d}_sample.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path, channels=sample.channels, valid_mask=sample.valid_mask,
        region_ids=sample.region_ids,
        region_weight=sample.region_weight, boundary_maps=sample.boundary_maps,
        boundary_weight=sample.boundary_weight,
        visibility_target=sample.visibility_target,
        visibility_weight=sample.visibility_weight, rows=sample.rows,
        shifts=sample.shifts, row0=np.array([sample.row0]),
        raw_row0=np.array([sample.raw_row0]), px_um=np.array([sample.px_um]),
        scan_id=np.array([sample.scan_id]), bscan=np.array([sample.bscan]),
        animal=np.array([sample.animal]))
    return path
