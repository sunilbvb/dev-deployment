/**
 * setup.js — Deployment Setup Modal
 * Handles credential configuration, melos injection, and command regeneration.
 * Keeps all logic separate from the main deployment console (app.js).
 */

const setupState = {
    apps: [],
    selectedAppId: null,
    deployConfig: { apps: {} },
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
    p8Path: document.getElementById('cfgP8Path'),
    playService: document.getElementById('cfgPlayService'),
    flavors: document.getElementById('cfgFlavors'),
    autoReleaseEnabled: document.getElementById('cfgAutoReleaseEnabled'),
    autoReleaseAction: document.getElementById('cfgAutoReleaseAction'),
    autoReleaseFlavors: document.getElementById('cfgAutoReleaseFlavors'),
    iosCertStatus: document.getElementById('iosCertStatus'),
    iosCertRecheckBtn: document.getElementById('iosCertRecheckBtn'),
    saveBtn: document.getElementById('saveConfigBtn'),
    injectBtn: document.getElementById('injectMelosBtn'),
    regenerateBtn: document.getElementById('regenerateBtn'),
    scanBtn: document.getElementById('autoScanBtn'),
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
    setupState.apps = appsRes.apps || [];
    setupState.deployConfig = configRes.config || { apps: {} };
    renderReleaseActionOptions((templatesRes.templates || {}).release || []);
    renderSetupAppNav();
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
    setupState.apps.forEach(app => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ui-sidebar-item' + (app.id === setupState.selectedAppId ? ' ui-active' : '');
        btn.dataset.appId = app.id;
        btn.innerHTML = `
            <span class="app-dot" style="background:${escapeHtml(app.color || '#3b82f6')}; margin-right: 8px;"></span>
            <span>${escapeHtml(app.name || app.id)}</span>
        `;
        btn.addEventListener('click', () => selectSetupApp(app.id));
        setupAppList.appendChild(btn);
    });
}

function getActiveFlavors() {
    const val = setupEls.flavors.value.trim();
    if (!val) return ['dev', 'qa', 'prod'];
    return val.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
}

function renderDynamicFields(flavors, cfg) {
    const bundleContainer = document.getElementById('dynamicBundleIdsContainer');
    const packageContainer = document.getElementById('dynamicPackageNamesContainer');
    const servicesContainer = document.getElementById('dynamicGoogleServicesContainer');

    bundleContainer.innerHTML = '';
    packageContainer.innerHTML = '';
    servicesContainer.innerHTML = '';

    flavors.forEach(flavor => {
        // iOS Bundle ID Input
        const bundleLabel = document.createElement('label');
        bundleLabel.textContent = `${flavor.toUpperCase()} Bundle ID`;
        const bundleInput = document.createElement('input');
        bundleInput.type = 'text';
        bundleInput.id = `cfgBundle_${flavor}`;
        bundleInput.placeholder = `com.example.app.${flavor}`;
        bundleInput.value = cfg[`bundle_id_${flavor}`] || '';
        bundleLabel.appendChild(bundleInput);
        bundleContainer.appendChild(bundleLabel);

        // Android Package ID Input
        const packageLabel = document.createElement('label');
        packageLabel.textContent = `${flavor.toUpperCase()} Package Name`;
        const packageInput = document.createElement('input');
        packageInput.type = 'text';
        packageInput.id = `cfgAndroidPackage_${flavor}`;
        packageInput.placeholder = `com.example.app.${flavor}`;
        packageInput.value = cfg[`android_package_${flavor}`] || '';
        packageLabel.appendChild(packageInput);
        packageContainer.appendChild(packageLabel);

        // Firebase google-services.json Path Input
        const servicesLabel = document.createElement('label');
        servicesLabel.textContent = `${flavor.toUpperCase()} google-services.json Path`;
        const servicesInput = document.createElement('input');
        servicesInput.type = 'text';
        servicesInput.id = `cfgGoogleServices_${flavor}`;
        servicesInput.placeholder = `private_keys/Firebase/${flavor}/google-services.json`;
        servicesInput.value = cfg[`google_services_json_${flavor}`] || '';
        servicesLabel.appendChild(servicesInput);
        servicesContainer.appendChild(servicesLabel);
    });
}

function selectSetupApp(appId) {
    setupState.selectedAppId = appId;
    renderSetupAppNav();
    addAppForm.classList.add('hidden');

    const app = setupState.apps.find(a => a.id === appId);
    const cfg = setupState.deployConfig.apps?.[appId] || {};

    setupEls.appTitle.textContent = app ? app.name : appId;
    
    const activeFlavors = cfg.flavors || ['dev', 'qa', 'prod'];
    setupEls.flavors.value = activeFlavors.join(', ');

    renderDynamicFields(activeFlavors, cfg);

    setupEls.appleId.value = cfg.apple_id || '';
    setupEls.p8Path.value = cfg.p8_key_path || '';
    setupEls.playService.value = cfg.play_service_account_path || '';

    setupEls.autoReleaseEnabled.checked = !!cfg.auto_release_on_success;
    setupEls.autoReleaseAction.value = cfg.auto_release_action || 'release_push';
    setupEls.autoReleaseFlavors.value = (cfg.auto_release_flavors || ['prod']).join(', ');

    fetchAndRenderCertStatus(appId);

    setupEls.noApp.classList.add('hidden');
    setupEls.form.classList.remove('hidden');
}

// Listen to flavor inputs changes to dynamically redraw fields
setupEls.flavors.addEventListener('input', () => {
    const cfg = setupState.deployConfig.apps?.[setupState.selectedAppId] || {};
    renderDynamicFields(getActiveFlavors(), cfg);
});

function readFormValues() {
    const flavors = getActiveFlavors();
    const values = {
        flavors: flavors,
        apple_id: setupEls.appleId.value.trim(),
        p8_key_path: setupEls.p8Path.value.trim(),
        play_service_account_path: setupEls.playService.value.trim(),
        auto_release_on_success: setupEls.autoReleaseEnabled.checked,
        auto_release_action: setupEls.autoReleaseAction.value || 'release_push',
        auto_release_flavors: setupEls.autoReleaseFlavors.value.trim()
            ? setupEls.autoReleaseFlavors.value.split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
            : ['prod'],
    };

    flavors.forEach(flavor => {
        const bundleVal = document.getElementById(`cfgBundle_${flavor}`)?.value.trim() || '';
        const packageVal = document.getElementById(`cfgAndroidPackage_${flavor}`)?.value.trim() || '';
        const servicesVal = document.getElementById(`cfgGoogleServices_${flavor}`)?.value.trim() || '';

        values[`bundle_id_${flavor}`] = bundleVal;
        values[`android_package_${flavor}`] = packageVal;
        values[`google_services_json_${flavor}`] = servicesVal;
    });

    return values;
}

async function saveDeployConfig() {
    if (!setupState.selectedAppId) { return; }
    if (!setupState.deployConfig.apps) { setupState.deployConfig.apps = {}; }
    setupState.deployConfig.apps[setupState.selectedAppId] = readFormValues();

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

async function injectMelosScripts() {
    if (!setupState.selectedAppId) { return; }
    await saveDeployConfig();

    const res = await fetch('/api/deployment/inject-melos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_id: setupState.selectedAppId }),
    }).then(r => r.json());

    if (res.success) {
        showToast(`Injected ${res.injected} lines into pubspec.yaml!`);
    } else {
        showToast('Inject failed: ' + (res.error || 'unknown'));
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
        const flavors = getActiveFlavors();
        let filled = 0;

        flavors.forEach(flavor => {
            const bundleInput = document.getElementById(`cfgBundle_${flavor}`);
            const packageInput = document.getElementById(`cfgAndroidPackage_${flavor}`);
            const servicesInput = document.getElementById(`cfgGoogleServices_${flavor}`);

            const scanBundle = d[`bundle_id_${flavor}`] || d[`android_id_${flavor}`];
            const scanPackage = d[`android_id_${flavor}`] || d[`bundle_id_${flavor}`];
            const scanServices = d[`google_services_json_${flavor}`];

            if (bundleInput && scanBundle && !bundleInput.value.trim()) {
                bundleInput.value = scanBundle;
                filled++;
            }
            if (packageInput && scanPackage && !packageInput.value.trim()) {
                packageInput.value = scanPackage;
                filled++;
            }
            if (servicesInput && scanServices && !servicesInput.value.trim()) {
                servicesInput.value = scanServices;
                filled++;
            }
        });

        if (filled > 0) {
            showToast(`Auto-filled ${filled} field(s) from workspace scan. Review and save.`);
        } else if (Object.keys(d).length > 0) {
            showToast('Fields already filled — scan found data but kept your existing values.');
        } else {
            showToast('Scan complete — no configuration files found.');
        }
    } finally {
        setupEls.scanBtn.disabled = false;
        setupEls.scanBtn.querySelector('span').textContent = 'Auto-Scan Workspace';
    }
}

// Register App Actions
addCustomAppBtn.addEventListener('click', () => {
    setupEls.form.classList.add('hidden');
    setupEls.noApp.classList.add('hidden');
    addAppForm.classList.remove('hidden');
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

    if (!id || !name) {
        showToast('App ID and App Name are required!');
        return;
    }

    const res = await fetch('/api/deployment/apps/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, name, version }),
    }).then(r => r.json());

    if (res.success) {
        showToast('App registered!');
        addAppForm.classList.add('hidden');
        document.getElementById('newAppId').value = '';
        document.getElementById('newAppName').value = '';
        document.getElementById('newAppVersion').value = '';
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
setupEls.injectBtn.addEventListener('click', injectMelosScripts);
setupEls.regenerateBtn.addEventListener('click', regenerateAllCommands);
setupEls.scanBtn.addEventListener('click', autoScanConfig);

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeSetupModal(); }
});

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

