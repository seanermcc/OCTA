# Cache-only reviewer packages

`code/build_portable_seg_review.py --destination <empty-folder>` selects all
acquisitions with a currently confirmed lead review, irrespective of sharing
flags. It verifies confirmation replay and model identity before copying the
complete canonical B-scan caches, frozen predictions, geometry, calibration,
and the current default CNV/vessel/ONH context. Human records and their histories
are copied byte-for-byte. No annotation writer is invoked by the builder.

A `PORTABLE_CACHE.json` at the copied project root activates cache-only mode.
Without it, the ordinary reviewer keeps its existing source-loading behavior.
The manifest restricts discovery to the included acquisitions, maps historical
and relocated provider/image paths to files inside the package, and retains
original processed-volume identity as provenance. It does not create placeholder
MAT files or alter source identities in human journals.

Loading checks SHA-256 hashes for prepared metadata, images, measurements,
geometry, calibration and context. Existing model identities remain unchanged.
External data fallback is disabled. Default overlays are a dated snapshot;
refresh reloads that snapshot, and experimental ONH is explicitly unavailable.

`code/verify_portable_seg_review.py <package-folder>` verifies all included
volumes and confirmations using the package's imports, blocks file reads from
the home project and all MAT/RAW opens, exercises native endpoint navigation,
and checks copied human records remain unchanged. Existing synthetic Qt tests
exercise editing, confirmation, saving/reopening, independent reviewers, undo,
and stale/interrupted saves. Synthetic fixtures cannot supply human labels.

The package includes a launcher and pinned Python requirements; the Python
environment is not bundled. Keep the whole folder together when moving it.
It is the lead's continuation copy, with the lead's answers. A coworker's
independent assignment must be prepared separately without those records.
