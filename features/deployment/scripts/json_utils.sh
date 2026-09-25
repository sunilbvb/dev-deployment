#!/bin/bash
# ===========================================================================
# Unified Deployment Utilities Hub
# This file contains platform-generic helper functions and automatically sources
# android_utils.sh and ios_utils.sh for Android and iOS-specific build workflows.
# ===========================================================================
# Ensure rbenv, CocoaPods, Dart, Melos, Flutter, and Homebrew binaries are in PATH
export PATH="$HOME/.rbenv/shims:$HOME/.rbenv/bin:$HOME/.rbenv/versions/3.2.0/bin:$HOME/.pub-cache/bin:$HOME/fvm/default/bin:$HOME/development/flutter/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

#------------------------------------------------------------------------------
# melosScriptEnv - Map env names to melos script naming.
#------------------------------------------------------------------------------
melosScriptEnv() {
    local env_name="${1:-}"
    local app_name="${2:-}"
    echo "$env_name"
}

#------------------------------------------------------------------------------
# checkMelosScript - Check if a melos script exists in the pubspec.yaml file.
#------------------------------------------------------------------------------
checkMelosScript() {
    local script_name="${1:-}"
    if [ -z "$script_name" ]; then
        return 0
    fi
    
    local root="${MELOS_ROOT_PATH:-}"
    if [ -z "$root" ]; then
        root="$(pwd | sed -E 's|/apps/[^/]+||' | sed -E 's|/packages/[^/]+||')"
    fi
    
    local pubspec_file="$root/pubspec.yaml"
    if [ ! -f "$pubspec_file" ]; then
        return 0
    fi
    
    if ! grep -q "^[[:space:]]*${script_name}:[[:space:]]*$" "$pubspec_file"; then
        echo "================================================================================"
        echo "❌ ERROR: Melos script '${script_name}' could not be found in pubspec.yaml."
        echo "Please verify the script name or regenerate your workspace scripts using:"
        echo "  dart developer-dashboard/features/deployment/melos/merge_scripts.dart"
        echo "================================================================================"
        return 1
    fi
    return 0
}

#------------------------------------------------------------------------------
# getMelosScriptName - Resolves the actual Melos script name, handling apps 
# with and without flavor suffixes (e.g., app:deploy:prod:ipa:raw vs app:deploy:ipa:raw).
#------------------------------------------------------------------------------
getMelosScriptName() {
    local app_name="$1"
    local action="$2" # build / deploy / upload
    local env_name="$3" # prod / dev / test
    local format="$4" # ipa:raw / aab:raw / aab / etc.
    
    local root="${MELOS_ROOT_PATH:-}"
    if [ -z "$root" ]; then
        root="$(pwd | sed -E 's|/apps/[^/]+||' | sed -E 's|/packages/[^/]+||')"
    fi
    
    local pubspec_file="$root/pubspec.yaml"
    
    # 1. Try script name WITH the environment name (e.g., app:deploy:prod:ipa:raw)
    local script_with_env="$app_name:$action:$env_name:$format"
    if [ -f "$pubspec_file" ] && grep -q "^[[:space:]]*${script_with_env}:[[:space:]]*$" "$pubspec_file"; then
        echo "$script_with_env"
        return 0
    fi
    
    # 2. Try script name WITHOUT the environment name (e.g., app:deploy:ipa:raw)
    local script_without_env="$app_name:$action:$format"
    if [ -f "$pubspec_file" ] && grep -q "^[[:space:]]*${script_without_env}:[[:space:]]*$" "$pubspec_file"; then
        echo "$script_without_env"
        return 0
    fi
    
    # Fallback to the one with env name if neither/both not found, to let checkMelosScript handle the error output
    echo "$script_with_env"
}

#------------------------------------------------------------------------------
# resolveDeploymentFastlaneDir - Locate the Fastlane folder owned by the deployment feature.
#------------------------------------------------------------------------------
resolveDeploymentFastlaneDir() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
    local fastlane_dir="$script_dir/../fastlane"

    if [ -f "$fastlane_dir/Fastfile" ]; then
        echo "$fastlane_dir"
        return 0
    fi

    local root="${MELOS_ROOT_PATH:-}"
    if [ -n "$root" ] && [ -f "$root/developer-dashboard/features/deployment/fastlane/Fastfile" ]; then
        echo "$root/developer-dashboard/features/deployment/fastlane"
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

#------------------------------------------------------------------------------
# getValueByKey - Extract values from JSON files
#------------------------------------------------------------------------------
# USAGE: getValueByKey <key> <json_file>
#
# EXAMPLES:
#   getValueByKey "APPLE_API_KEY" "env/prod.json"
#   getValueByKey "BASE_URL" "env/dev.json"
#
# DESCRIPTION:
#   Extracts the value for a given key from a JSON file using sed regex.
#   Handles whitespace, quotes, and carriage returns automatically.
#
# PARAMETERS:
#   $1 - key: The JSON key to search for (string)
#   $2 - json_file: Path to the JSON file (string)
#
# RETURNS:
#   0 - Success: Prints the extracted value
#   1 - Error: Prints error message and returns non-zero exit code
#
# ERROR HANDLING:
#   - Validates both parameters are provided
#   - Checks if JSON file exists
#   - Returns empty string if key not found
#------------------------------------------------------------------------------
getValueByKey() {
    local key="$1"
    local json_file="$2"
    
    # Parameter validation
    if [ -z "$key" ] || [ -z "$json_file" ]; then
        echo "Error: Both key and json_file must be provided"
        echo "Usage: getValueByKey <key> <json_file>"
        return 1
    fi
    
    # File existence check
    if [ ! -f "$json_file" ]; then
        echo "Error: JSON file '$json_file' not found"
        return 1
    fi
    
    # Extract value using sed regex
    # Pattern matches: "key": "value" (with optional whitespace)
    sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$json_file" | tr -d '\r' | xargs
}

#------------------------------------------------------------------------------
# get_deploy_config_val - Extract configurations dynamically from deploy_config.json
#------------------------------------------------------------------------------
get_deploy_config_val() {
    local app_name="$1"
    local key="$2"
    local root="${MELOS_ROOT_PATH:-}"
    if [ -z "$root" ]; then
        root="$(pwd | sed -E 's|/apps/[^/]+||' | sed -E 's|/packages/[^/]+||')"
    fi
    local config_file="$root/.dev-dashboard/deploy_config.json"
    if [ ! -f "$config_file" ]; then
        echo ""
        return 0
    fi
    python3 -c "
import json
try:
    data = json.load(open('$config_file'))
    print(data.get('apps', {}).get('$app_name', {}).get('$key', ''))
except Exception:
    pass
"
}

#------------------------------------------------------------------------------
# getProfileValue - Extract profile values from build_profiles.json
#------------------------------------------------------------------------------
# USAGE: getProfileValue <profile_name> <key>
#
# EXAMPLES:
#   getProfileValue "APP_PROD" "app_name"
#   getProfileValue "APP_DEV" "secret_file"
#------------------------------------------------------------------------------
getProfileValue() {
    local profile="$1"
    local key="$2"
    
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
    local config_file="$script_dir/build_profiles.json"
    if [ ! -f "$config_file" ] && [ -n "${JSON_UTILS_PATH:-}" ]; then
        config_file="$(dirname "$JSON_UTILS_PATH")/build_profiles.json"
    fi
    if [ ! -f "$config_file" ]; then
        local root="${MELOS_ROOT_PATH:-}"
        if [ -z "$root" ]; then
            root="$(pwd | sed -E 's|/apps/[^/]+||' | sed -E 's|/packages/[^/]+||')"
        fi
        config_file="$root/developer-dashboard/features/deployment/scripts/build_profiles.json"
        if [ ! -f "$config_file" ]; then
            config_file="$root/features/deployment/scripts/build_profiles.json"
        fi
    fi
    if [ ! -f "$config_file" ]; then
        return 1
    fi
    
    python3 -c "import json; print(json.load(open('$config_file')).get('$profile', {}).get('$key', ''))" 2>/dev/null
}

#------------------------------------------------------------------------------
# getProfileValueForApp - Finds first profile for an app and extracts its value
#------------------------------------------------------------------------------
getProfileValueForApp() {
    local app_name="$1"
    local key="$2"
    local env_name="${3:-}"
    
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
    local config_file="$script_dir/build_profiles.json"
    if [ ! -f "$config_file" ] && [ -n "${JSON_UTILS_PATH:-}" ]; then
        config_file="$(dirname "$JSON_UTILS_PATH")/build_profiles.json"
    fi
    if [ ! -f "$config_file" ]; then
        local root="${MELOS_ROOT_PATH:-}"
        if [ -z "$root" ]; then
            root="$(pwd | sed -E 's|/apps/[^/]+||' | sed -E 's|/packages/[^/]+||')"
        fi
        config_file="$root/developer-dashboard/features/deployment/scripts/build_profiles.json"
        if [ ! -f "$config_file" ]; then
            config_file="$root/features/deployment/scripts/build_profiles.json"
        fi
    fi
    if [ ! -f "$config_file" ]; then
        return 1
    fi
    
    python3 -c "
import json
data = json.load(open('$config_file'))
found = False
# 1. Match both app_name and env_name
for prof, val in data.items():
    if val.get('app_name') == '$app_name' and val.get('env_name') == '$env_name':
        print(val.get('$key', ''))
        found = True
        break
# 2. Fallback to flavorless app config (env_name = 'null')
if not found:
    for prof, val in data.items():
        if val.get('app_name') == '$app_name' and val.get('env_name') == 'null':
            print(val.get('$key', ''))
            found = True
            break
# 3. Fallback to first profile with app_name
if not found:
    for prof, val in data.items():
        if val.get('app_name') == '$app_name':
            print(val.get('$key', ''))
            break
" 2>/dev/null
}

#------------------------------------------------------------------------------
# logEnvironmentConfig - Log build configuration details with masked secrets
#------------------------------------------------------------------------------
logEnvironmentConfig() {
    local secret_file="$1"
    
    if [ ! -f "env/$secret_file" ]; then
        return 0
    fi
    
    echo "=========================================================="
    echo "  BUILD ENVIRONMENT DIAGNOSTICS"
    echo "  Config File: env/$secret_file"
    echo "=========================================================="
    
    local keys=("ENV" "APP_NAME" "BASE_URL" "BASE_DEEP_LINK_URL" "DDL_LINK" "APP_STORE_ID" "IAP_ENTITLEMENT_ID" "GOOGLE_MAPS_KEY" "APPLE_API_KEY" "APPLE_API_ISSUER" "APPSFLYER_DEV_KEY" "FACEBOOK_CLIENT_TOKEN" "IAP_IOS_KEY" "IAP_ANDROID_KEY")
    
    for key in "${keys[@]}"; do
        local val
        val="$(getValueByKey "$key" "env/$secret_file")"
        if [ -n "$val" ]; then
            # Mask sensitive values
            if [ "$key" = "GOOGLE_MAPS_KEY" ] || [ "$key" = "APPLE_API_KEY" ] || [ "$key" = "APPLE_API_ISSUER" ] || [ "$key" = "APPSFLYER_DEV_KEY" ] || [ "$key" = "FACEBOOK_CLIENT_TOKEN" ] || [[ "$key" == *"KEY"* ]] || [[ "$key" == *"TOKEN"* ]]; then
                local len=${#val}
                if [ $len -gt 5 ]; then
                    local prefix="${val:0:5}"
                    echo "  $key: $prefix********"
                else
                    echo "  $key: ********"
                fi
            else
                echo "  $key: $val"
            fi
        fi
    done
    echo "=========================================================="
}

#------------------------------------------------------------------------------
# exportAppContents - Export chat notification environment variables
#------------------------------------------------------------------------------
# USAGE: exportAppContents <app_name> <env_name> <secret_file> <internal_test_app_id>
#
# EXAMPLES:
#   exportAppContents "my_app" "qa" "qa.json" "1234567890"
#   exportAppContents "my_app" "prod" "env.json" "1234567890"
#
# ENVIRONMENT VARIABLES SET:
#   - REQUIRE_CHAT_NOTIFY: Set to 1 to enable chat notifications
#   - APP_NAME: Application name for notifications
#   - ENV_NAME: Environment name for notifications
#   - ENV_JSON: Path to environment JSON file
#   - DOWNLOAD_URL: Play Store internal test URL
#------------------------------------------------------------------------------
exportAppContents() {
    local app_name="$1"
    local env_name="$2"
    local secret_file="$3"
    local internal_test_app_id="${4:-}"
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ] || [ -z "$secret_file" ]; then
        echo "Usage: exportAppContents <app_name> <env_name> <secret_file> [internal_test_app_id]"
        echo "Example: exportAppContents \"sample_app\" \"qa\" \"qa.json\" \"123456789\""
        return 1
    fi
    
    # Export chat notification environment variables
    export REQUIRE_CHAT_NOTIFY=1
    export APP_NAME="$app_name"
    export ENV_NAME="$env_name"
    export ENV_JSON="apps/$app_name/env/$secret_file"
    if [ -n "$internal_test_app_id" ]; then
        export DOWNLOAD_URL="https://play.google.com/apps/internaltest/$internal_test_app_id"
    else
        export DOWNLOAD_URL=""
    fi
    
    echo "Chat notification variables exported:"
    echo "  APP_NAME: $APP_NAME"
    echo "  ENV_NAME: $ENV_NAME"
    echo "  ENV_JSON: $ENV_JSON"
    echo "  DOWNLOAD_URL: $DOWNLOAD_URL"
}

#------------------------------------------------------------------------------
# _retryUpload - Run a store-upload command (via runWithIosEnv/runWithAndroidEnv),
# retrying a few times on failure.
#------------------------------------------------------------------------------
# Apple's Transporter (used by both `fastlane upload_to_testflight` and
# `xcrun altool`) and Google Play's upload API are both known to intermittently
# fail large multi-part uploads with transient network errors (e.g. "The
# network connection was lost", NSURLErrorDomain -1005) that usually succeed
# on a plain retry. The build/archive step that precedes this can take many
# minutes; failing the whole pipeline for a few-second network blip on the
# very last step is wasteful, so this wraps just the upload call.
#
# DUPLICATE-VERSION SHORT-CIRCUIT
# ---------------------------------------------------------------------------
# The flip side of "the upload API is flaky" is a known FALSE NEGATIVE: the
# multipart upload actually lands on Apple's/Google's servers, but the client
# (altool/Transporter, or fastlane's Play Developer API call) still reports
# failure. A retry after that doesn't see a network error - it sees a hard,
# permanent rejection, because Apple/Google already have this exact
# build/version. Burning the remaining attempts against a guaranteed-to-fail
# duplicate-version rejection wastes ~5s per remaining attempt and ends in a
# scary "FAILED after N attempt(s)" message for something that is already
# fine - the actually-desired end state (this build is live on the store) is
# already true. So: after EVERY failed attempt we grep that attempt's own
# captured output for known duplicate-version signatures from both stores;
# on a match we stop retrying immediately and return success (exit 0).
#
# USAGE: _retryUpload <description> <runner_function_name> <command_string> [max_attempts]
#   description        - human-readable label for log lines, e.g. "TestFlight upload (Fastlane)"
#   runner_function_name - "runWithIosEnv" or "runWithAndroidEnv"
#   command_string     - the command to hand to that runner
#   max_attempts        - optional, default 3
#------------------------------------------------------------------------------
_retryUpload() {
    local description="$1"
    local runner="$2"
    local command="$3"
    local max_attempts="${4:-3}"
    local attempt=1

    # Fixed phrases/codes (matched case-insensitively, one line at a time)
    # that mean "this is not transient - Apple/Google are telling us this
    # exact build/version already made it to the store". Each entry below is
    # independently sourced (not guessed) - see docs/README.md for the
    # exact fastlane issues / Apple docs each one comes from. Extend this
    # list if a new real-world phrasing turns up.
    local -a duplicate_version_patterns=(
        # iOS / altool / Transporter / App Store Connect API.
        # HTTP 409, code ENTITY_ERROR.ATTRIBUTE.INVALID.DUPLICATE, underlying
        # error -19232. (matches the exact text seen in production; also see
        # fastlane issue #29741, Apple Developer Forums thread 693838.)
        "must be higher than the previously uploaded version"
        "ENTITY_ERROR\.ATTRIBUTE\.INVALID\.DUPLICATE"
        # iOS - distinct phrasing for the same underlying condition (same
        # build number reused), reported as ITMS-90189 "Redundant Binary
        # Upload". (fastlane issue #7429.)
        "redundant binary upload"
        "ITMS-90189"
        # Android / fastlane `upload_android` /`upload_to_play_store`
        # (Google Play Developer API via `supply`). Reason code
        # apkNotificationMessageKeyUpgradeVersionConflict, message "APK
        # specifies a version code that has already been used." Google's
        # message text has been observed to still say "APK" even for an AAB
        # upload (legacy wording), so we match the tail of the phrase rather
        # than anchoring on APK/AAB. (fastlane issues #16331, #21642, #15936.)
        "apkNotificationMessageKeyUpgradeVersionConflict"
        "specifies a version code that has already been used"
        "version code [0-9]+ has already been used"
    )

    while [ "$attempt" -le "$max_attempts" ]; do
        if [ "$attempt" -gt 1 ]; then
            echo "🔁 Retrying $description (attempt $attempt/$max_attempts)..."
            sleep 5
        fi

        # Stream live (unchanged - a human watching a 20-minute build still
        # sees real-time progress via `tee`) while also capturing this
        # attempt's combined stdout+stderr to a scratch file we can grep
        # afterward. A plain `output=$(...)` would fully buffer and break
        # live streaming, which is why this uses a pipe instead.
        local log_file
        log_file="$(mktemp "${TMPDIR:-/tmp}/retry_upload.XXXXXX")"

        # We read the runner's REAL exit code from ${PIPESTATUS[0]} - bash
        # always populates this per-pipeline-stage array, regardless of
        # whether `set -o pipefail` is active - rather than trusting the
        # pipeline's own $?, which without pipefail would just be tee's exit
        # code (nearly always 0) and would silently hide a real failure.
        #
        # Several sibling functions sourced into this same shell (buildAABRaw,
        # deployAAB, uploadAAB, buildAndUploadAndroid, deployBothPlatforms)
        # run `set -euo pipefail`, and that state is shell-global once
        # sourced, not scoped to this function - so we can't assume pipefail
        # is on or off here. If it happens to be ambiently ON and the runner
        # fails, this bare pipeline statement would otherwise trigger
        # `errexit` and abort the whole script before we get to inspect the
        # exit code or grep the log - so we temporarily disable -e around
        # just this one statement and restore it right after, leaving no net
        # change to the caller's error-handling once we return.
        local had_errexit=0
        case "$-" in *e*) had_errexit=1 ;; esac
        set +e

        # Wall-clock cap per attempt. Real-world cause this exists for: Ruby's
        # Net::HTTP (what fastlane/googleauth use) has no Happy-Eyeballs-style
        # dual-stack fallback - on a network where IPv6 is routed but silently
        # black-holed, it can sit for many minutes waiting out a TCP-level
        # timeout on an IPv6 attempt before ever trying IPv4, even though a
        # plain `curl` to the same host succeeds instantly. Without a cap here,
        # that shows up as a deploy job stuck indefinitely with no progress,
        # discoverable only by a human noticing and hitting Stop. `timeout`/
        # `gtimeout` aren't guaranteed present on macOS, so this is done with
        # a background job-control group + watchdog instead.
        local timeout_seconds="${UPLOAD_ATTEMPT_TIMEOUT_SECONDS:-300}"
        local rc_file
        rc_file="$(mktemp "${TMPDIR:-/tmp}/retry_upload_rc.XXXXXX")"
        local had_monitor=0
        case "$-" in *m*) had_monitor=1 ;; esac
        set -m

        ( "$runner" "$command" 2>&1 | tee "$log_file"; echo "${PIPESTATUS[0]}" > "$rc_file" ) &
        local pipe_pid=$!
        local pgid
        pgid="$(ps -o pgid= -p "$pipe_pid" 2>/dev/null | tr -d ' ')"

        (
            sleep "$timeout_seconds"
            if kill -0 "$pipe_pid" 2>/dev/null; then
                echo "⏱️  $description: no progress after ${timeout_seconds}s - assuming a hung network call, not a real long-running upload. Terminating this attempt so a retry can run." >> "$log_file"
                [ -n "$pgid" ] && kill -TERM -- "-$pgid" 2>/dev/null
                sleep 2
                [ -n "$pgid" ] && kill -KILL -- "-$pgid" 2>/dev/null
            fi
        ) &
        local watchdog_pid=$!

        wait "$pipe_pid" 2>/dev/null
        kill "$watchdog_pid" 2>/dev/null
        wait "$watchdog_pid" 2>/dev/null
        [ "$had_monitor" -eq 0 ] && set +m

        local rc
        rc="$(cat "$rc_file" 2>/dev/null)"
        [ -z "$rc" ] && rc=124   # killed by the watchdog before it could record its own exit code
        rm -f "$rc_file"

        [ "$had_errexit" -eq 1 ] && set -e

        if [ "$rc" -eq 0 ]; then
            rm -f "$log_file"
            return 0
        fi

        local pattern
        for pattern in "${duplicate_version_patterns[@]}"; do
            if grep -qiE "$pattern" "$log_file"; then
                echo "ℹ️  $description: Apple/Google rejected this as a duplicate build/version - it was already uploaded successfully in a prior run, no action needed."
                rm -f "$log_file"
                return 0
            fi
        done

        rm -f "$log_file"
        attempt=$((attempt + 1))
    done

    echo "❌ $description failed after $max_attempts attempt(s)."
    return 1
}

# =============================================================================
# Release & Git Tag Utilities (5 Modes)
# =============================================================================
_resolve_release_script() {
    local root="${MELOS_ROOT_PATH:-$(pwd)}"
    if [ -f "$JSON_SCRIPT_DIR/release_changelog_tagger.dart" ]; then
        echo "$JSON_SCRIPT_DIR/release_changelog_tagger.dart"
    elif [ -f "$root/tool/scripts/release_changelog_tagger.dart" ]; then
        echo "$root/tool/scripts/release_changelog_tagger.dart"
    else
        echo "$JSON_SCRIPT_DIR/release_changelog_tagger.dart"
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
# global _FLAVOR_VERSION_ARGS array. "any"/"all"/empty produce no args at all —
# that's the default, unsuffixed/primary release (also what apps with only one
# flavor, or none configured, should always resolve to).
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

# =============================================================================
# Source platform-specific utilities
# =============================================================================
resolve_scripts_dir() {
    cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd
}
JSON_SCRIPT_DIR="$(resolve_scripts_dir)"

# shellcheck source=developer-dashboard/features/deployment/scripts/android/android_utils.sh
source "$JSON_SCRIPT_DIR/android/android_utils.sh"
# shellcheck source=developer-dashboard/features/deployment/scripts/ios/ios_utils.sh
source "$JSON_SCRIPT_DIR/ios/ios_utils.sh"

#------------------------------------------------------------------------------
# deployBothPlatforms - Build & upload Android AND iOS together, sharing ONE
# build-number bump instead of two.
#------------------------------------------------------------------------------
# USAGE: deployBothPlatforms <app_name> <env_name>
#
# EXAMPLES:
#   deployBothPlatforms "sample_app" "prod"
#   deployBothPlatforms "sample_app" "qa"
#
# DESCRIPTION:
#   buildAABRaw (android/android_utils.sh) and buildIPARaw (ios/ios_build.sh)
#   each independently bump the SAME apps/<app>/pubspec.yaml version+build
#   number (gated by SKIP_VERSION_BUMP) when run alone. Running an Android
#   deploy then an iOS deploy back-to-back would therefore bump it TWICE,
#   leaving the two platforms shipped under different build numbers for what
#   is supposed to be the same release. This function bumps it exactly ONCE
#   up front, then sets SKIP_VERSION_BUMP=true so both platform builds below
#   build against that same, already-bumped version.
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
    if [ -z "$root" ] || [ ! -d "$root/apps/$app_name" ]; then root="$(pwd)"; fi

    echo "🚀 [Combined Deploy] Building & deploying Android + iOS together for '$app_name' ($env_name) — one shared build number for both."

    if [ "${SKIP_VERSION_BUMP:-false}" != "true" ]; then
        ( cd "$root/apps/$app_name" && perl -i -pe 's/version: (\d+\.\d+\.\d+)(?:\+(\d+))?/ "version: $1+" . (($2 || 0) + 1) /e' pubspec.yaml )
    fi
    local shared_version
    shared_version="$(grep '^version:' "$root/apps/$app_name/pubspec.yaml" | head -1 | sed -E 's/version:[[:space:]]*//')"
    echo "📌 Shared build version for both platforms: $shared_version"

    export SKIP_VERSION_BUMP=true

    echo ""
    echo "── Android ──────────────────────────────"
    deployAAB "$app_name" "$env_name"

    echo ""
    echo "── iOS ───────────────────────────────────"
    deployIPA "$app_name" "$env_name"

    unset SKIP_VERSION_BUMP
    echo ""
    echo "✅ Combined deploy complete for '$app_name' ($env_name) — Android + iOS both shipped from build $shared_version"
}
