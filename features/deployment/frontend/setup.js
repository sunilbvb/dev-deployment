/**
 * setup.js — Deployment Setup Modal
 * Handles credential configuration, and command regeneration.
 * Keeps all logic separate from the main deployment console (app.js).
 */

const setupState = {
    apps: [],
    selectedAppId: null,
    deployConfig: { apps: {} },
    currentWebhooks: [],
};

const setupEls = {
    overlay: document.getElementById('setupOverlay'),
    openBtn: document.getElementById('openSetupBtn'),
    closeBtn: document.getElementById('closeSetupBtn'),
    appNav: document.getElementById('setupAppNav'),
    noApp: document.getElementById('setupNoApp'),
    form: document.getElementById('setupForm'),
    appTitle: document.getElementById('setupAppTitle'),
    appleId: document.getElementById('cfgAppleId'),
    issuerId: document.getElementById('cfgIssuerId'),
    playService: document.getElementById('cfgPlayService'),
    flavors: document.getElementById('cfgFlavors'),
    autoReleaseEnabled: document.getElementById('cfgAutoReleaseEnabled'),
    autoReleaseAction: document.getElementById('cfgAutoReleaseAction'),
    autoReleaseFlavors: document.getElementById('cfgAutoReleaseFlavors'),
    iosCertStatus: document.getElementById('iosCertStatus'),
    iosCertRecheckBtn: document.getElementById('iosCertRecheckBtn'),
    saveBtn: document.getElementById('saveConfigBtn'),
    regenerateBtn: document.getElementById('regenerateBtn'),
    scanBtn: document.getElementById('autoScanBtn'),
    scanAllBtn: document.getElementById('scanAllBtn'),
    // p8 upload elements
    p8Dropzone: document.getElementById('p8Dropzone'),
    p8FileInput: document.getElementById('p8FileInput'),
    p8DropzoneTitle: document.getElementById('p8DropzoneTitle'),
    p8UploadStatus: document.getElementById('p8UploadStatus'),
    p8CurrentKeyInfo: document.getElementById('p8CurrentKeyInfo'),
    p8CurrentKeyId: document.getElementById('p8CurrentKeyId'),
    p8CurrentKeyPath: document.getElementById('p8CurrentKeyPath'),
    // Notification webhook elements
    webhookUrl: document.getElementById('cfgWebhookUrl'),
    webhookEnabled: document.getElementById('cfgWebhookEnabled'),
    webhookProvider: document.getElementById('cfgWebhookProvider'),
    notifyOnSuccess: document.getElementById('cfgNotifyOnSuccess'),
    notifyOnFailure: document.getElementById('cfgNotifyOnFailure'),
    playConsoleTrack: document.getElementById('cfgPlayConsoleTrack'),
    wsWebhookUrl: document.getElementById('cfgWorkspaceWebhookUrl'),
    wsWebhookEnabled: document.getElementById('cfgWorkspaceWebhookEnabled'),
    wsWebhookProvider: document.getElementById('cfgWorkspaceWebhookProvider'),
    wsNotifyOnSuccess: document.getElementById('cfgWorkspaceNotifySuccess'),
    wsNotifyOnFailure: document.getElementById('cfgWorkspaceNotifyFailure'),
    testWebhookBtn: document.getElementById('testWebhookBtn'),
    testWebhookResult: document.getElementById('testWebhookResult'),
    openAddWebhookChannelBtn: document.getElementById('openAddWebhookChannelBtn'),
    webhookChannelsList: document.getElementById('webhookChannelsList'),
    webhookChannelsCountBadge: document.getElementById('webhookChannelsCountBadge'),
    webhookChannelModal: document.getElementById('webhookChannelModal'),
    closeWebhookChannelModalBtn: document.getElementById('closeWebhookChannelModalBtn'),
    cancelWebhookChannelBtn: document.getElementById('cancelWebhookChannelBtn'),
    saveWebhookChannelBtn: document.getElementById('saveWebhookChannelBtn'),
    channelModalTestBtn: document.getElementById('channelModalTestBtn'),
    channelModalTestFeedback: document.getElementById('channelModalTestFeedback'),
    channelModalId: document.getElementById('channelModalId'),
    channelModalName: document.getElementById('channelModalName'),
    channelModalUrl: document.getElementById('channelModalUrl'),
    channelModalProvider: document.getElementById('channelModalProvider'),
    channelModalPhone: document.getElementById('channelModalPhone'),
    channelModalTemplate: document.getElementById('channelModalTemplate'),
    channelModalHeaders: document.getElementById('channelModalHeaders'),
    channelModalSuccess: document.getElementById('channelModalSuccess'),
    channelModalFailure: document.getElementById('channelModalFailure'),
    channelModalEnabled: document.getElementById('channelModalEnabled'),
    channelModalWhatsAppSection: document.getElementById('channelModalWhatsAppSection'),
    channelModalCustomSection: document.getElementById('channelModalCustomSection'),
    channelModalTitle: document.getElementById('webhookChannelModalTitle'),
    incomingWebhookUrlDisplay: document.getElementById('incomingWebhookUrlDisplay'),
    copyIncomingWebhookUrlBtn: document.getElementById('copyIncomingWebhookUrlBtn'),
    incomingWebhookSnippetTabs: document.getElementById('incomingWebhookSnippetTabs'),
    incomingWebhookSnippetCode: document.getElementById('incomingWebhookSnippetCode'),
};

// Add App Elements
const addAppForm = document.getElementById('addAppForm');
const addCustomAppBtn = document.getElementById('addCustomAppBtn');
const cancelAddAppBtn = document.getElementById('cancelAddAppBtn');
const saveNewAppBtn = document.getElementById('saveNewAppBtn');

function openSetupModal() {
    setupEls.overlay.classList.add('ui-active');
    loadSetupData();
}

function closeSetupModal() {
    setupEls.overlay.classList.remove('ui-active');
    addAppForm.classList.add('hidden');
}

async function loadSetupData() {
    const [appsRes, configRes, templatesRes] = await Promise.all([
        fetch('/api/deployment/apps').then(r => r.json()),
        fetch('/api/deployment/deploy-config').then(r => r.json()),
        fetch('/api/deployment/templates').then(r => r.json()),
    ]);
    setupState.apps = (appsRes.apps || []).filter(a => !a.is_package);
    setupState.deployConfig = configRes.config || { apps: {} };
    renderReleaseActionOptions((templatesRes.templates || {}).release || []);
    renderSetupAppNav();
    if (setupState.apps.length > 0) {
        selectSetupApp(setupState.selectedAppId || setupState.apps[0].id);
    } else {
        setupEls.form.classList.add('hidden');
        setupEls.noApp.classList.remove('hidden');
        setupState.selectedAppId = null;
    }
    if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
}

function renderReleaseActionOptions(releaseTemplates) {
    setupEls.autoReleaseAction.innerHTML = releaseTemplates
        .map(t => `<option value="${escapeHtml(t.id)}">${escapeHtml(t.name)}</option>`)
        .join('');
    if (!releaseTemplates.length) {
        setupEls.autoReleaseAction.innerHTML = '<option value="release_push">Full Release (Tag & Push to Remote)</option>';
    }
}

// Shared cert-expiry check cache — read by app.js's renderCertExpiryBanner() so a
// check done here (opening Setup) doesn't get re-fetched again when the execution
// panel shows the same app's prod iOS command. Keyed by appId; no TTL (this is a
// low-traffic single-operator local tool) — the Re-check button bypasses it.
const _certCheckCache = {};

function getCachedCertCheck(appId) {
    return _certCheckCache[appId] || null;
}

function setCachedCertCheck(appId, result) {
    _certCheckCache[appId] = result;
}

function renderCertStatusBox(result) {
    if (!result || !result.success) {
        setupEls.iosCertStatus.dataset.status = 'unknown';
        setupEls.iosCertStatus.textContent = 'Could not check (server error).';
        return;
    }
    if (result.status === 'not_ios_app') {
        setupEls.iosCertStatus.dataset.status = 'unknown';
        setupEls.iosCertStatus.textContent = 'This app has no iOS target.';
        return;
    }
    const cert = result.certificate || {};
    const profile = result.provisioningProfile || {};
    const rank = { expired: 3, warning: 2, unknown: 1, ok: 0 };
    const worst = (rank[profile.status] || 0) > (rank[cert.status] || 0) ? profile : cert;
    const lines = [];
    if (cert.status && cert.status !== 'unknown') {
        lines.push(`Certificate: ${cert.status.toUpperCase()}${cert.expiresOn ? ` (expires ${cert.expiresOn})` : ''} — ${cert.source}${cert.bestEffort ? ' [best-effort]' : ''}`);
    }
    if (profile.status && profile.status !== 'unknown') {
        lines.push(`Profile: ${profile.status.toUpperCase()}${profile.expiresOn ? ` (expires ${profile.expiresOn})` : ''} — ${profile.source}${profile.bestEffort ? ' [best-effort]' : ''}`);
    }
    if (!lines.length) {
        lines.push('No certificate/profile signal found (Keychain, local files, or a prior build) — likely fine if using Cloud Managed signing.');
    }
    (result.warnings || []).forEach(w => lines.push(`⚠️ ${w}`));
    setupEls.iosCertStatus.dataset.status = worst.status || 'unknown';
    setupEls.iosCertStatus.textContent = lines.join('  ·  ');
}

async function fetchAndRenderCertStatus(appId, { bypassCache = false } = {}) {
    if (!appId) return;
    if (!bypassCache) {
        const cached = getCachedCertCheck(appId);
        if (cached) { renderCertStatusBox(cached); return; }
    }
    setupEls.iosCertStatus.dataset.status = 'unknown';
    setupEls.iosCertStatus.textContent = 'Checking...';
    try {
        const res = await fetch(`/api/deployment/ios-cert-check?app=${encodeURIComponent(appId)}&flavor=prod`);
        const result = await res.json();
        setCachedCertCheck(appId, result);
        if (setupState.selectedAppId === appId) renderCertStatusBox(result);
    } catch (error) {
        setupEls.iosCertStatus.dataset.status = 'unknown';
        setupEls.iosCertStatus.textContent = `Check failed: ${error.message}`;
    }
}

setupEls.iosCertRecheckBtn.addEventListener('click', () => fetchAndRenderCertStatus(setupState.selectedAppId, { bypassCache: true }));

function renderSetupAppNav() {
    const setupAppList = document.getElementById('setupAppList');
    setupAppList.innerHTML = '';
    if (!setupState.apps.length) {
        setupAppList.innerHTML = '<div style="padding: 10px 8px; font-size: 0.75rem; color: var(--ui-text-muted); line-height: 1.4;">No apps configured yet. Click below to add an app.</div>';
        return;
    }
    setupState.apps.forEach(app => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ui-sidebar-item' + (app.id === setupState.selectedAppId ? ' ui-active' : '');
        btn.dataset.appId = app.id;
        btn.innerHTML = `
            <span class="app-dot" style="background:${escapeHtml(app.color || '#3b82f6')};"></span>
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(app.name || app.id)}</span>
        `;
        btn.addEventListener('click', () => selectSetupApp(app.id));
        setupAppList.appendChild(btn);
    });
}

function getActiveFlavors() {
    const val = setupEls.flavors.value.trim();
    if (!val || val.toLowerCase() === 'none' || val.toLowerCase() === 'single') return [];
    return val.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
}

function renderDynamicFields(flavors, cfg) {
    const bundleContainer = document.getElementById('dynamicBundleIdsContainer');
    const packageContainer = document.getElementById('dynamicPackageNamesContainer');
    const servicesContainer = document.getElementById('dynamicGoogleServicesContainer');

    bundleContainer.innerHTML = '';
    packageContainer.innerHTML = '';
    servicesContainer.innerHTML = '';

    if (!flavors || flavors.length === 0) {
        // ── Single App Mode (No Flavors) ──
        // iOS Bundle ID Input
        const bundleField = document.createElement('div');
        bundleField.className = 'ui-field';
        bundleField.style.marginBottom = '0';
        bundleField.innerHTML = `
            <label class="ui-label">iOS Bundle Identifier</label>
            <input type="text" class="ui-input" id="cfgBundle_single" placeholder="e.g. com.example.app" value="${escapeHtml(cfg.bundle_id || cfg.bundle_id_prod || '')}">
            <span class="ui-help-text">Used for TestFlight uploads and provisioning profile verification.</span>
        `;
        bundleContainer.appendChild(bundleField);

        // Android Package ID Input
        const packageField = document.createElement('div');
        packageField.className = 'ui-field';
        packageField.style.marginBottom = '0';
        packageField.innerHTML = `
            <label class="ui-label">Android Package Name (Application ID)</label>
            <input type="text" class="ui-input" id="cfgAndroidPackage_single" placeholder="e.g. com.example.app" value="${escapeHtml(cfg.android_package || cfg.android_package_prod || '')}">
            <span class="ui-help-text">Matches applicationId in build.gradle(.kts) for Play Store deployment.</span>
        `;
        packageContainer.appendChild(packageField);

        // Firebase Client Config (Android & iOS)
        const notice = document.createElement('div');
        notice.className = 'cert-status-box';
        notice.dataset.status = 'info';
        notice.style.marginBottom = '14px';
        notice.style.fontSize = '0.82rem';
        notice.style.lineHeight = '1.45';
        notice.innerHTML = `
            <strong>💡 Single-App Project (No Flavors):</strong> Standard Firebase files live directly in project folders:
            <code>android/app/google-services.json</code> and <code>ios/Runner/GoogleService-Info.plist</code>.
            If kept in <code>private_keys/</code> or a custom directory, provide paths below.
        `;
        servicesContainer.appendChild(notice);

        const grid = document.createElement('div');
        grid.className = 'dynamic-inputs-grid';

        const gServicesField = document.createElement('div');
        gServicesField.className = 'ui-field';
        gServicesField.style.marginBottom = '0';
        gServicesField.innerHTML = `
            <label class="ui-label">Android (google-services.json) Path</label>
            <input type="text" class="ui-input" id="cfgGoogleServices_single" placeholder="android/app/google-services.json" value="${escapeHtml(cfg.google_services_json || cfg.google_services_json_prod || '')}">
        `;
        grid.appendChild(gServicesField);

        const gInfoField = document.createElement('div');
        gInfoField.className = 'ui-field';
        gInfoField.style.marginBottom = '0';
        gInfoField.innerHTML = `
            <label class="ui-label">iOS (GoogleService-Info.plist) Path</label>
            <input type="text" class="ui-input" id="cfgGoogleServiceInfo_single" placeholder="ios/Runner/GoogleService-Info.plist" value="${escapeHtml(cfg.google_service_info_plist || cfg.google_service_info_plist_prod || '')}">
        `;
        grid.appendChild(gInfoField);

        servicesContainer.appendChild(grid);
        return;
    }

    // ── Flavored App Mode ──
    const notice = document.createElement('div');
    notice.className = 'cert-status-box';
    notice.dataset.status = 'info';
    notice.style.marginBottom = '14px';
    notice.style.fontSize = '0.82rem';
    notice.style.lineHeight = '1.45';
    notice.innerHTML = `
        <strong>Flavor-Specific Firebase Config:</strong> Provide individual client files per environment flavor.
    `;
    servicesContainer.appendChild(notice);

    const servicesGrid = document.createElement('div');
    servicesGrid.className = 'dynamic-inputs-grid';

    flavors.forEach(flavor => {
        // iOS Bundle ID Input
        const bundleField = document.createElement('div');
        bundleField.className = 'ui-field';
        bundleField.style.marginBottom = '0';
        bundleField.innerHTML = `
            <label class="ui-label">${flavor.toUpperCase()} Bundle ID</label>
            <input type="text" class="ui-input" id="cfgBundle_${flavor}" placeholder="com.example.app.${flavor}" value="${escapeHtml(cfg[`bundle_id_${flavor}`] || '')}">
        `;
        bundleContainer.appendChild(bundleField);

        // Android Package ID Input
        const packageField = document.createElement('div');
        packageField.className = 'ui-field';
        packageField.style.marginBottom = '0';
        packageField.innerHTML = `
            <label class="ui-label">${flavor.toUpperCase()} Package Name</label>
            <input type="text" class="ui-input" id="cfgAndroidPackage_${flavor}" placeholder="com.example.app.${flavor}" value="${escapeHtml(cfg[`android_package_${flavor}`] || '')}">
        `;
        packageContainer.appendChild(packageField);

        // Android google-services.json
        const androidField = document.createElement('div');
        androidField.className = 'ui-field';
        androidField.style.marginBottom = '0';
        androidField.innerHTML = `
            <label class="ui-label">${flavor.toUpperCase()} google-services.json (Android)</label>
            <input type="text" class="ui-input" id="cfgGoogleServices_${flavor}" placeholder="private_keys/Firebase/${flavor}/google-services.json" value="${escapeHtml(cfg[`google_services_json_${flavor}`] || '')}">
        `;
        servicesGrid.appendChild(androidField);

        // iOS GoogleService-Info.plist
        const iosField = document.createElement('div');
        iosField.className = 'ui-field';
        iosField.style.marginBottom = '0';
        iosField.innerHTML = `
            <label class="ui-label">${flavor.toUpperCase()} GoogleService-Info.plist (iOS)</label>
            <input type="text" class="ui-input" id="cfgGoogleServiceInfo_${flavor}" placeholder="private_keys/Firebase/${flavor}/GoogleService-Info.plist" value="${escapeHtml(cfg[`google_service_info_plist_${flavor}`] || '')}">
        `;
        servicesGrid.appendChild(iosField);
    });

    servicesContainer.appendChild(servicesGrid);
}

function selectSetupApp(appId) {
    setupState.selectedAppId = appId;
    renderSetupAppNav();
    addAppForm.classList.add('hidden');

    const app = setupState.apps.find(a => a.id === appId);
    const cfg = setupState.deployConfig.apps?.[appId] || {};

    setupEls.appTitle.textContent = app ? app.name : appId;
    
    const activeFlavors = cfg.flavors !== undefined && Array.isArray(cfg.flavors)
        ? cfg.flavors
        : [];
    setupEls.flavors.value = activeFlavors.join(', ');

    renderDynamicFields(activeFlavors, cfg);

    setupEls.appleId.value = cfg.apple_id || '';
    setupEls.issuerId.value = cfg.apple_issuer_id || '';
    setupEls.playService.value = cfg.play_service_account_path || '';

    setupEls.autoReleaseEnabled.checked = !!cfg.auto_release_on_success;
    setupEls.autoReleaseAction.value = cfg.auto_release_action || 'release_push';
    setupEls.autoReleaseFlavors.value = (cfg.auto_release_flavors || ['prod']).join(', ');

    // Populate notification settings (multi-channel, app & workspace fallback)
    const depCfg = setupState.deployConfig || {};
    setupState.currentWebhooks = Array.isArray(cfg.webhooks) ? JSON.parse(JSON.stringify(cfg.webhooks)) : [];
    renderWebhookChannels();
    updateIncomingWebhookSnippets();

    if (setupEls.webhookUrl) {
        setupEls.webhookUrl.value = cfg.webhook_url || '';
        setupEls.webhookEnabled.checked = cfg.webhook_enabled !== false;
        setupEls.webhookProvider.value = cfg.webhook_provider || 'auto';
        setupEls.notifyOnSuccess.checked = cfg.notify_on_success !== false;
        setupEls.notifyOnFailure.checked = cfg.notify_on_failure !== false;
        setupEls.playConsoleTrack.value = cfg.play_console_track || '';
    }
    if (setupEls.wsWebhookUrl) {
        setupEls.wsWebhookUrl.value = depCfg.workspace_webhook_url || '';
        setupEls.wsWebhookEnabled.checked = depCfg.workspace_webhook_enabled !== false;
        setupEls.wsWebhookProvider.value = depCfg.workspace_webhook_provider || 'auto';
        setupEls.wsNotifyOnSuccess.checked = depCfg.workspace_notify_on_success !== false;
        setupEls.wsNotifyOnFailure.checked = depCfg.workspace_notify_on_failure !== false;
    }
    if (setupEls.testWebhookResult) {
        setupEls.testWebhookResult.style.display = 'none';
    }

    renderP8KeyInfo(null);
    credEls.scanResults.innerHTML = '';
    loadCredentialStatus(appId);
    renderSetupPipelines(appId);

    fetchAndRenderCertStatus(appId);

    setupEls.noApp.classList.add('hidden');
    setupEls.form.classList.remove('hidden');
    if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
}

/** Render the configured .p8 key (from /api/deployment/credentials) beneath the dropzone. */
function renderP8KeyInfo(apple) {
    const hasKey = !!(apple && apple.exists);

    setupEls.p8DropzoneTitle.textContent = hasKey
        ? `✅ Key ${apple.key_id} configured (${scopeLabel(apple.source)}) — drop a new file to replace`
        : apple
            ? `⚠️ Key ${apple.key_id} is configured but its file is missing — drop it again`
            : 'Drag & drop AuthKey_XXXXXXXXXX.p8 or click to browse';

    if (apple) {
        setupEls.p8CurrentKeyInfo.style.display = 'block';
        setupEls.p8CurrentKeyId.textContent = apple.key_id;
        setupEls.p8CurrentKeyPath.textContent = apple.path;
        if (apple.issuer_id && !setupEls.issuerId.value) {
            setupEls.issuerId.value = apple.issuer_id;
        }
    } else {
        setupEls.p8CurrentKeyInfo.style.display = 'none';
    }

    // Hide the upload status from any previous operation
    setupEls.p8UploadStatus.style.display = 'none';
}

// Listen to flavor inputs changes to dynamically redraw fields
setupEls.flavors.addEventListener('input', () => {
    const cfg = setupState.deployConfig.apps?.[setupState.selectedAppId] || {};
    renderDynamicFields(getActiveFlavors(), cfg);
});

function readFormValues() {
    const flavors = getActiveFlavors();
    // Preserve any already-uploaded p8 fields
    const existingCfg = setupState.deployConfig.apps?.[setupState.selectedAppId] || {};
    const values = {
        flavors: flavors,
        apple_id: setupEls.appleId.value.trim(),
        apple_issuer_id: setupEls.issuerId.value.trim(),
        apple_key_id: existingCfg.apple_key_id || '',
        play_service_account_path: setupEls.playService.value.trim(),
        auto_release_on_success: setupEls.autoReleaseEnabled.checked,
        auto_release_action: setupEls.autoReleaseAction.value || 'release_push',
        auto_release_flavors: setupEls.autoReleaseFlavors.value.trim()
            ? setupEls.autoReleaseFlavors.value.split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
            : ['prod'],
        pipelines: existingCfg.pipelines || [],
        webhooks: setupState.currentWebhooks || [],
        webhook_url: setupEls.webhookUrl ? setupEls.webhookUrl.value.trim() : (existingCfg.webhook_url || ''),
        webhook_enabled: setupEls.webhookEnabled ? setupEls.webhookEnabled.checked : (existingCfg.webhook_enabled !== false),
        webhook_provider: setupEls.webhookProvider ? setupEls.webhookProvider.value : (existingCfg.webhook_provider || 'auto'),
        notify_on_success: setupEls.notifyOnSuccess ? setupEls.notifyOnSuccess.checked : (existingCfg.notify_on_success !== false),
        notify_on_failure: setupEls.notifyOnFailure ? setupEls.notifyOnFailure.checked : (existingCfg.notify_on_failure !== false),
        play_console_track: setupEls.playConsoleTrack ? setupEls.playConsoleTrack.value.trim() : (existingCfg.play_console_track || ''),
    };

    if (flavors.length === 0) {
        const bundleVal = document.getElementById('cfgBundle_single')?.value.trim() || '';
        const packageVal = document.getElementById('cfgAndroidPackage_single')?.value.trim() || '';
        const servicesVal = document.getElementById('cfgGoogleServices_single')?.value.trim() || '';
        const infoVal = document.getElementById('cfgGoogleServiceInfo_single')?.value.trim() || '';

        values.bundle_id = bundleVal;
        values.bundle_id_prod = bundleVal;
        values.android_package = packageVal;
        values.android_package_prod = packageVal;
        values.google_services_json = servicesVal;
        values.google_services_json_prod = servicesVal;
        values.google_service_info_plist = infoVal;
        values.google_service_info_plist_prod = infoVal;
    } else {
        flavors.forEach(flavor => {
            const bundleVal = document.getElementById(`cfgBundle_${flavor}`)?.value.trim() || '';
            const packageVal = document.getElementById(`cfgAndroidPackage_${flavor}`)?.value.trim() || '';
            const servicesVal = document.getElementById(`cfgGoogleServices_${flavor}`)?.value.trim() || '';
            const infoVal = document.getElementById(`cfgGoogleServiceInfo_${flavor}`)?.value.trim() || '';

            values[`bundle_id_${flavor}`] = bundleVal;
            values[`android_package_${flavor}`] = packageVal;
            values[`google_services_json_${flavor}`] = servicesVal;
            values[`google_service_info_plist_${flavor}`] = infoVal;
        });

        const primary = flavors.includes('prod') ? 'prod' : flavors[0];
        values.bundle_id = values[`bundle_id_${primary}`] || '';
        values.bundle_id_prod = values[`bundle_id_${primary}`] || '';
        values.android_package = values[`android_package_${primary}`] || '';
        values.android_package_prod = values[`android_package_${primary}`] || '';
        values.google_services_json = values[`google_services_json_${primary}`] || '';
        values.google_services_json_prod = values[`google_services_json_${primary}`] || '';
        values.google_service_info_plist = values[`google_service_info_plist_${primary}`] || '';
        values.google_service_info_plist_prod = values[`google_service_info_plist_${primary}`] || '';
    }

    return values;
}

async function saveDeployConfig() {
    if (!setupState.selectedAppId) { return; }
    if (!setupState.deployConfig.apps) { setupState.deployConfig.apps = {}; }

    const values = readFormValues();

    // A2 fix: warn when user has typed flavors but the project scan found none.
    // This prevents silent build failures from invalid --flavor flags.
    const typedFlavors = values.flavors || [];
    if (typedFlavors.length > 0) {
        const app = setupState.apps.find(a => a.id === setupState.selectedAppId);
        const savedCfg = setupState.deployConfig.apps[setupState.selectedAppId] || {};
        const hasScannedData = savedCfg.bundle_id || savedCfg.android_package;
        const scanFoundNoFlavors = Array.isArray(savedCfg.flavors) && savedCfg.flavors.length === 0;
        if (hasScannedData && scanFoundNoFlavors) {
            const appName = app ? app.name : setupState.selectedAppId;
            showToast(`⚠️ Warning: Autoscan found NO flavors for "${appName}". Typed flavors may cause build failures with --flavor flag. Leave Flavors empty for a single app.`, 'warning');
        }
    }

    setupState.deployConfig.apps[setupState.selectedAppId] = values;

    if (setupEls.wsWebhookUrl) {
        setupState.deployConfig.workspace_webhook_url = setupEls.wsWebhookUrl.value.trim();
        setupState.deployConfig.workspace_webhook_enabled = setupEls.wsWebhookEnabled.checked;
        setupState.deployConfig.workspace_webhook_provider = setupEls.wsWebhookProvider.value;
        setupState.deployConfig.workspace_notify_on_success = setupEls.wsNotifyOnSuccess.checked;
        setupState.deployConfig.workspace_notify_on_failure = setupEls.wsNotifyOnFailure.checked;
    }

    const res = await fetch('/api/deployment/deploy-config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(setupState.deployConfig),
    }).then(r => r.json());

    if (res.success) {
        showToast('Config saved!');
    } else {
        showToast('Error saving config: ' + (res.error || 'unknown'));
    }
}

async function regenerateAllCommands() {
    await saveDeployConfig();

    const res = await fetch('/api/deployment/regenerate-commands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    }).then(r => r.json());

    if (res.success) {
        showToast(`Generated ${res.count} commands! Reload the console.`);
        if (typeof loadApps === 'function') { loadApps(); }
    } else {
        showToast('Regen failed: ' + (res.error || 'unknown'));
    }
}

async function autoScanConfig() {
    if (!setupState.selectedAppId) { return; }

    setupEls.scanBtn.disabled = true;
    setupEls.scanBtn.querySelector('span').textContent = 'Scanning...';

    try {
        const res = await fetch(`/api/deployment/scan-config?app=${encodeURIComponent(setupState.selectedAppId)}`).then(r => r.json());
        if (!res.success) {
            showToast('Scan failed: ' + (res.error || 'unknown'));
            return;
        }

        const d = res.discovered || {};
        const detectedFlavors = d.flavors || [];

        // If app had empty flavors but scan detected flavors, update
        if (detectedFlavors.length > 0 && !setupEls.flavors.value.trim()) {
            setupEls.flavors.value = detectedFlavors.join(', ');
            renderDynamicFields(detectedFlavors, d);
        }

        const flavors = getActiveFlavors();
        let filled = 0;

        if (flavors.length === 0) {
            const bundleInput = document.getElementById('cfgBundle_single');
            const packageInput = document.getElementById('cfgAndroidPackage_single');
            const servicesInput = document.getElementById('cfgGoogleServices_single');
            const infoInput = document.getElementById('cfgGoogleServiceInfo_single');

            const scanBundle = d.bundle_id || d.bundle_id_prod;
            const scanPackage = d.android_package || d.android_package_prod;
            const scanServices = d.google_services_json || d.google_services_json_prod;
            const scanInfo = d.google_service_info_plist || d.google_service_info_plist_prod;

            if (bundleInput && scanBundle && (!bundleInput.value.trim() || bundleInput.value !== scanBundle)) {
                bundleInput.value = scanBundle;
                filled++;
            }
            if (packageInput && scanPackage && (!packageInput.value.trim() || packageInput.value !== scanPackage)) {
                packageInput.value = scanPackage;
                filled++;
            }
            if (servicesInput && scanServices && (!servicesInput.value.trim() || servicesInput.value !== scanServices)) {
                servicesInput.value = scanServices;
                filled++;
            }
            if (infoInput && scanInfo && (!infoInput.value.trim() || infoInput.value !== scanInfo)) {
                infoInput.value = scanInfo;
                filled++;
            }
        } else {
            flavors.forEach(flavor => {
                const bundleInput = document.getElementById(`cfgBundle_${flavor}`);
                const packageInput = document.getElementById(`cfgAndroidPackage_${flavor}`);
                const servicesInput = document.getElementById(`cfgGoogleServices_${flavor}`);
                const infoInput = document.getElementById(`cfgGoogleServiceInfo_${flavor}`);

                const scanBundle = d[`bundle_id_${flavor}`] || d.bundle_id || d.bundle_id_prod;
                const scanPackage = d[`android_package_${flavor}`] || d[`android_id_${flavor}`] || d.android_package || d.android_package_prod;
                const scanServices = d[`google_services_json_${flavor}`] || d.google_services_json;
                const scanInfo = d[`google_service_info_plist_${flavor}`] || d.google_service_info_plist;

                if (bundleInput && scanBundle && (!bundleInput.value.trim() || bundleInput.value !== scanBundle)) {
                    bundleInput.value = scanBundle;
                    filled++;
                }
                if (packageInput && scanPackage && (!packageInput.value.trim() || packageInput.value !== scanPackage)) {
                    packageInput.value = scanPackage;
                    filled++;
                }
                if (servicesInput && scanServices && (!servicesInput.value.trim() || servicesInput.value !== scanServices)) {
                    servicesInput.value = scanServices;
                    filled++;
                }
                if (infoInput && scanInfo && (!infoInput.value.trim() || infoInput.value !== scanInfo)) {
                    infoInput.value = scanInfo;
                    filled++;
                }
            });
        }

        if (d.play_service_account_path && !setupEls.playService.value.trim()) {
            setupEls.playService.value = d.play_service_account_path;
            filled++;
        }

        if (filled > 0) {
            showToast(`Auto-filled ${filled} field(s) from project scan (Android & iOS). Review and save.`);
        } else if (Object.keys(d).length > 0) {
            showToast('Fields matched project files — values are up to date.');
        } else {
            showToast('Scan complete — no configuration files found.');
        }
    } finally {
        setupEls.scanBtn.disabled = false;
        setupEls.scanBtn.querySelector('span').textContent = 'Auto-Scan App';
    }
}

async function autoScanAllConfig({ force = false } = {}) {
    if (!setupEls.scanAllBtn) return;
    setupEls.scanAllBtn.disabled = true;
    setupEls.scanAllBtn.querySelector('span').textContent = force ? 'Force Scanning...' : 'Scanning All...';

    try {
        const res = await fetch('/api/deployment/scan-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force }),
        }).then(r => r.json());
        if (res.success) {
            const diffCount = Object.keys(res.diffs || {}).length;
            const msg = force && diffCount > 0
                ? `Force-scanned ${res.count}/${res.total} app(s) — ${diffCount} updated. Review and save.`
                : `Scanned and saved configuration for ${res.count} of ${res.total} app(s)!`;
            showToast(msg);
            if (setupState.selectedAppId) {
                await loadSetupData();
                selectSetupApp(setupState.selectedAppId);
            }
        } else {
            showToast('Bulk scan failed: ' + (res.error || 'unknown'));
        }
    } catch (_) {
        showToast('Bulk scan failed — check network');
    } finally {
        setupEls.scanAllBtn.disabled = false;
        setupEls.scanAllBtn.querySelector('span').textContent = 'Scan All Apps';
    }
}

async function rescanWorkspace() {
    const btn = document.getElementById('rescanWorkspaceBtn');
    if (btn) {
        btn.disabled = true;
        btn.querySelector('span').textContent = 'Rescanning...';
    }
    try {
        const res = await fetch('/api/deployment/rescan-workspace', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        }).then(r => r.json());
        if (res.success) {
            showToast(`Workspace rescanned — found ${res.apps.length} app(s), scanned ${res.scanned}. Reloading…`);
            await loadSetupData();
            if (setupState.apps.length > 0) {
                selectSetupApp(setupState.apps[0].id);
            }
            if (typeof loadApps === 'function') loadApps();
        } else {
            showToast('Rescan failed: ' + (res.error || 'unknown'));
        }
    } catch (_) {
        showToast('Rescan failed — check network');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.querySelector('span').textContent = 'Rescan Workspace';
        }
    }
}

if (setupEls.scanAllBtn) {
    setupEls.scanAllBtn.addEventListener('click', () => autoScanAllConfig({ force: false }));
}

const rescanWorkspaceBtn = document.getElementById('rescanWorkspaceBtn');
if (rescanWorkspaceBtn) {
    rescanWorkspaceBtn.addEventListener('click', rescanWorkspace);
}

// ── Add App Path Detection & Registration ─────────────────────────────────────
const newAppPath = document.getElementById('newAppPath');
const detectAppPathBtn = document.getElementById('detectAppPathBtn');
const pathDetectBadge = document.getElementById('pathDetectBadge');

async function detectAppFromPath() {
    if (!newAppPath) return;
    const pathVal = newAppPath.value.trim();
    if (!pathVal) {
        if (pathDetectBadge) pathDetectBadge.style.display = 'none';
        return;
    }
    if (pathDetectBadge) {
        pathDetectBadge.style.display = 'block';
        pathDetectBadge.dataset.status = 'unknown';
        pathDetectBadge.textContent = 'Inspecting directory...';
    }

    try {
        const res = await fetch(`/api/deployment/inspect-path?path=${encodeURIComponent(pathVal)}`).then(r => r.json());
        if (!res.success || !res.exists) {
            if (pathDetectBadge) {
                pathDetectBadge.dataset.status = 'error';
                pathDetectBadge.textContent = `❌ ${res.error || 'Directory does not exist'}`;
            }
            return;
        }

        const app = res.detectedApp || (res.apps && res.apps.length > 0 ? res.apps[0] : null);
        if (app) {
            if (pathDetectBadge) {
                pathDetectBadge.dataset.status = 'valid';
                pathDetectBadge.innerHTML = `✅ Found <strong>${escapeHtml(app.name)}</strong> (${escapeHtml(app.stack || 'app')}) • v${escapeHtml(app.version || '1.0.0 (1)')}`;
            }
            const idInput = document.getElementById('newAppId');
            const nameInput = document.getElementById('newAppName');
            const verInput = document.getElementById('newAppVersion');

            if (idInput && (!idInput.value.trim() || idInput.dataset.autofilled === 'true')) {
                idInput.value = app.id;
                idInput.dataset.autofilled = 'true';
            }
            if (nameInput && (!nameInput.value.trim() || nameInput.dataset.autofilled === 'true')) {
                nameInput.value = app.name;
                nameInput.dataset.autofilled = 'true';
            }
            if (verInput && (!verInput.value.trim() || verInput.dataset.autofilled === 'true')) {
                verInput.value = app.version || '1.0.0 (1)';
                verInput.dataset.autofilled = 'true';
            }
        } else {
            if (pathDetectBadge) {
                pathDetectBadge.dataset.status = 'warning';
                pathDetectBadge.textContent = 'ℹ️ Folder found, but no pubspec.yaml / package.json detected. Configure manually.';
            }
        }
    } catch (err) {
        if (pathDetectBadge) {
            pathDetectBadge.dataset.status = 'error';
            pathDetectBadge.textContent = `❌ Detection failed: ${err.message}`;
        }
    }
}

if (detectAppPathBtn) {
    detectAppPathBtn.addEventListener('click', detectAppFromPath);
}
if (newAppPath) {
    newAppPath.addEventListener('blur', () => {
        if (newAppPath.value.trim() && !document.getElementById('newAppId')?.value.trim()) {
            detectAppFromPath();
        }
    });
}

// Register App Actions
addCustomAppBtn.addEventListener('click', () => {
    setupEls.form.classList.add('hidden');
    setupEls.noApp.classList.add('hidden');
    addAppForm.classList.remove('hidden');
    if (newAppPath) newAppPath.value = '';
    if (pathDetectBadge) pathDetectBadge.style.display = 'none';
    if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
});

cancelAddAppBtn.addEventListener('click', () => {
    addAppForm.classList.add('hidden');
    if (setupState.selectedAppId) {
        setupEls.form.classList.remove('hidden');
    } else {
        setupEls.noApp.classList.remove('hidden');
    }
});

saveNewAppBtn.addEventListener('click', async () => {
    const id = document.getElementById('newAppId').value.trim();
    const name = document.getElementById('newAppName').value.trim();
    const version = document.getElementById('newAppVersion').value.trim() || '1.0.0 (1)';
    const path = newAppPath ? newAppPath.value.trim() : '';

    if (!id || !name) {
        showToast('App ID and App Name are required!');
        return;
    }

    const res = await fetch('/api/deployment/apps/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, name, version, path }),
    }).then(r => r.json());

    if (res.success) {
        showToast('App registered and auto-scanned from project!');
        addAppForm.classList.add('hidden');
        document.getElementById('newAppId').value = '';
        document.getElementById('newAppName').value = '';
        document.getElementById('newAppVersion').value = '';
        if (newAppPath) newAppPath.value = '';
        if (pathDetectBadge) pathDetectBadge.style.display = 'none';
        await loadSetupData();
        selectSetupApp(id);

        if (typeof loadApps === 'function') { loadApps(); }
    } else {
        showToast('Failed to register app: ' + (res.error || 'unknown'));
    }
});

// Wire up events
setupEls.openBtn.addEventListener('click', openSetupModal);
setupEls.closeBtn.addEventListener('click', closeSetupModal);
setupEls.overlay.addEventListener('click', e => { if (e.target === setupEls.overlay) { closeSetupModal(); } });
setupEls.saveBtn.addEventListener('click', saveDeployConfig);
setupEls.regenerateBtn.addEventListener('click', regenerateAllCommands);
setupEls.scanBtn.addEventListener('click', autoScanConfig);

// ─────────────────────────────────────────────────────────────────────────────
// Outgoing Webhooks (Slack / Discord / Teams) Test
// ─────────────────────────────────────────────────────────────────────────────

async function runWebhookTest() {
    if (!setupEls.testWebhookBtn) return;
    const appUrl = setupEls.webhookUrl ? setupEls.webhookUrl.value.trim() : '';
    const wsUrl = setupEls.wsWebhookUrl ? setupEls.wsWebhookUrl.value.trim() : '';
    const url = appUrl || wsUrl;
    if (!url) {
        showToast('Please enter a Webhook URL (app or workspace) to test.', 'warning');
        return;
    }
    const provider = appUrl ? setupEls.webhookProvider.value : setupEls.wsWebhookProvider.value;
    setupEls.testWebhookBtn.disabled = true;
    setupEls.testWebhookBtn.querySelector('span').textContent = 'Testing...';
    if (setupEls.testWebhookResult) {
        setupEls.testWebhookResult.style.display = 'block';
        setupEls.testWebhookResult.dataset.status = 'unknown';
        setupEls.testWebhookResult.textContent = 'Posting test notification card...';
    }

    try {
        const res = await postJson('/api/deployment/notifications/test', {
            url,
            provider,
            app: setupState.selectedAppId || '',
        });
        if (res.success) {
            if (setupEls.testWebhookResult) {
                setupEls.testWebhookResult.dataset.status = 'valid';
                setupEls.testWebhookResult.innerHTML = `✅ Delivered to <strong>${escapeHtml((res.provider || provider).toUpperCase())}</strong> (HTTP ${res.statusCode})! Check your channel.`;
            }
            showToast('✅ Webhook test card delivered!');
        } else {
            if (setupEls.testWebhookResult) {
                setupEls.testWebhookResult.dataset.status = 'error';
                setupEls.testWebhookResult.innerHTML = `❌ Delivery failed: ${escapeHtml(res.error || ('HTTP ' + res.statusCode))}`;
            }
            showToast('Webhook test failed: ' + (res.error || 'HTTP error'));
        }
    } catch (err) {
        if (setupEls.testWebhookResult) {
            setupEls.testWebhookResult.dataset.status = 'error';
            setupEls.testWebhookResult.innerHTML = `❌ Network error: ${escapeHtml(err.message)}`;
        }
        showToast('Network error: ' + err.message);
    } finally {
        setupEls.testWebhookBtn.disabled = false;
        setupEls.testWebhookBtn.querySelector('span').textContent = 'Test Webhook';
    }
}

if (setupEls.testWebhookBtn) {
    setupEls.testWebhookBtn.addEventListener('click', runWebhookTest);
}

// ─────────────────────────────────────────────────────────────────────────────
// Multi-Destination Webhooks & Incoming Ingestion Engine
// ─────────────────────────────────────────────────────────────────────────────

function getProviderBadgeVariant(provider) {
    switch ((provider || '').toLowerCase()) {
        case 'slack': return 'primary';
        case 'discord': return 'info';
        case 'teams': return 'primary';
        case 'google_chat': return 'success';
        case 'whatsapp': return 'success';
        case 'custom': return 'warning';
        default: return 'secondary';
    }
}

function getProviderDisplayName(provider) {
    switch ((provider || '').toLowerCase()) {
        case 'slack': return 'Slack';
        case 'discord': return 'Discord';
        case 'teams': return 'MS Teams';
        case 'google_chat': return 'Google Chat';
        case 'whatsapp': return 'WhatsApp';
        case 'custom': return 'Custom Template';
        case 'generic': return 'Generic JSON';
        default: return 'Auto-Detect';
    }
}

function renderWebhookChannels() {
    if (!setupEls.webhookChannelsList) return;
    const channels = setupState.currentWebhooks || [];
    if (setupEls.webhookChannelsCountBadge) {
        setupEls.webhookChannelsCountBadge.textContent = `${channels.length} Channel${channels.length === 1 ? '' : 's'}`;
    }

    if (channels.length === 0) {
        setupEls.webhookChannelsList.innerHTML = `
            <div style="padding: 14px; text-align: center; background: rgba(0,0,0,0.02); border: 1px dashed var(--ui-border-color); border-radius: 6px; font-size: 0.82rem; color: var(--ui-text-muted);">
                <span>No webhook channels configured yet. Click <strong>+ Add Channel</strong> to broadcast deployment notifications to Slack, Discord, WhatsApp, Teams, Google Chat, or custom HTTP templates simultaneously.</span>
            </div>
        `;
        return;
    }

    setupEls.webhookChannelsList.innerHTML = channels.map((ch, idx) => {
        const providerName = getProviderDisplayName(ch.provider);
        const badgeVariant = getProviderBadgeVariant(ch.provider);
        const name = escapeHtml(ch.name || `Channel #${idx + 1}`);
        const url = escapeHtml(ch.url || '');
        const isEnabled = ch.enabled !== false;
        const successBadge = ch.notify_on_success !== false ? '<span class="ui-badge" data-variant="success" style="font-size:0.65rem;">✅ Success</span>' : '';
        const failBadge = ch.notify_on_failure !== false ? '<span class="ui-badge" data-variant="error" style="font-size:0.65rem;">❌ Failure</span>' : '';
        const disabledBadge = !isEnabled ? '<span class="ui-badge" data-variant="secondary" style="font-size:0.65rem;">Disabled</span>' : '';
        const phoneBadge = ch.phone ? `<span class="ui-badge" data-variant="info" style="font-size:0.65rem;">📱 ${escapeHtml(ch.phone)}</span>` : '';

        return `
            <div class="ui-card" style="padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 0;">
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
                        <strong style="font-size: 0.88rem; color: var(--ui-text-primary);">${name}</strong>
                        <span class="ui-badge" data-variant="${badgeVariant}">${providerName}</span>
                        ${successBadge}
                        ${failBadge}
                        ${phoneBadge}
                        ${disabledBadge}
                    </div>
                    <div style="font-size: 0.76rem; color: var(--ui-text-muted); font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${url}
                    </div>
                </div>
                <div style="display: flex; gap: 6px; align-items: center; flex-shrink: 0;">
                    <button type="button" class="ui-button" data-variant="secondary" data-size="xs" data-action="test-channel" data-idx="${idx}" title="Test Channel">
                        <i data-lucide="send"></i>
                        <span>Test</span>
                    </button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-action="edit-channel" data-idx="${idx}" title="Edit Channel">
                        <i data-lucide="edit-2"></i>
                        <span>Edit</span>
                    </button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-action="delete-channel" data-idx="${idx}" title="Delete Channel" style="color: var(--ui-danger, #ef4444);">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
}

function syncChannelModalProviderSections() {
    const provider = setupEls.channelModalProvider ? setupEls.channelModalProvider.value : 'auto';
    if (setupEls.channelModalWhatsAppSection) {
        setupEls.channelModalWhatsAppSection.style.display = provider === 'whatsapp' ? 'block' : 'none';
    }
    if (setupEls.channelModalCustomSection) {
        setupEls.channelModalCustomSection.style.display = (provider === 'custom' || provider === 'generic') ? 'block' : 'none';
    }
}

function openWebhookChannelModal(idx = null) {
    if (!setupEls.webhookChannelModal) return;
    const channels = setupState.currentWebhooks || [];
    const isEdit = idx !== null && channels[idx];
    const ch = isEdit ? channels[idx] : null;

    if (setupEls.channelModalId) setupEls.channelModalId.value = isEdit ? String(idx) : '';
    if (setupEls.channelModalTitle) setupEls.channelModalTitle.textContent = isEdit ? 'Edit Webhook Channel' : 'Add Webhook Channel';
    if (setupEls.channelModalName) setupEls.channelModalName.value = ch ? (ch.name || '') : '';
    if (setupEls.channelModalUrl) setupEls.channelModalUrl.value = ch ? (ch.url || '') : '';
    if (setupEls.channelModalProvider) setupEls.channelModalProvider.value = ch ? (ch.provider || 'auto') : 'auto';
    if (setupEls.channelModalPhone) setupEls.channelModalPhone.value = ch ? (ch.phone || '') : '';
    if (setupEls.channelModalTemplate) setupEls.channelModalTemplate.value = ch ? (ch.custom_template || '') : '';

    if (setupEls.channelModalHeaders) {
        if (ch && ch.custom_headers) {
            if (typeof ch.custom_headers === 'object') {
                setupEls.channelModalHeaders.value = Object.entries(ch.custom_headers).map(([k, v]) => `${k}: ${v}`).join('\n');
            } else {
                setupEls.channelModalHeaders.value = String(ch.custom_headers);
            }
        } else {
            setupEls.channelModalHeaders.value = '';
        }
    }

    if (setupEls.channelModalSuccess) setupEls.channelModalSuccess.checked = ch ? ch.notify_on_success !== false : true;
    if (setupEls.channelModalFailure) setupEls.channelModalFailure.checked = ch ? ch.notify_on_failure !== false : true;
    if (setupEls.channelModalEnabled) setupEls.channelModalEnabled.checked = ch ? ch.enabled !== false : true;

    if (setupEls.channelModalTestFeedback) {
        setupEls.channelModalTestFeedback.style.display = 'none';
    }

    syncChannelModalProviderSections();
    setupEls.webhookChannelModal.classList.add('ui-active');
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
}

function closeWebhookChannelModal() {
    if (!setupEls.webhookChannelModal) return;
    setupEls.webhookChannelModal.classList.remove('ui-active');
}

function parseHeadersFromInput(text) {
    const raw = (text || '').trim();
    if (!raw) return null;
    if (raw.startsWith('{')) {
        try { return JSON.parse(raw); } catch (e) {}
    }
    const headers = {};
    raw.split('\n').forEach(line => {
        const colon = line.indexOf(':');
        if (colon > 0) {
            const k = line.substring(0, colon).trim();
            const v = line.substring(colon + 1).trim();
            if (k) headers[k] = v;
        }
    });
    return Object.keys(headers).length > 0 ? headers : null;
}

function saveWebhookChannel() {
    const url = setupEls.channelModalUrl ? setupEls.channelModalUrl.value.trim() : '';
    if (!url) {
        showToast('Webhook destination URL is required.', 'warning');
        return;
    }

    const provider = setupEls.channelModalProvider ? setupEls.channelModalProvider.value : 'auto';
    const name = (setupEls.channelModalName ? setupEls.channelModalName.value.trim() : '') || `${getProviderDisplayName(provider)} Channel`;
    const phone = setupEls.channelModalPhone ? setupEls.channelModalPhone.value.trim() : '';
    const template = setupEls.channelModalTemplate ? setupEls.channelModalTemplate.value.trim() : '';
    const headers = parseHeadersFromInput(setupEls.channelModalHeaders ? setupEls.channelModalHeaders.value : '');
    const notifyOnSuccess = setupEls.channelModalSuccess ? setupEls.channelModalSuccess.checked : true;
    const notifyOnFailure = setupEls.channelModalFailure ? setupEls.channelModalFailure.checked : true;
    const enabled = setupEls.channelModalEnabled ? setupEls.channelModalEnabled.checked : true;

    const channelObj = {
        name,
        url,
        provider,
        notify_on_success: notifyOnSuccess,
        notify_on_failure: notifyOnFailure,
        enabled,
    };
    if (phone) channelObj.phone = phone;
    if (template) channelObj.custom_template = template;
    if (headers) channelObj.custom_headers = headers;

    if (!Array.isArray(setupState.currentWebhooks)) {
        setupState.currentWebhooks = [];
    }

    const idVal = setupEls.channelModalId ? setupEls.channelModalId.value : '';
    if (idVal !== '') {
        const idx = parseInt(idVal, 10);
        if (!isNaN(idx) && idx >= 0 && idx < setupState.currentWebhooks.length) {
            setupState.currentWebhooks[idx] = channelObj;
        } else {
            setupState.currentWebhooks.push(channelObj);
        }
    } else {
        setupState.currentWebhooks.push(channelObj);
    }

    renderWebhookChannels();
    closeWebhookChannelModal();
    showToast(`Saved channel "${name}"`);
}

async function testModalWebhookChannel() {
    const url = setupEls.channelModalUrl ? setupEls.channelModalUrl.value.trim() : '';
    if (!url) {
        showToast('Enter a destination URL to test.', 'warning');
        return;
    }

    const provider = setupEls.channelModalProvider ? setupEls.channelModalProvider.value : 'auto';
    const phone = setupEls.channelModalPhone ? setupEls.channelModalPhone.value.trim() : '';
    const customTemplate = setupEls.channelModalTemplate ? setupEls.channelModalTemplate.value.trim() : '';
    const customHeaders = parseHeadersFromInput(setupEls.channelModalHeaders ? setupEls.channelModalHeaders.value : '');

    const btn = setupEls.channelModalTestBtn;
    const fb = setupEls.channelModalTestFeedback;

    if (btn) {
        btn.disabled = true;
        btn.querySelector('span').textContent = 'Testing...';
    }
    if (fb) {
        fb.style.display = 'block';
        fb.dataset.status = 'unknown';
        fb.textContent = 'Sending test notification...';
    }

    try {
        const res = await postJson('/api/deployment/notifications/test', {
            url,
            provider,
            app: setupState.selectedAppId || '',
            custom_template: customTemplate,
            custom_headers: customHeaders,
            phone,
        });

        if (res.success) {
            if (fb) {
                fb.dataset.status = 'valid';
                fb.innerHTML = `✅ Delivered to <strong>${escapeHtml((res.provider || provider).toUpperCase())}</strong> (HTTP ${res.statusCode})!`;
            }
            showToast('✅ Webhook channel test succeeded!');
        } else {
            if (fb) {
                fb.dataset.status = 'error';
                fb.innerHTML = `❌ Failed: ${escapeHtml(res.error || ('HTTP ' + res.statusCode))}`;
            }
            showToast('Channel test failed: ' + (res.error || 'HTTP error'), 'warning');
        }
    } catch (err) {
        if (fb) {
            fb.dataset.status = 'error';
            fb.innerHTML = `❌ Network error: ${escapeHtml(err.message)}`;
        }
        showToast('Network error: ' + err.message, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.querySelector('span').textContent = 'Test Channel';
        }
    }
}

async function testIndividualChannel(idx) {
    const ch = (setupState.currentWebhooks || [])[idx];
    if (!ch || !ch.url) {
        showToast('Invalid channel configuration', 'warning');
        return;
    }
    showToast(`Testing "${ch.name || ch.url}"...`);
    try {
        const res = await postJson('/api/deployment/notifications/test', {
            url: ch.url,
            provider: ch.provider || 'auto',
            app: setupState.selectedAppId || '',
            custom_template: ch.custom_template || '',
            custom_headers: ch.custom_headers || null,
            phone: ch.phone || '',
        });
        if (res.success) {
            showToast(`✅ "${ch.name || 'Channel'}" delivered successfully (HTTP ${res.statusCode})!`);
        } else {
            showToast(`❌ Test failed: ${res.error || ('HTTP ' + res.statusCode)}`, 'warning');
        }
    } catch (err) {
        showToast(`❌ Error: ${err.message}`, 'error');
    }
}

// Incoming Webhook Snippets
let activeSnippetTab = 'curl';

function updateIncomingWebhookSnippets(tab = activeSnippetTab) {
    activeSnippetTab = tab;
    const appId = setupState.selectedAppId || 'my_app';
    const baseUrl = `${window.location.origin}/api/deployment/webhook/incoming`;
    if (setupEls.incomingWebhookUrlDisplay) {
        setupEls.incomingWebhookUrlDisplay.value = baseUrl;
    }

    if (!setupEls.incomingWebhookSnippetCode) return;

    let snippet = '';
    switch (tab) {
        case 'curl':
            snippet = `# Trigger standard build command via cURL:\ncurl -X POST "${baseUrl}" \\\n  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \\\n  -H "Content-Type: application/json" \\\n  -d '{"app": "${appId}", "flavor": "prod", "templateId": "build_aab"}'`;
            break;
        case 'pipeline':
            snippet = `# Trigger an automated multi-step pipeline:\ncurl -X POST "${baseUrl}" \\\n  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \\\n  -H "Content-Type: application/json" \\\n  -d '{"app": "${appId}", "pipeline": "full_release", "flavor": "prod"}'`;
            break;
        case 'github':
            snippet = `# In GitHub Actions Workflow (.github/workflows/deploy.yml):\n- name: Trigger Deploy Pipeline\n  run: |\n    curl -s -X POST "${baseUrl}" \\\n      -H "X-Webhook-Secret: \${{ secrets.WEBHOOK_SECRET }}" \\\n      -H "Content-Type: application/json" \\\n      -d '{"app": "${appId}", "pipeline": "full_release"}'`;
            break;
        case 'gitlab':
            snippet = `# In GitLab CI (.gitlab-ci.yml):\ndeploy_step:\n  script:\n    - 'curl -s -X POST "${baseUrl}" -H "X-Gitlab-Token: $WEBHOOK_SECRET" -H "Content-Type: application/json" -d "{\\"app\\": \\"${appId}\\", \\"flavor\\": \\"prod\\", \\"templateId\\": \\"build_aab\\"}"'`;
            break;
        case 'slack':
            snippet = `# Slack Slash Command Integration (/deploy):\n# Request URL: ${baseUrl}\n# Method: POST\n# Usage in Slack:\n/deploy ${appId} prod build_aab\n# Or to trigger pipeline:\n/deploy pipeline full_release ${appId}`;
            break;
        default:
            snippet = `curl -X POST "${baseUrl}" -H "X-Webhook-Secret: $WEBHOOK_SECRET" -d '{"app": "${appId}"}'`;
    }

    setupEls.incomingWebhookSnippetCode.textContent = snippet;
}

// Wire Multi-Channel Webhook UI Events
if (setupEls.openAddWebhookChannelBtn) {
    setupEls.openAddWebhookChannelBtn.addEventListener('click', () => openWebhookChannelModal(null));
}
if (setupEls.closeWebhookChannelModalBtn) {
    setupEls.closeWebhookChannelModalBtn.addEventListener('click', closeWebhookChannelModal);
}
if (setupEls.cancelWebhookChannelBtn) {
    setupEls.cancelWebhookChannelBtn.addEventListener('click', closeWebhookChannelModal);
}
if (setupEls.saveWebhookChannelBtn) {
    setupEls.saveWebhookChannelBtn.addEventListener('click', saveWebhookChannel);
}
if (setupEls.channelModalTestBtn) {
    setupEls.channelModalTestBtn.addEventListener('click', testModalWebhookChannel);
}
if (setupEls.channelModalProvider) {
    setupEls.channelModalProvider.addEventListener('change', syncChannelModalProviderSections);
}

if (setupEls.webhookChannelsList) {
    setupEls.webhookChannelsList.addEventListener('click', e => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        const idx = parseInt(btn.dataset.idx, 10);
        if (isNaN(idx)) return;

        if (action === 'test-channel') {
            testIndividualChannel(idx);
        } else if (action === 'edit-channel') {
            openWebhookChannelModal(idx);
        } else if (action === 'delete-channel') {
            const ch = (setupState.currentWebhooks || [])[idx];
            if (confirm(`Remove webhook channel "${ch ? (ch.name || 'Channel') : 'Channel'}"?`)) {
                setupState.currentWebhooks.splice(idx, 1);
                renderWebhookChannels();
                showToast('Channel removed');
            }
        }
    });
}

// Custom Template chip button insertions
document.querySelectorAll('.template-chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tag = btn.dataset.tag;
        if (!tag || !setupEls.channelModalTemplate) return;
        const textarea = setupEls.channelModalTemplate;
        const start = textarea.selectionStart || 0;
        const end = textarea.selectionEnd || 0;
        const val = textarea.value;
        textarea.value = val.substring(0, start) + tag + val.substring(end);
        textarea.focus();
        textarea.selectionStart = textarea.selectionEnd = start + tag.length;
    });
});

// Incoming webhook snippet tabs & copy
if (setupEls.incomingWebhookSnippetTabs) {
    setupEls.incomingWebhookSnippetTabs.addEventListener('click', e => {
        const btn = e.target.closest('button[data-snippet-tab]');
        if (!btn) return;
        setupEls.incomingWebhookSnippetTabs.querySelectorAll('button').forEach(b => {
            b.dataset.variant = 'secondary';
        });
        btn.dataset.variant = 'primary';
        updateIncomingWebhookSnippets(btn.dataset.snippetTab);
    });
}

if (setupEls.copyIncomingWebhookUrlBtn) {
    setupEls.copyIncomingWebhookUrlBtn.addEventListener('click', () => {
        const url = setupEls.incomingWebhookUrlDisplay ? setupEls.incomingWebhookUrlDisplay.value : '';
        if (url) {
            navigator.clipboard.writeText(url).then(() => {
                showToast('📋 Webhook URL copied to clipboard!');
            }).catch(() => {
                showToast('Failed to copy URL');
            });
        }
    });
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeSetupModal(); }
});

// ─────────────────────────────────────────────────────────────────────────────
// App Store Connect API Key (.p8) Dropzone
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Upload a .p8 file to the backend via multipart/form-data.
 * The backend extracts the Key ID from the filename, base64-encodes the content,
 * saves it to deploy_config.json, and writes the file to the Apple-standard path
 * ~/.appstoreconnect/private_keys/AuthKey_<KeyID>.p8 with chmod 600.
 */
async function uploadP8File(file) {
    if (!setupState.selectedAppId) {
        showToast('Please select an app first.');
        return;
    }
    if (!file || !file.name.toLowerCase().endsWith('.p8')) {
        showToast('Please select a valid .p8 file.');
        return;
    }

    // Show uploading state
    setupEls.p8DropzoneTitle.textContent = `⏳ Uploading ${file.name}…`;
    setupEls.p8UploadStatus.style.display = 'none';
    setupEls.p8Dropzone.classList.add('ui-dropzone--active');

    const formData = new FormData();
    formData.append('app_id', setupState.selectedAppId);
    formData.append('issuer_id', setupEls.issuerId.value.trim());
    formData.append('file', file, file.name);

    let res;
    try {
        res = await fetch('/api/deployment/p8/upload', {
            method: 'POST',
            body: formData,
            // Do NOT set Content-Type — browser sets it automatically with boundary
        }).then(r => r.json());
    } catch (err) {
        setupEls.p8Dropzone.classList.remove('ui-dropzone--active');
        setupEls.p8DropzoneTitle.textContent = '❌ Upload failed — network error';
        showToast('Upload failed: ' + err.message);
        return;
    }

    setupEls.p8Dropzone.classList.remove('ui-dropzone--active');

    if (res.success) {
        await loadCredentialStatus(setupState.selectedAppId);
        setupEls.p8UploadStatus.dataset.status = 'valid';
        setupEls.p8UploadStatus.textContent =
            `✅ Key ID: ${res.key_id}  •  Stored at: ${res.stored_path}`;
        setupEls.p8UploadStatus.style.display = 'block';
        showToast(`✅ Key ID ${res.key_id} uploaded and stored.`);
    } else {
        setupEls.p8DropzoneTitle.textContent = '❌ Upload failed — try again';
        setupEls.p8UploadStatus.dataset.status = 'error';
        setupEls.p8UploadStatus.textContent = `❌ ${res.error || 'Unknown error'}`;
        setupEls.p8UploadStatus.style.display = 'block';
        showToast('Upload error: ' + (res.error || 'Unknown'));
    }
}

// ── Click-to-browse ───────────────────────────────────────────────────────────
setupEls.p8Dropzone.addEventListener('click', () => {
    setupEls.p8FileInput.value = '';   // reset so same file can be re-selected
    setupEls.p8FileInput.click();
});

setupEls.p8FileInput.addEventListener('change', () => {
    const file = setupEls.p8FileInput.files?.[0];
    if (file) { uploadP8File(file); }
});

// ── Drag-and-drop ─────────────────────────────────────────────────────────────
setupEls.p8Dropzone.addEventListener('dragover', e => {
    e.preventDefault();
    setupEls.p8Dropzone.classList.add('ui-dropzone--active');
});

setupEls.p8Dropzone.addEventListener('dragleave', () => {
    setupEls.p8Dropzone.classList.remove('ui-dropzone--active');
});

setupEls.p8Dropzone.addEventListener('drop', e => {
    e.preventDefault();
    setupEls.p8Dropzone.classList.remove('ui-dropzone--active');
    const file = e.dataTransfer?.files?.[0];
    if (file) { uploadP8File(file); }
});

// ─────────────────────────────────────────────────────────────────────────────
// Tabs: show one configuration section at a time
// ─────────────────────────────────────────────────────────────────────────────

const SETUP_TAB_KEY = 'setup_active_tab';
const setupTabs = document.getElementById('setupTabs');

function showSetupTab(tab) {
    const buttons = [...setupTabs.querySelectorAll('.setup-tab')];
    if (!buttons.some(b => b.dataset.tab === tab)) tab = 'general';
    buttons.forEach(b => {
        const active = b.dataset.tab === tab;
        b.setAttribute('aria-selected', String(active));
        b.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('#setupForm [data-setup-panel]').forEach(panel => {
        panel.hidden = panel.dataset.setupPanel !== tab;
    });
    try { sessionStorage.setItem(SETUP_TAB_KEY, tab); } catch (_) { /* storage may be blocked */ }
}

setupTabs.addEventListener('click', event => {
    const btn = event.target.closest('.setup-tab');
    if (btn) showSetupTab(btn.dataset.tab);
});

setupTabs.addEventListener('keydown', event => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    const buttons = [...setupTabs.querySelectorAll('.setup-tab')];
    const idx = buttons.findIndex(b => b.getAttribute('aria-selected') === 'true');
    const next = buttons[(idx + (event.key === 'ArrowRight' ? 1 : buttons.length - 1)) % buttons.length];
    showSetupTab(next.dataset.tab);
    next.focus();
});

function setTabStatus(tab, ok) {
    const dot = setupTabs.querySelector(`[data-tab-status="${tab}"]`);
    if (!dot) return;
    dot.dataset.state = ok ? 'ok' : 'missing';
    dot.title = ok ? 'Upload credentials configured' : 'Upload credentials missing';
}

let initialTab = 'general';
try { initialTab = sessionStorage.getItem(SETUP_TAB_KEY) || 'general'; } catch (_) { /* ignore */ }
showSetupTab(initialTab);

// ─────────────────────────────────────────────────────────────────────────────
// Pipelines: list, create, edit, duplicate, delete
// ─────────────────────────────────────────────────────────────────────────────

const pipelineEls = {
    list: document.getElementById('setupPipelinesList'),
    newBtn: document.getElementById('newPipelineBtn'),
    card: document.getElementById('pipelineEditorCard'),
    title: document.getElementById('pipelineEditorTitle'),
    name: document.getElementById('pipelineEditName'),
    flavor: document.getElementById('pipelineEditFlavor'),
    addStepBtn: document.getElementById('addStepBtn'),
    addCustomStepBtn: document.getElementById('addCustomStepBtn'),
    stepsContainer: document.getElementById('pipelineEditStepsContainer'),
    cancelBtn: document.getElementById('cancelPipelineEditBtn'),
    saveBtn: document.getElementById('savePipelineBtn'),
    // Visual Step Picker Modal elements
    stepPickerModal: document.getElementById('stepPickerModal'),
    closeStepPickerModalBtn: document.getElementById('closeStepPickerModalBtn'),
    cancelStepPickerBtn: document.getElementById('cancelStepPickerBtn'),
    stepPickerFilterTabs: document.getElementById('stepPickerFilterTabs'),
    stepPickerSearch: document.getElementById('stepPickerSearch'),
    stepPickerTilesContainer: document.getElementById('stepPickerTilesContainer'),
    // Custom Shell Step Modal elements
    customStepModal: document.getElementById('customStepModal'),
    closeCustomStepModalBtn: document.getElementById('closeCustomStepModalBtn'),
    cancelCustomStepBtn: document.getElementById('cancelCustomStepBtn'),
    confirmAddCustomStepBtn: document.getElementById('confirmAddCustomStepBtn'),
    customStepLabelInput: document.getElementById('customStepLabelInput'),
    customStepCmdInput: document.getElementById('customStepCmdInput'),
    customStepContinueChk: document.getElementById('customStepContinueChk'),
};

let currentEditingPipeline = null;
let currentEditingSteps = [];
let availableAppCommands = [];
let currentStepFilterCat = 'all';

const STEP_TEMPLATES_CATALOG = [
    // Build
    { id: 'build_apk', category: 'build', name: 'Build Android APK', icon: 'smartphone', desc: 'Compile Android APK install package for local distribution or device testing.' },
    { id: 'build_aab', category: 'build', name: 'Build Android App Bundle (AAB)', icon: 'package', desc: 'Compile optimized Google Play Store release bundle ready for store upload.' },
    { id: 'build_ipa', category: 'build', name: 'Build iOS IPA', icon: 'apple', desc: 'Archive and codesign iOS IPA application for TestFlight or App Store.' },

    // Deploy & Upload
    { id: 'deploy_aab', category: 'deploy', name: 'Upload to Google Play', icon: 'upload-cloud', desc: 'Deploy App Bundle to Google Play Console track (Internal, Closed Beta, or Production).' },
    { id: 'deploy_ipa', category: 'deploy', name: 'Upload to TestFlight', icon: 'send', desc: 'Upload signed IPA to Apple App Store Connect TestFlight via API key.' },
    { id: 'deploy_both', category: 'deploy', name: 'Deploy Both Platforms', icon: 'rocket', desc: 'Sequentially build and deploy both Android AAB and iOS IPA.' },

    // Diagnostics & Health
    { id: 'sentinel', category: 'diagnostics', name: 'Deployment Sentinel Check', icon: 'shield-check', desc: 'Pre-flight check: validate keystores, bundle IDs, and certificates.', customCmd: 'python3 tool/sentinel.py' },
    { id: 'doctor', category: 'diagnostics', name: 'App Health Doctor', icon: 'activity', desc: 'Run diagnostics to verify local build toolchains & prerequisites.', customCmd: 'python3 -m unittest discover tests' },
    { id: 'unit_tests', category: 'diagnostics', name: 'Run Automated Tests', icon: 'check-circle-2', desc: 'Execute automated test suite before building artifacts.', customCmd: 'flutter test' },

    // Release Automation
    { id: 'release_changelog', category: 'release', name: 'Generate Changelog', icon: 'file-text', desc: 'Collate recent git commits into structured release notes.' },
    { id: 'release_bump_patch', category: 'release', name: 'Bump Patch Version', icon: 'hash', desc: 'Increment patch version (e.g. v1.0.0 → v1.0.1).' },
    { id: 'release_bump_minor', category: 'release', name: 'Bump Minor Version', icon: 'arrow-up-circle', desc: 'Increment minor version (e.g. v1.0.0 → v1.1.0).' },
    { id: 'release_bump_major', category: 'release', name: 'Bump Major Version', icon: 'award', desc: 'Increment major version (e.g. v1.0.0 → v2.0.0).' },
    { id: 'release_tag', category: 'release', name: 'Create Git Release Tag', icon: 'tag', desc: 'Tag git commit with current semantic version string.' },
    { id: 'release_push', category: 'release', name: 'Push to Remote Git', icon: 'git-pull-request', desc: 'Push current branch commits and newly created release tags.' },
];

async function renderSetupPipelines(appId) {
    if (!appId || !pipelineEls.list) return;
    const cfg = setupState.deployConfig.apps?.[appId] || {};
    const pipelines = cfg.pipelines || [];

    if (!pipelines.length) {
        pipelineEls.list.innerHTML = `
            <div style="padding: 16px; text-align: center; color: var(--ui-text-muted); font-size: 0.85rem; border: 1px dashed var(--ui-border-color); border-radius: 6px;">
                No pipelines created for this app yet. Click <strong>New Pipeline</strong> above to create your first automated workflow.
            </div>
        `;
        return;
    }

    pipelineEls.list.innerHTML = pipelines.map(pipe => {
        const stepCount = (pipe.steps || []).length;
        const flavorLabel = pipe.flavor ? `<span class="ui-badge" data-variant="info">${escapeHtml(pipe.flavor.toUpperCase())}</span>` : '<span class="ui-badge" data-variant="ghost">ANY FLAVOR</span>';
        const stepsPreview = (pipe.steps || []).map(s => escapeHtml(s.name || s.templateId || 'Custom')).join(' → ');

        return `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--ui-card-bg, #1e293b); border: 1px solid var(--ui-border-color); border-radius: 8px;">
                <div style="min-width: 0; flex: 1; margin-right: 12px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <strong style="font-size: 0.95rem;">${escapeHtml(pipe.name)}</strong>
                        ${flavorLabel}
                        <span style="font-size: 0.75rem; color: var(--ui-text-muted);">${stepCount} step${stepCount === 1 ? '' : 's'}</span>
                    </div>
                    <div style="font-size: 0.78rem; color: var(--ui-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${stepsPreview}">
                        ${stepsPreview || 'No steps configured'}
                    </div>
                </div>
                <div style="display: flex; gap: 6px; flex-shrink: 0;">
                    <button type="button" class="ui-button" data-variant="primary" data-size="sm" data-pipe-run="${escapeHtml(pipe.id)}" title="Run this pipeline on Dashboard">
                        <i data-lucide="play" style="width:12px;height:12px;"></i>
                        <span>Run</span>
                    </button>
                    <button type="button" class="ui-button" data-variant="secondary" data-size="sm" data-pipe-edit="${escapeHtml(pipe.id)}">Edit</button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="sm" data-pipe-dup="${escapeHtml(pipe.id)}" title="Duplicate">Duplicate</button>
                    <button type="button" class="ui-button" data-variant="danger" data-size="sm" data-pipe-del="${escapeHtml(pipe.id)}" title="Delete">Delete</button>
                </div>
            </div>
        `;
    }).join('');

    pipelineEls.list.querySelectorAll('[data-pipe-run]').forEach(btn => {
        btn.addEventListener('click', () => {
            const pipeId = btn.dataset.pipeRun;
            closeSetupModal();
            const pipeCard = document.querySelector(`[data-pipeline-id="${pipeId}"]`);
            if (pipeCard) {
                pipeCard.click();
                pipeCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                showToast(`Selected pipeline on dashboard. Click 'Run Pipeline' to execute.`);
            } else {
                showToast(`Pipeline selected. Switch to dashboard to run.`);
            }
        });
    });

    pipelineEls.list.querySelectorAll('[data-pipe-edit]').forEach(btn => {
        btn.addEventListener('click', () => {
            const p = pipelines.find(x => x.id === btn.dataset.pipeEdit);
            if (p) openPipelineEditor(p);
        });
    });

    pipelineEls.list.querySelectorAll('[data-pipe-dup]').forEach(btn => {
        btn.addEventListener('click', () => duplicatePipeline(btn.dataset.pipeDup));
    });

    pipelineEls.list.querySelectorAll('[data-pipe-del]').forEach(btn => {
        btn.addEventListener('click', () => deletePipeline(btn.dataset.pipeDel));
    });

    if (window.lucide && typeof lucide.createIcons === 'function') window.lucide.createIcons();
}

async function openPipelineEditor(pipe = null) {
    currentEditingPipeline = pipe ? JSON.parse(JSON.stringify(pipe)) : null;
    currentEditingSteps = pipe ? (pipe.steps || []).map(s => ({...s})) : [];

    pipelineEls.title.textContent = pipe ? `Edit Pipeline: ${pipe.name}` : 'New Pipeline';
    pipelineEls.name.value = pipe ? pipe.name : '';

    // Populate flavors
    const flavors = getActiveFlavors();
    pipelineEls.flavor.innerHTML = '<option value="">Any / Selected Flavor</option>' +
        flavors.map(f => `<option value="${escapeHtml(f)}" ${pipe && pipe.flavor === f ? 'selected' : ''}>${escapeHtml(f.toUpperCase())}</option>`).join('');

    // Fetch available commands for template picker
    try {
        const cmdRes = await fetch(`/api/deployment/commands?app=${encodeURIComponent(setupState.selectedAppId)}`).then(r => r.json());
        availableAppCommands = cmdRes.commands || [];
    } catch (_) {
        availableAppCommands = [];
    }

    renderPipelineEditingSteps();
    pipelineEls.card.classList.remove('hidden');
    pipelineEls.name.focus();
}

function closePipelineEditor() {
    currentEditingPipeline = null;
    currentEditingSteps = [];
    pipelineEls.card.classList.add('hidden');
}

function renderPipelineEditingSteps() {
    if (!currentEditingSteps.length) {
        pipelineEls.stepsContainer.innerHTML = `
            <div style="padding: 12px; text-align: center; color: var(--ui-text-muted); font-size: 0.8rem; border: 1px dashed var(--ui-border-color); border-radius: 6px;">
                No steps added yet. Click <strong>Add Template Step</strong> or <strong>Add Custom Shell Step</strong> above.
            </div>
        `;
        return;
    }

    const flavors = getActiveFlavors();

    pipelineEls.stepsContainer.innerHTML = currentEditingSteps.map((step, idx) => {
        const isCustom = !!step.command;
        const title = step.name || (isCustom ? step.command : step.templateId);
        const subtitle = isCustom ? `Custom: ${escapeHtml(step.command)}` : `Template: ${escapeHtml(step.templateId)}`;
        const badge = isCustom ? '<span class="ui-badge" data-variant="warning" style="margin-left:6px;">Custom</span>' : '';

        const flavorOptions = ['<option value="">Default (Inherit)</option>']
            .concat(flavors.map(f => `<option value="${escapeHtml(f)}" ${step.flavor === f ? 'selected' : ''}>${escapeHtml(f.toUpperCase())}</option>`))
            .join('');

        return `
            <div class="pipeline-step-item" data-step-idx="${idx}" style="display:flex; align-items:center; gap:10px; padding:10px 12px; background:var(--ui-card-bg, #1e293b); border:1px solid var(--ui-border-color); border-radius:6px;">
                <div class="pipeline-step-index" style="width:24px; height:24px; border-radius:50%; background:var(--ui-surface-2, rgba(255,255,255,0.06)); display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.75rem;">${idx + 1}</div>
                <div style="min-width: 0; flex: 1;">
                    <div style="font-weight: 600; font-size: 0.88rem; display:flex; align-items:center;">
                        ${escapeHtml(title)} ${badge}
                    </div>
                    <div style="font-size: 0.72rem; color: var(--ui-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${subtitle}
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:8px; flex-shrink:0;">
                    <select class="ui-select" data-step-flavor="${idx}" style="font-size:0.75rem; padding:3px 8px; height:28px; width:auto;" title="Step-specific flavor override">
                        ${flavorOptions}
                    </select>
                    <label class="ui-control" style="font-size: 0.75rem; margin: 0; display: flex; align-items: center; gap: 4px;" title="Continue running later steps even if this step fails">
                        <input type="checkbox" class="ui-checkbox" data-step-continue="${idx}" ${step.continueOnFailure ? 'checked' : ''}>
                        <span>Continue on fail</span>
                    </label>
                </div>
                <div class="step-actions" style="display:flex; gap:2px; flex-shrink:0;">
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-step-up="${idx}" ${idx === 0 ? 'disabled' : ''} title="Move Up">↑</button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-step-down="${idx}" ${idx === currentEditingSteps.length - 1 ? 'disabled' : ''} title="Move Down">↓</button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-step-rm="${idx}" title="Remove Step">×</button>
                </div>
            </div>
        `;
    }).join('');

    pipelineEls.stepsContainer.querySelectorAll('[data-step-flavor]').forEach(sel => {
        sel.addEventListener('change', () => {
            const idx = Number(sel.dataset.stepFlavor);
            if (currentEditingSteps[idx]) currentEditingSteps[idx].flavor = sel.value;
        });
    });

    pipelineEls.stepsContainer.querySelectorAll('[data-step-continue]').forEach(chk => {
        chk.addEventListener('change', () => {
            const idx = Number(chk.dataset.stepContinue);
            if (currentEditingSteps[idx]) currentEditingSteps[idx].continueOnFailure = chk.checked;
        });
    });

    pipelineEls.stepsContainer.querySelectorAll('[data-step-up]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = Number(btn.dataset.stepUp);
            if (idx > 0) {
                const temp = currentEditingSteps[idx];
                currentEditingSteps[idx] = currentEditingSteps[idx - 1];
                currentEditingSteps[idx - 1] = temp;
                renderPipelineEditingSteps();
            }
        });
    });

    pipelineEls.stepsContainer.querySelectorAll('[data-step-down]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = Number(btn.dataset.stepDown);
            if (idx < currentEditingSteps.length - 1) {
                const temp = currentEditingSteps[idx];
                currentEditingSteps[idx] = currentEditingSteps[idx + 1];
                currentEditingSteps[idx + 1] = temp;
                renderPipelineEditingSteps();
            }
        });
    });

    pipelineEls.stepsContainer.querySelectorAll('[data-step-rm]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = Number(btn.dataset.stepRm);
            currentEditingSteps.splice(idx, 1);
            renderPipelineEditingSteps();
        });
    });
}

function renderStepPickerTiles(filterCat = 'all', searchQuery = '') {
    if (!pipelineEls.stepPickerTilesContainer) return;
    currentStepFilterCat = filterCat;
    const query = searchQuery.trim().toLowerCase();

    const filtered = STEP_TEMPLATES_CATALOG.filter(item => {
        if (filterCat !== 'all' && item.category !== filterCat) return false;
        if (query) {
            const matchName = item.name.toLowerCase().includes(query);
            const matchDesc = item.desc.toLowerCase().includes(query);
            const matchId = item.id.toLowerCase().includes(query);
            if (!matchName && !matchDesc && !matchId) return false;
        }
        return true;
    });

    if (!filtered.length) {
        pipelineEls.stepPickerTilesContainer.innerHTML = `
            <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--ui-text-muted); font-size: 0.85rem;">
                No matching steps found for "${escapeHtml(searchQuery)}".
            </div>
        `;
        return;
    }

    const catBadges = {
        build: '<span class="ui-badge" data-variant="primary" style="font-size:0.65rem;">Build</span>',
        deploy: '<span class="ui-badge" data-variant="success" style="font-size:0.65rem;">Deploy</span>',
        diagnostics: '<span class="ui-badge" data-variant="warning" style="font-size:0.65rem;">Quality</span>',
        release: '<span class="ui-badge" data-variant="info" style="font-size:0.65rem;">Release</span>',
    };

    pipelineEls.stepPickerTilesContainer.innerHTML = filtered.map(item => {
        const badge = catBadges[item.category] || '';
        return `
            <div class="ui-card step-picker-tile" data-template-id="${escapeHtml(item.id)}" style="padding: 14px; cursor: pointer; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid var(--ui-border-color); border-radius: 8px; transition: border-color 0.15s, background 0.15s;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i data-lucide="${escapeHtml(item.icon)}" style="width: 18px; height: 18px; color: var(--ui-primary, #6366f1);"></i>
                            <strong style="font-size: 0.88rem;">${escapeHtml(item.name)}</strong>
                        </div>
                        ${badge}
                    </div>
                    <p style="font-size: 0.76rem; color: var(--ui-text-muted); margin: 0 0 10px 0; line-height: 1.35;">${escapeHtml(item.desc)}</p>
                </div>
                <div style="display: flex; justify-content: flex-end; align-items: center; margin-top: 6px;">
                    <button type="button" class="ui-button" data-variant="secondary" data-size="xs" style="pointer-events: none;">
                        <i data-lucide="plus"></i>
                        <span>Add</span>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    pipelineEls.stepPickerTilesContainer.querySelectorAll('.step-picker-tile').forEach(tile => {
        tile.addEventListener('click', () => {
            const tmplId = tile.dataset.templateId;
            const def = STEP_TEMPLATES_CATALOG.find(x => x.id === tmplId);
            if (!def) return;

            if (def.customCmd) {
                currentEditingSteps.push({
                    name: def.name,
                    command: def.customCmd,
                    continueOnFailure: false,
                });
            } else {
                currentEditingSteps.push({
                    templateId: def.id,
                    name: def.name,
                    continueOnFailure: false,
                });
            }

            closeStepPickerModal();
            renderPipelineEditingSteps();
            showToast(`Added step: ${def.name}`);
        });
    });

    if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
}

function openStepPickerModal() {
    if (!pipelineEls.stepPickerModal) return;
    if (pipelineEls.stepPickerSearch) pipelineEls.stepPickerSearch.value = '';
    if (pipelineEls.stepPickerFilterTabs) {
        pipelineEls.stepPickerFilterTabs.querySelectorAll('button').forEach(b => {
            b.dataset.variant = b.dataset.stepCat === 'all' ? 'primary' : 'secondary';
        });
    }
    renderStepPickerTiles('all', '');
    pipelineEls.stepPickerModal.classList.add('ui-active');
    if (pipelineEls.stepPickerSearch) pipelineEls.stepPickerSearch.focus();
}

function closeStepPickerModal() {
    if (pipelineEls.stepPickerModal) pipelineEls.stepPickerModal.classList.remove('ui-active');
}

function openCustomStepModal() {
    if (!pipelineEls.customStepModal) return;
    if (pipelineEls.customStepLabelInput) pipelineEls.customStepLabelInput.value = '';
    if (pipelineEls.customStepCmdInput) pipelineEls.customStepCmdInput.value = '';
    if (pipelineEls.customStepContinueChk) pipelineEls.customStepContinueChk.checked = false;
    pipelineEls.customStepModal.classList.add('ui-active');
    if (pipelineEls.customStepLabelInput) pipelineEls.customStepLabelInput.focus();
}

function closeCustomStepModal() {
    if (pipelineEls.customStepModal) pipelineEls.customStepModal.classList.remove('ui-active');
}

function addCustomStepFromModal() {
    const cmd = pipelineEls.customStepCmdInput ? pipelineEls.customStepCmdInput.value.trim() : '';
    if (!cmd) {
        showToast('Please enter a shell command.', 'warning');
        return;
    }
    const label = (pipelineEls.customStepLabelInput ? pipelineEls.customStepLabelInput.value.trim() : '') || cmd;
    const cont = pipelineEls.customStepContinueChk ? pipelineEls.customStepContinueChk.checked : false;

    currentEditingSteps.push({
        name: label,
        command: cmd,
        continueOnFailure: cont,
    });

    closeCustomStepModal();
    renderPipelineEditingSteps();
    showToast(`Added custom step: ${label}`);
}

async function savePipelineFromEditor() {
    const name = pipelineEls.name.value.trim();
    if (!name || name.length > 60) {
        showToast('Pipeline name is required (1–60 characters).', 'error');
        return;
    }

    if (!currentEditingSteps.length) {
        showToast('Pipeline must have at least 1 step.', 'error');
        return;
    }
    if (currentEditingSteps.length > 20) {
        showToast('Maximum 20 steps allowed per pipeline.', 'error');
        return;
    }

    const appId = setupState.selectedAppId;
    if (!appId) return;

    const flavor = pipelineEls.flavor.value || undefined;
    let pipeId = currentEditingPipeline?.id;
    if (!pipeId) {
        pipeId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
        if (!pipeId) pipeId = 'pipeline-' + Date.now();
    }

    const pipelineObj = {
        id: pipeId,
        name,
        flavor,
        steps: currentEditingSteps,
    };

    pipelineEls.saveBtn.disabled = true;
    try {
        const res = await fetch('/api/deployment/pipelines/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app: appId, pipeline: pipelineObj }),
        }).then(r => r.json());

        if (res.success) {
            showToast('Pipeline saved successfully!');
            closePipelineEditor();
            if (setupState.deployConfig.apps?.[appId]) {
                setupState.deployConfig.apps[appId].pipelines = res.pipelines;
            }
            renderSetupPipelines(appId);
            if (typeof loadCommands === 'function') {
                loadCommands(appId);
            }
        } else {
            showToast('Failed to save pipeline: ' + (res.error || 'unknown error'), 'error');
        }
    } catch (err) {
        showToast('Error saving pipeline: ' + err.message, 'error');
    } finally {
        pipelineEls.saveBtn.disabled = false;
    }
}

async function duplicatePipeline(pipeId) {
    const appId = setupState.selectedAppId;
    if (!appId) return;
    const cfg = setupState.deployConfig.apps?.[appId];
    if (!cfg || !cfg.pipelines) return;

    const source = cfg.pipelines.find(p => p.id === pipeId);
    if (!source) return;

    const copy = JSON.parse(JSON.stringify(source));
    copy.id = `${source.id}-copy`;
    let suffix = 1;
    while (cfg.pipelines.some(p => p.id === copy.id)) {
        copy.id = `${source.id}-copy-${suffix++}`;
    }
    copy.name = `${source.name} (Copy)`;

    try {
        const res = await fetch('/api/deployment/pipelines/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app: appId, pipeline: copy }),
        }).then(r => r.json());

        if (res.success) {
            showToast('Pipeline duplicated!');
            if (setupState.deployConfig.apps?.[appId]) {
                setupState.deployConfig.apps[appId].pipelines = res.pipelines;
            }
            renderSetupPipelines(appId);
            if (typeof loadCommands === 'function') loadCommands(appId);
        } else {
            showToast('Duplicate failed: ' + (res.error || ''), 'error');
        }
    } catch (err) {
        showToast('Duplicate failed: ' + err.message, 'error');
    }
}

async function deletePipeline(pipeId) {
    if (!confirm('Are you sure you want to delete this pipeline?')) return;
    const appId = setupState.selectedAppId;
    if (!appId) return;

    try {
        const res = await fetch('/api/deployment/pipelines/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app: appId, pipelineId: pipeId }),
        }).then(r => r.json());

        if (res.success) {
            showToast('Pipeline deleted.');
            if (currentEditingPipeline && currentEditingPipeline.id === pipeId) {
                closePipelineEditor();
            }
            if (setupState.deployConfig.apps?.[appId]) {
                setupState.deployConfig.apps[appId].pipelines = res.pipelines;
            }
            renderSetupPipelines(appId);
            if (typeof loadCommands === 'function') loadCommands(appId);
        } else {
            showToast('Delete failed: ' + (res.error || ''), 'error');
        }
    } catch (err) {
        showToast('Delete failed: ' + err.message, 'error');
    }
}

if (pipelineEls.newBtn) pipelineEls.newBtn.addEventListener('click', () => openPipelineEditor(null));
if (pipelineEls.cancelBtn) pipelineEls.cancelBtn.addEventListener('click', closePipelineEditor);
if (pipelineEls.saveBtn) pipelineEls.saveBtn.addEventListener('click', savePipelineFromEditor);
if (pipelineEls.addStepBtn) pipelineEls.addStepBtn.addEventListener('click', openStepPickerModal);
if (pipelineEls.addCustomStepBtn) pipelineEls.addCustomStepBtn.addEventListener('click', openCustomStepModal);
if (pipelineEls.closeStepPickerModalBtn) pipelineEls.closeStepPickerModalBtn.addEventListener('click', closeStepPickerModal);
if (pipelineEls.cancelStepPickerBtn) pipelineEls.cancelStepPickerBtn.addEventListener('click', closeStepPickerModal);
if (pipelineEls.stepPickerSearch) {
    pipelineEls.stepPickerSearch.addEventListener('input', e => renderStepPickerTiles(currentStepFilterCat, e.target.value));
}
if (pipelineEls.stepPickerFilterTabs) {
    pipelineEls.stepPickerFilterTabs.addEventListener('click', e => {
        const btn = e.target.closest('button[data-step-cat]');
        if (!btn) return;
        pipelineEls.stepPickerFilterTabs.querySelectorAll('button').forEach(b => { b.dataset.variant = 'secondary'; });
        btn.dataset.variant = 'primary';
        renderStepPickerTiles(btn.dataset.stepCat, pipelineEls.stepPickerSearch ? pipelineEls.stepPickerSearch.value : '');
    });
}
if (pipelineEls.closeCustomStepModalBtn) pipelineEls.closeCustomStepModalBtn.addEventListener('click', closeCustomStepModal);
if (pipelineEls.cancelCustomStepBtn) pipelineEls.cancelCustomStepBtn.addEventListener('click', closeCustomStepModal);
if (pipelineEls.confirmAddCustomStepBtn) pipelineEls.confirmAddCustomStepBtn.addEventListener('click', addCustomStepFromModal);

// ─────────────────────────────────────────────────────────────────────────────
// Credentials: status, Play key upload, folder scan & import
// ─────────────────────────────────────────────────────────────────────────────

const credEls = {
    playStatus: document.getElementById('playKeyStatus'),
    playChoose: document.getElementById('playKeyChooseBtn'),
    playFile: document.getElementById('playKeyFileInput'),
    playAllApps: document.getElementById('playKeyAllApps'),
    playRemove: document.getElementById('playKeyRemoveBtn'),
    scanFolder: document.getElementById('credScanFolder'),
    scanBtn: document.getElementById('credScanBtn'),
    pickFolderBtn: document.getElementById('credPickFolderBtn'),
    scanWorkspaceBtn: document.getElementById('credScanWorkspaceBtn'),
    scanManual: document.getElementById('credScanManual'),
    scanResults: document.getElementById('credScanResults'),
};

const CRED_KIND_LABELS = {
    play_service_account: 'Google Play service account',
    apple_p8: 'App Store Connect API key (.p8)',
    firebase_android: 'Firebase google-services.json',
    firebase_ios: 'Firebase GoogleService-Info.plist',
    apple_other_p8: 'Other Apple key (.p8) — not for uploads',
};

const PLAY_HINT_BADGES = {
    likely: '<span class="ui-badge" data-variant="success" style="font-size:0.62rem;">likely Play uploader</span>',
    unlikely: '<span class="ui-badge" data-variant="secondary" style="font-size:0.62rem;">likely Firebase / other service</span>',
};

async function postJson(url, body) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return res.json();
}

function scopeLabel(source) {
    if (source === 'workspace') return 'all apps';
    if (source === 'deploy_config') return 'path from deploy config';
    if (source === 'auto') return 'auto-detected';
    if (source && source.startsWith('env file')) return `from app ${source}`;
    return 'this app';
}

const IMPORTED_SOURCES = new Set(['app', 'workspace']);

async function loadCredentialStatus(appId) {
    if (!appId) return;
    let status;
    try {
        status = await fetch(`/api/deployment/credentials?app=${encodeURIComponent(appId)}`).then(r => r.json());
    } catch (err) {
        credEls.playStatus.dataset.status = 'error';
        credEls.playStatus.textContent = `Could not load credentials: ${err.message}`;
        return;
    }
    if (appId !== setupState.selectedAppId) return;

    const play = status.play;
    if (!play) {
        credEls.playStatus.dataset.status = 'warning';
        credEls.playStatus.textContent = 'No key configured — Android uploads will fail until you choose or import one.';
    } else if (!play.exists || !play.valid) {
        credEls.playStatus.dataset.status = 'error';
        credEls.playStatus.textContent = `${play.exists ? 'Not a service-account key' : 'File missing'}: ${play.path}`;
    } else {
        credEls.playStatus.dataset.status = 'valid';
        credEls.playStatus.textContent = `✅ ${play.client_email} • ${scopeLabel(play.source)} • ${play.path}`;
    }
    credEls.playRemove.hidden = !play || !IMPORTED_SOURCES.has(play.source);
    setTabStatus('android', !!(play && play.exists && play.valid));
    setTabStatus('ios', !!(status.apple && status.apple.exists));
    credEls.playRemove.dataset.app = play && play.source === 'workspace' ? '' : appId;

    renderP8KeyInfo(status.apple);
}

async function uploadCredentialFile(file, { appId, issuerId = '' }) {
    const buf = new Uint8Array(await file.arrayBuffer());
    let binary = '';
    for (let i = 0; i < buf.length; i += 0x8000) {
        binary += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    }
    return postJson('/api/deployment/credentials/upload', {
        filename: file.name, contentBase64: btoa(binary), app: appId, issuerId,
    });
}

credEls.playChoose.addEventListener('click', () => {
    if (!setupState.selectedAppId) { showToast('Please select an app first.'); return; }
    credEls.playFile.value = '';
    credEls.playFile.click();
});

credEls.playFile.addEventListener('change', async () => {
    const file = credEls.playFile.files?.[0];
    if (!file) return;
    const appId = credEls.playAllApps.checked ? '' : setupState.selectedAppId;
    const res = await uploadCredentialFile(file, { appId });
    if (res.success && res.kind === 'play_service_account') {
        showToast(`✅ Play key for ${res.client_email} imported.`);
    } else if (res.success) {
        showToast(`That file is a ${CRED_KIND_LABELS[res.kind] || res.kind}, not a Play service account — imported as such.`);
    } else {
        showToast('Import failed: ' + (res.error || 'Unknown error'));
    }
    loadCredentialStatus(setupState.selectedAppId);
});

credEls.playRemove.addEventListener('click', async () => {
    const res = await postJson('/api/deployment/credentials/remove', {
        kind: 'play_service_account', app: credEls.playRemove.dataset.app || '',
    });
    showToast(res.success ? 'Play key removed (the file itself was not deleted).' : 'Remove failed: ' + res.error);
    loadCredentialStatus(setupState.selectedAppId);
});

function describeFound(item) {
    if (item.kind === 'play_service_account') return item.client_email;
    if (item.kind === 'apple_p8') return item.key_id ? `Key ID ${item.key_id}` : 'Key ID unknown — rename to AuthKey_<KEYID>.p8';
    if (item.kind === 'firebase_android') return (item.packages || []).join(', ') || item.project_id;
    if (item.kind === 'firebase_ios') return item.bundle_id;
    return item.note || '';
}

function renderScanResults(res) {
    if (!res.success) {
        credEls.scanResults.innerHTML = `<div class="cert-status-box" data-status="error">${escapeHtml(res.error || 'Scan failed')}</div>`;
        return;
    }
    if (!res.found.length) {
        credEls.scanResults.innerHTML = `<div class="cert-status-box" data-status="unknown">No keys found in ${escapeHtml(res.folder)}.</div>`;
        return;
    }
    const appId = setupState.selectedAppId;
    const rows = res.found.map((item, idx) => {
        const forThisApp = (item.matches || []).filter(m => m.app === appId);
        const matchText = (item.matches || []).length
            ? item.matches.map(m => `${m.app}${m.flavor !== 'default' ? ` (${m.flavor})` : ''}`).join(', ')
            : 'no matching app';
        const isFirebase = item.kind.startsWith('firebase');
        const flavorOptions = isFirebase
            ? (forThisApp.length ? forThisApp.map(m => m.flavor) : ['default', ...getActiveFlavors()])
                .filter((f, i, arr) => arr.indexOf(f) === i)
                .map(f => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`).join('')
            : '';
        const importable = item.kind !== 'apple_other_p8';
        const scopeControl = !importable ? '' : isFirebase
            ? `<select class="ui-input" data-cred-flavor="${idx}" style="width:auto;">${flavorOptions}</select>`
            : `<select class="ui-input" data-cred-scope="${idx}" style="width:auto;">
                   <option value="app">This app</option>
                   <option value="workspace">All apps</option>
               </select>`;
        const importBtn = importable
            ? `<button type="button" class="ui-button" data-variant="secondary" data-size="sm" data-cred-import="${idx}">Import</button>`
            : '';
        return `
            <div style="display:flex; gap:10px; align-items:center; padding:8px 0; border-top:1px solid var(--ui-border-color);${importable ? '' : ' opacity:0.6;'}">
                <div style="flex:1; min-width:0;">
                    <div style="font-size:0.82rem; font-weight:600;">${escapeHtml(CRED_KIND_LABELS[item.kind] || item.kind)} ${PLAY_HINT_BADGES[item.play_hint] || ''}</div>
                    <div style="font-size:0.78rem;">${escapeHtml(describeFound(item))}</div>
                    <div style="font-size:0.72rem; color:var(--ui-text-muted); overflow-wrap:anywhere;" title="${escapeHtml(item.path)}">${escapeHtml(item.path)}</div>
                    ${isFirebase ? `<div style="font-size:0.72rem; color:var(--ui-text-muted);">Matches: ${escapeHtml(matchText)}</div>` : ''}
                </div>
                ${scopeControl}
                ${importBtn}
            </div>`;
    }).join('');
    credEls.scanResults.innerHTML = `
        <div style="font-size:0.78rem; color:var(--ui-text-muted); margin-bottom:4px;">
            Found ${res.found.length} in ${escapeHtml(res.folder)}${res.truncated ? ' (scan stopped early — choose a narrower folder)' : ''}
        </div>${rows}`;
    credEls.scanResults.querySelectorAll('[data-cred-import]').forEach(btn => {
        btn.addEventListener('click', () => importScanned(res.found[Number(btn.dataset.credImport)], Number(btn.dataset.credImport), btn));
    });
}

async function importScanned(item, idx, btn) {
    const appId = setupState.selectedAppId;
    if (!appId) { showToast('Please select an app first.'); return; }
    const scope = credEls.scanResults.querySelector(`[data-cred-scope="${idx}"]`)?.value || 'app';
    const flavor = credEls.scanResults.querySelector(`[data-cred-flavor="${idx}"]`)?.value || '';
    btn.disabled = true;
    const res = await postJson('/api/deployment/credentials/import', {
        path: item.path,
        app: item.kind.startsWith('firebase') || scope === 'app' ? appId : '',
        flavor,
        issuerId: item.kind === 'apple_p8' ? setupEls.issuerId.value.trim() : '',
    });
    btn.disabled = false;
    if (res.success) {
        btn.textContent = 'Imported ✓';
        showToast(`✅ ${CRED_KIND_LABELS[res.kind]} imported.`);
        if (res.field) {
            const app = (setupState.deployConfig.apps[appId] = setupState.deployConfig.apps[appId] || {});
            app[res.field] = res.stored_path;
            renderDynamicFields(getActiveFlavors(), app);
        }
        loadCredentialStatus(appId);
    } else {
        showToast('Import failed: ' + (res.error || 'Unknown error'));
    }
}

async function runCredentialScan(folder) {
    const buttons = [credEls.scanBtn, credEls.pickFolderBtn, credEls.scanWorkspaceBtn];
    buttons.forEach(b => { b.disabled = true; });
    credEls.scanResults.innerHTML = `<div class="cert-status-box" data-status="unknown">Scanning ${escapeHtml(folder || 'workspace')}…</div>`;
    try {
        renderScanResults(await postJson('/api/deployment/credentials/scan', { folder }));
    } catch (err) {
        renderScanResults({ success: false, error: err.message });
    } finally {
        buttons.forEach(b => { b.disabled = false; });
    }
}

/** Open the OS folder/file dialog via the local server; resolves to a path, or null if cancelled/unsupported. */
async function pickNativePath({ kind = 'folder', prompt = '', extensions = [] } = {}) {
    const res = await postJson('/api/deployment/pick', { kind, prompt, extensions });
    if (res.success) return { path: res.path };
    return { path: null, unsupported: res.supported === false, error: res.cancelled ? '' : res.error };
}
window.pickNativePath = pickNativePath;

credEls.pickFolderBtn.addEventListener('click', async () => {
    credEls.pickFolderBtn.disabled = true;
    credEls.scanResults.innerHTML = '<div class="cert-status-box" data-status="unknown">Waiting for you to choose a folder in the dialog…</div>';
    const picked = await pickNativePath({ kind: 'folder', prompt: 'Choose a folder to scan for signing keys' });
    credEls.pickFolderBtn.disabled = false;
    if (picked.path) {
        credEls.scanFolder.value = picked.path;
        runCredentialScan(picked.path);
    } else if (picked.unsupported) {
        credEls.scanManual.hidden = false;
        credEls.scanResults.innerHTML = '<div class="cert-status-box" data-status="warning">No folder dialog is available on this system. Type the folder path below.</div>';
        credEls.scanFolder.focus();
    } else {
        credEls.scanResults.innerHTML = picked.error
            ? `<div class="cert-status-box" data-status="error">${escapeHtml(picked.error)}</div>` : '';
    }
});

credEls.scanWorkspaceBtn.addEventListener('click', () => runCredentialScan(''));
credEls.scanBtn.addEventListener('click', () => runCredentialScan(credEls.scanFolder.value.trim()));

// ─────────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────────

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
