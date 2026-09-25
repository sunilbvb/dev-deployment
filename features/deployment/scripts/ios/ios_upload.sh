#!/usr/bin/env bash
#------------------------------------------------------------------------------
# ios_upload.sh - iOS Deployment upload automation functions
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# runWithIosEnv - Execute commands with iOS environment variables
#------------------------------------------------------------------------------
runWithIosEnv() {
    local command="${1:-}"
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
        print_command_required_error
        return 1
    fi
    
    if [[ "$command" == *"bundle exec"* ]]; then
        if ! BUNDLE_GEMFILE="$bundle_gemfile" bundle check >/dev/null 2>&1; then
            print_installing_ruby_gems
            BUNDLE_GEMFILE="$bundle_gemfile" bundle install || true
        fi
    fi
    
    # Check for required environment variables
    if [ -z "${APPLE_API_KEY:-}" ] || [ -z "${APPLE_API_ISSUER:-}" ]; then
        print_apple_creds_required_error
        return 1
    fi
    
    # Execute command with environment variables
    FASTLANE_SKIP_UPDATE_CHECK=1 \
    FASTLANE_HIDE_CHANGELOG=1 \
    BUNDLE_GEMFILE="$bundle_gemfile" \
    APPLE_API_KEY="$APPLE_API_KEY" \
    APPLE_API_ISSUER="$APPLE_API_ISSUER" \
    APPLE_API_KEY_BASE64="${APPLE_API_KEY_BASE64:-}" \
    APPLE_API_KEY_PATH="${APPLE_API_KEY_PATH:-}" \
    IOS_IPA_PATH="${IOS_IPA_PATH:-}" \
    IPA_PATH="${IPA_PATH:-}" \
    eval "$command"
}

#------------------------------------------------------------------------------
# upload_via_fastlane - Execute Fastlane upload command
#------------------------------------------------------------------------------
upload_via_fastlane() {
    local env_name="${1:-}"
    print_uploading_via_fastlane
    local deployment_fastlane_dir
    deployment_fastlane_dir="$(resolveDeploymentFastlaneDir)" || return 1
    if ! _retryUpload "TestFlight upload (Fastlane)" runWithIosEnv "cd '$deployment_fastlane_dir' && bundle exec fastlane ios testflight_build"; then
        print_testflight_upload_failed_fastlane_with_env "$env_name"
        return 1
    fi
}

#------------------------------------------------------------------------------
# upload_via_altool - Execute App Store altool upload command
#------------------------------------------------------------------------------
upload_via_altool() {
    local ipa_path="${1:-}"
    local apple_key="${2:-}"
    local apple_issuer="${3:-}"
    print_uploading_via_altool
    export IPA_PATH="$ipa_path"
    if ! _retryUpload "App Store upload (altool)" runWithIosEnv "xcrun altool --upload-app --type ios --file '$IPA_PATH' --apiKey '$apple_key' --apiIssuer '$apple_issuer'"; then
        print_app_store_upload_failed_altool
        return 1
    fi
}

#------------------------------------------------------------------------------
# uploadIPARaw - Generic raw IPA upload logic
#------------------------------------------------------------------------------
uploadIPARaw() {
    local app_name="${1:-}"
    local env_name="${2:-}"
    
    # Parameter validation
    if [ -z "$app_name" ] || [ -z "$env_name" ]; then
        print_upload_ipa_raw_validation_error
        return 1
    fi
    
    # Navigate to workspace root for centralized Fastlane
    cd "$MELOS_ROOT_PATH" || return 1
    
    # Export Apple API credentials
    local env_file=""
    if [ -f "apps/$app_name/env/$env_name.json" ]; then
        env_file="apps/$app_name/env/$env_name.json"
    elif [ -f "apps/$app_name/env/env.json" ]; then
        env_file="apps/$app_name/env/env.json"
    elif [ -f "env/$env_name.json" ]; then
        env_file="env/$env_name.json"
    elif [ -f "env/env.json" ]; then
        env_file="env/env.json"
    else
        print_env_json_missing_error "$app_name" "$env_name"
        return 1
    fi

    if [ -z "${APPLE_API_KEY:-}" ]; then
        APPLE_API_KEY="$(getValueByKey "APPLE_API_KEY" "$env_file")"
        export APPLE_API_KEY
    fi
    if [ -z "${APPLE_API_ISSUER:-}" ]; then
        APPLE_API_ISSUER="$(getValueByKey "APPLE_API_ISSUER" "$env_file")"
        export APPLE_API_ISSUER
    fi
    if [ -z "${APPLE_API_KEY_PATH:-}" ]; then
        if [ -n "${APPLE_API_KEY:-}" ] && [ -f "$HOME/.appstoreconnect/private_keys/AuthKey_${APPLE_API_KEY}.p8" ]; then
            export APPLE_API_KEY_PATH="$HOME/.appstoreconnect/private_keys/AuthKey_${APPLE_API_KEY}.p8"
        elif [ -n "${APPLE_API_KEY:-}" ] && [ -f "$HOME/.private_keys/AuthKey_${APPLE_API_KEY}.p8" ]; then
            export APPLE_API_KEY_PATH="$HOME/.private_keys/AuthKey_${APPLE_API_KEY}.p8"
        else
            export APPLE_API_KEY_PATH="$MELOS_ROOT_PATH/private_keys/AuthKey_${APPLE_API_KEY}.p8"
        fi
    fi
    
    # Debug output
    print_apple_creds_debug "${APPLE_API_KEY:-}" "${APPLE_API_ISSUER:-}" "${APPLE_API_KEY_PATH}"
    
    # Locate IPA file (from app directory)
    cd "$MELOS_ROOT_PATH/apps/$app_name" || return 1
    local raw_ipa_path
    raw_ipa_path="$(findIpaFile)" || exit 2
    IOS_IPA_PATH="$(pwd)/$raw_ipa_path"
    export IOS_IPA_PATH
    
    # Upload to TestFlight using the configured tool (altool or fastlane)
    cd "$MELOS_ROOT_PATH" || return 1
    if [ "${UPLOAD_TOOL:-fastlane}" = "altool" ]; then
        upload_via_altool "$IOS_IPA_PATH" "$APPLE_API_KEY" "$APPLE_API_ISSUER"
    else
        upload_via_fastlane "$env_name"
    fi
}
