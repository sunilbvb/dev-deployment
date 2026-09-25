#!/usr/bin/env bash
#------------------------------------------------------------------------------
# ios_build.sh - iOS Build automation functions
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# setup_ios_dependencies - Set up CocoaPods for iOS build
#------------------------------------------------------------------------------
setup_ios_dependencies() {
    # iOS dependencies setup
    export PATH="$HOME/.rbenv/shims:$HOME/.rbenv/bin:$HOME/.rbenv/versions/3.2.0/bin:$HOME/.pub-cache/bin:$HOME/fvm/default/bin:$HOME/development/flutter/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
    cd ios || return 1
    
    print_running_pod_install
    # Try fast pod install without --repo-update first
    if ! env -u GEM_HOME -u GEM_PATH pod install; then
        print_pod_install_failed_attempting_fix
        print_retrying_pod_install
        # Fallback to repo-update if missing specs
        if ! env -u GEM_HOME -u GEM_PATH pod install --repo-update; then
            env -u GEM_HOME -u GEM_PATH pod update AppsFlyerFramework --no-repo-update || true
            env -u GEM_HOME -u GEM_PATH pod repo remove trunk || true
            env -u GEM_HOME -u GEM_PATH pod install --repo-update
        fi
    fi
    cd .. || return 1
}

#------------------------------------------------------------------------------
# generate_export_options_plist - Resolve and patch ExportOptions.plist
#------------------------------------------------------------------------------
# USAGE: generate_export_options_plist <secret_file> <signing_cert> <export_method> <result_var_name>
generate_export_options_plist() {
    local secret_file="${1:-}"
    local signing_cert="${2:-}"
    local export_method="${3:-}"
    local result_var="${4:-}"

    local source_plist=""
    if [ -f "$MELOS_ROOT_PATH/ios/ExportOptions.plist" ]; then
        source_plist="$MELOS_ROOT_PATH/ios/ExportOptions.plist"
    elif [ -f "ios/ExportOptions.plist" ]; then
        source_plist="ios/ExportOptions.plist"
    fi

    local temp_plist=""
    if [ -n "$source_plist" ]; then
        # Copy source plist to a writable temp location so we can patch it without modifying the shared source
        temp_plist=$(mktemp -t export_options_XXXXXX.plist)
        cp "$source_plist" "$temp_plist"
        print_using_export_options_template "$source_plist" "$temp_plist"
    else
        print_export_options_not_found_warning "$MELOS_ROOT_PATH"
        temp_plist=$(mktemp -t export_options_XXXXXX.plist)
        cat <<EOF > "$temp_plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>compileBitcode</key>
	<false/>
	<key>destination</key>
	<string>export</string>
	<key>method</key>
	<string>app-store-connect</string>
	<key>signingCertificate</key>
	<string>Apple Distribution</string>
	<key>signingStyle</key>
	<string>automatic</string>
	<key>manageAppVersionAndBuildNumber</key>
	<false/>
	<key>uploadBitcode</key>
	<false/>
	<key>uploadSymbols</key>
	<true/>
</dict>
</plist>
EOF
    fi

    # Dynamically patch ExportOptions.plist with runtime values
    if [ -f "$temp_plist" ]; then
        print_patching_export_options "$export_method" "$signing_cert" "$temp_plist"
        plutil -replace method -string "$export_method" "$temp_plist"
        # Remove signingCertificate for automatic signing style to let Xcode auto-resolve
        plutil -remove signingCertificate "$temp_plist" || true
        
        # Resolve team_id from environment, config files, or .env files
        local team_id="${TEAM_ID:-}"
        if [ -z "$team_id" ] && [ -f "env/$secret_file" ]; then
            team_id="$(getValueByKey "TEAM_ID" "env/$secret_file")"
        fi
        if [ -z "$team_id" ] && [ -f "$MELOS_ROOT_PATH/.env" ]; then
            team_id=$(grep -E "^TEAM_ID=" "$MELOS_ROOT_PATH/.env" | cut -d'=' -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        fi
        if [ -z "$team_id" ] && [ -f ".env" ]; then
            team_id=$(grep -E "^TEAM_ID=" ".env" | cut -d'=' -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        fi
        
        # Inject Team ID if specified, otherwise warn the user
        if [ -n "$team_id" ]; then
            print_injecting_team_id "$team_id" "$temp_plist"
            plutil -replace teamID -string "$team_id" "$temp_plist"
        elif [ -n "${DEFAULT_TEAM_ID:-}" ]; then
            print_injecting_team_id "$DEFAULT_TEAM_ID" "$temp_plist"
            plutil -replace teamID -string "$DEFAULT_TEAM_ID" "$temp_plist"
        else
            print_team_id_missing_warning "$secret_file"
        fi
    fi

    eval "$result_var=\"\$temp_plist\""
}

#------------------------------------------------------------------------------
# run_xcode_build_and_export - Archive and export the built IPA
#------------------------------------------------------------------------------
# USAGE: run_xcode_build_and_export <env_name> <secret_file> <flutter_flavor> <export_method> <export_plist> <apple_key> <apple_issuer> <apple_key_path> <result_var_name> <app_name> <log_file_var_name>
run_xcode_build_and_export() {
    local env_name="${1:-}"
    local secret_file="${2:-}"
    local flutter_flavor="${3:-}"
    local export_method="${4:-}"
    local export_plist="${5:-}"
    local apple_key="${6:-}"
    local apple_issuer="${7:-}"
    local apple_key_path="${8:-}"
    local result_var="${9:-}"
    local app_name="${10:-}"
    local log_file_var="${11:-}"

    # Fetch secrets from Keychain in-memory if script exists and enabled
    local keychain_defines=""
    local secrets_script="$(dirname "$JSON_UTILS_PATH")/build_secrets.sh"
    if [ -f "$secrets_script" ] && [ "${USE_KEYCHAIN_SECRETS:-false}" = "true" ]; then
        keychain_defines="$(bash "$secrets_script" "$env_name")"
    fi

    local ipa_build_status=0
    set +e
    local define_file_arg=""
    if [ -n "$secret_file" ] && [ -f "env/$secret_file" ]; then
        define_file_arg="--dart-define-from-file=env/$secret_file"
    fi

    # Build and export IPA using standard Flutter export-options flow (uses Xcode Automatic Signing like Xcode GUI Organizer)
    # Tee full output to a log file (in addition to the normal live stream) so a failure can be
    # diagnosed against known toolchain-error signatures instead of just the bare exit code.
    local build_log_file
    build_log_file="$(mktemp "${TMPDIR:-/tmp}/ios_build_log.XXXXXX")"
    if [ "$env_name" = "null" ]; then
        flutter build ipa --no-tree-shake-icons $define_file_arg --export-options-plist="$export_plist" $keychain_defines 2>&1 | tee "$build_log_file"
    else
        flutter build ipa --no-tree-shake-icons --flavor "$flutter_flavor" $define_file_arg --export-options-plist="$export_plist" $keychain_defines 2>&1 | tee "$build_log_file"
    fi
    ipa_build_status="${PIPESTATUS[0]}"
    set -e

    eval "$result_var=\$ipa_build_status"
    if [ -n "$log_file_var" ]; then
        eval "$log_file_var=\$build_log_file"
    else
        rm -f "$build_log_file"
    fi
}

#------------------------------------------------------------------------------
# auto_install_to_device - Detects connected iOS devices and installs the app
#------------------------------------------------------------------------------
auto_install_to_device() {
    local app_name="$1"
    
    echo "🔍 Scanning for connected physical iOS devices..."
    
    local device_ids
    device_ids=$(xcrun devicectl list devices 2>/dev/null | python3 -c "
import sys, re
available = []
for line in sys.stdin:
    if 'iphone' in line.lower() or 'ipad' in line.lower():
        match = re.search(r'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})\s+available', line, re.IGNORECASE)
        if match:
            available.append(match.group(1))
print(' '.join(available))
" 2>/dev/null || true)

    if [ -z "$device_ids" ]; then
        echo "ℹ️ No available physical iOS devices found."
        echo "💡 Tip: Connect your iPhone via USB, unlock it, and ensure it is 'trusted' by this Mac."
        return 0
    fi
    
    # Path to the compiled .app bundle inside xcarchive
    local app_bundle_path="build/ios/archive/Runner.xcarchive/Products/Applications/Runner.app"
    if [ ! -d "$app_bundle_path" ]; then
        echo "⚠️ Warning: Could not locate built .app bundle at $app_bundle_path"
        return 0
    fi
    
    # Extract bundle identifier
    local bundle_id
    bundle_id=$(plutil -extract CFBundleIdentifier raw "$app_bundle_path/Info.plist" 2>/dev/null || true)
    
    for udid in $device_ids; do
        echo "🚀 Installing app onto device: $udid..."
        if xcrun devicectl device install app --device "$udid" "$app_bundle_path"; then
            echo "✅ Successfully installed app!"
            if [ -n "$bundle_id" ]; then
                echo "⚡ Launching app '$bundle_id' on device..."
                xcrun devicectl device process launch --device "$udid" --terminate-existing "$bundle_id" || true
            fi
        else
            echo "❌ Failed to install app onto device $udid."
        fi
    done
}

#------------------------------------------------------------------------------
# buildIPARaw - Generic raw IPA build logic
#------------------------------------------------------------------------------
buildIPARaw() {
    local app_name="${1:-}"
    local env_name="${2:-}"
    
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
        flutter_flavor="$(flutterIosFlavor "$env_name" "$app_name")"
    else
        flutter_flavor=""
    fi
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ]; then
        print_build_ipa_raw_validation_error
        return 1
    fi
    
    # Set strict error handling
    set -euo pipefail
    
    # Setup environment
    ROOT="${MELOS_ROOT_PATH:-}"
    if [ -z "$ROOT" ] || [ ! -d "$ROOT/apps/$app_name" ]; then ROOT="$(pwd)"; fi
    cd "$ROOT/apps/$app_name" || return 1
    
    # Print environment config diagnostics
    logEnvironmentConfig "$secret_file"
    
    if [ "${SKIP_CLEAN:-false}" = "true" ]; then
        echo "⚡ FAST BUILD: Skipping clean step for incremental build speed..."
    else
        print_running_flutter_clean
        # Only wipe the two output paths that can actually hold a stale
        # artifact from a previous flavor - flutter build ipa always names
        # the archive "Runner.xcarchive" and the ipa search glob isn't
        # flavor-scoped either, so *those* need clearing. build/ios/SourcePackages
        # (Xcode's local SPM checkout cache, -clonedSourcePackagesDirPath) does
        # NOT - wiping the whole build/ios tree here was forcing Xcode to
        # re-fetch/re-verify every SPM dependency from its remote origin on
        # every single build ("Xcode is fetching Swift Package Manager
        # dependencies... (cached)" still taking 2-3 minutes despite being
        # "cached", because the per-project checkout it validates against was
        # deleted each time) instead of reusing the already-resolved checkout.
        # Also preserves Android's build/app/* Gradle/Kotlin cache in a
        # combined deploy_both run, same reasoning as the Android-side fix.
        chmod -R 777 build/ios/archive build/ios/ipa 2>/dev/null || true
        rm -rf build/ios/archive build/ios/ipa .dart_tool ios/Flutter/Generated.xcconfig ios/Flutter/flutter_export_environment.sh
    fi
    print_running_flutter_pub_get
    flutter pub get
    # Force TRACK_WIDGET_CREATION=false to prevent debug instrumentation in release builds
    # (flutter pub get may set this to true if last run was in debug context)
    if [ -f "ios/Flutter/Generated.xcconfig" ]; then
        sed -i '' 's/TRACK_WIDGET_CREATION=true/TRACK_WIDGET_CREATION=false/' ios/Flutter/Generated.xcconfig
    fi
    
    # Version management
    if [ "${SKIP_VERSION_BUMP:-false}" != "true" ]; then
        perl -i -pe 's/version: (\d+\.\d+\.\d+)(?:\+(\d+))?/ "version: $1+" . (($2 || 0) + 1) /e' pubspec.yaml
    fi
    
    # iOS dependencies setup
    setup_ios_dependencies
    
    # Disable icon tree shaking to prevent Font subsetting crash (exit code -9)
    export TREE_SHAKE_ICONS=false
    
    # Extract API key if possible
    local apple_key=""
    local apple_issuer=""
    local apple_key_path=""
    
    if [ -f "env/$secret_file" ]; then
        apple_key="$(getValueByKey "APPLE_API_KEY" "env/$secret_file")"
        apple_issuer="$(getValueByKey "APPLE_API_ISSUER" "env/$secret_file")"
        if [ -n "$apple_key" ]; then
            # Resolve key path: prefer industry-standard locations before legacy workspace path.
            # Priority:
            #   1. APPLE_API_KEY_BASE64 already set (in-memory — no file needed)
            #   2. ~/.appstoreconnect/private_keys/  (Apple's own recommended location)
            #   3. ~/.private_keys/                   (Apple secondary fallback)
            #   4. <workspace>/private_keys/          (legacy — kept for backward compat)
            local _std_kp1="$HOME/.appstoreconnect/private_keys/AuthKey_${apple_key}.p8"
            local _std_kp2="$HOME/.private_keys/AuthKey_${apple_key}.p8"
            local _legacy_kp="$MELOS_ROOT_PATH/private_keys/AuthKey_${apple_key}.p8"
            if [ -n "${APPLE_API_KEY_BASE64:-}" ]; then
                mkdir -p "$HOME/.appstoreconnect/private_keys"
                echo "$APPLE_API_KEY_BASE64" | base64 -d > "$_std_kp1"
                chmod 600 "$_std_kp1"
                apple_key_path="$_std_kp1"
            elif [ -f "$_std_kp1" ]; then
                apple_key_path="$_std_kp1"
            elif [ -f "$_std_kp2" ]; then
                apple_key_path="$_std_kp2"
            else
                apple_key_path="$_legacy_kp"
            fi
        fi
    fi

    # Read export method from env var override or secrets config, default to app-store-connect
    local export_method="app-store-connect"
    local signing_cert="Apple Distribution"
    local configured_method="${EXPORT_METHOD:-}"
    if [ -z "$configured_method" ] && [ -f "env/$secret_file" ]; then
        configured_method="$(getValueByKey "EXPORT_METHOD" "env/$secret_file")"
    fi
    if [ "$configured_method" = "development" ] || [ "$configured_method" = "debugging" ]; then
        export_method="development"
        signing_cert="Apple Development"
    fi

    # Resolve ExportOptions.plist
    local export_plist=""
    generate_export_options_plist "$secret_file" "$signing_cert" "$export_method" "export_plist"

    # Build and export the IPA archive
    local ipa_build_status=0
    local ipa_build_log_file=""
    run_xcode_build_and_export "$env_name" "$secret_file" "$flutter_flavor" "$export_method" "$export_plist" "$apple_key" "$apple_issuer" "$apple_key_path" "ipa_build_status" "$app_name" "ipa_build_log_file"

    # Clean up the temporary plist file if created
    if [ -n "$export_plist" ] && [ -f "$export_plist" ]; then
        rm -f "$export_plist"
    fi

    if [ "$ipa_build_status" -ne 0 ]; then
        print_ios_root_cause_hints "$ipa_build_log_file"
        print_ios_build_failed_error "$ipa_build_status" "$app_name" "$secret_file"
        rm -f "$ipa_build_log_file"
        return "$ipa_build_status"
    fi
    rm -f "$ipa_build_log_file"
    
    if [ "$export_method" = "development" ]; then
        # Run device installation in a safe set +e block to prevent script aborts
        set +e
        auto_install_to_device "$app_name"
        set -e
    fi
}
