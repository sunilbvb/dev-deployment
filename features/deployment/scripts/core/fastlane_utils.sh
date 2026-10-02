#!/usr/bin/env bash
# ===========================================================================
# Fastlane Directory & Fastfile Locator
# ===========================================================================
set -euo pipefail

#------------------------------------------------------------------------------
# resolveDeploymentFastlaneDir - Locate the Fastlane folder owned by the deployment feature.
#------------------------------------------------------------------------------
resolveDeploymentFastlaneDir() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
    local fastlane_dir="$script_dir/../../fastlane"

    if [ -f "$fastlane_dir/Fastfile" ]; then
        echo "$fastlane_dir"
        return 0
    fi

    local root="${MELOS_ROOT_PATH:-}"
    if [ -n "$root" ] && [ -f "$root/developer-dashboard/features/deployment/fastlane/Fastfile" ]; then
        echo "$root/developer-dashboard/features/deployment/fastlane"
        return 0
    fi

    if [ -n "$root" ] && [ -f "$root/features/deployment/fastlane/Fastfile" ]; then
        echo "$root/features/deployment/fastlane"
        return 0
    fi

    echo "Error: Deployment Fastlane folder not found" >&2
    return 1
}

# Backward-compatible alias for older local scripts that may call this helper.
resolveDeploymentFastfile() {
    local fastlane_dir
    fastlane_dir="$(resolveDeploymentFastlaneDir)" || return 1
    echo "$fastlane_dir/Fastfile"
}
