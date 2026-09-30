#!/bin/bash
# CNV-Core / Full-CNV release 2026-09-29. Apple Silicon launcher. The spelling matches the requested main-folder name.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ "$(uname -s)" != Darwin ]]; then
    echo 'This launcher requires macOS on Apple Silicon. Use the Windows .cmd on Windows.'
    exit 1
fi
if [[ "$(uname -m)" != arm64 ]]; then
    if [[ "$(/usr/sbin/sysctl -in hw.optional.arm64 2>/dev/null || true)" == 1 ]]; then
        exec /usr/bin/arch -arm64 /bin/bash "$0" "$@"
    fi
    echo 'This package requires an Apple Silicon Mac (M1 or newer).'
    exit 1
fi
if [[ ! -f "$HERE/Mac_Boundary_Reviewer/start_mac.sh" ]]; then
    # Also supports the executable ZIP launcher extracted onto the Mac desktop.
    HERE="$(/usr/bin/osascript -e 'POSIX path of (choose folder with prompt "Select the octa folder containing Mac_Boundary_Reviewer and For_Segmentation")')" || exit 1
    if [[ ! -f "$HERE/Mac_Boundary_Reviewer/start_mac.sh" ]]; then
        echo 'The selected folder does not contain Mac_Boundary_Reviewer.'
        read -r -p 'Press Return to close. ' || true
        exit 1
    fi
fi
/bin/bash "$HERE/Mac_Boundary_Reviewer/start_mac.sh" "$@" || {
    result=$?
    echo "Reviewer did not finish successfully (exit $result). See the message above."
    read -r -p 'Press Return to close. ' || true
    exit "$result"
}
