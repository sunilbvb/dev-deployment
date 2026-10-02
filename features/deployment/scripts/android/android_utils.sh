#!/bin/bash
# ===========================================================================
# Android Deployment Utilities Hub
# This file serves as the coordinator hub for Android automation.
# Slices build, upload, and diagnostics into dedicated single-responsibility scripts.
# ===========================================================================

resolve_android_scripts_dir() {
    if [ -n "${MELOS_ROOT_PATH:-}" ] && [ -d "$MELOS_ROOT_PATH/developer-dashboard/features/deployment/scripts/android" ]; then
        echo "$MELOS_ROOT_PATH/developer-dashboard/features/deployment/scripts/android"
        return
    fi
    local git_root
    git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    if [ -n "$git_root" ] && [ -d "$git_root/developer-dashboard/features/deployment/scripts/android" ]; then
        echo "$git_root/developer-dashboard/features/deployment/scripts/android"
        return
    fi
    cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd
}
ANDROID_SCRIPT_DIR="$(resolve_android_scripts_dir)"

resolve_json_utils_path() {
    local parent_dir
    parent_dir="$(cd "$ANDROID_SCRIPT_DIR/.." && pwd)"
    echo "$parent_dir/json_utils.sh"
}
JSON_UTILS_PATH="$(resolve_json_utils_path)"
CHAT_NOTIFY_PATH="$(dirname "$JSON_UTILS_PATH")/chat_notify.sh"

# Source sub-components
if [ -f "$ANDROID_SCRIPT_DIR/android_diagnostics.sh" ]; then
    # shellcheck source=developer-dashboard/features/deployment/scripts/android/android_diagnostics.sh
    source "$ANDROID_SCRIPT_DIR/android_diagnostics.sh"
fi

if [ -f "$ANDROID_SCRIPT_DIR/android_build.sh" ]; then
    # shellcheck source=developer-dashboard/features/deployment/scripts/android/android_build.sh
    source "$ANDROID_SCRIPT_DIR/android_build.sh"
fi

if [ -f "$ANDROID_SCRIPT_DIR/android_upload.sh" ]; then
    # shellcheck source=developer-dashboard/features/deployment/scripts/android/android_upload.sh
    source "$ANDROID_SCRIPT_DIR/android_upload.sh"
fi

#------------------------------------------------------------------------------
# flutterAndroidFlavor - Map env names to Flutter Android flavors.
#
# Android flavors are lowercase: dev / qa / prod.
#------------------------------------------------------------------------------
flutterAndroidFlavor() {
    local env_name="${1:-}"
    case "$env_name" in
        dev|qa|prod) echo "$env_name" ;;
        *) echo "$env_name" ;;
    esac
}

#------------------------------------------------------------------------------
# findAabFile - Locate built AAB files for deployment
#------------------------------------------------------------------------------
# USAGE: findAabFile [search_directory]
#
# EXAMPLES:
#   findAabFile                    # Uses default: build/app/outputs/bundle
#   findAabFile "custom/path"      # Uses custom directory
#
# DESCRIPTION:
#   Finds the first .aab file in the specified directory.
#   Defaults to build/app/outputs/bundle since all Flutter Android builds use this path.
#
# PARAMETERS:
#   $1 - search_directory: Optional custom directory path (string)
#                          Defaults to "build/app/outputs/bundle" if not provided
#
# RETURNS:
#   0 - Success: Prints the full path to the found AAB file
#   1 - Error: Prints error message and available AAB files
#
# ERROR HANDLING:
#   - Shows searched directory when file not found
#   - Lists all available AAB files in build directory
#   - Provides helpful error messages for debugging
#------------------------------------------------------------------------------
# shellcheck disable=SC2120
findAabFile() {
    local search_dir="${1:-build/app/outputs/bundle}"
    
    # Find the first AAB file in the specified directory
    local aab_path
    aab_path=$(find "$search_dir" -name '*.aab' 2>/dev/null | head -n 1)
    
    # Error handling when no AAB found
    if [ -z "${aab_path:-}" ] || [ ! -f "$aab_path" ]; then
        print_aab_not_found_error "$search_dir"
        return 1
    fi
    
    echo "$aab_path"
}

#------------------------------------------------------------------------------
# buildAndUploadAndroid - Complete Android build and upload automation
#------------------------------------------------------------------------------
# USAGE: buildAndUploadAndroid <app_name> <flavor> [secret_file] [build_command]
#
# EXAMPLES:
#   buildAndUploadAndroid "my_app" "dev" "dev.json"
#   buildAndUploadAndroid "my_app" "prod" "env.json"
#
# DESCRIPTION:
#   Performs complete Android build and upload automation for any app.
#   Handles Flutter build, AAB finding, service account setup, and Fastlane upload.
#
# PARAMETERS:
#   $1 - app_name: Name of the app (e.g., "my_app", "store_app")
#   $2 - flavor: Build flavor (e.g., "dev", "qa", "prod")
#   $3 - secret_file: Optional JSON file containing service account (defaults to "env.json")
#   $4 - build_command: Optional custom build command (defaults to "<app>:build:aab:raw")
#
# RETURNS:
#   0 - Success: Build and upload completed successfully
#   1 - Error: Build or upload failed, or invalid parameters
#
# ENVIRONMENT VARIABLES SET:
#   - SERVICE_ACCOUNT_JSON: Path to Google Play service account JSON
#   - ANDROID_AAB_PATH: Path to built AAB file
#   - ANDROID_PACKAGE_NAME: Package name for the app/flavor
#------------------------------------------------------------------------------
buildAndUploadAndroid() {
    local app_name flavor package_name secret_file script_env build_command

    if [ "$#" -eq 1 ]; then
        local profile="$1"
        app_name="$(getProfileValue "$profile" "app_name")"
        flavor="$(getProfileValue "$profile" "env_name")"
        package_name="$(getProfileValue "$profile" "package_name")"
        secret_file="$(getProfileValue "$profile" "secret_file")"
        script_env="$(melosScriptEnv "$flavor" "$app_name")"
        build_command="$(getMelosScriptName "$app_name" "build" "$script_env" "aab:raw")"
    else
        app_name="${1:-}"
        flavor="${2:-}"
        package_name="${3:-}"
        secret_file="${4:-env.json}"
        script_env="$(melosScriptEnv "$flavor" "$app_name")"
        build_command="${5:-$(getMelosScriptName "$app_name" "build" "$script_env" "aab:raw")}"
    fi

    local tmp_json_utils="$JSON_UTILS_PATH"
    if [ -z "$package_name" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        package_name="$(getProfileValueForApp "$app_name" "package_name" "$flavor")"
    fi
    if [ -z "$package_name" ] || [ "$package_name" = "null" ]; then
        package_name="$(resolveAndroidPackageName "$app_name" "$flavor")"
    fi

    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$flavor" ] || [ -z "$package_name" ]; then
        print_build_upload_validation_error
        return 1
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Source utility functions with dynamic path resolution
    source "$JSON_UTILS_PATH"
    
    # Execute build command
    echo "Building Android AAB for $app_name ($flavor)..."
    if melosScriptExists "$build_command"; then
        melos run "$build_command"
    else
        echo "ℹ️  Melos script '$build_command' not defined; running buildAABRaw directly"
        bash "$JSON_SCRIPT_DIR/run_build.sh" buildAABRaw "$app_name" "$flavor"
    fi
    
    # Use uploadAndroid function to handle the upload
    uploadAndroid "$app_name" "$package_name"
    
    echo "✅ Android build and upload completed for $app_name ($flavor)"
}

#------------------------------------------------------------------------------
# deployAAB - Generic AAB deploy with chat notifications
#------------------------------------------------------------------------------
# USAGE: deployAAB <app_name> <env_name> <secret_file> <package_name> <internal_test_app_id>
#
# EXAMPLES:
#   deployAAB "sample_app" "dev" "dev.json" "com.example.sample_app.dev" "123456789"
#
# This function:
#   - Sets up the environment for AAB deployment
#   - Exports chat notification variables
#   - Runs the corresponding AAB deploy script with notifications
#------------------------------------------------------------------------------
deployAAB() {
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

    local tmp_json_utils="$JSON_UTILS_PATH"
    if [ -z "$secret_file" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        secret_file="$(getProfileValueForApp "$app_name" "secret_file" "$env_name")"
        if [ "$secret_file" = "null" ] || [ -z "$secret_file" ]; then
            secret_file="$env_name.json"
        fi
    fi
    if [ -z "$package_name" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        package_name="$(getProfileValueForApp "$app_name" "package_name" "$env_name")"
    fi
    if [ -z "$package_name" ] || [ "$package_name" = "null" ]; then
        package_name="$(resolveAndroidPackageName "$app_name" "$env_name")"
    fi
    if [ -z "$internal_test_app_id" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        internal_test_app_id="$(getProfileValueForApp "$app_name" "internal_test_app_id" "$env_name")"
    fi
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ] || [ -z "$secret_file" ] || [ -z "$package_name" ]; then
        print_deploy_aab_validation_error
        return 1
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Setup environment
    ROOT="${MELOS_ROOT_PATH:-}"
    if [ -z "$ROOT" ]; then ROOT="$(pwd)"; fi
    cd "$ROOT"
    
    # Source utility functions with dynamic path resolution
    source "$JSON_UTILS_PATH"
    
    # Export chat notification environment variables
    exportAppContents "$app_name" "$env_name" "$secret_file" "$internal_test_app_id"
    
    # Run the AAB deploy script with chat notifications
    runMelosOrDirect --notify "$app_name" deploy "$env_name" aab:raw
}
