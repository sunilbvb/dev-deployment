#!/usr/bin/env bash
# ===========================================================================
# Android Build Automation
# This file contains Android-specific build functions (buildAAB, buildAABRaw).
# ===========================================================================

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

    local tmp_json_utils="${JSON_UTILS_PATH:-}"
    if [ -z "$secret_file" ] && [ -n "$tmp_json_utils" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        secret_file="$(getProfileValueForApp "$app_name" "secret_file" "$env_name")"
        if [ "$secret_file" = "null" ] || [ -z "$secret_file" ]; then
            secret_file="$env_name.json"
        fi
    fi
    if [ -z "$package_name" ] && [ -n "$tmp_json_utils" ] && [ -f "$tmp_json_utils" ]; then
        source "$tmp_json_utils"
        package_name="$(getProfileValueForApp "$app_name" "package_name" "$env_name")"
    fi
    if [ -z "$package_name" ] || [ "$package_name" = "null" ]; then
        package_name="$(resolveAndroidPackageName "$app_name" "$env_name")"
    fi
    if [ -z "$internal_test_app_id" ] && [ -n "$tmp_json_utils" ] && [ -f "$tmp_json_utils" ]; then
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
    if [ -z "$ROOT" ]; then ROOT="$(pwd)"; fi
    cd "$ROOT"
    
    # Source utility functions with dynamic path resolution
    if [ -n "${JSON_UTILS_PATH:-}" ] && [ -f "$JSON_UTILS_PATH" ]; then
        source "$JSON_UTILS_PATH"
    fi
    
    # Export chat notification environment variables
    exportAppContents "$app_name" "$env_name" "$secret_file" "$internal_test_app_id"
    
    # Run the AAB build script with chat notifications
    runMelosOrDirect --notify "$app_name" build "$env_name" aab:raw
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
    # The console passes "default"/"any"/"none" for apps without flavors (see commands.py).
    case "$env_name" in
        default|any|none) env_name="null" ;;
    esac
    
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
    if [ -z "$ROOT" ]; then ROOT="$(pwd)"; fi
    cd "$(resolveAppDir "$app_name")"

    # Resolve JDK version to prevent compilation failures on newer Java versions (like JDK 26)
    if [ -d "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home" ]; then
        export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
        export PATH="$JAVA_HOME/bin:$PATH"
        echo "☕ Java Home set to openjdk@17: $JAVA_HOME"
    fi

    # Print environment config diagnostics
    logEnvironmentConfig "$secret_file"
    
    # Reverted back to full build/ wipe before every Android build to guarantee build correctness.
    # Gradle's up-to-date checks can incorrectly treat native compile steps as unchanged
    # and reuse stale binaries when only deleting the output folder.
    # CLEAN_BUILD=false (console default for non-prod flavors) keeps build/ so Gradle
    # can reuse its incremental output; anything else wipes it.
    if [ "${CLEAN_BUILD:-true}" = "false" ]; then
        echo "Incremental build: keeping build/ (enable 'Clean build' in the console to wipe it)."
    else
        echo "Cleaning build directory (wiping build/ to ensure clean compilation)..."
        rm -rf build/
    fi
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
        local secrets_script=""
        if [ -n "${JSON_UTILS_PATH:-}" ]; then
            secrets_script="$(dirname "$JSON_UTILS_PATH")/build_secrets.sh"
            if [ ! -f "$secrets_script" ]; then
                secrets_script="$(dirname "$JSON_UTILS_PATH")/security/build_secrets.sh"
            fi
            if [ ! -f "$secrets_script" ]; then
                secrets_script="$(dirname "$JSON_UTILS_PATH")/../security/build_secrets.sh"
            fi
        fi
        if [ -z "$secrets_script" ] || [ ! -f "$secrets_script" ]; then
            secrets_script="$ROOT/developer-dashboard/features/deployment/scripts/security/build_secrets.sh"
        fi
        if [ ! -f "$secrets_script" ]; then
            secrets_script="$ROOT/developer-dashboard/features/deployment/scripts/build_secrets.sh"
        fi
        if [ ! -f "$secrets_script" ]; then
            secrets_script="$ROOT/features/deployment/scripts/security/build_secrets.sh"
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
