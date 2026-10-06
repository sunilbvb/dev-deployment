/**
 * setup.js — Deployment Setup Modal Coordinator
 * Handles credential configuration, dynamic form fields, tab orchestration,
 * and command regeneration. Delegates to modular components in modules/setup/:
 * - setup_scanner.js: autoScanConfig, autoScanAllConfig, rescanWorkspace, detectAppFromPath
 * - setup_webhooks.js: multi-channel notification webhooks, modals, cURL snippets
 * - setup_pipelines.js: pipeline builder, step catalog picker, custom shell steps
 * - setup_credentials.js: P8 dropzone/upload, credential inspection, native path picker
 * - setup_github.js: GitHub Actions cloud CI PAT, repo override, workflow template installer
 */

// setupState / setupEls live in modules/setup/setup_state.js (loaded first).

const addAppForm = document.getElementById('addAppForm');
const addCustomAppBtn = document.getElementById('addCustomAppBtn');
const cancelAddAppBtn = document.getElementById('cancelAddAppBtn');
const saveNewAppBtn = document.getElementById('saveNewAppBtn');

// Core form logic restored from before the modularization (f3e23ef), which
// broke config load/save endpoints and the identifier field containers.
function openSetupModal() {
    setupEls.overlay.classList.add('ui-active');
    let tab = 'general';
    try { tab = sessionStorage.getItem(SETUP_TAB_KEY) || tab; } catch (_) {}
    if (!setupTabs || !setupTabs.querySelector(`[data-tab="${tab}"]`)) tab = 'general';
    showSetupTab(tab);
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

// Tab Orchestration
const SETUP_TAB_KEY = 'setup_active_tab';
const setupTabs = document.getElementById('setupTabs');

function showSetupTab(tabName) {
    if (!setupTabs) return;
    setupTabs.querySelectorAll('.setup-tab-btn, .setup-tab').forEach(btn => {
        const isActive = btn.dataset.tab === tabName;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
    document.querySelectorAll('[data-setup-panel]').forEach(pane => {
        pane.style.display = (pane.dataset.setupPanel === tabName) ? '' : 'none';
    });
    document.querySelectorAll('.setup-tab-pane').forEach(pane => {
        pane.classList.toggle('active', pane.dataset.tabPane === tabName);
    });
    if (tabName === 'github' && typeof loadGitHubConfig === 'function') {
        loadGitHubConfig();
    }
    try { sessionStorage.setItem(SETUP_TAB_KEY, tabName); } catch (_) {}
}

function setTabStatus(tabName, isReady) {
    const dot = document.getElementById(`tabStatus_${tabName}`);
    if (!dot) return;
    dot.dataset.status = isReady ? 'ok' : 'missing';
    dot.title = isReady ? 'Credentials configured' : 'Action needed: key missing or invalid';
}

if (setupTabs) {
    setupTabs.addEventListener('click', e => {
        const btn = e.target.closest('.setup-tab-btn, .setup-tab');
        if (btn && btn.dataset.tab) {
            showSetupTab(btn.dataset.tab);
        }
    });
}

// Setup Event Listeners
if (setupEls.openBtn) setupEls.openBtn.addEventListener('click', openSetupModal);
if (setupEls.closeBtn) setupEls.closeBtn.addEventListener('click', closeSetupModal);
if (setupEls.overlay) setupEls.overlay.addEventListener('click', e => { if (e.target === setupEls.overlay) closeSetupModal(); });
if (setupEls.saveBtn) setupEls.saveBtn.addEventListener('click', saveDeployConfig);
if (setupEls.regenerateBtn) setupEls.regenerateBtn.addEventListener('click', regenerateAllCommands);
if (setupEls.scanBtn) setupEls.scanBtn.addEventListener('click', () => { if (typeof autoScanConfig === 'function') autoScanConfig(); });
if (setupEls.scanAllBtn) setupEls.scanAllBtn.addEventListener('click', () => { if (typeof autoScanAllConfig === 'function') autoScanAllConfig({ force: false }); });
// Add App Dialog Events
if (addCustomAppBtn) {
    addCustomAppBtn.addEventListener('click', () => {
        if (setupEls.form) setupEls.form.classList.add('hidden');
        if (setupEls.noApp) setupEls.noApp.classList.add('hidden');
        if (addAppForm) addAppForm.classList.remove('hidden');
        const newAppPath = document.getElementById('newAppPath');
        const pathDetectBadge = document.getElementById('pathDetectBadge');
        if (newAppPath) newAppPath.value = '';
        if (pathDetectBadge) pathDetectBadge.style.display = 'none';
        if (window.lucide && typeof lucide.createIcons === 'function') lucide.createIcons();
    });
}

if (cancelAddAppBtn) {
    cancelAddAppBtn.addEventListener('click', () => {
        if (addAppForm) addAppForm.classList.add('hidden');
        if (setupState.selectedAppId) {
            if (setupEls.form) setupEls.form.classList.remove('hidden');
        } else {
            if (setupEls.noApp) setupEls.noApp.classList.remove('hidden');
        }
    });
}

if (saveNewAppBtn) {
    saveNewAppBtn.addEventListener('click', async () => {
        const id = document.getElementById('newAppId')?.value.trim();
        const name = document.getElementById('newAppName')?.value.trim();
        const version = document.getElementById('newAppVersion')?.value.trim() || '1.0.0 (1)';
        const newAppPath = document.getElementById('newAppPath');
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
            if (addAppForm) addAppForm.classList.add('hidden');
            if (document.getElementById('newAppId')) document.getElementById('newAppId').value = '';
            if (document.getElementById('newAppName')) document.getElementById('newAppName').value = '';
            if (document.getElementById('newAppVersion')) document.getElementById('newAppVersion').value = '';
            if (newAppPath) newAppPath.value = '';
            const pathDetectBadge = document.getElementById('pathDetectBadge');
            if (pathDetectBadge) pathDetectBadge.style.display = 'none';
            await loadSetupData();
            selectSetupApp(id);

            if (typeof loadApps === 'function') { loadApps(); }
        } else {
            showToast('Failed to register app: ' + (res.error || 'unknown'));
        }
    });
}

const detectAppPathBtn = document.getElementById('detectAppPathBtn');
if (detectAppPathBtn) {
    detectAppPathBtn.addEventListener('click', () => {
        if (typeof detectAppFromPath === 'function') detectAppFromPath();
    });
}

const rescanWorkspaceBtn = document.getElementById('rescanWorkspaceBtn');
if (rescanWorkspaceBtn) {
    rescanWorkspaceBtn.addEventListener('click', () => {
        if (typeof rescanWorkspace === 'function') rescanWorkspace();
    });
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
window.escapeHtml = escapeHtml;

// Attach coordinators to window
window.openSetupModal = openSetupModal;
window.closeSetupModal = closeSetupModal;
window.loadSetupData = loadSetupData;
window.selectSetupApp = selectSetupApp;
window.renderSetupAppNav = renderSetupAppNav;
window.getActiveFlavors = getActiveFlavors;
window.renderDynamicFields = renderDynamicFields;
window.renderP8KeyInfo = renderP8KeyInfo;
window.readFormValues = readFormValues;
window.saveDeployConfig = saveDeployConfig;
window.regenerateAllCommands = regenerateAllCommands;
window.showSetupTab = showSetupTab;
window.setTabStatus = setTabStatus;
window.getCachedCertCheck = getCachedCertCheck;
window.setCachedCertCheck = setCachedCertCheck;
window.renderCertStatusBox = renderCertStatusBox;
window.fetchAndRenderCertStatus = fetchAndRenderCertStatus;
