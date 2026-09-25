#!/usr/bin/env bash
#------------------------------------------------------------------------------
# ios_diagnostics.sh - iOS Build & Deploy Diagnostic Output Printers
#------------------------------------------------------------------------------

print_ipa_not_found_error() {
    local search_dir="$1"
    echo "Error: IPA file not found"
    echo "Searched in: $search_dir"
    echo "Available IPA files:"
    find build/ios -maxdepth 4 -type f -name "*.ipa" -print 2>/dev/null || echo "  No IPA files found in build/ios directory"
}

print_command_required_error() {
    echo "Error: Command must be provided"
    echo "Usage: runWithIosEnv <command>"
}

print_apple_creds_required_error() {
    echo "Error: APPLE_API_KEY and APPLE_API_ISSUER must be set"
}

print_build_upload_validation_error() {
    echo "Error: app_name and secret_file must be provided"
    echo "Usage: buildAndUploadIOS <app_name> <secret_file> [build_command] [upload_command] or buildAndUploadIOS <profile_name>"
}

print_testflight_upload_failed_fastlane() {
    echo ""
    echo "================================================================================"
    echo "❌ TESTFLIGHT UPLOAD FAILED! (via Fastlane)"
    echo "================================================================================"
    echo "Please check the logs above for the specific error."
    echo "If this is an authentication issue, verify your APPLE_API_KEY and APPLE_API_ISSUER credentials."
    echo "================================================================================"
}

print_app_store_upload_failed_altool() {
    echo ""
    echo "================================================================================"
    echo "❌ APP STORE UPLOAD FAILED! (via xcrun altool)"
    echo "================================================================================"
    echo "Please check the logs above for the specific error."
    echo "If this is an authentication issue, verify your APPLE_API_KEY and APPLE_API_ISSUER credentials."
    echo "================================================================================"
}

print_unknown_app_error() {
    local app_name="$1"
    echo "Error: Unknown or unconfigured app '$app_name'"
}

print_build_ipa_validation_error() {
    echo "Error: app_name, env_name, and secret_file must be provided"
    echo "Usage: buildIPA <app_name> <env_name> <secret_file> [internal_test_app_id] or buildIPA <profile_name>"
}

print_build_ipa_raw_validation_error() {
    echo "Error: app_name and env_name must be provided"
    echo "Usage: buildIPARaw <app_name> <env_name>"
    echo "Example: buildIPARaw \"my_app\" \"dev\""
}

#------------------------------------------------------------------------------
# print_ios_root_cause_hints - Scans a captured build log for known toolchain
# error signatures and prints the ACTUAL cause + exact fix up front, instead of
# leaving it to be found by scrolling through the raw xcodebuild/Flutter output
# (or the generic "possible reasons" list in print_ios_build_failed_error).
#------------------------------------------------------------------------------
print_ios_root_cause_hints() {
    local log_file="$1"
    [ -n "$log_file" ] && [ -f "$log_file" ] || return 0

    local found=0

    if grep -qi "You have not agreed to the Xcode license agreements" "$log_file"; then
        found=1
        echo ""
        echo "🎯 ROOT CAUSE DETECTED: Xcode license not accepted"
        echo "   This blocks the whole toolchain (Swift Package Manager, xcodebuild) after any"
        echo "   Xcode install/update, and often surfaces as a confusing 'dyld: Library not"
        echo "   loaded' or 'Could not resolve package dependencies' error instead of the real one."
        echo "   👉 Fix: run in Terminal (needs your password, cannot be automated here):"
        echo "        sudo xcodebuild -license"
        echo "        sudo xcodebuild -runFirstLaunch"
    fi

    if grep -qi "Library not loaded:.*libPackageDescription\|Could not resolve package dependencies" "$log_file"; then
        found=1
        echo ""
        echo "🎯 Swift Package Manager failed to resolve dependencies"
        echo "   Usually caused by the Xcode license not being accepted yet (see above if also"
        echo "   detected), a stale/corrupted Xcode install, or 'xcode-select' pointing at the"
        echo "   wrong Xcode. Check with: xcode-select -p && xcodebuild -version"
    fi

    if grep -qi 'No signing certificate "iOS Distribution"\|No signing certificate "Apple Distribution"\|exportArchive No Accounts' "$log_file"; then
        found=1
        echo ""
        echo "🎯 ROOT CAUSE DETECTED: No Distribution signing certificate in Keychain"
        echo "   The archive built fine, but exporting to a store IPA needs an 'Apple"
        echo "   Distribution' certificate for this app's team, which isn't installed locally."
        echo "   👉 Fix: open Xcode → Settings → Accounts → sign in with the team's Apple ID →"
        echo "   select the team → Manage Certificates → + → Apple Distribution."
        echo "   Check what's currently installed with: security find-identity -v -p codesigning"
    fi

    if grep -qi "no such module\|Sandbox: .* deny\|Command PhaseScriptExecution failed" "$log_file"; then
        found=1
        echo ""
        echo "🎯 Xcode build phase / sandbox failure detected"
        echo "   Often a stale Pods install or a script phase blocked by sandboxing. Try:"
        echo "   👉 flutter clean && flutter pub get && cd ios && pod install --repo-update"
    fi

    if [ "$found" -eq 1 ]; then
        echo ""
        echo "(Full raw build output is above/in the job log if you need more detail.)"
    fi
}

print_ios_build_failed_error() {
    local ipa_build_status="$1"
    local app_name="$2"
    local secret_file="$3"
    echo ""
    echo "================================================================================"
    echo "❌ FLUTTER iOS BUILD FAILED! (Exit Code: $ipa_build_status)"
    echo "================================================================================"
    echo "Possible reasons for failure and how to fix:"
    echo ""
    echo "1. 🔐 Xcode Provisioning Profile / Signing Issues:"
    echo "   Verify that Apple Developer credentials in env/$secret_file are correct."
    echo "   Ensure you have configured proper provisioning profiles in Xcode."
    echo ""
    echo "2. 📦 Stale Pods or CocoaPods Cache:"
    echo "   Try clean-building the iOS workspace manually:"
    echo "   👉 Run: flutter clean && flutter pub get && cd ios && pod install"
    echo ""
    echo "3. 📝 Missing Env Config File:"
    echo "   Ensure 'apps/$app_name/env/$secret_file' exists and contains valid JSON."
    echo "================================================================================"
}

print_deploy_ipa_validation_error() {
    echo "Error: app_name, env_name, and secret_file must be provided"
    echo "Usage: deployIPA <app_name> <env_name> <secret_file> [internal_test_app_id] or deployIPA <profile_name>"
}

print_upload_ipa_validation_error() {
    echo "Error: app_name, env_name, and secret_file must be provided"
    echo "Usage: uploadIPA <app_name> <env_name> <secret_file> [internal_test_app_id] or uploadIPA <profile_name>"
}

print_upload_ipa_raw_validation_error() {
    echo "Error: app_name and env_name must be provided"
    echo "Usage: uploadIPARaw <app_name> <env_name>"
    echo "Example: uploadIPARaw \"my_app\" \"dev\""
}

print_env_json_missing_error() {
    local app_name="$1"
    local env_name="$2"
    echo "Error: environment JSON not found for $app_name/$env_name"
    echo "Tried: apps/$app_name/env/$env_name.json, apps/$app_name/env/env.json, env/$env_name.json, env/env.json"
}

print_testflight_upload_failed_fastlane_with_env() {
    local env_name="$1"
    echo ""
    echo "================================================================================"
    echo "❌ TESTFLIGHT UPLOAD FAILED! (via Fastlane)"
    echo "================================================================================"
    echo "Please check the logs above for the specific error."
    echo "If this is an authentication issue, verify your APPLE_API_KEY and APPLE_API_ISSUER credentials in env/$env_name.json."
    echo "================================================================================"
}

print_installing_ruby_gems() {
    echo "Installing missing ruby gems (bundle install)..."
}

print_building_ios_ipa() {
    local app_name="$1"
    local script_env="$2"
    echo "Building iOS IPA for $app_name ($script_env)..."
}

print_extracting_apple_creds() {
    local secret_file="$1"
    echo "Extracting Apple credentials from env/$secret_file..."
}

print_apple_creds_debug() {
    local key="${1:-<empty>}"
    local issuer="${2:-<empty>}"
    local key_path="$3"
    echo "APPLE_API_KEY=$key"
    echo "APPLE_API_ISSUER=$issuer"
    echo "APPLE_API_KEY_PATH=$key_path"
}

print_locating_ipa() {
    echo "Locating IPA file..."
}

print_uploading_via_fastlane() {
    echo "Uploading via Fastlane..."
}

print_uploading_via_altool() {
    echo "Uploading via xcrun altool..."
}

print_ios_build_upload_success() {
    local app_name="$1"
    echo "✅ iOS build and upload completed for $app_name"
}

print_running_flutter_clean() {
    echo "Running flutter clean..."
}

print_running_flutter_pub_get() {
    echo "Running flutter pub get..."
}

print_removing_podfile_lock() {
    echo "Removing Podfile.lock to allow fresh pod resolution..."
}

print_running_pod_install() {
    echo "Running pod install..."
}

print_pod_install_failed_attempting_fix() {
    echo "pod install failed. Attempting targeted fix for AppsFlyerFramework and CDN issues..."
}

print_retrying_pod_install() {
    echo "Retrying pod install --repo-update..."
}

print_second_pod_install_failed() {
    echo "Second pod install failed. Waiting 5s before final retry..."
}

print_using_export_options_template() {
    local source_plist="$1"
    local export_plist="$2"
    echo "Using ExportOptions.plist template from: $source_plist (copied to temp path: $export_plist)"
}

print_export_options_not_found_warning() {
    local melos_root="$1"
    echo "Warning: No ExportOptions.plist template found at $melos_root/ios/ExportOptions.plist or ios/ExportOptions.plist. Creating temporary fallback."
}

print_patching_export_options() {
    local export_method="$1"
    local signing_cert="$2"
    local export_plist="$3"
    echo "Patching ExportOptions.plist: method=$export_method, signingCertificate=$signing_cert..."
}

print_injecting_team_id() {
    local team_id="$1"
    local export_plist="$2"
    echo "Injecting TEAM_ID=$team_id into ExportOptions.plist..."
}

print_team_id_missing_warning() {
    local secret_file="$1"
    local default_team="${DEFAULT_TEAM_ID:-}"
    if [ -n "$default_team" ]; then
        echo "Warning: TEAM_ID not specified in environment, .env, or env/$secret_file. Falling back to DEFAULT_TEAM_ID: $default_team"
    else
        echo "Warning: TEAM_ID not specified in environment, .env, or env/$secret_file."
    fi
}

print_api_key_found_custom_flow() {
    local apple_key="$1"
    echo "App Store Connect API key found ($apple_key). Using custom archive & export flow..."
}

print_xcode_archive_built_exporting() {
    echo "Xcode archive successfully built. Exporting IPA using App Store Connect API credentials..."
}

print_no_api_key_standard_build() {
    echo "No App Store Connect API key found or key file missing. Using standard flutter build ipa..."
}

print_unknown_app_fallback_warning() {
    local app_name="$1"
    echo "Warning: Unknown app '$app_name'. Falling back to Fastlane upload..."
}

