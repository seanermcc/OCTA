# octa-auto_cnv_v2 — lesion assessment first, integrated manual correction

Status: implemented and pilot-verified, 2026-09-11. See START_HERE.md and DELIVERY.md. V1 results and behavior are unchanged.
Planned code, automatic results and new GUI review records will live under
`outputs/octa-auto_cnv_v2/`, separate from existing labels and released models.

## Direction agreed with the user

Assess potential lesions before estimating unaffected background. Background
quality determines whether percentage thinning can be reported; it must not
determine whether a lesion can be detected, displayed or corrected.

Treat localized invalid boundary geometry as positive evidence for a potential
lesion. It can reflect the structural disruption that matters here, rather than
being only a reason to discard a measurement. Preserve the missing thickness at
that location. Geometry failure contributes evidence; it does not by itself
prove CNV, because vessels, motion and segmentation errors can also cause it.

Use automatic proposals followed by manual review in one interface. Reuse the
older CNV annotation tools rather than relying on automatic results alone.

## Specific failure that motivates v2

The user identified a missed site in **TS267_OD_2025-03-05_D14_s01_104048**,
approximately native A-line 85, B-scan 230. The screenshot shows the
`upper_reference` display. Saved arrays at that approximate point show:

- Automatic and viewer thickness are unavailable.
- Invalid neural geometry is flagged.
- Vessel, shadow, low-signal and automatic not-traceable flags are false.
- Background support is false for default, narrow-halo and upper-reference fits.
- No core is proposed. The surrounding 40 × 40-pixel window has no support in
  the upper-reference variant.

V1 uses background support as a prerequisite for both the deficit map and the
clustered-loss candidate branch. That prevents geometry failure at this site
from contributing to a proposal. Its support region also follows a straight-edged
polygon around retained background tile centers, producing the arbitrary-looking
colored region in the screenshot. That polygon is not anatomy or a lesion border.

Record this as a user-identified review target and regression example. The point
is approximate; this plan does not create a human lesion mask or exact border.
Trace which boundary pair or crop violation caused the geometry flag before
interpreting the failure further: full-retina availability can be lost because
an endpoint crosses an intermediate surface, not just because ILM crosses RPE.

## 1. Generate lesion proposals independently of background support

Build candidates across the native field using interpretable evidence:

- Spatial clusters of automatic crossings, nonfinite positions and out-of-crop
  boundaries, with the responsible boundaries and violation sizes recorded.
- Local structural disruption in en-face images and linked B-scans, including
  whether a focus persists across neighboring B-scans.
- Localized automatic trace loss or uncertainty and directly observed thickness
  changes where measurable. Missing tissue measurements remain missing.

Record each evidence type separately and combine them into an explainable
candidate priority. Begin with classical rules; no new neural-network training
is required for this step. Retain tentative candidates with incomplete evidence
for review instead of forcing a binary absence decision.

Do not require a supported global background, a missing center, 30% severe
thinning, or a ring of 15% thinning to admit a candidate. Do not require circular
shape. Candidate detection must still operate when no background fit is possible.

Use vessel/shadow, low signal, image seams and borders as artifact evidence.
Do not erase an entire lesion because it crosses a vessel or reaches the field
edge. Distinguish the affected pixels, mark uncertain or clipped margins, and
allow multiple lesions and shared surrounding thinning zones. An isolated noisy
crossing should not be treated the same as a persistent structural focus.

## 2. Estimate background and thinning after lesion assessment

Use proposed lesion locations to exclude likely lesions and surrounding halos
from background sampling. Estimate a spatially varying reference from remaining
measurable retina, accounting for vessels, shadows and acquisition problems.
Check sensitivity to halo exclusion and background model choice. Avoid allowing
a broad halo to lower its own expected thickness.

Keep three outputs separate:

1. Candidate lesion/core extent and its supporting evidence.
2. Measurable lesion-associated thinning footprint under a stated rule.
3. Descriptive 10%, 20% and 30% thinning contours, with reference sensitivity.

Preserve the viewer's Full retina definition: ILM to outer RPE edge ×1.12 µm/px.
Preserve signed deficits and native [B-scan,A-line] coordinates. Unsupported
background and missing thickness must not become zero deficit or zero lesion area.

Reassess reference support using local sample coverage, distance and fit
sensitivity. Do not replace the arbitrary polygon by an equally arbitrary
smoothed boundary. Keep unsupported numerical deficits unavailable. If a fitted
extrapolation is shown for inspection, label it explicitly as an estimate and
exclude it from supported quantitative area summaries.

The automatic candidate set must not change merely because the user switches
background variants. Background-dependent quantitative contours may change.

## 3. Integrate the older manual CNV tools into the map viewer

Recommendation: one viewer with automatic proposals and manual correction.
V1 already opens the established region editor through **Edit proposals**, but
that separate window is only a starting point. V2 should bring its region editing
and the older en-face CNV brush/outline tools into the same native-coordinate
review flow.

Reuse `eight_surface/cnv_gui.py` for brush and outline interactions and
`cnv_review_v1/gui.py` / `RegionStore` for region selection, classification,
undo/redo, conflict detection and review history. Inspect their persistence
contracts before extending them; avoid adding a competing annotation format
without a documented adapter.

The review interface should support:

- Structural en-face, candidate evidence, thickness/deficit and linked B-scans
  with synchronized crosshairs and the same selected lesion.
- Select, add a missed lesion, paint/erase, redraw, split/merge, or reject a
  proposal; undo/redo and explicit review completion.
- Separate candidate-core editing from manual structural lesion-footprint
  editing. Editing a lesion border must not redefine a numerical thinning contour.
- A reason panel showing geometry failures, structural support, vessel/shadow
  evidence and missing-data causes at the selected candidate or point.
- Clearly different displays for missing thickness, uncertain background,
  vessel/shadow exclusions, uncertain margins and field clipping. Keep candidates
  visible through all these overlays; never imply that gray means no lesion.
- Original manual footprints as comparison overlays. Reuse saved work safely;
  opening a proposal or switching views must not save or approve labels.

Use actual OCTA only if an appropriate source projection is loaded. Never label
a structural or deficit image as OCTA. Background-region inspection remains
available but is secondary to the lesion review task.

## 4. Preserve provenance and use corrections carefully

Store original automatic masks separately from human corrections. Retain the
seed hash, edited pixels/regions, explicit approval or rejection, unreviewed
parts, source coordinates and revision history. No automatic pixels become
ground truth merely because the file was opened or another region was edited.
Only GUI actions may create human annotations.

Differentiate machine-generated geometry failures from holes introduced by
human position edits, not-visible decisions, unreliability or region exclusion.
The automatic branch must exclude target CNV masks and their downstream review
effects where separable. Any branch using them must be labeled assisted.

Human corrections should first evaluate and improve the proposal rules. Consider
a small learned candidate-ranking component only after measured results justify
it. There is no need to train a large segmentation network as part of this plan.

## 5. Validation and delivery gates

1. **D14 regression:** candidate evaluation must reach the user-identified region
   and expose its geometry-failure evidence even when background support is false.
   Review the structural evidence; do not hard-code a lesion at the supplied point.
2. **Independence:** removing background support or changing reference variants
   cannot suppress the first-stage candidate list. Quantitative outputs still
   honor their own support requirements.
3. **Artifact challenges:** test isolated crossings, vessels, seams, diffuse low
   signal, multiple lesions, shared halos, and lesions near the field edge. Record
   remaining misses and uncertain candidates rather than hiding them.
4. **TS267 pilot:** compare v1 and v2 on all 17 selected acquisitions, including
   D0 and the D7/D28 manual-location failures. Measure location agreement, manual
   review burden, candidate rejection and contour/area stability. Count reviewed
   unaffected tissue as negative only when that review actually exists. Nominal
   D0 is not proof of absence; disconnected manual-mask fragments are not necessarily
   distinct lesions, and ambiguous edges are not exact ground truth.
5. **Annotation checks:** verify native-coordinate clicks, add/erase/redraw,
   split/merge, undo/redo, save/reload, conflict handling, no writes on opening,
   and preservation of unreviewed automatic pixels and original labels.
6. **Quantitative checks:** missing-data and unit invariants, lesion-free spatial
   gradients, broad-halo contamination, insufficient-background behavior, and
   separate supported versus extrapolated summaries.

Deliver a separate v2 launcher, integrated reviewer, saved automatic and assisted
outputs, comparisons against v1, and visual examples including failures. Preserve
v1 for reproducibility. Continue to disclose upstream ALL_LABELLED training
overlap, including TS267. Reserve other animals for subsequent detector evaluation
and distinguish that from the upstream model's existing training exposure.
No longitudinal lesion-change claim without registration.

## Position on fully automatic use

Aim for automatic proposals that require little correction, with a manual
correction path retained. V1's default 0/7 agreement with the reviewed manual-mask
components does not justify unattended use. Better automation needs explicit
measurements of missed lesions and false candidates, and corrections provide the
reference needed to measure those improvements. Fully automatic performance is
an outcome to demonstrate, not an assumption for v2.
