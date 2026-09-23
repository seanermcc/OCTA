# Portable octa-seg_v3 reviewer

Double-click **OPEN_REVIEWER.cmd**. This is your **lead** continuation copy.
Contains 14 acquisitions / 21 confirmed B-scans, plus other saved work in these acquisitions.
All cached B-scans remain available. Original human journals and labels are copied unchanged.
No RAW or processed MAT source files are required. Keep this entire folder together when moving it.
Predictions, cache geometry and calibration are hash-checked. Source paths in records identify provenance only.
CNV/vessel/ONH overlays are frozen at 2026-09-23 10:06:59; Refresh reloads that snapshot.
Experimental ONH proposals are not included. This package is not a live link to the home data.

## On a new Windows computer

Install Miniconda if needed. In its prompt, run:

```
conda create -n octa python=3.11 pip
conda activate octa
cd /d "H:\octa\For_Segmentation"
python -m pip install -r requirements-reviewer.txt
OPEN_REVIEWER.cmd
```

Use the actual folder path if the drive letter differs. Installing dependencies needs internet once.
The Python environment is not bundled. If Anaconda is in an unusual location, activate octa first,
or set OCTA_CONDA_ACTIVATE to its Scripts\activate.bat path.

## Saving and returning work

Work saves locally under `outputs/octa-seg/octa-seg_v3/review/reviewers/lead/`.
Close the reviewer before copying. Return that entire folder, including journals/history and surface_labels.
Do not edit the same lead case on home and portable copies concurrently or blindly overwrite a newer copy.
This package includes your answers: prepare a separate annotation-free assignment before giving it to a coworker.
The nine sharing flags remain unchanged; inclusion here does not flag additional cases for colleagues.

## Validation

See PORTABLE_VALIDATION.json and PORTABLE_CACHE.json for executed checks and the exact inventory.
