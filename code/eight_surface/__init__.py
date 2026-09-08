"""Eight-boundary OCT segmentation and manual-review workflow.

This package is intentionally separate from the original ten-surface tools in
``code/``.  The old GUI and cascade remain usable for their existing labels;
new outputs carry an incompatible cascade version so the two label sets cannot
be mixed accidentally.
"""

from .config import (  # noqa: F401
    ANALYSIS_LAYER_DEFS,
    CASCADE_VERSION,
    LAYER_DEFS,
    N_SURFACES,
    SURFACE_NAMES,
)

