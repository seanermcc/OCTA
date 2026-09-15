from pathlib import Path
p=Path('outputs/octa-thick_v1/test_pilot.py'); s=p.read_text()
for name in ['test_pairings_units_and_missing_internal','test_raw_ilm_preview_only_and_other_raw_never_used','test_pending_stroke_approval_denial_undo','test_stale_context_and_fixed_limits']:
 s=s.replace('    def '+name, "    @unittest.skip('Historical strict-reporting policy; superseded by test_policy.py')\n    def "+name)
p.write_text(s)
p=Path('outputs/octa-thick_v1/START_HERE.md')
s=p.read_text(encoding='utf-8')
p.write_text('''# Current pilot behavior — updated September 10, 2026

Available saved segmentation positions are assumed usable for this preliminary
analysis. Full-retina thickness uses saved U-Net ILM by default. All boundaries
may use saved model positions where reported/context positions are unavailable.
Direct human strokes take precedence without requiring a training approval.

**Include unreliable measurements** is off by default. It adds positions explicitly
marked unreliable by a human (saved reliability flags or frozen explicit-human
unreliable reason). Model uncertainty/calibration withholding alone does not
exclude a position. Dotted lines and white map stipple identify included unreliable
measurements. Color limits stay fixed when toggling.

Shadows, image exclusions, rejected rows, not-traceable endpoints, and invalid
geometry remain blank in both modes. Source labels and segmentation files are
unchanged. This is an analysis assumption, not a change to ground truth or validation.

NPZ exports now provide `exclude_unreliable_um`, `include_unreliable_um`, and
unreliable endpoint/measurement masks. Legacy array names remain as aliases;
`estimated_mask` now means explicitly unreliable measurements. Metadata records
this revised policy. Point CSV files use a new `_pilot_v2_points.csv` filename.
Previous-policy exports are flagged stale when their scan is loaded.

Current policy tests: `test_policy.py`. Historical strict-policy details below
are retained for reference and no longer describe the default behavior.

---

'''+s,encoding='utf-8')
