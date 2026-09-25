#!/bin/bash
# ===========================================================================
# Android Deployment Utilities
# This file contains Android-specific build and deployment automation functions.
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

if [ -f "$ANDROID_SCRIPT_DIR/android_diagnostics.sh" ]; then
    # shellcheck source=developer-dashboard/features/deployment/scripts/android/android_diagnostics.sh
    source "$ANDROID_SCRIPT_DIR/android_diagnostics.sh"
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
    checkMelosScript "$build_command" || return 1
    melos run "$build_command"
    
    # Use uploadAndroid function to handle the upload
    uploadAndroid "$app_name" "$package_name"
    
    echo "✅ Android build and upload completed for $app_name ($flavor)"
}

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
    local command="$1"
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
    
    # Validate command parameter
    if [ -z "$command" ]; then
        echo "Error: Command must be provided"
        echo "Usage: runWithAndroidEnv <command>"
        return 1
    fi
    
    if [[ "$command" == *"bundle exec"* ]]; then
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
    eval "$command"
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
    local app_name package_name
    
    if [ "$#" -eq 1 ]; then
        local profile="$1"
        app_name="$(getProfileValue "$profile" "app_name")"
        package_name="$(getProfileValue "$profile" "package_name")"
    else
        app_name="${1:-}"
        package_name="${2:-}"
    fi

    local tmp_json_utils="$JSON_UTILS_PATH"
    if [ -n "$app_name" ] && [[ "$package_name" != com.* ]] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        local resolved_pkg
        resolved_pkg="$(getProfileValueForApp "$app_name" "package_name" "$package_name")"
        if [ -n "$resolved_pkg" ] && [ "$resolved_pkg" != "null" ]; then
            package_name="$resolved_pkg"
        fi
    fi
    
    # Validate parameters
    if [ -z "$app_name" ] || [ -z "$package_name" ]; then
        print_upload_android_validation_error
        return 1
    fi
    
    # Source utility functions with dynamic path resolution
    source "$JSON_UTILS_PATH"
    
    # Setup service account JSON - use centralized workspace private_keys
    export SERVICE_ACCOUNT_JSON="$MELOS_ROOT_PATH/private_keys/play-store-deployer.json"
    
    # Change to app directory
    cd "$MELOS_ROOT_PATH/apps/$app_name" || return 1
    
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
    if ! _retryUpload "Play Store upload (Fastlane)" runWithAndroidEnv "cd '$deployment_fastlane_dir' && bundle exec fastlane android upload_android track:internal release_status:completed"; then
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

    local tmp_json_utils="$JSON_UTILS_PATH"
    if [ -n "$package_name" ] && [[ "$package_name" != com.* ]] && [ -z "$internal_test_app_id" ]; then
        internal_test_app_id="$package_name"
        package_name=""
    fi
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
    if [ -z "$package_name" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        package_name="$(getProfileValueForApp "$app_name" "package_name" "$env_name")"
    fi
    if [ "$package_name" = "null" ]; then
        package_name=""
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
    export SERVICE_ACCOUNT_JSON="$MELOS_ROOT_PATH/private_keys/play-store-deployer.json"
    if [ ! -f "$SERVICE_ACCOUNT_JSON" ]; then
        print_service_account_missing_error "$SERVICE_ACCOUNT_JSON" "$app_name"
        return 1
    fi

    # Export chat notification environment variables
    exportAppContents "$app_name" "$env_name" "$secret_file" "$internal_test_app_id"
    
    # Locate AAB file (from app directory)
    cd "$MELOS_ROOT_PATH/apps/$app_name" || return 1
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
    if ! _retryUpload "Play Store upload (Fastlane)" runWithAndroidEnv "cd '$deployment_fastlane_dir' && bundle exec fastlane android upload_android track:internal release_status:completed"; then
        print_play_store_upload_failed_error
        return 1
    fi
}

#------------------------------------------------------------------------------
# buildAAB - Generic AAB build with chat notifications
#------------------------------------------------------------------------------
# USAGE: buildAAB <app_name> <env_name> <secret_file> <package_name> <internal_test_app_id>
#
# EXAMPLES:
#   buildAAB "sample_app" "dev" "dev.json" "com.example.sample_app.dev" "123456789"
#
# This function:
#   - Sets up the environment for AAB builds
#   - Exports chat notification variables
#   - Runs the corresponding AAB build script with notifications
#------------------------------------------------------------------------------
buildAAB() {
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
    if [ -z "$internal_test_app_id" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        internal_test_app_id="$(getProfileValueForApp "$app_name" "internal_test_app_id" "$env_name")"
    fi
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ] || [ -z "$secret_file" ] || [ -z "$package_name" ]; then
        print_build_aab_validation_error
        return 1
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Setup environment
    ROOT="${MELOS_ROOT_PATH:-}"
    if [ -z "$ROOT" ] || [ ! -d "$ROOT/apps/$app_name" ]; then ROOT="$(pwd)"; fi
    cd "$ROOT"
    
    # Source utility functions with dynamic path resolution
    source "$JSON_UTILS_PATH"
    
    # Export chat notification environment variables
    exportAppContents "$app_name" "$env_name" "$secret_file" "$internal_test_app_id"
    
    # Run the AAB build script with chat notifications
    local script_env target_script
    script_env="$(melosScriptEnv "$env_name" "$app_name")"
    target_script="$(getMelosScriptName "$app_name" "build" "$script_env" "aab:raw")"
    checkMelosScript "$target_script" || return 1
    bash "$CHAT_NOTIFY_PATH" -- melos run "$target_script"
}

#------------------------------------------------------------------------------
# buildAABRaw - Generic raw AAB build logic
#------------------------------------------------------------------------------
# USAGE: buildAABRaw <app_name> <env_name>
#
# EXAMPLES:
#   buildAABRaw "my_app" "dev"
#   buildAABRaw "my_app" "prod"
#
# This function:
#   - Sets up the environment for AAB builds
#   - Handles Flutter dependencies and version management
#   - Builds the AAB file with proper configuration
#------------------------------------------------------------------------------
buildAABRaw() {
    local app_name="$1"
    local env_name="$2"
    
    # Check if this app has flavor options. If the profile has env_name = "null", treat it as flavorless.
    local profile_env_name
    profile_env_name="$(getProfileValueForApp "$app_name" "env_name" "$env_name")"
    if [ "$profile_env_name" = "null" ]; then
        env_name="null"
    fi
    
    local secret_file
    secret_file="$(getProfileValueForApp "$app_name" "secret_file" "$env_name")"
    if [ -z "$secret_file" ]; then
        secret_file="$env_name.json"
    fi
    
    local flutter_flavor
    if [ "$env_name" != "null" ]; then
        flutter_flavor="$(flutterAndroidFlavor "$env_name")"
    else
        flutter_flavor=""
    fi
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ]; then
        print_build_aab_raw_validation_error
        return 1
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Setup environment
    ROOT="${MELOS_ROOT_PATH:-}"
    if [ -z "$ROOT" ] || [ ! -d "$ROOT/apps/$app_name" ]; then ROOT="$(pwd)"; fi
    cd "$ROOT/apps/$app_name"

    # Resolve JDK version to prevent compilation failures on newer Java versions (like JDK 26)
    if [ -d "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home" ]; then
        export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
        export PATH="$JAVA_HOME/bin:$PATH"
        echo "☕ Java Home set to openjdk@17: $JAVA_HOME"
    fi

    # Print environment config diagnostics
    logEnvironmentConfig "$secret_file"
    
    # Only remove the AAB *output* directory - that's the only thing findAabFile()
    # (called later) can pick a stale result from (e.g. a leftover .aab from a
    # different flavor's earlier build). Wiping the whole build/ tree here was
    # unnecessarily also destroying Gradle/Kotlin's own incremental-compilation
    # state (build/app/intermediates, build/app/kotlin, build/.transforms, etc.),
    # forcing every single Android build to fully recompile from scratch
    # regardless of the local Gradle build cache being enabled - this is why
    # bundleDevRelease's own timing crept from ~3min up to 5+min as the app grew.
    echo "Cleaning stale AAB output (skipping flutter clean / full build/ wipe to preserve Gradle's incremental cache)..."
    rm -rf build/app/outputs/bundle/
    echo "Running flutter pub get..."
    flutter pub get
    
    # Version management
    if [ "${SKIP_VERSION_BUMP:-false}" != "true" ]; then
        perl -i -pe 's/version: (\d+\.\d+\.\d+)(?:\+(\d+))?/ "version: $1+" . (($2 || 0) + 1) /e' pubspec.yaml
    fi
    
    # Build AAB
    local DART_DEFINES_SCRIPT="$ROOT/tool/generate_android_dart_defines.dart"
    if [ -f "$DART_DEFINES_SCRIPT" ]; then
        (cd "$ROOT" && dart "tool/generate_android_dart_defines.dart")
    fi
    # Fetch secrets from Keychain in-memory if requested via USE_KEYCHAIN_SECRETS
    local keychain_defines=""
    if [ "${USE_KEYCHAIN_SECRETS:-false}" = "true" ] || [ "${USE_KEYCHAIN_SECRETS:-0}" = "1" ]; then
        local secrets_script="$(dirname "$JSON_UTILS_PATH")/build_secrets.sh"
        if [ ! -f "$secrets_script" ]; then
            secrets_script="$ROOT/developer-dashboard/features/deployment/scripts/build_secrets.sh"
        fi
        if [ ! -f "$secrets_script" ]; then
            secrets_script="$ROOT/features/deployment/scripts/build_secrets.sh"
        fi
        if [ -f "$secrets_script" ]; then
            keychain_defines="$(bash "$secrets_script" "$env_name")"
        fi
    fi

    local define_file_arg=""
    if [ -n "$secret_file" ] && [ -f "env/$secret_file" ]; then
        define_file_arg="--dart-define-from-file=env/$secret_file"
    fi

    set +e
    if [ "$env_name" = "null" ]; then
        flutter build appbundle --no-tree-shake-icons --target-platform android-arm64 $define_file_arg $keychain_defines
    else
        flutter build appbundle --no-tree-shake-icons --target-platform android-arm64 --flavor "$flutter_flavor" $define_file_arg $keychain_defines
    fi
    local build_status=$?
    set -e

    # Flutter/Gradle sometimes produces an AAB but still returns non-zero.
    # Only treat as success if we can find an AAB for the *same flavor*.
    if [ "$build_status" -ne 0 ]; then
        local bundle_dir
        if [ "$env_name" = "null" ]; then
            bundle_dir="build/app/outputs/bundle/release"
        else
            bundle_dir="build/app/outputs/bundle/${flutter_flavor}Release"
        fi
        local built_aab_path=""
        if [ -d "$bundle_dir" ]; then
            # shellcheck disable=SC2012
            built_aab_path="$(ls -t "$bundle_dir"/*.aab 2>/dev/null | head -n 1 || true)"
        fi
        if [ -n "${built_aab_path:-}" ] && [ -f "$built_aab_path" ]; then
            echo "WARNING: flutter build exited with $build_status but produced: $built_aab_path"
            return 0
        fi
        echo "ERROR: flutter build failed with exit code $build_status and no AAB was found under: $bundle_dir"
        return "$build_status"
    fi
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
    if [ -z "$ROOT" ] || [ ! -d "$ROOT/apps/$app_name" ]; then ROOT="$(pwd)"; fi
    cd "$ROOT"
    
    # Source utility functions with dynamic path resolution
    source "$JSON_UTILS_PATH"
    
    # Export chat notification environment variables
    exportAppContents "$app_name" "$env_name" "$secret_file" "$internal_test_app_id"
    
    # Run the AAB deploy script with chat notifications
    local script_env target_script
    script_env="$(melosScriptEnv "$env_name" "$app_name")"
    target_script="$(getMelosScriptName "$app_name" "deploy" "$script_env" "aab:raw")"
    checkMelosScript "$target_script" || return 1
    bash "$CHAT_NOTIFY_PATH" -- melos run "$target_script"
}
