#!/usr/bin/env bash
#------------------------------------------------------------------------------
# android_diagnostics.sh - Android Build & Deploy Diagnostic Output Printers
#------------------------------------------------------------------------------

print_aab_not_found_error() {
    local search_dir="$1"
    echo "Error: AAB file not found"
    echo "Searched in: $search_dir"
    echo "Available AAB files:"
    find build/app/outputs -name "*.aab" -print 2>/dev/null || echo "  No AAB files found in build directory"
}

print_service_account_missing_error() {
    local service_account_json="$1"
    local app_name="$2"
    local expected_workspace_path
    expected_workspace_path="${MELOS_ROOT_PATH:-}/private_keys/play-store-deployer.json"

    echo "❌ ERROR: Service account file not found"
    echo "   Expected path: $service_account_json"
    echo ""
    echo "📋 SOLUTION:"
    echo "   Please ensure the private_keys directory exists in the workspace root:"
    echo "   The service account file should be located at: $expected_workspace_path"
    echo "   This file contains the Google Play Store API credentials for Android deployment."
}

print_play_store_upload_failed_error() {
    echo ""
    echo "================================================================================"
    echo "❌ GOOGLE PLAY STORE UPLOAD FAILED!"
    echo "================================================================================"
    echo "Please check the logs above for the specific error."
    echo "If this is a permissions issue, verify your Google Play Service Account JSON."
    echo "================================================================================"
}

print_build_upload_validation_error() {
    echo "Error: app_name, flavor, and package_name must be provided"
    echo "Usage: buildAndUploadAndroid <app_name> <flavor> <package_name> [secret_file] [build_command]"
    echo "Example: buildAndUploadAndroid \"my_app\" \"prod\" \"com.example.app\" \"prod.json\""
}

print_upload_android_validation_error() {
    echo "Error: app_name and package_name must be provided"
    echo "Usage: uploadAndroid <app_name> <package_name> or uploadAndroid <profile_name>"
}

print_upload_aab_validation_error() {
    echo "Error: app_name, env_name, secret_file, and package_name must be provided"
    echo "Usage: uploadAAB <app_name> <env_name> <secret_file> <package_name> [internal_test_app_id] or uploadAAB <profile_name>"
}

print_build_aab_validation_error() {
    echo "Error: app_name, env_name, secret_file, and package_name must be provided"
    echo "Usage: buildAAB <app_name> <env_name> <secret_file> <package_name> [internal_test_app_id] or buildAAB <profile_name>"
}

print_build_aab_raw_validation_error() {
    echo "Error: app_name and env_name must be provided"
    echo "Usage: buildAABRaw <app_name> <env_name>"
    echo "Example: buildAABRaw \"my_app\" \"dev\""
}

print_deploy_aab_validation_error() {
    echo "Error: app_name, env_name, secret_file, and package_name must be provided"
    echo "Usage: deployAAB <app_name> <env_name> <secret_file> <package_name> [internal_test_app_id] or deployAAB <profile_name>"
}
