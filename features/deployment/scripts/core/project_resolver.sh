#!/usr/bin/env bash
# ===========================================================================
# Project, App, Flavor & Environment Configuration Resolvers
# Resolves paths, JSON keys, package names, service accounts, and exports configs.
# ===========================================================================
set -euo pipefail

#------------------------------------------------------------------------------
# getValueByKey - Extract values from JSON files
#------------------------------------------------------------------------------
# USAGE: getValueByKey <key> <json_file>
#
# EXAMPLES:
#   getValueByKey "APPLE_API_KEY" "env/prod.json"
#   getValueByKey "BASE_URL" "env/dev.json"
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
        config_file="$root/developer-dashboard/features/deployment/scripts/core/build_profiles.json"
        if [ ! -f "$config_file" ]; then
            config_file="$root/developer-dashboard/features/deployment/scripts/build_profiles.json"
        fi
        if [ ! -f "$config_file" ]; then
            config_file="$root/features/deployment/scripts/core/build_profiles.json"
        fi
        if [ ! -f "$config_file" ]; then
            config_file="$root/features/deployment/scripts/build_profiles.json"
        fi
    fi
    local value=""
    if [ -f "$config_file" ]; then
        value="$(python3 -c "import json; print(json.load(open('$config_file')).get('$profile', {}).get('$key', ''))" 2>/dev/null || true)"
    fi
    if [ -z "$value" ]; then
        value="$(profileFallbackValue "$profile" "$key")"
    fi
    # app_name is read first by every profile-based entry point, so report an
    # unresolvable profile once here instead of letting a vague "must be
    # provided" error be the only hint.
    if [ -z "$value" ] && [ "$key" = "app_name" ]; then
        explainUnresolvedProfile "$profile" "$config_file" >&2
    fi
    echo "$value"
}

#------------------------------------------------------------------------------
# explainUnresolvedProfile - tell the user why <profile> could not be resolved
# and how to fix it.
#------------------------------------------------------------------------------
explainUnresolvedProfile() {
    local profile="$1" config_file="${2:-}"
    echo "Error: build profile '$profile' could not be resolved."
    if [ -z "$config_file" ] || [ ! -f "$config_file" ]; then
        echo "  - build_profiles.json was not found, so no profiles are defined."
    else
        echo "  - '$profile' is not defined in $config_file"
    fi
    case "$profile" in
        *_*) echo "  - '${profile%_*}' (from '<APP>_<ENV>') does not match an app folder in the current workspace." ;;
        *)   echo "  - The name is not in '<APP>_<ENV>' form (for example GYO_DEV), so no app could be derived." ;;
    esac
    echo "  Fix: select the right project in the console, add a '$profile' entry to build_profiles.json,"
    echo "       or call the command with explicit arguments (<app_name> <env_name> ...) instead of a profile name."
}

#------------------------------------------------------------------------------
# profileFallbackValue - derive profile values from a "<APP>_<ENV>" name (e.g.
# GYO_DEV) when it is not listed in build_profiles.json. The app must resolve
# to a real app folder in the workspace.
#------------------------------------------------------------------------------
profileFallbackValue() {
    local profile="$1" key="$2"
    case "$profile" in *_*) ;; *) return 0 ;; esac
    local app_part="${profile%_*}" env_name app_name
    env_name="$(echo "${profile##*_}" | tr '[:upper:]' '[:lower:]')"
    app_name="$(echo "$app_part" | tr '[:upper:]' '[:lower:]')"
    local app_dir root
    app_dir="$(resolveAppDir "$app_name")"
    root="${WORKSPACE_ROOT:-${MELOS_ROOT_PATH:-$(pwd)}}"
    # An unknown app id resolves to the workspace root itself; reject that.
    if [ ! -d "$app_dir" ] || [ "$(cd "$app_dir" && pwd -P)" = "$(cd "$root" && pwd -P)" ]; then
        return 0
    fi
    case "$key" in
        app_name)    echo "$app_name" ;;
        env_name)    echo "$env_name" ;;
        secret_file) echo "$env_name.json" ;;
    esac
}

#------------------------------------------------------------------------------
# resolveAppDir - absolute folder of <app_id>, wherever it lives in the
# workspace (apps/, packages/, nested folders, or the root itself).
#------------------------------------------------------------------------------
resolveAppDir() {
    local backend_dir root resolved
    backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../backend" >/dev/null 2>&1 && pwd)"
    root="${WORKSPACE_ROOT:-${MELOS_ROOT_PATH:-$(pwd)}}"
    resolved="$(WORKSPACE_ROOT="$root" "${DEPLOYMENT_PYTHON:-python3}" - "$backend_dir" "$1" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, sys.argv[1])
import config
print(config._resolve_app_dir(sys.argv[2]))
PY
)"
    # Never return empty: `cd ""` would silently stay in the current directory.
    echo "${resolved:-$root/apps/$1}"
}

#------------------------------------------------------------------------------
# resolveReleaseNotes - release notes per language for a build, as JSON
# ({"en-US": "...", "de-DE": "..."}; "{}" when there are none).
# USAGE: resolveReleaseNotes <app_id> <android|ios>
# Order: $RELEASE_NOTES_JSON (dashboard / API), $RELEASE_NOTES (plain text,
# first app language), then the app's fastlane metadata files.
#------------------------------------------------------------------------------
resolveReleaseNotes() {
    local backend_dir out
    backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../backend" >/dev/null 2>&1 && pwd)"
    out="$(WORKSPACE_ROOT="${WORKSPACE_ROOT:-${MELOS_ROOT_PATH:-$(pwd)}}" \
        "${DEPLOYMENT_PYTHON:-python3}" - "$backend_dir" "$(resolveAppDir "$1")" "$2" "$1" <<'PY' 2>/dev/null
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from metadata import release_notes
print(json.dumps(release_notes.resolve_notes_map(Path(sys.argv[2]), sys.argv[3], app_id=sys.argv[4]), ensure_ascii=False))
PY
)"
    echo "${out:-{\}}"
}

#------------------------------------------------------------------------------
# exportReleaseNotes - export RELEASE_NOTES_JSON for the upload step.
# Release notes are optional: with none, the upload simply goes without them.
# USAGE: exportReleaseNotes <app_id> <android|ios>
#------------------------------------------------------------------------------
exportReleaseNotes() {
    local notes_json
    notes_json="$(resolveReleaseNotes "$1" "$2")"
    if [ "$notes_json" = "{}" ]; then
        echo "ℹ️  No release notes for $1 ($2); uploading without them (add them in the dashboard to include them)."
    else
        echo "📝 Release notes ($(printf '%s' "$notes_json" | wc -c | tr -d ' ') bytes of JSON) will be sent with the $2 upload."
    fi
    export RELEASE_NOTES_JSON="$notes_json"
}

#------------------------------------------------------------------------------
# resolvePlayServiceAccount - Google Play service-account JSON for <app_id>.
# Order: $SERVICE_ACCOUNT_JSON, deploy config (per app, then global),
# then conventional locations in the workspace, app, and user config.
#------------------------------------------------------------------------------
resolvePlayServiceAccount() {
    local app_name="$1"
    if [ -n "${SERVICE_ACCOUNT_JSON:-}" ]; then
        echo "$SERVICE_ACCOUNT_JSON"
        return 0
    fi
    local root="${WORKSPACE_ROOT:-${MELOS_ROOT_PATH:-$(pwd)}}"
    local app_dir configured backend_dir
    app_dir="$(resolveAppDir "$app_name")"
    backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../backend" >/dev/null 2>&1 && pwd)"
    configured="$(WORKSPACE_ROOT="$root" "${DEPLOYMENT_PYTHON:-python3}" - "$backend_dir" "$app_name" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, sys.argv[1])
import config
cfg = config.load_deploy_config()
print(cfg.get("apps", {}).get(sys.argv[2], {}).get("play_service_account") or cfg.get("play_service_account") or "")
PY
)"
    local candidates=()
    if [ -n "$configured" ]; then
        [[ "$configured" = /* ]] && candidates+=("$configured") || candidates+=("$root/$configured")
    fi
    candidates+=(
        "$root/private_keys/play-store-deployer.json"
        "$app_dir/private_keys/play-store-deployer.json"
        "$app_dir/android/play-store-deployer.json"
        "$HOME/.config/dev-deployment/play-store-deployer.json"
    )
    local c
    for c in "${candidates[@]}"; do
        if [ -f "$c" ]; then
            echo "$c"
            return 0
        fi
    done
    echo "${candidates[0]}"
}

#------------------------------------------------------------------------------
# resolveAndroidPackageName - applicationId for <app_id> <flavor> from the
# workspace deploy config, falling back to the app's Gradle files.
#------------------------------------------------------------------------------
resolveAndroidPackageName() {
    local backend_dir
    backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../backend" >/dev/null 2>&1 && pwd)"
    WORKSPACE_ROOT="${WORKSPACE_ROOT:-${MELOS_ROOT_PATH:-$(pwd)}}" \
    "${DEPLOYMENT_PYTHON:-python3}" - "$backend_dir" "$1" "${2:-}" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, sys.argv[1])
import config
app_id, flavor = sys.argv[2], sys.argv[3] or "default"
saved = config.load_deploy_config().get("apps", {}).get(app_id, {})
scanned = config._scan_android_app_ids(config._resolve_app_dir(app_id))
# Flavor-specific IDs from any source first: a missing saved QA id must not fall
# back to the generic (prod) package while Gradle knows the real QA id.
for keys in ((f"android_id_{flavor}", f"android_package_{flavor}"),
             ("android_id_default", "android_id", "android_package")):
    if flavor not in ("default", "prod") and keys[0] == "android_id_default" and \
            any(k.startswith("android_") and k.endswith(("_dev", "_qa", "_staging", "_uat")) for k in {**saved, **scanned}):
        sys.exit(0)  # app has flavor IDs but none for this flavor: refuse to guess prod's
    for src in (saved, scanned):
        for key in keys:
            if src.get(key):
                print(src[key]); sys.exit(0)
PY
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
        config_file="$root/developer-dashboard/features/deployment/scripts/core/build_profiles.json"
        if [ ! -f "$config_file" ]; then
            config_file="$root/developer-dashboard/features/deployment/scripts/build_profiles.json"
        fi
        if [ ! -f "$config_file" ]; then
            config_file="$root/features/deployment/scripts/core/build_profiles.json"
        fi
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
    export APP_NAME="$app_name"
    export ENV_NAME="$env_name"
    export APP_DIR="$(resolveAppDir "$app_name")"
    export ENV_JSON="$APP_DIR/env/$secret_file"
    # A missing webhook is fatal only for apps that ship an env JSON (where it is
    # expected to live); apps without one just skip the chat card.
    if [ -z "${REQUIRE_CHAT_NOTIFY:-}" ]; then
        if [ -f "$ENV_JSON" ]; then export REQUIRE_CHAT_NOTIFY=1; else export REQUIRE_CHAT_NOTIFY=0; fi
    fi
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
