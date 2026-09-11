# Implementation validation

- **19 unit checks passed.** Physical anisotropic pixel outlines, circular and
  irregular lesions, exact bin boundaries, overlap ownership, ONH exclusion,
  clipped-outline recovery, rigid transforms, half-pixel mask transfer,
  classification overrides, unresolved dates, failed image matches, ambiguous
  identities, duplicate observations, missing layers, and equal-animal weights.
- **End-to-end synthetic run passed:** 672 measurement rows and 22 numbered
  figures. A second measurement run reused verified checkpoints and produced an
  identical numerical table. The deliberately absent OPL remained unavailable;
  “6mo” remained categorical. This artificial dataset is not study evidence.
- **Three real scans passed thickness/interface checks:** TS241 D42 s03,
  TS247 D14 s05, and TS250 D27 s03. Every layer matched independent endpoint
  subtraction under the exact octa-thick policy. Shadow NaNs were preserved.
  Protected annotation and segmentation artifact hashes remained unchanged.
- **Real registration failure retained:** TS247 D21 s03 against D14 s05 produced
  only three inliers among 16 tentative matches and failed the configured
  diagnostics. Its overlay visibly shows vessel disagreement; the transform is
  not eligible for tissue tracking. This is evidence that rejection works, not
  validation of registration accuracy across the cohort.
- **Visual inspection:** reviewed the three-panel real ring check, the real
  failed-registration overlay, individual synthetic distance/longitudinal plots,
  and a contact sheet of all 22 synthetic figures. Missing layers and coverage
  remain blank, anatomical labels retain their provisional explanation, and
  unresolved dates are not converted into invented day numbers. Numbering,
  caption presence, image decoding, and source-table hashes are checked by the
  figure builder.
- **Final cohort gate tested:** `run` stops before registration/measurement when
  the upstream batch's `FINAL_VERIFIED.json` is absent. No final cohort analysis
  completion marker has been issued in the release root.

This verifies implementation behavior and data interfaces. It does not establish
biological accuracy of the experimental segmentation or manual lesion identities.
Final scientific figures require the completed batch and the supported/reviewed
alignments documented in the output guide.
