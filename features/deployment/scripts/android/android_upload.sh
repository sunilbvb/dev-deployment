#!/usr/bin/env bash
# ===========================================================================
# Android Upload Automation
# This file contains Android deployment upload functions (runWithAndroidEnv,
# uploadAndroid, uploadAAB).
# ===========================================================================

#------------------------------------------------------------------------------
# runWithAndroidEnv - Execute commands with Android environment variables
#------------------------------------------------------------------------------
# USAGE: runWithAndroidEnv <command>
#
# EXAMPLES:
#   runWithAndroidEnv "cd '<deployment fastlane dir>' && bundle exec fastlane android upload_android track:internal"
#   runWithAndroidEnv "./gradlew assembleRelease"
#
# DESCRIPTION:
#   Executes a command with standard Android deployment environment variables.
#   Automatically passes SERVICE_ACCOUNT_JSON, ANDROID_AAB_PATH, and ANDROID_PACKAGE_NAME
#   to ensure the command receives required values.
#
# PARAMETERS:
#   $1 - command: The command to execute with Android environment variables
#
# RETURNS:
#   0 - Success: Command executed successfully
#   1 - Error: Command failed or required variables not set
#
# ENVIRONMENT VARIABLES USED:
#   - SERVICE_ACCOUNT_JSON: Path to Google Play service account JSON
#   - ANDROID_AAB_PATH: Path to AAB file
#   - ANDROID_PACKAGE_NAME: Package name for the app
#------------------------------------------------------------------------------
runWithAndroidEnv() {
    local -a cmd=("$@")
    if [ "${#cmd[@]}" -eq 0 ]; then
        echo "Error: Command must be provided"
        echo "Usage: runWithAndroidEnv <command>"
        return 1
    fi
    if [ "${#cmd[@]}" -eq 1 ] && [[ "${cmd[0]}" == *" "* ]]; then
        read -r -a cmd <<< "${cmd[0]}"
    fi

    local bundle_gemfile="${BUNDLE_GEMFILE:-}"
    if [ -z "$bundle_gemfile" ]; then
        local deployment_fastlane_dir_for_gemfile
        deployment_fastlane_dir_for_gemfile="$(resolveDeploymentFastlaneDir 2>/dev/null)" || true
        if [ -n "$deployment_fastlane_dir_for_gemfile" ] && [ -f "$deployment_fastlane_dir_for_gemfile/Gemfile" ]; then
            bundle_gemfile="$deployment_fastlane_dir_for_gemfile/Gemfile"
        elif [ -n "${MELOS_ROOT_PATH:-}" ] && [ -f "$MELOS_ROOT_PATH/Gemfile" ]; then
            bundle_gemfile="$MELOS_ROOT_PATH/Gemfile"
        fi
    fi
    
    local cmd_str="${cmd[*]}"
    if [[ "$cmd_str" == *"bundle exec"* ]]; then
        if ! BUNDLE_GEMFILE="$bundle_gemfile" bundle check >/dev/null 2>&1; then
            echo "Installing missing ruby gems (bundle install)..."
            BUNDLE_GEMFILE="$bundle_gemfile" bundle install || true
        fi
    fi

    # Check for required environment variables
    if [ -z "${SERVICE_ACCOUNT_JSON:-}" ]; then
        echo "Error: SERVICE_ACCOUNT_JSON not set"
        return 1
    fi
    
    # Execute command with environment variables
    FASTLANE_SKIP_UPDATE_CHECK=1 \
    FASTLANE_HIDE_CHANGELOG=1 \
    BUNDLE_GEMFILE="$bundle_gemfile" \
    SERVICE_ACCOUNT_JSON="$SERVICE_ACCOUNT_JSON" \
    ANDROID_AAB_PATH="${ANDROID_AAB_PATH:-}" \
    ANDROID_PACKAGE_NAME="${ANDROID_PACKAGE_NAME:-}" \
    "${cmd[@]}"
}

#------------------------------------------------------------------------------
# uploadAndroid - Upload Android AAB to Play Store
#------------------------------------------------------------------------------
# USAGE: uploadAndroid <app_name> <package_name>
#
# EXAMPLES:
#   uploadAndroid "sample_app" "com.example.sample_app"
#
# DESCRIPTION:
#   Uploads a pre-built Android AAB to Google Play Store.
#   Automatically locates the AAB file and sets up service account credentials.
#
# PARAMETERS:
#   $1 - app_name: The app name (e.g., "my_app", "store_app")
#   $2 - package_name: The Android package name for the app
#
# RETURNS:
#   0 - Success: AAB uploaded successfully
#   1 - Error: Missing parameters, file not found, or upload failed
#
# ERROR HANDLING:
#   - Validates required parameters
#   - Checks for service account file existence
#   - Verifies AAB file exists
#   - Provides clear error messages for debugging
#------------------------------------------------------------------------------
uploadAndroid() {
    local app_name package_name flavor=""

    if [ "$#" -eq 1 ]; then
        local profile="$1"
        app_name="$(getProfileValue "$profile" "app_name")"
        package_name="$(getProfileValue "$profile" "package_name")"
        if [ -z "$app_name" ] || [ "$app_name" = "null" ]; then
            # No bundled profile: treat APP_ID_FLAVOR (e.g. GYO_BUSINESS_QA) as app + flavor.
            local lower
            lower="$(printf '%s' "$profile" | tr '[:upper:]' '[:lower:]')"
            app_name="${lower%_*}"
            flavor="${lower##*_}"
            package_name="$(resolveAndroidPackageName "$app_name" "$flavor")"
            if [ -z "$package_name" ]; then
                app_name="$lower"
                flavor="default"
                package_name="$(resolveAndroidPackageName "$app_name" "$flavor")"
            fi
        fi
    else
        app_name="${1:-}"
        package_name="${2:-}"
        [[ "$package_name" != *.* ]] && flavor="$package_name"
    fi

    local tmp_json_utils="${JSON_UTILS_PATH:-}"
    if [ -n "$app_name" ] && [[ "$package_name" != com.* ]] && [ -n "$tmp_json_utils" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        local resolved_pkg
        resolved_pkg="$(getProfileValueForApp "$app_name" "package_name" "$package_name")"
        if [ -n "$resolved_pkg" ] && [ "$resolved_pkg" != "null" ]; then
            package_name="$resolved_pkg"
        fi
    fi
    if [ -n "$app_name" ] && [[ "$package_name" != *.* ]]; then
        package_name="$(resolveAndroidPackageName "$app_name" "${flavor:-default}")"
    fi

    # Validate parameters
    if [ -z "$app_name" ] || [ -z "$package_name" ]; then
        print_upload_android_validation_error
        return 1
    fi
    
    # Source utility functions with dynamic path resolution
    if [ -n "${JSON_UTILS_PATH:-}" ] && [ -f "$JSON_UTILS_PATH" ]; then
        source "$JSON_UTILS_PATH"
    fi
    
    # Setup service account JSON - use centralized workspace private_keys
    export SERVICE_ACCOUNT_JSON="$(resolvePlayServiceAccount "$app_name")"
    
    # Change to app directory
    cd "$(resolveAppDir "$app_name")" || return 1
    
    # Check if service account file exists
    if [ ! -f "$SERVICE_ACCOUNT_JSON" ]; then
        print_service_account_missing_error "$SERVICE_ACCOUNT_JSON" "$app_name"
        return 1
    fi
    
    # Find built AAB file using dedicated function
    echo "Locating AAB file..."
    local raw_aab_path
    raw_aab_path="$(findAabFile)" || return 1
    ANDROID_AAB_PATH="$(pwd)/$raw_aab_path"
    export ANDROID_AAB_PATH
    
    # Set package name
    export ANDROID_PACKAGE_NAME="$package_name"
    
    echo "Uploading to Play Store..."
    echo "Package: $ANDROID_PACKAGE_NAME"
    echo "AAB: $ANDROID_AAB_PATH"
    echo "Service Account: $SERVICE_ACCOUNT_JSON"
    
    # Change back to workspace root so Fastlane runs with workspace-local Gemfile/paths.
    cd "$MELOS_ROOT_PATH"
    local deployment_fastlane_dir
    deployment_fastlane_dir="$(resolveDeploymentFastlaneDir)" || return 1
    
    # Upload using Fastlane (retries a few times - Play Store's upload API can
    # also hit transient network errors on large files, same as iOS's Transporter)
    local -a cmd=(bundle exec fastlane android upload_android track:internal release_status:completed)
    if ! ( cd "$deployment_fastlane_dir" && _retryUpload "Play Store upload (Fastlane)" runWithAndroidEnv "${cmd[@]}" ); then
        print_play_store_upload_failed_error
        return 1
    fi
    
    echo "✅ Android upload completed for $app_name ($package_name)"
}

#------------------------------------------------------------------------------
# uploadAAB - Generic AAB upload with chat notifications
#------------------------------------------------------------------------------
# USAGE: uploadAAB <app_name> <env_name> [secret_file] [package_name] [internal_test_app_id]
#
# EXAMPLES:
#   uploadAAB "sample_app" "prod"
#   uploadAAB "sample_app" "prod" "prod.json" "com.example.sample_app" "123456789"
#
# This function:
#   - Sets up the environment for AAB upload
#   - Exports chat notification variables
#   - Runs the corresponding AAB upload script with notifications
#------------------------------------------------------------------------------
uploadAAB() {
    local app_name env_name secret_file package_name internal_test_app_id
    
    if [ "$#" -eq 1 ]; then
        local profile="$1"
        app_name="$(getProfileValue "$profile" "app_name")"
        env_name="$(getProfileValue "$profile" "env_name")"
        secret_file="$(getProfileValue "$profile" "secret_file")"
        package_name="$(getProfileValue "$profile" "package_name")"
        internal_test_app_id="$(getProfileValue "$profile" "internal_test_app_id")"
    else
        app_name="${1:-}"
        env_name="${2:-}"
        secret_file="${3:-}"
        package_name="${4:-}"
        internal_test_app_id="${5:-}"
    fi

    local tmp_json_utils="${JSON_UTILS_PATH:-}"
    if [ -n "$package_name" ] && [[ "$package_name" != com.* ]] && [ -z "$internal_test_app_id" ]; then
        internal_test_app_id="$package_name"
        package_name=""
    fi
    if [ -z "$secret_file" ] && [ -n "$tmp_json_utils" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        secret_file="$(getProfileValueForApp "$app_name" "secret_file" "$env_name")"
        if [ "$secret_file" = "null" ] || [ -z "$secret_file" ]; then
            secret_file="$env_name.json"
        fi
    fi
    if [ -z "$internal_test_app_id" ] && [ -n "$tmp_json_utils" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        internal_test_app_id="$(getProfileValueForApp "$app_name" "internal_test_app_id" "$env_name")"
    fi
    if [ -z "$package_name" ] && [ -n "$tmp_json_utils" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        package_name="$(getProfileValueForApp "$app_name" "package_name" "$env_name")"
    fi
    if [ -z "$package_name" ] || [ "$package_name" = "null" ]; then
        package_name="$(resolveAndroidPackageName "$app_name" "$env_name")"
    fi

    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ] || [ -z "$secret_file" ] || [ -z "$package_name" ]; then
        print_upload_aab_validation_error
        return 1
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Navigate to workspace root for centralized Fastlane
    cd "$MELOS_ROOT_PATH"
    
    # Setup service account JSON - use centralized workspace private_keys
    export SERVICE_ACCOUNT_JSON="$(resolvePlayServiceAccount "$app_name")"
    if [ ! -f "$SERVICE_ACCOUNT_JSON" ]; then
        print_service_account_missing_error "$SERVICE_ACCOUNT_JSON" "$app_name"
        return 1
    fi

    # Export chat notification environment variables
    exportAppContents "$app_name" "$env_name" "$secret_file" "$internal_test_app_id"
    
    # Locate AAB file (from app directory)
    cd "$(resolveAppDir "$app_name")" || return 1
    local raw_aab_path
    raw_aab_path="$(findAabFile)" || exit 2
    ANDROID_AAB_PATH="$(pwd)/$raw_aab_path"
    export ANDROID_AAB_PATH
    export ANDROID_PACKAGE_NAME="$package_name"
    
    # Change back to workspace root so Fastlane runs with workspace-local Gemfile/paths.
    cd "$MELOS_ROOT_PATH"
    local deployment_fastlane_dir
    deployment_fastlane_dir="$(resolveDeploymentFastlaneDir)" || return 1

    # Upload to Play Store using centralized Fastlane
    local -a cmd=(bundle exec fastlane android upload_android track:internal release_status:completed)
    if ! ( cd "$deployment_fastlane_dir" && _retryUpload "Play Store upload (Fastlane)" runWithAndroidEnv "${cmd[@]}" ); then
        print_play_store_upload_failed_error
        return 1
    fi
}
