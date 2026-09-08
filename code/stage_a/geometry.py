"""One native-depth canonical channel; identical preprocessing at train/infer."""
import numpy as np
from eight_surface.segment import prepare_bscan

PREPROCESS = dict(version="native-single-db-p1-p99.5-v1", bscan_avg=1,
                  channels=1, spatial_resampling=False, crop="full_native_depth",
                  percentiles=[1.0, 99.5], clip=[-0.5, 1.5])


def preprocess(raw, vitreous_high):
    image = prepare_bscan(raw, vitreous_high)
    if not np.isfinite(image).all():
        raise ValueError("Non-finite source image")
    lo, hi = np.percentile(image, PREPROCESS["percentiles"])
    if not hi > lo:
        raise ValueError("Degenerate image intensity range")
    x = np.clip((image-lo)/(hi-lo), *PREPROCESS["clip"]).astype(np.float32)
    return x[None], image, [float(lo),float(hi)]


def label_offset(band, native_depth, vitreous_high):
    lo, hi = band
    if not 0 <= lo < hi <= native_depth:
        raise ValueError("Invalid label band")
    return native_depth-hi if vitreous_high else lo


def to_disk_rows(canonical, native_depth, vitreous_high):
    return native_depth-1-np.asarray(canonical) if vitreous_high else np.asarray(canonical).copy()
