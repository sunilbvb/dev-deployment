#!/bin/bash
# ===========================================================================
# iOS Deployment Utilities
# This file contains iOS-specific build and deployment automation functions.
# ===========================================================================

# Resolve directory of iOS scripts
resolve_ios_scripts_dir() {
    if [ -n "${MELOS_ROOT_PATH:-}" ] && [ -d "$MELOS_ROOT_PATH/developer-dashboard/features/deployment/scripts/ios" ]; then
        echo "$MELOS_ROOT_PATH/developer-dashboard/features/deployment/scripts/ios"
        return
    fi
    local git_root
    git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    if [ -n "$git_root" ] && [ -d "$git_root/developer-dashboard/features/deployment/scripts/ios" ]; then
        echo "$git_root/developer-dashboard/features/deployment/scripts/ios"
        return
    fi
    cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd
}
IOS_SCRIPT_DIR="$(resolve_ios_scripts_dir)"

resolve_json_utils_path() {
    local parent_dir
    parent_dir="$(cd "$IOS_SCRIPT_DIR/.." && pwd)"
    echo "$parent_dir/json_utils.sh"
}
JSON_UTILS_PATH="$(resolve_json_utils_path)"
CHAT_NOTIFY_PATH="$(dirname "$JSON_UTILS_PATH")/chat_notify.sh"

# Source sub-components
if [ -f "$IOS_SCRIPT_DIR/ios_diagnostics.sh" ]; then
    # shellcheck source=developer-dashboard/features/deployment/scripts/ios/ios_diagnostics.sh
    source "$IOS_SCRIPT_DIR/ios_diagnostics.sh"
fi

if [ -f "$IOS_SCRIPT_DIR/ios_build.sh" ]; then
    # shellcheck source=developer-dashboard/features/deployment/scripts/ios/ios_build.sh
    source "$IOS_SCRIPT_DIR/ios_build.sh"
fi

if [ -f "$IOS_SCRIPT_DIR/ios_upload.sh" ]; then
    # shellcheck source=developer-dashboard/features/deployment/scripts/ios/ios_upload.sh
    source "$IOS_SCRIPT_DIR/ios_upload.sh"
fi

#------------------------------------------------------------------------------
# flutterIosFlavor - Map env names to Flutter iOS scheme/flavor names.
#------------------------------------------------------------------------------
flutterIosFlavor() {
    local env_name="${1:-}"
    local app_name="${2:-}"
    # Fallback to default mapping
    case "$env_name" in
        dev) echo "dev" ;;
        qa) echo "qa" ;;
        prod) echo "prod" ;;
        *) echo "$env_name" ;;
    esac
}

#------------------------------------------------------------------------------
# findIpaFile - Locate built IPA files for deployment
#------------------------------------------------------------------------------
# shellcheck disable=SC2120
findIpaFile() {
    local search_dir="${1:-build/ios/ipa}"
    
    # Find the first IPA file in the specified directory
    local ipa_path
    ipa_path=$(find "$search_dir" -name '*.ipa' 2>/dev/null | head -n 1)
    
    # Error handling when no IPA found
    if [ -z "${ipa_path:-}" ] || [ ! -f "$ipa_path" ]; then
        print_ipa_not_found_error "$search_dir"
        return 1
    fi
    
    echo "$ipa_path"
}

#------------------------------------------------------------------------------
# buildAndUploadIOS - Complete iOS build and upload automation
#------------------------------------------------------------------------------
buildAndUploadIOS() {
    if [ "$#" -eq 0 ]; then
        print_build_upload_validation_error
        return 1
    fi

    local app_name secret_file env_name script_env build_command
    
    if [ "$#" -eq 1 ]; then
        local profile="${1:-}"
        app_name="$(getProfileValue "$profile" "app_name")"
        env_name="$(getProfileValue "$profile" "env_name")"
        secret_file="$(getProfileValue "$profile" "secret_file")"
    else
        app_name="${1:-}"
        secret_file="${2:-}"
        env_name="${secret_file%.json}"
    fi

    local tmp_json_utils="$JSON_UTILS_PATH"
    if [ -n "$app_name" ] && [ -n "$env_name" ] && [[ "$secret_file" != *.json ]] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        local resolved_secret
        resolved_secret="$(getProfileValueForApp "$app_name" "secret_file" "$env_name")"
        if [ -n "$resolved_secret" ] && [ "$resolved_secret" != "null" ]; then
            secret_file="$resolved_secret"
        else
            secret_file="${env_name}.json"
        fi
    fi
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$secret_file" ]; then
        print_build_upload_validation_error
        return 1
    fi

    script_env="$(melosScriptEnv "$env_name" "$app_name")"
    if [ "$#" -eq 1 ]; then
        build_command="$(getMelosScriptName "$app_name" "build" "$script_env" "ipa:raw")"
    else
        build_command="${3:-$(getMelosScriptName "$app_name" "build" "$script_env" "ipa:raw")}"
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Source utility functions with dynamic path resolution
    source "$JSON_UTILS_PATH"
    
    # Execute build command
    print_building_ios_ipa "$app_name" "$script_env"
    checkMelosScript "$build_command" || return 1
    melos run "$build_command"
    
    # Change to app directory
    cd "$MELOS_ROOT_PATH/apps/$app_name" || return 1
    
    # Extract Apple credentials from JSON
    print_extracting_apple_creds "$secret_file"
    APPLE_API_KEY="$(getValueByKey "APPLE_API_KEY" "env/$secret_file")"
    export APPLE_API_KEY
    APPLE_API_ISSUER="$(getValueByKey "APPLE_API_ISSUER" "env/$secret_file")"
    export APPLE_API_ISSUER

    # Resolve key path: prefer industry-standard locations before legacy workspace path.
    # Priority:
    #   1. APPLE_API_KEY_BASE64 already set (in-memory — no file needed; altool/notarytool reads it via APPLE_API_KEY_PATH env)
    #   2. ~/.appstoreconnect/private_keys/  (Apple's own recommended location)
    #   3. ~/.private_keys/                   (Apple secondary fallback)
    #   4. <workspace>/private_keys/          (legacy — kept for backward compat)
    local _std_key_path_1="$HOME/.appstoreconnect/private_keys/AuthKey_${APPLE_API_KEY}.p8"
    local _std_key_path_2="$HOME/.private_keys/AuthKey_${APPLE_API_KEY}.p8"
    local _legacy_key_path="$MELOS_ROOT_PATH/private_keys/AuthKey_${APPLE_API_KEY}.p8"

    if [ -n "${APPLE_API_KEY_BASE64:-}" ]; then
        # In-memory path: write key to standard location so altool/notarytool can find it
        mkdir -p "$HOME/.appstoreconnect/private_keys"
        echo "$APPLE_API_KEY_BASE64" | base64 -d > "$_std_key_path_1"
        chmod 600 "$_std_key_path_1"
        export APPLE_API_KEY_PATH="$_std_key_path_1"
    elif [ -f "$_std_key_path_1" ]; then
        export APPLE_API_KEY_PATH="$_std_key_path_1"
    elif [ -f "$_std_key_path_2" ]; then
        export APPLE_API_KEY_PATH="$_std_key_path_2"
    else
        export APPLE_API_KEY_PATH="$_legacy_key_path"
    fi
    
    # Debug output
    print_apple_creds_debug "${APPLE_API_KEY:-}" "${APPLE_API_ISSUER:-}" "${APPLE_API_KEY_PATH}"
    
    # Find built IPA file
    print_locating_ipa
    local raw_ipa_path
    raw_ipa_path="$(findIpaFile)" || exit 2
    IOS_IPA_PATH="$(pwd)/$raw_ipa_path"
    export IOS_IPA_PATH
    
    # Determine upload method based on app.
    # Reuses upload_via_fastlane/upload_via_altool (ios_upload.sh) rather than
    # duplicating the upload calls here - keeps the retry-on-transient-network-
    # error logic in _retryUpload (json_utils.sh) in one place for both callers
    # (this build+upload path, and the raw upload-only path in uploadIPARaw).
    if [ "${UPLOAD_TOOL:-fastlane}" = "altool" ]; then
        upload_via_altool "$IOS_IPA_PATH" "$APPLE_API_KEY" "$APPLE_API_ISSUER" || return 1
    else
        cd "$MELOS_ROOT_PATH" || return 1
        upload_via_fastlane "$env_name" || return 1
    fi
    
    print_ios_build_upload_success "$app_name"
}

#------------------------------------------------------------------------------
# buildIPA - Generic IPA build with chat notifications
#------------------------------------------------------------------------------
buildIPA() {
    if [ "$#" -eq 0 ]; then
        print_build_ipa_validation_error
        return 1
    fi

    local app_name env_name secret_file internal_test_app_id
    
    if [ "$#" -eq 1 ]; then
        local profile="${1:-}"
        app_name="$(getProfileValue "$profile" "app_name")"
        env_name="$(getProfileValue "$profile" "env_name")"
        secret_file="$(getProfileValue "$profile" "secret_file")"
        internal_test_app_id="$(getProfileValue "$profile" "internal_test_app_id")"
    else
        app_name="${1:-}"
        env_name="${2:-}"
        secret_file="${3:-}"
        internal_test_app_id="${4:-}"
    fi

    local tmp_json_utils="$JSON_UTILS_PATH"
    if [ -z "$secret_file" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        secret_file="$(getProfileValueForApp "$app_name" "secret_file" "$env_name")"
        if [ "$secret_file" = "null" ] || [ -z "$secret_file" ]; then
            secret_file="$env_name.json"
        fi
    fi
    if [ -z "$internal_test_app_id" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        internal_test_app_id="$(getProfileValueForApp "$app_name" "internal_test_app_id" "$env_name")"
    fi
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ] || [ -z "$secret_file" ]; then
        print_build_ipa_validation_error
        return 1
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Setup environment
    ROOT="${MELOS_ROOT_PATH:-}"
    if [ -z "$ROOT" ] || [ ! -d "$ROOT/apps/$app_name" ]; then ROOT="$(pwd)"; fi
    cd "$ROOT" || return 1
    
    # Source utility functions with dynamic path resolution
    source "$JSON_UTILS_PATH"
    
    # Export chat notification environment variables
    exportAppContents "$app_name" "$env_name" "$secret_file" "$internal_test_app_id"
    
    # Run the AAB build script with chat notifications
    local script_env target_script
    script_env="$(melosScriptEnv "$env_name" "$app_name")"
    target_script="$(getMelosScriptName "$app_name" "build" "$script_env" "ipa:raw")"
    checkMelosScript "$target_script" || return 1
    bash "$CHAT_NOTIFY_PATH" -- melos run "$target_script"
}

#------------------------------------------------------------------------------
# deployIPA - Generic IPA deploy with chat notifications
#------------------------------------------------------------------------------
deployIPA() {
    if [ "$#" -eq 0 ]; then
        print_deploy_ipa_validation_error
        return 1
    fi

    local app_name env_name secret_file internal_test_app_id
    
    if [ "$#" -eq 1 ]; then
        local profile="${1:-}"
        app_name="$(getProfileValue "$profile" "app_name")"
        env_name="$(getProfileValue "$profile" "env_name")"
        secret_file="$(getProfileValue "$profile" "secret_file")"
        internal_test_app_id="$(getProfileValue "$profile" "internal_test_app_id")"
    else
        app_name="${1:-}"
        env_name="${2:-}"
        secret_file="${3:-}"
        internal_test_app_id="${4:-}"
    fi

    local tmp_json_utils="$JSON_UTILS_PATH"
    if [ -z "$secret_file" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        secret_file="$(getProfileValueForApp "$app_name" "secret_file" "$env_name")"
        if [ "$secret_file" = "null" ] || [ -z "$secret_file" ]; then
            secret_file="$env_name.json"
        fi
    fi
    if [ -z "$internal_test_app_id" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        internal_test_app_id="$(getProfileValueForApp "$app_name" "internal_test_app_id" "$env_name")"
    fi
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ] || [ -z "$secret_file" ]; then
        print_deploy_ipa_validation_error
        return 1
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Setup environment
    ROOT="${MELOS_ROOT_PATH:-}"
    if [ -z "$ROOT" ] || [ ! -d "$ROOT/apps/$app_name" ]; then ROOT="$(pwd)"; fi
    cd "$ROOT" || return 1
    
    # Source utility functions with dynamic path resolution
    source "$JSON_UTILS_PATH"
    
    # Export chat notification environment variables
    exportAppContents "$app_name" "$env_name" "$secret_file" "$internal_test_app_id"
    
    # Run the IPA deploy script with chat notifications
    local script_env target_script
    script_env="$(melosScriptEnv "$env_name" "$app_name")"
    target_script="$(getMelosScriptName "$app_name" "deploy" "$script_env" "ipa:raw")"
    checkMelosScript "$target_script" || return 1
    bash "$CHAT_NOTIFY_PATH" -- melos run "$target_script"
}

#------------------------------------------------------------------------------
# uploadIPA - Generic IPA upload with chat notifications
#------------------------------------------------------------------------------
uploadIPA() {
    if [ "$#" -eq 0 ]; then
        print_upload_ipa_validation_error
        return 1
    fi

    local app_name env_name secret_file internal_test_app_id
    
    if [ "$#" -eq 1 ]; then
        local profile="${1:-}"
        app_name="$(getProfileValue "$profile" "app_name")"
        env_name="$(getProfileValue "$profile" "env_name")"
        secret_file="$(getProfileValue "$profile" "secret_file")"
        internal_test_app_id="$(getProfileValue "$profile" "internal_test_app_id")"
    else
        app_name="${1:-}"
        env_name="${2:-}"
        secret_file="${3:-}"
        internal_test_app_id="${4:-}"
    fi

    local tmp_json_utils="$JSON_UTILS_PATH"
    if [ -z "$secret_file" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        secret_file="$(getProfileValueForApp "$app_name" "secret_file" "$env_name")"
        if [ "$secret_file" = "null" ] || [ -z "$secret_file" ]; then
            secret_file="$env_name.json"
        fi
    fi
    if [ -z "$internal_test_app_id" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        internal_test_app_id="$(getProfileValueForApp "$app_name" "internal_test_app_id" "$env_name")"
    fi
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ] || [ -z "$secret_file" ]; then
        print_upload_ipa_validation_error
        return 1
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Setup environment
    ROOT="${MELOS_ROOT_PATH:-}"
    if [ -z "$ROOT" ] || [ ! -d "$ROOT/apps/$app_name" ]; then ROOT="$(pwd)"; fi
    cd "$ROOT" || return 1
    
    # Source utility functions with dynamic path resolution
    source "$JSON_UTILS_PATH"
    
    # Export chat notification environment variables
    exportAppContents "$app_name" "$env_name" "$secret_file" "$internal_test_app_id"
    
    # Run the IPA upload script with chat notifications
    local script_env target_script
    script_env="$(melosScriptEnv "$env_name" "$app_name")"
    target_script="$(getMelosScriptName "$app_name" "upload" "$script_env" "ipa:raw")"
    checkMelosScript "$target_script" || return 1
    bash "$CHAT_NOTIFY_PATH" -- melos run "$target_script"
}
