**Next annotation step — proposal only**

Start with the saved nine-image pilot. The decoder experiment is complete; this queue is ready for human review, but no new annotation files have been created. Its 24 items are selected review suggestions, not visibility labels.

Use the clean-image panel on each card before considering any model overlay. For each boundary and interval, record visible, locally unidentifiable, or unknown. Separately record whether a position is reliable enough to analyze. Draw a boundary only where it can be identified. Keep every unreviewed region unknown. Mark whole-column exclusion only when the image is unusable for every boundary; local loss of a deep boundary must not erase a visible ILM. Darkness alone does not establish invisibility.

Highest priority is D98 ILM columns 232–250: all three decoders retain a 25–39 um error against the existing manual reference. Review its exact visible boundary and record local drawing support. Next inspect b0510: C2/C3 withhold the entire image, so the pilot must establish which intervals can still be traced. Then review useful tissue lost in D42 b0023/b0508 and TS169 b0164. Add the two TS336 images with no eligible boundary-accuracy labels and the two training controls.

| Image | Partition | Suggested items | Card |
| --- | --- | --- | --- |
| TS325_OD_2026-03-03_D98_s01_131308_b0061 | validation | 4 | [Open](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/annotation_cards/TS325_OD_2026-03-03_D98_s01_131308_b0061.png) |
| TS325_OD_2026-05-26_6mo_s01_112940_b0510 | validation | 4 | [Open](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/annotation_cards/TS325_OD_2026-05-26_6mo_s01_112940_b0510.png) |
| TS169_OS_2025-01-14_D35_s04_121533_b0164 | validation | 4 | [Open](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/annotation_cards/TS169_OS_2025-01-14_D35_s04_121533_b0164.png) |
| TS325_OD_2026-01-05_D42_s05_131602_b0023 | validation | 4 | [Open](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/annotation_cards/TS325_OD_2026-01-05_D42_s05_131602_b0023.png) |
| TS325_OD_2026-01-05_D42_s05_131602_b0508 | validation | 4 | [Open](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/annotation_cards/TS325_OD_2026-01-05_D42_s05_131602_b0508.png) |
| TS336_OD_2026-06-09_D35_s03_154413_b0399 | validation | 1 | [Open](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/annotation_cards/TS336_OD_2026-06-09_D35_s03_154413_b0399.png) |
| TS336_OD_2026-06-09_D35_s03_154413_b0351 | validation | 1 | [Open](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/annotation_cards/TS336_OD_2026-06-09_D35_s03_154413_b0351.png) |
| TS165_OS_2025-04-29_WT_s02_121711_b0315 | train | 1 | [Open](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/annotation_cards/TS165_OS_2025-04-29_WT_s02_121711_b0315.png) |
| TS241_OS_2024-09-04_D21_s03_110143_b0420 | train | 1 | [Open](G:/OCT_TreeShrew/octa/outputs/stage_a/20260908_v6_conservative_decoder/annotation_cards/TS241_OS_2024-09-04_D21_s03_110143_b0420.png) |

The CSV gives zero-based start and end-exclusive A-line coordinates. Cards show the corresponding inclusive endpoint for reading. Items spanning all 512 columns request a review pass, not continuous drawing across unreadable tissue.

The current eight_surface/label_gui.py already supports left-drag drawing, shift+right-drag local invisibility, ctrl+shift+right-drag visibility restoration, alt+right-drag local unreliability, shift+left-drag explicit review, and whole-column right-drag exclusion. Verify the displayed controls before the session because that GUI belongs to separate ongoing work. This experiment has not changed or launched it. Human annotations must be saved through the GUI into a new, versioned label destination; preserve existing labels and the frozen evaluation targets.

The next training target must use actual local drawn provenance for boundary positions and explicit local visibility states for per-boundary readability. Reviewed automatic lines, taper joins, ordering-displaced points, absent labels and unknown regions cannot become drawn boundary ground truth. Existing legacy surface-wide flags cannot recover missing stroke history. Reviewed visibility can support a separate visibility target without turning the automatic boundary into a position target.

Keep the original animal splits. Training-side annotations may support model fitting; the repeatedly inspected validation examples remain development diagnostics. Do not claim independent validation by relabelling these examples. After a small annotated pilot, audit known/unknown counts, visible versus unidentifiable balance, and endpoint support for every layer before specifying the next bounded model experiment. Final-test and repeatability data remain unopened.

A useful pilot outcome is paired evidence within the same A-line: ILM visible while a deeper boundary is explicitly unidentifiable, plus clear positive intervals for every surface. This directly addresses the useful coverage lost by whole-column rejection. Agreement on local visibility and faithful stroke provenance come before adding more threshold rules.
