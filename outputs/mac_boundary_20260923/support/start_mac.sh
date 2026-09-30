#!/bin/bash
set -euo pipefail
PACKAGE="$(cd "$(dirname "$0")" && pwd)"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || {
    echo 'Run OPEN_BOUNDRY_REVIEWER_MAC.command on an Apple Silicon Mac.'; exit 1;
}
[[ -d "$PACKAGE/../For_Segmentation/Reviewed_Samples" ]] || {
    echo 'Missing For_Segmentation/Reviewed_Samples beside this package.'; exit 1;
}
TOOLS="$HOME/.octa-boundary-reviewer"
BASE="$TOOLS/miniforge-26.7.2-0"
ENVIRONMENT="$TOOLS/envs/mac-20260923/octa"
STATE="$HOME/Documents/OCTA_Boundary_Reviews/portable-20260923"
mkdir -p "$TOOLS/downloads" "$STATE/runtime/logs"
LOG="$STATE/runtime/logs/launch-$(date +%Y%m%d-%H%M%S)-$$.log"
exec > >(tee -a "$LOG") 2>&1
echo 'OCTA boundary reviewer - Apple Silicon Mac'
echo "Scan caches: $PACKAGE/../For_Segmentation"
echo "Saved Mac reviews: $STATE/Reviews"
echo "Launch log: $LOG"
echo 'The external drive and Windows installation are read only for this launcher.'

# Isolate from a system Python, Conda, Qt installation or Rosetta shell.
unset PYTHONHOME PYTHONPATH QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH QML2_IMPORT_PATH
unset QT_QPA_PLATFORM CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL CONDA_EXE
unset CONDA_PYTHON_EXE _CONDA_EXE _CONDA_ROOT CONDA_SUBDIR
export PATH='/usr/bin:/bin:/usr/sbin:/sbin'
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export MPLCONFIGDIR="$STATE/runtime/matplotlib"
export OCTA_MAC_STATE="$STATE"
mkdir -p "$MPLCONFIGDIR"

# Hold a PID lock only during setup. Never remove somebody else's live lock.
LOCK="$TOOLS/setup.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    owner="$(cat "$LOCK/pid" 2>/dev/null || true)"
    if [[ ! "$owner" =~ ^[0-9]+$ ]]; then
        echo "Setup lock is being initialized or needs inspection: $LOCK. Try again shortly."; exit 1
    fi
    if [[ "$owner" =~ ^[0-9]+$ ]] && kill -0 "$owner" 2>/dev/null; then
        echo "Another Mac setup is running (PID $owner). Let it finish."; exit 1
    fi
    echo "A previous setup was interrupted. Preserving its lock in $TOOLS."
    mv "$LOCK" "$TOOLS/setup.lock.interrupted-$(date +%Y%m%d-%H%M%S)-$$"
    mkdir "$LOCK"
fi
echo "$$" > "$LOCK/pid"
release_lock() { rm -f "$LOCK/pid"; rmdir "$LOCK"; }
trap release_lock EXIT

if [[ ! -f "$BASE/.octa-base-ready" ]]; then
    if [[ -e "$BASE" ]]; then
        mv "$BASE" "$BASE.interrupted-$(date +%Y%m%d-%H%M%S)-$$"
    fi
    INSTALLER="$TOOLS/downloads/Miniforge3-26.7.2-0-MacOSX-arm64.sh"
    SHA='d70bfa2e97afcda96927c9b9ca0e2316cb7750e4ce651c94388267cbe9588711'
    if [[ ! -f "$INSTALLER" ]] || [[ "$(shasum -a 256 "$INSTALLER" | awk '{print $1}')" != "$SHA" ]]; then
        echo '1/4 Downloading the Apple Silicon Python installer (first launch needs internet)...'
        curl --fail --location --retry 3 --connect-timeout 30 --progress-bar \
            'https://github.com/conda-forge/miniforge/releases/download/26.7.2-0/Miniforge3-26.7.2-0-MacOSX-arm64.sh' \
            --output "$INSTALLER.part"
        [[ "$(shasum -a 256 "$INSTALLER.part" | awk '{print $1}')" == "$SHA" ]] || {
            echo 'Installer checksum mismatch. Installation stopped.'; exit 1;
        }
        mv "$INSTALLER.part" "$INSTALLER"
    fi
    echo '1/4 Installing private Mac tools (no administrator password required)...'
    /bin/bash "$INSTALLER" -b -p "$BASE"
    touch "$BASE/.octa-base-ready"
fi
source "$BASE/etc/profile.d/conda.sh"
REQUIREMENTS_HASH="$(shasum -a 256 "$PACKAGE/requirements-mac.txt" | awk '{print $1}')"
if [[ ! -f "$ENVIRONMENT/.octa-ready" ]] || [[ "$(cat "$ENVIRONMENT/.octa-ready")" != "$REQUIREMENTS_HASH" ]]; then
    if [[ -d "$ENVIRONMENT" && ! -f "$ENVIRONMENT/conda-meta/history" ]]; then
        mv "$ENVIRONMENT" "$ENVIRONMENT.interrupted-$(date +%Y%m%d-%H%M%S)-$$"
    fi
    if [[ ! -f "$ENVIRONMENT/conda-meta/history" ]]; then
        echo '2/4 Installing native ARM64 Python 3.11 (first launch needs internet)...'
        CONDA_SUBDIR=osx-arm64 conda create --yes --prefix "$ENVIRONMENT" \
            --override-channels --channel conda-forge 'python=3.11' pip
    fi
    conda activate "$ENVIRONMENT"
    echo '3/4 Installing the reviewer libraries; download progress appears below...'
    python -m pip --isolated install --only-binary=:all: --index-url https://pypi.org/simple \
        --requirement "$PACKAGE/requirements-mac.txt"
    python -m pip check
    python "$PACKAGE/run_mac.py" --check-dependencies
    echo "$REQUIREMENTS_HASH" > "$ENVIRONMENT/.octa-ready"
else
    conda activate "$ENVIRONMENT"
    echo 'Using the installed Mac environment; no downloads needed.'
fi
release_lock
trap - EXIT
echo '4/4 Opening the reviewer. The first scan is checksum-verified as it loads.'
python "$PACKAGE/run_mac.py" "$@"
