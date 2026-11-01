#!/usr/bin/env bash
# ===========================================================================
# Multiplatform Build & Deploy Orchestrator
# Bumps shared build number once and coordinates back-to-back Android & iOS deployments.
# ===========================================================================
set -euo pipefail

#------------------------------------------------------------------------------
# deployBothPlatforms - Build & upload Android AND iOS together, sharing ONE
# build-number bump instead of two.
# USAGE: deployBothPlatforms <app_name> <env_name>
#------------------------------------------------------------------------------
deployBothPlatforms() {
    local app_name="${1:-}"
    local env_name="${2:-}"

    if [ -z "$app_name" ] || [ -z "$env_name" ]; then
        echo "❌ Error: App name and environment required for deployBothPlatforms"
        echo "Usage: deployBothPlatforms <app_name> <env_name>"
        return 1
    fi

    set -euo pipefail

    local root="${MELOS_ROOT_PATH:-}"
    if [ -z "$root" ]; then root="$(pwd)"; fi
    local app_dir
    app_dir="$(resolveAppDir "$app_name")"

    echo "🚀 [Combined Deploy] Building & deploying Android + iOS together for '$app_name' ($env_name) — one shared build number for both."

    if [ "${SKIP_VERSION_BUMP:-false}" != "true" ]; then
        ( cd "$app_dir" && perl -i -pe 's/version: (\d+\.\d+\.\d+)(?:\+(\d+))?/ "version: $1+" . (($2 || 0) + 1) /e' pubspec.yaml )
    fi
    local shared_version
    shared_version="$(grep '^version:' "$app_dir/pubspec.yaml" | head -1 | sed -E 's/version:[[:space:]]*//')"
    echo "📌 Shared build version for both platforms: $shared_version"

    export SKIP_VERSION_BUMP=true

    echo ""
    echo "── Android ──────────────────────────────"
    local android_rc=0 ios_rc=0
    deployAAB "$app_name" "$env_name" || android_rc=$?
    if [ "$android_rc" -ne 0 ]; then
        echo "⚠️  Android deploy failed (exit $android_rc) - continuing with iOS so one store problem does not block the other."
    fi

    echo ""
    echo "── iOS ───────────────────────────────────"
    deployIPA "$app_name" "$env_name" || ios_rc=$?

    unset SKIP_VERSION_BUMP
    echo ""
    if [ "$android_rc" -ne 0 ] || [ "$ios_rc" -ne 0 ]; then
        echo "❌ Combined deploy finished with failures for '$app_name' ($env_name): Android exit=$android_rc, iOS exit=$ios_rc (build $shared_version)"
        return 1
    fi
    echo "✅ Combined deploy complete for '$app_name' ($env_name) — Android + iOS both shipped from build $shared_version"
}
