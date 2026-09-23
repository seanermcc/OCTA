#!/usr/bin/env python3
"""
Diagnose the Python environment before running the pipeline.

Run this whenever something says a package is missing that you believe you just
installed. It reports which interpreter is actually running, which conda
environment that corresponds to, and for each dependency whether it imports,
where it was imported from, and -- crucially -- the real error if it fails.

    python check_env.py
"""

from __future__ import annotations

import importlib
import os
import sys

REQUIRED = ["numpy", "h5py"]
OPTIONAL = ["scipy", "skimage", "matplotlib", "pandas"]
# Only `label_gui.py` needs these. `pack`, `refit`, `batch_segment.py` and
# `qc_vs_reference.py` all run headless, so a missing PySide6 blocks hand
# correction and nothing else.
GUI = ["PySide6"]


def report(name: str, required: bool) -> bool:
    try:
        m = importlib.import_module(name)
    except Exception as e:  # noqa: BLE001 - we want everything, incl. DLL errors
        tag = "MISSING" if required else "missing (optional)"
        print(f"  [{tag}] {name}")
        print(f"      {type(e).__name__}: {e}")
        if "DLL load failed" in str(e):
            print("      -> the package is installed but its native libraries "
                  "will not load;")
            print("         that is a broken environment, not a missing package.")
        return False
    ver = getattr(m, "__version__", "?")
    path = getattr(m, "__file__", "?")
    print(f"  [ok]      {name} {ver}")
    print(f"      {path}")
    return True


def main() -> int:
    print("interpreter")
    print(f"  executable : {sys.executable}")
    print(f"  version    : {sys.version.split()[0]}")
    print(f"  conda env  : {os.environ.get('CONDA_DEFAULT_ENV', '(none)')}")
    print(f"  conda path : {os.environ.get('CONDA_PREFIX', '(none)')}")

    in_env = os.environ.get("CONDA_PREFIX")
    if in_env and not sys.executable.lower().startswith(in_env.lower()):
        print("\n  !! WARNING: the active conda environment is not the interpreter")
        print("     that is running. 'conda install' is putting packages somewhere")
        print("     this python will never look. That alone explains a package")
        print("     that installs fine but imports as missing.")

    print("\nrequired")
    ok = all(report(n, True) for n in REQUIRED)
    print("\noptional (needed later, for segmentation and figures)")
    for n in OPTIONAL:
        report(n, False)

    print("\nhand correction (label_gui.py only; everything else is headless)")
    gui_ok = all(report(n, False) for n in GUI)
    if not gui_ok:
        print("      pip install PySide6")

    print()
    if ok:
        print("Environment looks good - export_sample.py should run.")
    else:
        print("Fix the MISSING entries above. If repairing this environment is")
        print("fiddly, a clean one is faster and cannot break suite2p:")
        print()
        print("  conda create -n octa -c conda-forge python=3.11 h5py numpy scipy \\")
        print("               scikit-image matplotlib pandas")
        print("  conda activate octa")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
