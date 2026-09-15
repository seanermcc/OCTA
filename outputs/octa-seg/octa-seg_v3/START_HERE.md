# octa-seg_v3 — independent boundary review

Open **OPEN_OCTA_SEG_V3.cmd** and enter your reviewer ID (`lead` is suggested
for the initial selection). New software, documents, review records, queues and
verification results live in this folder. Existing datasets are referenced in
place and existing human annotations remain read-only.

Read [TRAINING_PLAN.md](TRAINING_PLAN.md) for the 120-B-scan development/assessment
plan, independent shared review and the later training criteria.

## First session

1. Choose a volume from the dropdown or use Previous/Next Scan. The reviewer
   discovers the 314 completed cohort volumes, preferring the ten v2 providers
   where available. All 512 native B-scans can be browsed.
2. Select a boundary with 1–8, `[ ]`, or the boundary list. Clicking near a visible
   curve selects it when **Pick nearest visible boundary on click** is enabled.
   Left-click/drag immediately corrects it; there is no initial strip-marking mode.
3. Use **Draw as unreliable** in Boundary review: **ON** draws dashed uncertain
   best guesses; **OFF** draws solid reliable corrections. Only your exact stroke
   receives that judgment. Switching modes alone changes no labels. Software
   joins remain uncertain and are never manual evidence. The numeric range is
   used only by range actions, not by drawing. Model uncertainty is also dashed.
   Alt + right-drag still marks uncertainty without moving the boundary.
4. On the right, choose any applicable case categories: CNV, ONH, shadow/low
   signal/artifact, and clearly readable tissue. Mark **Especially ambiguous**
   for the hard subset and **For review** for any case to share, including controls.
5. Switch the tab **under the map** from En face to Thickness, then select a
   layer in the dropdown. This reuses the same navigator image. Click the map
   to navigate to its native B-scan/A-line. Thickness updates with your edits.

| Gesture | Action |
|---|---|
| Left-click / drag | Correct selected boundary |
| Shift + right-drag | Selected boundary not traceable |
| Alt + right-drag | Selected boundary unreliable |
| Ctrl + Shift + right-drag | Restore visibility only |
| Ctrl + Alt + right-drag | Restore reliability only |
| Shift + left-drag | Explicitly visible and reliable review |
| Right-drag | Exclude columns for every boundary |
| Ctrl + right-drag | Clear that image exclusion |
| Ctrl+Z / Ctrl+Y / Ctrl+S | Undo / redo / save |
| 1–8 or `[ ]` | Select boundary |
| Left/right arrow, comma/period, PgUp/PgDn | Previous/next B-scan |
| Wheel, middle-drag/Space, F | Zoom, pan, fit |
| U / E | Clear selected boundary state marks / clear image exclusions |

**Not traceable** describes image evidence. **Absent / interrupted** is a separate
explicit anatomical judgment with its own button. Restore it with **Clear
anatomical-absence mark**. Visibility restoration alone does not remove an
anatomical-absence decision.

## Independent colleagues’ review

Click **Export colleagues’ queue** after marking cases For review. The generated
manifest includes scan identities, B-scan indices, source/model identities and
data roles, but no lead traces, notes or ambiguity/category judgments. It is
written to `review_queues`; prior exports remain intact.

Colleagues on this workstation open **OPEN_SHARED_REVIEW.cmd** and enter their
own reviewer ID. Everyone sees the same frozen automatic starting model and
only their own corrections. Each ID has its own folder and a session lock to
prevent concurrent windows overwriting that person's work. Do not reuse `lead`
for a colleague. The queue starts up to five ambiguous and five other cases
with model overlays hidden. That mode is also available manually; overlay
exposure is recorded per stroke/review. Thickness is disabled while drawing blind.

This is a shared-workstation/filesystem workflow. The queue is not a self-contained
off-site data package: another computer needs the project runtime and referenced
image/prediction files. No files are uploaded or messages sent automatically.

## Saved data and display

* `reviewers/<id>/journals`: authoritative GUI-written events, native coordinates,
  reviewer/source/model identity, state judgments, case flags, timing and history.
* `reviewers/<id>/surface_labels`: compatibility records written through the
  established GUI/label writer. Training must use exact provenance and the v3
  journals, not every surface stored in an NPZ.
* `reviewers/<id>/surface_context` and `surface_history`: source/revision context
  and previous compatibility versions.
* `review_queues`: annotation-free independent review manifests.
* `tests`: synthetic verification records and read-only real-volume screenshots;
  never a training-label source.

Boundary events save immediately; navigation, periodic saving and closing flush
outstanding review time and notes. Undo/redo also saves and retains history.
Simply opening a case creates no human boundary label.

The position network remains the existing frozen model. V3 uses the v2 working
ILM/expanded-candidate policy on frozen raw predictions, with **no other
reviewer's saved positions or state overrides preloaded**. Saved vessel/CNV/ONH
masks are read-only visual context and are identified as manual/draft/automatic.
The saved model vessel inputs remain frozen when visual overlays are refreshed.

Thickness is the endpoint depth difference × 1.12 µm. Available layers are RNFL,
GCL, IPL, INL, OPL, photoreceptor composite, RPE, full retina, and inner retina.
It uses only currently reportable endpoints. Uncertain candidates, not-traceable
or absent boundaries, shadows, image exclusions and invalid geometry stay blank.
Maps are experimental, with no filling or smoothing. They intentionally use a
stricter policy than the separate octa-thick exploratory viewer.

The background reader keeps the current volume and attempts the next two. The
RAM budget is at most 3 GB or one quarter of available memory when opened;
large images fall back to read-only memory mapping. Status in the lower left
shows what is ready. Only read operations run in the preload worker.
