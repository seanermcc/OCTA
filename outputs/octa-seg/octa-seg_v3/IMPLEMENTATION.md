# v3 implementation and verification

This is an annotation/workflow release. No weights, training labels, prior
settings, source volumes or existing segmentation outputs were modified.

## Relationship to earlier applications

The historical v1 label audit identifies exactly **160 format-2 records** from
the eight-boundary workflow. Its editor is `code/eight_surface/label_gui.py`,
using `code/label_gui.py` for the native Qt canvas and `code/octa/labels.py` for
stroke joining and order constraints. There are now 161 files in the original
eight-surface label directory; the historical frozen audit remains the evidence
for the 160-record workflow the user recalled.

The v3 editor reuses that canvas and its modifier-intent implementation through
`cnv_review_v1.label_gui.BoundaryEditor`. Default input immediately edits a curve.
V2's default all-boundary strip mode is not installed. The existing stroke and
ordering functions are reused, with explicit protection against NaN propagation
when a numerical base is missing. The standard eight-boundary serializer is
called only through the GUI's staged save, with the actual reviewer ID recorded.

Versioned v3 code is in `code/octa_seg_v3` under this directory. The launcher
activates the octa environment and imports the existing project and v2 libraries
read-only. Large cached images and predictions are referenced in place. The ten
v2 providers take precedence over duplicate cohort providers; the catalog contains
314 unique acquisitions.

## Evidence contract

The GUI-written JSON journal is authoritative and stores actual gestures and
case decisions, not inferred corrections. A replay creates exact stroke, taper,
ordering-displacement and explicit-review masks. Anatomy, visibility,
reliability and image exclusions stay separate. Visibility restoration does not
restore reliability or clear an anatomical-absence judgment. Clearing a regional
default reveals the previous local judgment rather than asserting reliability.

Exact-position approvals include the reviewed coordinates. Changed positions,
denials, exclusions and ordering displacement revoke their eligibility. Ordinary
review/approval remains distinct from a drawn stroke. Positive state judgments
inside image exclusions are masked from prepared training targets; explicit
negative evidence survives. `feedback.position_targets` exposes separate reliable
manual, ambiguous manual and approved-position pools. A future training importer
must also enforce frozen data roles and reviewer/animal partitions.

Case categories, ambiguity/sharing flags, notes, completion and data roles are
metadata events. They do not automatically mark any boundary reliable. Compatibility
NPZ files include numerical working curves, so treating every coordinate in one as
a manual label would be incorrect. Their sidecars point to the journal, which
also preserves the separate anatomical-absence meaning unavailable in the legacy
format. The `tests` subtree is never an annotation source.

Per-reviewer session locks and per-file exclusive locks prevent simultaneous
writers. Hash comparison rejects stale saves. Journals use atomic replacement,
retain old revisions and abandoned redo branches, and are saved before derived
compatibility files. If a compatibility save fails, the authoritative event
survives and can be replayed. Source/model identity is checked when reopening a
journal or assigned shared case. No other reviewer's position labels or state
guards preload; saved anatomical footprint masks remain visual context.

## Maps and cache

The navigator switches its existing image between structural OCT with optional
vessel/CNV/ONH masks and nine native thickness maps. Color scaling is fixed per
scan/layer while editing. Thickness is an endpoint difference times 1.12 µm,
with no interpolation, smoothing, or uncertain-position substitution. Direct
uncertain strokes and software joins remain candidates until affirmed. New stroke
events store `drawing_reliability`: the ON mode marks exact drawn support unreliable;
OFF marks it reliable. Events without that field preserve historical semantics.
Switching the drawing mode writes no annotation. A shadow,
excluded image, invalid/crossing endpoint, explicit absence or untraceable endpoint
produces NaN. Changes update the current row; reopening a scan replays this
reviewer's saved rows into a private copy of the maps.

The background cache has one read worker and retains at most three volumes,
targeting the current scan plus the next two. Its budget is the smaller of 3 GB
and one quarter of available RAM, with a small-memory fallback. Large image arrays
use read-only memory mapping if the per-volume RAM allowance is insufficient.
Completed futures are released so they do not retain evicted volume buffers.
Loading/navigation is asynchronous; no annotation writes run in the preload worker.

## Verification — September 14, 2026

`VERIFY_V3.cmd --real` passed:

* 11 evidence/geometry contract checks, including independent modifier axes,
  anatomical absence, exact strokes versus software changes, position-approval
  invalidation, positive-state exclusion masking, and thickness units/NaNs.
* Actual Qt mouse/key events for single-click correction, all original modifier
  gestures, keyboard boundary/B-scan navigation, undo/redo, save/reopen, local
  anatomical absence, case flags, notes across navigation and hidden-model mode.
* Reviewer isolation, annotation-free sharing, exact reviewer attribution and
  stale-writer rejection. No Qt callback errors were recorded.
* Read-only loading of real WT, before-laser and CNV cohort caches. The current
  and next two volumes were held in memory. One cold opening took 2.19 seconds;
  opening a cached scan took 0.24 seconds. Their retained arrays occupied
  1,363,149,739 bytes (1.27 GiB), within the 2.15-GiB budget measured for that run.
  These are workstation measurements, not guaranteed timings for every scan.
* All **199 protected existing annotation files** hashed before/after remained
  unchanged. Real-volume verification created no boundary labels.
* Visual inspection of the real en-face and thickness screens confirmed the
  shared navigator, color scale, visible gesture key, category/sharing controls
  and large boundary-editing canvas.

See `tests/latest_verification.json` for the result and screenshot directory.
Synthetic GUI data is identified explicitly and stored only under `tests`.

## Subsequent work

The training plan deliberately precedes model fitting. Real label collection,
the remainder of the 30-case frozen assessment set, adjudication/reader-agreement
analysis, new absence prediction and model calibration remain later stages. The
queue is a same-project/shared-workstation handoff, not a portable off-site image
package. Existing all-label checkpoint exposure still prevents unseen-animal
claims without animal-excluded training and ancestry checks.
