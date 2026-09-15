# OCTA models: overview and demonstration guide

Prepared September 15, 2026, from the saved local release reports and completion records.

## Start here tomorrow

**Project folder: `G:\OCT_TreeShrew\octa`**

Double-click **SHOW_MODELS.cmd** for a numbered menu. It opens the existing
applications and saved predictions; selecting a demo does not start training.
The editing GUIs save real work when you draw, rate, or review. Browse without
editing during a presentation unless you intend to create review evidence.

From **Anaconda Prompt** (these commands use CMD syntax):

```bat
conda activate octa
cd /d G:\OCT_TreeShrew\octa
SHOW_MODELS.cmd --check
SHOW_MODELS.cmd
```

You can also choose directly: `SHOW_MODELS.cmd 1` opens layer v3,
`SHOW_MODELS.cmd 3` opens CNV v6, and `SHOW_MODELS.cmd 5` opens the vessel comparison.
In PowerShell use `Set-Location G:\OCT_TreeShrew\octa` and ` .\SHOW_MODELS.cmd`.

## High-level summary for a meeting

We have three related tools: tracing retinal layers, suggesting CNV lesion
footprints, and identifying major vessels and the optic nerve head (ONH).
Layer positions also support exploratory thickness maps. Each tool links
automatic output to visual review, with human decisions recorded separately.
These remain research tools; completion of a processing batch does not establish
accuracy on new animals.

| Release | What it is and does | Current interpretation |
|---|---|---|
| **octa-seg v1** | Learned eight-boundary position model plus separate traceability/reliability judgments. Produces saved curves, uncertain candidates and experimental thickness inputs. | Completed 314-volume batch. Learned reporting states failed the release's animal-excluded validation; availability is not validated accuracy. |
| **octa-seg v2** | Focused boundary-review workflow over the same frozen weights. Adds a working solid ILM, more dashed candidates, regional unreliability, and separate position approval versus measurability decisions. | Ten complete volumes / 5,120 B-scans. Initial feedback was insufficient for a new trained release. No demonstrated learned improvement over v1. |
| **octa-seg v3** | Current independent-review editor: direct boundary drawing, reliable/unreliable strokes, separate anatomical absence, per-reviewer records, shared case queues, and linked thickness maps. | Same frozen position model and v2 working policy. Browses 314 acquisitions, preferring v2 providers for ten. This is an annotation/workflow advance, with future model training planned. |
| **CNV U-Net v6** | Learned two-dimensional lesion suggestions from structural OCT and real OCTA projections, optionally adding availability, shadow and numerical thickness maps. Reviewer compares B/C predictions and seeds alongside native B-scans. | 324 acquisitions / 11 animals / 1,944 B/C predictions completed. Training evidence is a within-TS267 pilot; cohort inference is not cross-animal validation. |
| **Major-vessel v1 + vessel/ONH v1 editor** | Frozen contrast/shape method proposes major vessel masks. Separate editor corrects vessels and draws/reviews ONH, with independent target completion and uncertainty. | Working baseline for continued correction. ONH in this baseline is human annotation, not an automatic ONH detector. The flagged editing queue contains 85 scans. |
| **Vessel/ONH v2** | New compact U-Net learns two masks directly from structural en-face images: vessels and ONH. Separate animal-held-out models evaluate development performance; another model supplies final predictions. | 312 predictions plus two excluded scans in the 314-scan selection. Keep as an experimental comparison: the release explicitly advises against replacing v1 because of background/border false positives and poor partial-ONH detection. |
| **octa-thick v1** | Interactive map/point viewer measuring distances between saved layer endpoints, in micrometres. Shows the matching B-scan and supports exports. | Exploratory analysis software, not another trained model. Uses a more permissive saved-position policy than v3's in-editor maps; the two displays need not have identical coverage. |

The older `outputs\segment_v2` and `outputs\segment_v3` folders are historical
classical segmentation outputs. They are **different versions/families** from
`outputs\octa-seg\octa-seg_v2` and `octa-seg_v3` above.

### CNV v6: what B versus C means

- **A:** structural OCT + actual OCTA, two input channels; retained in the pilot.
- **B:** A + eight automatic thickness-availability maps + a shadow map, 11 channels.
- **C:** B + eight numerical thickness maps, 19 channels.
- Each has seeds 267, 268 and 269: three training initializations, not three
  independent biological studies. The full-cohort review compares the six B/C models.

On the same three later-visit TS267 holdout scans, mean Dice overlap across
seeds was A **0.678**, B **0.584**, C **0.733**. C recovered all six held-out
lesion entries in each seed, but still generated false suggestions and needed
outline corrections. This is six repeatedly evaluated lesion entries in the
same animal, not evidence of generalization to other animals. Scores are
uncalibrated; missing thickness is not healthy tissue or zero thickness.
See [the v6 report](outputs/octa-auto_cnv_unet_v6/START_HERE.md).

### Vessel/ONH v2: why a better score did not make it the preferred model

Animal-balanced vessel Dice improved from **35.1% to 69.7%**, but scoring covered
only **7.6% of the reviewed image area**, concentrated on brush edits. That does
not measure complete-image vessel precision or recall. ONH positive-case Dice
was **49.8%**, with false detections in **9/16** reviewed-absence cases.
The release's visual review found additional background and border predictions.
Show this as an instructive experimental result, not an established improvement.
See [the v2 release decision](outputs/octo-vessel_onh_v2/START_HERE.md).

## Exact folders and original launchers

All folders below are under **`G:\OCT_TreeShrew\octa\`**. Paste the complete
path into File Explorer, then double-click the named file. Several original
launchers assume Anaconda at `D:\Anaconda`; the new root menu also supports an
already activated `octa` environment on another computer.

| What to open | Folder on the drive | Original file / root menu choice |
|---|---|---|
| Current layer editor | `G:\OCT_TreeShrew\octa\outputs\octa-seg\octa-seg_v3` | `OPEN_OCTA_SEG_V3.cmd` / **1** |
| Previous layer editor | `G:\OCT_TreeShrew\octa\outputs\octa-seg\octa-seg_v2` | `OPEN_OCTA_SEG_V2.cmd` / **2** |
| Current CNV B/C reviewer | `G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_unet_v6\review` | `OPEN_CNV_REVIEW.cmd` / **3** |
| Vessel/ONH correction | `G:\OCT_TreeShrew\octa\outputs\octo-vessel_onh_v1` | `OPEN_REVIEW.cmd` / **4** |
| Learned vessel/ONH comparison | `G:\OCT_TreeShrew\octa\outputs\octo-vessel_onh_v2` | `OPEN_GALLERY.cmd` or `index.html` / **5** |
| Full-batch thickness viewer | `G:\OCT_TreeShrew\octa\outputs\octa-thick_v1` | `octa-thick_batch_v1.cmd` / **6**; root menu bypasses this older launcher's different Anaconda path |
| CNV six-model offline comparison | `G:\OCT_TreeShrew\octa\outputs\octa-auto_cnv_unet_v6\all_samples\comparison` | `index.html` / **7** |
| Frozen vessel baseline gallery | `G:\OCT_TreeShrew\octa\outputs\octa-vessel_seg_v1-batch` | `index.html` |
| TS267/TS328 longitudinal thickness | `G:\OCT_TreeShrew\octa\outputs\octa-thick_v1` | `OPEN_LONGITUDINAL_THICK_v1.cmd` or `OPEN_LONGITUDINAL_THICK_v2.cmd` |

The root menu does not retrain anything. For deliberate processing later:
CNV v6 `RUN_PILOT.cmd` reproduces/resumes the pilot and
`all_samples\RUN_ALL.cmd` resumes cohort inference; vessel v2
`RUN_OR_RESUME.cmd` resumes its matching stages. These require local training
inputs/checkpoints and the appropriate numerical/GPU environment. They are
unnecessary for the saved-result demonstration.

## Suggested 10-minute demonstration

1. **Layer v3 (3 minutes):** enter your own reviewer ID, select a readable
   scan and a CNV scan, move through B-scans, and switch En face to Thickness.
   Explain solid/dashed boundaries and why unavailable measurements stay blank.
   This shows the current review workflow; avoid presenting v3 as retrained weights.
2. **CNV v6 (3 minutes):** choose an acquisition, seed 267, and **B vs C at
   this seed**. Show original orange suggestions and linked native B-scans.
   Magenta means disagreement, not correctness. Ratings are about original
   outputs; leave them unset during browsing.
3. **Vessels/ONH (2 minutes):** open the v2 gallery, compare v1 versus final
   automatic output, and show both an appealing example and a failure. Explain
   why the sparse-label accuracy gain did not justify replacing v1.
4. **Thickness (2 minutes):** select a layer and click a map point to show
   its matching B-scan/endpoints. Explain that full retina is ILM to the outer
   RPE edge; the photoreceptor composite includes ONL, and isolated ONL is not
   available from these eight-boundary exports.

## Work-computer preparation

**Bring/connect the actual OCT_TreeShrew hard drive. GitHub alone is insufficient.**
The applications reference saved caches, predictions, JSON manifests, model
files and sometimes processed `.mat` volumes at absolute paths. Preserve the
whole local project `octa` and the sibling `OCTA_RawData` dataset structure.
Do not copy only a launcher or a shared-review queue. Prefer mounting the
drive at **G:** as on this workstation; a different letter requires deliberate
path updates in referenced manifests, not just changing the starting directory.

1. Have a Windows `octa` conda environment available with Python 3.11, NumPy,
   SciPy, h5py, scikit-image, matplotlib, pandas and PySide6. PyTorch is needed
   for learning/inference and some implementation tools. Activate the environment
   before running Python; calling its executable directly can fail to load DLLs.
2. If Anaconda is installed elsewhere, open that computer's Anaconda Prompt,
   run `conda activate octa`, then the root menu. Alternatively set
   `OCTA_CONDA_ACTIVATE` to that installation's `Scripts\activate.bat`.
   Installing packages on the work computer is a separate setup step; this guide
   does not assume the existing workstation environment is portable by copying it.
3. Run `SHOW_MODELS.cmd --check`, then actually open each intended demonstration
   before the meeting. The check tests runtime imports and entry-file presence,
   not every referenced data file. First image loading can take longer than
   switching between prefetched scans. Close other large applications.
4. **Python-free backup:** double-click the vessel v2 `index.html` and CNV v6
   `all_samples\comparison\index.html` directly. Keep their adjacent data/assets
   folders intact. These saved browser galleries do not require model inference
   or an internet connection. They do not provide the native editing GUIs.

The current workstation passed the core/Qt environment check. The different
work computer has not been tested in this session.

## Other recent CNV stages and analysis tools

| Item | Short description | Where to start under `outputs` |
|---|---|---|
| CNV v1 | Early thickness-deficit/background-reference candidate pilot. | `octa-auto_cnv_v1\START_HERE.md`; `OPEN_OCTA_AUTO_CNV_V1.cmd` |
| CNV v2 | Integrated evidence/lesion review; more proposals and substantial false-suggestion burden. | `octa-auto_cnv_v2\START_HERE.md`; `OPEN_OCTA_AUTO_CNV_V2.cmd` |
| CNV v3 | Stricter structural/shape heuristic reduced 220 proposals to 29 in 17 TS267 acquisitions. | `octa-auto_cnv_v3\START_HERE.md`; `OPEN_OCTA_AUTO_CNV_V3.cmd` |
| CNV v4 | Manual footprint painting and revision workflow over saved proposals. | `octa-auto_cnv_v4\START_HERE.md`; `OPEN_MANUAL_REVIEW.cmd` |
| CNV v5 | Simplified lesion editor with actual OCTA, optional thickness, and explicit whole-field review semantics; supplied training evidence for v6. | `octa-auto_cnv_v5\START_HERE.md`; `OPEN_OCTA_AUTO_CNV_V5.cmd` |
| CNV analysis v1 | Manual-mask spatial/longitudinal analyses using exploratory thickness. | `octa-seg\octa-seg_v1\cnv_analysis_v1\START_HERE.md` |
| Control map v1 | Preliminary per-eye and animal-balanced ONH atlas, with vessel registration of repeated tissue. | `octa-seg\octa-seg_v1\control_map_v1\README.md` |

## Source reports

- [Layer v2](outputs/octa-seg/octa-seg_v2/START_HERE.md), [layer v3](outputs/octa-seg/octa-seg_v3/START_HERE.md), [v3 implementation checks](outputs/octa-seg/octa-seg_v3/IMPLEMENTATION.md).
- [CNV v6 full cohort](outputs/octa-auto_cnv_unet_v6/all_samples/START_HERE.md), [current reviewer](outputs/octa-auto_cnv_unet_v6/review/START_HERE.md).
- [Vessel/ONH v1](outputs/octo-vessel_onh_v1/README.md), [vessel/ONH v2](outputs/octo-vessel_onh_v2/START_HERE.md).
- [Thickness viewer](outputs/octa-thick_v1/START_HERE.md): its opening September 10 update supersedes the historical policy description farther down the file.

Git preserves code, launchers and text reports. Existing tracked vessel-gallery
artifacts are preserved at their relocated path. Newly generated arrays, model
checkpoints and human annotations remain excluded from Git and available only
on the local dataset drive.
