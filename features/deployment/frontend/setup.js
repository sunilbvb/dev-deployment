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

const setupState = window.setupState = window.setupState || {
    apps: [],
    selectedAppId: null,
    deployConfig: { apps: {} },
    currentWebhooks: [],
};

const setupEls = window.setupEls = window.setupEls || {
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
    channelModalId: document.getElementById('channelModalId'),
    channelModalTitle: document.getElementById('channelModalTitle'),
    channelModalName: document.getElementById('channelModalName'),
    channelModalUrl: document.getElementById('channelModalUrl'),
    channelModalProvider: document.getElementById('channelModalProvider'),
    channelModalPhone: document.getElementById('channelModalPhone'),
    channelModalTemplate: document.getElementById('channelModalTemplate'),
    channelModalHeaders: document.getElementById('channelModalHeaders'),
    channelModalSuccess: document.getElementById('channelModalSuccess'),
    channelModalFailure: document.getElementById('channelModalFailure'),
    channelModalEnabled: document.getElementById('channelModalEnabled'),
    channelModalTestBtn: document.getElementById('channelModalTestBtn'),
    channelModalTestFeedback: document.getElementById('channelModalTestFeedback'),
    channelModalWhatsAppSection: document.getElementById('channelModalWhatsAppSection'),
    channelModalCustomSection: document.getElementById('channelModalCustomSection'),
    incomingWebhookSnippetTabs: document.getElementById('incomingWebhookSnippetTabs'),
    incomingWebhookSnippetCode: document.getElementById('incomingWebhookSnippetCode'),
    incomingWebhookUrlDisplay: document.getElementById('incomingWebhookUrlDisplay'),
    copyIncomingWebhookUrlBtn: document.getElementById('copyIncomingWebhookUrlBtn'),
};

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
    if (addAppForm) addAppForm.classList.add('hidden');
}

async function loadSetupData() {
    try {
        const [appsRes, configRes] = await Promise.all([
            fetch('/api/deployment/apps').then(r => r.json()),
            fetch('/api/deployment/config').then(r => r.json()),
        ]);

        // Packages are not deployable, so they have no per-app settings.
        setupState.apps = (appsRes.apps || []).filter(a => !a.is_package);
        setupState.deployConfig = configRes || { apps: {} };

        renderSetupAppNav();

        if (setupState.apps.length > 0) {
            const currentSelected = setupState.selectedAppId;
            const valid = setupState.apps.some(a => a.id === currentSelected);
            selectSetupApp(valid ? currentSelected : setupState.apps[0].id);
        } else {
            selectSetupApp(null);
        }
    } catch (err) {
        showToast('Failed to load setup data: ' + err.message);
    }
}

function renderReleaseActionOptions(targetSelect, currentAction) {
    if (!targetSelect) return;
    const actions = [
        { id: 'build_aab', label: 'Android AAB only' },
        { id: 'build_ipa', label: 'iOS IPA only' },
        { id: 'build_both', label: 'Both platforms' },
        { id: 'custom', label: 'Custom command' },
    ];
    targetSelect.innerHTML = actions.map(act =>
        `<option value="${act.id}" ${currentAction === act.id ? 'selected' : ''}>${act.label}</option>`
    ).join('');
}

const certCheckCache = new Map();

function getCachedCertCheck(appId) {
    return certCheckCache.get(appId) || null;
}

function setCachedCertCheck(appId, result) {
    certCheckCache.set(appId, result);
}

function renderCertStatusBox(result, container) {
    if (!container) return;
    if (!result || !result.success) {
        container.innerHTML = `<div class="cert-status-box" data-status="error">Check failed: ${escapeHtml(result?.error || 'unknown')}</div>`;
        return;
    }
    if (result.status === 'not_ios_app') {
        container.innerHTML = '<div class="cert-status-box" data-status="ok">Not an iOS app (no ios/ directory)</div>';
        return;
    }
    const cert = result.certificate || {};
    const prof = result.provisioningProfile || {};
    const certDays = cert.expiresOn ? Math.ceil((new Date(cert.expiresOn) - new Date()) / 86400000) : null;
    const profDays = prof.expiresOn ? Math.ceil((new Date(prof.expiresOn) - new Date()) / 86400000) : null;

    container.innerHTML = `
        <div class="cert-status-box" data-status="${cert.status || 'unknown'}" style="margin-bottom:8px;">
            <strong>Apple Distribution Cert:</strong> ${cert.status || 'unknown'}
            ${cert.expiresOn ? ` — expires ${escapeHtml(cert.expiresOn)} (${certDays}d)` : ''}
            ${cert.source ? ` [${cert.source}]` : ''}
        </div>
        <div class="cert-status-box" data-status="${prof.status || 'unknown'}">
            <strong>Provisioning Profile:</strong> ${prof.status || 'unknown'}
            ${prof.expiresOn ? ` — expires ${escapeHtml(prof.expiresOn)} (${profDays}d)` : ''}
            ${prof.source ? ` [${prof.source}]` : ''}
        </div>
    `;
}

async function fetchAndRenderCertStatus(appId, container) {
    if (!container) return;
    container.innerHTML = '<div class="cert-status-box" data-status="unknown">Checking certificates…</div>';
    try {
        const res = await fetch(`/api/deployment/ios-cert-check?app=${encodeURIComponent(appId)}&flavor=prod`).then(r => r.json());
        setCachedCertCheck(appId, res);
        renderCertStatusBox(res, container);
    } catch (e) {
        renderCertStatusBox({ success: false, error: e.message }, container);
    }
}

function renderSetupAppNav() {
    const list = document.getElementById('setupAppList');
    if (!list) return;
    list.innerHTML = setupState.apps.map(app => `
        <button type="button" class="ui-sidebar-item setup-app-item" data-state="${app.id === setupState.selectedAppId ? 'active' : ''}" data-app-id="${escapeHtml(app.id)}">
            <span class="app-dot" style="background: ${escapeHtml(app.color || '#6366f1')}"></span>
            <span>${escapeHtml(app.name)}</span>
        </button>
    `).join('');

    list.querySelectorAll('.setup-app-item').forEach(btn => {
        btn.addEventListener('click', () => {
            selectSetupApp(btn.dataset.appId);
        });
    });
}

function getActiveFlavors() {
    const raw = setupEls.flavors ? setupEls.flavors.value : '';
    return raw.split(',').map(f => f.trim().toLowerCase()).filter(Boolean);
}

function renderDynamicFields(flavors, appCfg = {}) {
    const container = document.getElementById('dynamicFlavorFields');
    if (!container) return;

    if (!flavors || flavors.length === 0) {
        container.innerHTML = `
            <div class="ui-form-group">
                <label class="ui-label">Bundle ID (iOS)</label>
                <input type="text" class="ui-input" id="cfgBundle_single" value="${escapeHtml(appCfg.bundle_id || appCfg.bundle_id_prod || '')}" placeholder="com.example.app">
            </div>
            <div class="ui-form-group">
                <label class="ui-label">Android Package Name / Application ID</label>
                <input type="text" class="ui-input" id="cfgAndroidPackage_single" value="${escapeHtml(appCfg.android_package || appCfg.android_package_prod || appCfg.android_id_prod || '')}" placeholder="com.example.app">
            </div>
            <div class="ui-form-group">
                <label class="ui-label">google-services.json Path (Android)</label>
                <input type="text" class="ui-input" id="cfgGoogleServices_single" value="${escapeHtml(appCfg.google_services_json || appCfg.google_services_json_prod || '')}" placeholder="android/app/google-services.json">
            </div>
            <div class="ui-form-group">
                <label class="ui-label">GoogleService-Info.plist Path (iOS)</label>
                <input type="text" class="ui-input" id="cfgGoogleServiceInfo_single" value="${escapeHtml(appCfg.google_service_info_plist || appCfg.google_service_info_plist_prod || '')}" placeholder="ios/Runner/GoogleService-Info.plist">
            </div>
        `;
        return;
    }

    container.innerHTML = flavors.map(flavor => `
        <div class="flavor-field-card" style="padding: 12px; border: 1px solid var(--ui-border-color); border-radius: 6px; margin-bottom: 12px; background: rgba(255,255,255,0.02);">
            <div style="font-weight: 700; font-size: 0.82rem; text-transform: uppercase; margin-bottom: 8px; color: var(--ui-primary, #6366f1);">${escapeHtml(flavor)}</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <div class="ui-form-group">
                    <label class="ui-label" style="font-size:0.75rem;">Bundle ID</label>
                    <input type="text" class="ui-input" id="cfgBundle_${escapeHtml(flavor)}" value="${escapeHtml(appCfg[`bundle_id_${flavor}`] || appCfg.bundle_id || '')}" placeholder="com.example.${escapeHtml(flavor)}">
                </div>
                <div class="ui-form-group">
                    <label class="ui-label" style="font-size:0.75rem;">Android Package</label>
                    <input type="text" class="ui-input" id="cfgAndroidPackage_${escapeHtml(flavor)}" value="${escapeHtml(appCfg[`android_package_${flavor}`] || appCfg[`android_id_${flavor}`] || appCfg.android_package || '')}" placeholder="com.example.${escapeHtml(flavor)}">
                </div>
                <div class="ui-form-group">
                    <label class="ui-label" style="font-size:0.75rem;">google-services.json</label>
                    <input type="text" class="ui-input" id="cfgGoogleServices_${escapeHtml(flavor)}" value="${escapeHtml(appCfg[`google_services_json_${flavor}`] || appCfg.google_services_json || '')}" placeholder="path/to/google-services.json">
                </div>
                <div class="ui-form-group">
                    <label class="ui-label" style="font-size:0.75rem;">GoogleService-Info.plist</label>
                    <input type="text" class="ui-input" id="cfgGoogleServiceInfo_${escapeHtml(flavor)}" value="${escapeHtml(appCfg[`google_service_info_plist_${flavor}`] || appCfg.google_service_info_plist || '')}" placeholder="path/to/GoogleService-Info.plist">
                </div>
            </div>
        </div>
    `).join('');
}

function selectSetupApp(appId) {
    setupState.selectedAppId = appId;
    document.querySelectorAll('#setupAppList .setup-app-item').forEach(btn => {
        btn.dataset.state = btn.dataset.appId === appId ? 'active' : '';
    });
    if (addAppForm) addAppForm.classList.add('hidden');

    if (!appId) {
        if (setupEls.form) setupEls.form.classList.add('hidden');
        if (setupEls.noApp) setupEls.noApp.classList.remove('hidden');
        return;
    }

    if (setupEls.form) setupEls.form.classList.remove('hidden');
    if (setupEls.noApp) setupEls.noApp.classList.add('hidden');

    renderSetupAppNav();

    const app = setupState.apps.find(a => a.id === appId) || {};
    const appCfg = (setupState.deployConfig.apps || {})[appId] || {};

    if (setupEls.appTitle) setupEls.appTitle.textContent = `${app.name || appId} Configuration`;
    if (setupEls.appleId) setupEls.appleId.value = appCfg.apple_id || '';
    if (setupEls.issuerId) setupEls.issuerId.value = appCfg.apple_issuer_id || '';
    if (setupEls.playService) setupEls.playService.value = appCfg.play_service_account_path || '';

    const flavorsList = Array.isArray(appCfg.flavors) ? appCfg.flavors : [];
    if (setupEls.flavors) setupEls.flavors.value = flavorsList.join(', ');

    renderDynamicFields(flavorsList, appCfg);

    // Auto-release configuration
    if (setupEls.autoReleaseEnabled) setupEls.autoReleaseEnabled.checked = !!appCfg.auto_release_on_success;
    renderReleaseActionOptions(setupEls.autoReleaseAction, appCfg.auto_release_action || 'build_aab');
    const autoFlavorsList = Array.isArray(appCfg.auto_release_flavors) ? appCfg.auto_release_flavors : [];
    if (setupEls.autoReleaseFlavors) setupEls.autoReleaseFlavors.value = autoFlavorsList.join(', ');

    // Webhooks
    if (setupEls.webhookUrl) setupEls.webhookUrl.value = appCfg.webhook_url || '';
    if (setupEls.webhookEnabled) setupEls.webhookEnabled.checked = appCfg.webhook_enabled !== false;
    if (setupEls.webhookProvider) setupEls.webhookProvider.value = appCfg.webhook_provider || 'auto';
    if (setupEls.notifyOnSuccess) setupEls.notifyOnSuccess.checked = appCfg.notify_on_success !== false;
    if (setupEls.notifyOnFailure) setupEls.notifyOnFailure.checked = appCfg.notify_on_failure !== false;
    if (setupEls.playConsoleTrack) setupEls.playConsoleTrack.value = appCfg.play_console_track || 'internal';

    // Workspace-level webhooks
    if (setupEls.wsWebhookUrl) setupEls.wsWebhookUrl.value = setupState.deployConfig.workspace_webhook_url || '';
    if (setupEls.wsWebhookEnabled) setupEls.wsWebhookEnabled.checked = setupState.deployConfig.workspace_webhook_enabled !== false;
    if (setupEls.wsWebhookProvider) setupEls.wsWebhookProvider.value = setupState.deployConfig.workspace_webhook_provider || 'auto';
    if (setupEls.wsNotifyOnSuccess) setupEls.wsNotifyOnSuccess.checked = setupState.deployConfig.workspace_notify_success !== false;
    if (setupEls.wsNotifyOnFailure) setupEls.wsNotifyOnFailure.checked = setupState.deployConfig.workspace_notify_failure !== false;

    setupState.currentWebhooks = Array.isArray(appCfg.webhooks) ? JSON.parse(JSON.stringify(appCfg.webhooks)) : [];
    if (typeof renderWebhookChannels === 'function') renderWebhookChannels();
    if (typeof updateIncomingWebhookSnippets === 'function') updateIncomingWebhookSnippets();

    // P8 info
    renderP8KeyInfo(appCfg);

    // Credentials status & Pipelines
    if (typeof loadCredentialStatus === 'function') loadCredentialStatus(appId);
    if (typeof renderSetupPipelines === 'function') renderSetupPipelines(appId);

    // iOS cert status check
    const cached = getCachedCertCheck(appId);
    if (cached) {
        renderCertStatusBox(cached, setupEls.iosCertStatus);
    } else {
        fetchAndRenderCertStatus(appId, setupEls.iosCertStatus);
    }
}

function renderP8KeyInfo(appCfg) {
    if (!setupEls.p8CurrentKeyInfo) return;
    const keyId = appCfg?.apple_key_id;
    const keyPath = appCfg?.apple_key_path;
    if (keyId || keyPath) {
        setupEls.p8CurrentKeyInfo.style.display = 'block';
        if (setupEls.p8CurrentKeyId) setupEls.p8CurrentKeyId.textContent = keyId || 'Unknown';
        if (setupEls.p8CurrentKeyPath) setupEls.p8CurrentKeyPath.textContent = keyPath || 'AuthKey stored in standard path';
    } else {
        setupEls.p8CurrentKeyInfo.style.display = 'none';
    }
}

function readFormValues() {
    const appId = setupState.selectedAppId;
    if (!appId) return null;

    const existingAppCfg = (setupState.deployConfig.apps || {})[appId] || {};
    const flavors = getActiveFlavors();

    const appCfg = {
        ...existingAppCfg,
        apple_id: setupEls.appleId ? setupEls.appleId.value.trim() : '',
        apple_issuer_id: setupEls.issuerId ? setupEls.issuerId.value.trim() : '',
        play_service_account_path: setupEls.playService ? setupEls.playService.value.trim() : '',
        flavors,
        auto_release_on_success: setupEls.autoReleaseEnabled ? setupEls.autoReleaseEnabled.checked : false,
        auto_release_action: setupEls.autoReleaseAction ? setupEls.autoReleaseAction.value : 'build_aab',
        auto_release_flavors: setupEls.autoReleaseFlavors ? setupEls.autoReleaseFlavors.value.split(',').map(s => s.trim().toLowerCase()).filter(Boolean) : [],
        webhook_url: setupEls.webhookUrl ? setupEls.webhookUrl.value.trim() : '',
        webhook_enabled: setupEls.webhookEnabled ? setupEls.webhookEnabled.checked : true,
        webhook_provider: setupEls.webhookProvider ? setupEls.webhookProvider.value : 'auto',
        notify_on_success: setupEls.notifyOnSuccess ? setupEls.notifyOnSuccess.checked : true,
        notify_on_failure: setupEls.notifyOnFailure ? setupEls.notifyOnFailure.checked : true,
        play_console_track: setupEls.playConsoleTrack ? setupEls.playConsoleTrack.value : 'internal',
        webhooks: setupState.currentWebhooks || [],
    };

    if (flavors.length === 0) {
        const b = document.getElementById('cfgBundle_single');
        const p = document.getElementById('cfgAndroidPackage_single');
        const s = document.getElementById('cfgGoogleServices_single');
        const i = document.getElementById('cfgGoogleServiceInfo_single');
        if (b) appCfg.bundle_id = b.value.trim();
        if (p) appCfg.android_package = p.value.trim();
        if (s) appCfg.google_services_json = s.value.trim();
        if (i) appCfg.google_service_info_plist = i.value.trim();
    } else {
        flavors.forEach(f => {
            const b = document.getElementById(`cfgBundle_${f}`);
            const p = document.getElementById(`cfgAndroidPackage_${f}`);
            const s = document.getElementById(`cfgGoogleServices_${f}`);
            const i = document.getElementById(`cfgGoogleServiceInfo_${f}`);
            if (b) appCfg[`bundle_id_${f}`] = b.value.trim();
            if (p) appCfg[`android_package_${f}`] = p.value.trim();
            if (s) appCfg[`google_services_json_${f}`] = s.value.trim();
            if (i) appCfg[`google_service_info_plist_${f}`] = i.value.trim();
        });
    }

    return appCfg;
}

async function saveDeployConfig() {
    const appId = setupState.selectedAppId;
    if (!appId) return;

    const appCfg = readFormValues();
    if (!appCfg) return;

    const dataToSave = {
        ...setupState.deployConfig,
        workspace_webhook_url: setupEls.wsWebhookUrl ? setupEls.wsWebhookUrl.value.trim() : '',
        workspace_webhook_enabled: setupEls.wsWebhookEnabled ? setupEls.wsWebhookEnabled.checked : true,
        workspace_webhook_provider: setupEls.wsWebhookProvider ? setupEls.wsWebhookProvider.value : 'auto',
        workspace_notify_success: setupEls.wsNotifyOnSuccess ? setupEls.wsNotifyOnSuccess.checked : true,
        workspace_notify_failure: setupEls.wsNotifyOnFailure ? setupEls.wsNotifyOnFailure.checked : true,
        apps: {
            ...(setupState.deployConfig.apps || {}),
            [appId]: appCfg,
        },
    };

    setupEls.saveBtn.disabled = true;
    setupEls.saveBtn.querySelector('span').textContent = 'Saving...';

    try {
        const res = await fetch('/api/deployment/config/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dataToSave),
        }).then(r => r.json());

        if (res.success) {
            setupState.deployConfig = dataToSave;
            showToast('Configuration saved successfully!');
            await loadSetupData();
            selectSetupApp(appId);
        } else {
            showToast('Save failed: ' + (res.error || 'Unknown error'));
        }
    } catch (err) {
        showToast('Error saving: ' + err.message);
    } finally {
        setupEls.saveBtn.disabled = false;
        setupEls.saveBtn.querySelector('span').textContent = 'Save Configuration';
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
if (setupEls.iosCertRecheckBtn) {
    setupEls.iosCertRecheckBtn.addEventListener('click', () => {
        if (setupState.selectedAppId) fetchAndRenderCertStatus(setupState.selectedAppId, setupEls.iosCertStatus);
    });
}

if (setupEls.flavors) {
    setupEls.flavors.addEventListener('input', () => {
        const flavors = getActiveFlavors();
        const appCfg = readFormValues() || {};
        renderDynamicFields(flavors, appCfg);
    });
}

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
