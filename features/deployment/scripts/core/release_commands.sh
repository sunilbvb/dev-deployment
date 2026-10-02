#!/usr/bin/env bash
# ===========================================================================
# Release & Git Tag Utilities
# Wrappers for release_changelog_tagger.dart (Preview, Changelog, Commit, Tag, Push, Bump, Undo).
# ===========================================================================
set -euo pipefail

_resolve_release_script() {
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    if [ -f "$JSON_SCRIPT_DIR/release/release_changelog_tagger.dart" ]; then
        echo "$JSON_SCRIPT_DIR/release/release_changelog_tagger.dart"
    elif [ -f "$JSON_SCRIPT_DIR/release_changelog_tagger.dart" ]; then
        echo "$JSON_SCRIPT_DIR/release_changelog_tagger.dart"
    elif [ -f "$root/tool/scripts/release_changelog_tagger.dart" ]; then
        echo "$root/tool/scripts/release_changelog_tagger.dart"
    else
        echo "$JSON_SCRIPT_DIR/release/release_changelog_tagger.dart"
    fi
}

_is_flavor_arg() {
    case "${1:-}" in
        any|all|qa|test|dev|prod|production|staging|release|"") return 0 ;;
        *) return 1 ;;
    esac
}

# The release* functions' shared 2nd positional arg has historically doubled as
# either an explicit version string OR an environment/flavor keyword (dev/qa/...)
# forwarded straight from the dashboard's env selector. Split it into the right
# --version=/--flavor= CLI args for release_changelog_tagger.dart, populating the
# global _FLAVOR_VERSION_ARGS array.
_flavor_version_args() {
    local value="${1:-}"
    _FLAVOR_VERSION_ARGS=()
    if _is_flavor_arg "$value"; then
        case "$value" in
            ""|any|all) ;;
            *) _FLAVOR_VERSION_ARGS+=("--flavor=$value") ;;
        esac
    else
        _FLAVOR_VERSION_ARGS+=("--version=$value")
    fi
}

# Mode 1: Preview Only (Dry-run)
releasePreview() {
    local app_name="${1:-}"
    local flavor="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"

    if [ -z "$app_name" ]; then
        echo "❌ Error: App name required for releasePreview"
        return 1
    fi

    _flavor_version_args "$flavor"
    echo "🔍 [Mode 1: Preview] Previewing Release Changelog for '$app_name' (Workspace: $root)..."
    dart run "$script_path" "--workspace=$root" "--app=$app_name" "--mode=preview" "${_FLAVOR_VERSION_ARGS[@]-}"
}

# Mode 2: Update CHANGELOG.md only
releaseChangelog() {
    local app_name="${1:-}"
    local version="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"

    if [ -z "$app_name" ]; then
        echo "❌ Error: App name required for releaseChangelog"
        return 1
    fi

    _flavor_version_args "$version"
    local cmd_args=("--workspace=$root" "--app=$app_name" "--mode=changelog" "${_FLAVOR_VERSION_ARGS[@]-}")

    echo "📝 [Mode 2: Changelog Only] Updating CHANGELOG.md files for '$app_name' (Workspace: $root)..."
    dart run "$script_path" "${cmd_args[@]}"
}

# Mode 3: Update CHANGELOG.md + Git Commit
releaseCommit() {
    local app_name="${1:-}"
    local version="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"

    if [ -z "$app_name" ]; then
        echo "❌ Error: App name required for releaseCommit"
        return 1
    fi

    _flavor_version_args "$version"
    local cmd_args=("--workspace=$root" "--app=$app_name" "--mode=commit" "${_FLAVOR_VERSION_ARGS[@]-}")

    echo "💾 [Mode 3: Commit] Updating CHANGELOG.md & committing for '$app_name' (Workspace: $root)..."
    dart run "$script_path" "${cmd_args[@]}"
}

# Mode 4: Update CHANGELOG.md + Git Commit + Local Git Tag
releaseTag() {
    local app_name="${1:-}"
    local version="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"

    if [ -z "$app_name" ]; then
        echo "❌ Error: App name required for releaseTag"
        return 1
    fi

    _flavor_version_args "$version"
    local cmd_args=("--workspace=$root" "--app=$app_name" "--mode=tag" "${_FLAVOR_VERSION_ARGS[@]-}")

    echo "🏷️ [Mode 4: Local Tag] Generating changelog, commit, and local tag for '$app_name' (Workspace: $root)..."
    dart run "$script_path" "${cmd_args[@]}"
}

# Mode 5: Full Release (Changelog + Commit + Tag + Remote Push)
releasePush() {
    local app_name="${1:-}"
    local version="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"

    if [ -z "$app_name" ]; then
        echo "❌ Error: App name required for releasePush"
        return 1
    fi

    _flavor_version_args "$version"
    local cmd_args=("--workspace=$root" "--app=$app_name" "--mode=push" "${_FLAVOR_VERSION_ARGS[@]-}")

    echo "🚀 [Mode 5: Full Release] Releasing, tagging, and pushing to remote for '$app_name' (Workspace: $root)..."
    dart run "$script_path" "${cmd_args[@]}"
}

# Advanced Operation: Workspace Unreleased Status Report
releaseStatus() {
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"
    echo "📊 Running Monorepo Unreleased Status Report (Workspace: $root)..."
    dart run "$script_path" "--workspace=$root" "--status"
}

# Advanced Operation: SemVer Bump (Patch) & Tag
releaseBumpPatch() {
    local app_name="${1:-}"
    local flavor="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"
    if [ -z "$app_name" ]; then echo "❌ Error: App name required"; return 1; fi
    _flavor_version_args "$flavor"
    echo "📈 Auto-bumping PATCH version and tagging '$app_name' (Workspace: $root)..."
    dart run "$script_path" "--workspace=$root" "--app=$app_name" "--bump=patch" "--mode=tag" "${_FLAVOR_VERSION_ARGS[@]-}"
}

# Advanced Operation: SemVer Bump (Minor) & Tag
releaseBumpMinor() {
    local app_name="${1:-}"
    local flavor="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"
    if [ -z "$app_name" ]; then echo "❌ Error: App name required"; return 1; fi
    _flavor_version_args "$flavor"
    echo "📈 Auto-bumping MINOR version and tagging '$app_name' (Workspace: $root)..."
    dart run "$script_path" "--workspace=$root" "--app=$app_name" "--bump=minor" "--mode=tag" "${_FLAVOR_VERSION_ARGS[@]-}"
}

# Advanced Operation: SemVer Bump (Major) & Tag
releaseBumpMajor() {
    local app_name="${1:-}"
    local flavor="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"
    if [ -z "$app_name" ]; then echo "❌ Error: App name required"; return 1; fi
    _flavor_version_args "$flavor"
    echo "📈 Auto-bumping MAJOR version and tagging '$app_name' (Workspace: $root)..."
    dart run "$script_path" "--workspace=$root" "--app=$app_name" "--bump=major" "--mode=tag" "${_FLAVOR_VERSION_ARGS[@]-}"
}

# Advanced Operation: Store "What's New" Release Notes
releaseStoreNotes() {
    local app_name="${1:-}"
    local flavor="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"
    if [ -z "$app_name" ]; then echo "❌ Error: App name required"; return 1; fi
    _flavor_version_args "$flavor"
    echo "📱 Generating App Store / Play Store Release Notes for '$app_name' (Workspace: $root)..."
    dart run "$script_path" "--workspace=$root" "--app=$app_name" "--store" "--mode=preview" "${_FLAVOR_VERSION_ARGS[@]-}"
}

# Advanced Operation: Pre-flight Verification & Push
releaseVerify() {
    local app_name="${1:-}"
    local flavor="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"
    if [ -z "$app_name" ]; then echo "❌ Error: App name required"; return 1; fi
    _flavor_version_args "$flavor"
    echo "🩺 Verifying static analysis & tests, then full releasing '$app_name' (Workspace: $root)..."
    dart run "$script_path" "--workspace=$root" "--app=$app_name" "--verify" "--mode=push" "${_FLAVOR_VERSION_ARGS[@]-}"
}

# Advanced Operation: Rollback / Undo Tag
releaseUndo() {
    local app_name="${1:-}"
    local version="${2:-}"
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    local script_path="$(_resolve_release_script)"
    if [ -z "$app_name" ]; then echo "❌ Error: App name required"; return 1; fi
    _flavor_version_args "$version"
    local cmd_args=("--workspace=$root" "--app=$app_name" "--undo" "${_FLAVOR_VERSION_ARGS[@]-}")
    echo "⚠️ Rolling back release tag for '$app_name' (Workspace: $root)..."
    dart run "$script_path" "${cmd_args[@]}"
}

# Snake_case aliases for run_build.sh dispatch
release_preview() { releasePreview "$@"; }
release_changelog() { releaseChangelog "$@"; }
release_commit() { releaseCommit "$@"; }
release_tag() { releaseTag "$@"; }
release_push() { releasePush "$@"; }
release_status() { releaseStatus "$@"; }
release_bump_patch() { releaseBumpPatch "$@"; }
release_bump_minor() { releaseBumpMinor "$@"; }
release_bump_major() { releaseBumpMajor "$@"; }
release_store_notes() { releaseStoreNotes "$@"; }
release_verify() { releaseVerify "$@"; }
release_undo() { releaseUndo "$@"; }
