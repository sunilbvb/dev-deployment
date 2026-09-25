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
    issuerId: document.getElementById('cfgIssuerId'),
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
    // p8 upload elements
    p8Dropzone: document.getElementById('p8Dropzone'),
    p8FileInput: document.getElementById('p8FileInput'),
    p8DropzoneTitle: document.getElementById('p8DropzoneTitle'),
    p8UploadStatus: document.getElementById('p8UploadStatus'),
    p8CurrentKeyInfo: document.getElementById('p8CurrentKeyInfo'),
    p8CurrentKeyId: document.getElementById('p8CurrentKeyId'),
    p8CurrentKeyPath: document.getElementById('p8CurrentKeyPath'),
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
        const bundleField = document.createElement('div');
        bundleField.className = 'ui-field';
        bundleField.style.marginBottom = '0';

        const bundleLabel = document.createElement('label');
        bundleLabel.className = 'ui-label';
        bundleLabel.textContent = `${flavor.toUpperCase()} Bundle ID`;

        const bundleInput = document.createElement('input');
        bundleInput.type = 'text';
        bundleInput.className = 'ui-input';
        bundleInput.id = `cfgBundle_${flavor}`;
        bundleInput.placeholder = `com.example.app.${flavor}`;
        bundleInput.value = cfg[`bundle_id_${flavor}`] || '';

        bundleField.appendChild(bundleLabel);
        bundleField.appendChild(bundleInput);
        bundleContainer.appendChild(bundleField);

        // Android Package ID Input
        const packageField = document.createElement('div');
        packageField.className = 'ui-field';
        packageField.style.marginBottom = '0';

        const packageLabel = document.createElement('label');
        packageLabel.className = 'ui-label';
        packageLabel.textContent = `${flavor.toUpperCase()} Package Name`;

        const packageInput = document.createElement('input');
        packageInput.type = 'text';
        packageInput.className = 'ui-input';
        packageInput.id = `cfgAndroidPackage_${flavor}`;
        packageInput.placeholder = `com.example.app.${flavor}`;
        packageInput.value = cfg[`android_package_${flavor}`] || '';

        packageField.appendChild(packageLabel);
        packageField.appendChild(packageInput);
        packageContainer.appendChild(packageField);

        // Firebase google-services.json Path Input
        const servicesField = document.createElement('div');
        servicesField.className = 'ui-field';
        servicesField.style.marginBottom = '0';

        const servicesLabel = document.createElement('label');
        servicesLabel.className = 'ui-label';
        servicesLabel.textContent = `${flavor.toUpperCase()} google-services.json Path`;

        const servicesInput = document.createElement('input');
        servicesInput.type = 'text';
        servicesInput.className = 'ui-input';
        servicesInput.id = `cfgGoogleServices_${flavor}`;
        servicesInput.placeholder = `private_keys/Firebase/${flavor}/google-services.json`;
        servicesInput.value = cfg[`google_services_json_${flavor}`] || '';

        servicesField.appendChild(servicesLabel);
        servicesField.appendChild(servicesInput);
        servicesContainer.appendChild(servicesField);
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
    setupEls.issuerId.value = cfg.apple_issuer_id || '';
    setupEls.playService.value = cfg.play_service_account_path || '';

    setupEls.autoReleaseEnabled.checked = !!cfg.auto_release_on_success;
    setupEls.autoReleaseAction.value = cfg.auto_release_action || 'release_push';
    setupEls.autoReleaseFlavors.value = (cfg.auto_release_flavors || ['prod']).join(', ');

    // Show stored Key ID info in the dropzone area
    renderP8KeyInfo(cfg);

    fetchAndRenderCertStatus(appId);

    setupEls.noApp.classList.add('hidden');
    setupEls.form.classList.remove('hidden');
    if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
}

/** Render stored .p8 key metadata beneath the dropzone. */
function renderP8KeyInfo(cfg) {
    const keyId = cfg.apple_key_id || '';
    const hasKey = !!cfg.apple_p8_base64;

    // Reset dropzone title
    setupEls.p8DropzoneTitle.textContent =
        hasKey
            ? `✅ Key uploaded — drop a new file to replace`
            : 'Drag & drop AuthKey_XXXXXXXXXX.p8 or click to browse';

    if (keyId) {
        setupEls.p8CurrentKeyInfo.style.display = 'block';
        setupEls.p8CurrentKeyId.textContent = keyId;
        setupEls.p8CurrentKeyPath.textContent =
            `~/.appstoreconnect/private_keys/AuthKey_${keyId}.p8`;
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
    // Preserve any already-uploaded p8 fields — those are written by the /p8/upload
    // endpoint and should NOT be overwritten when the user clicks "Save Config".
    const existingCfg = setupState.deployConfig.apps?.[setupState.selectedAppId] || {};
    const values = {
        flavors: flavors,
        apple_id: setupEls.appleId.value.trim(),
        apple_issuer_id: setupEls.issuerId.value.trim(),
        // Preserve Base64 + key ID written by /api/deployment/p8/upload
        apple_key_id: existingCfg.apple_key_id || '',
        apple_p8_base64: existingCfg.apple_p8_base64 || '',
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
        // Update in-memory config so Save Config preserves the new key
        if (!setupState.deployConfig.apps) { setupState.deployConfig.apps = {}; }
        if (!setupState.deployConfig.apps[setupState.selectedAppId]) {
            setupState.deployConfig.apps[setupState.selectedAppId] = {};
        }
        // The backend already persisted these; sync them locally so readFormValues picks them up
        setupState.deployConfig.apps[setupState.selectedAppId].apple_key_id = res.key_id;
        // We don't get b64 back (too large), but the backend saved it — mark as present
        setupState.deployConfig.apps[setupState.selectedAppId].apple_p8_base64 = '__uploaded__';

        setupEls.p8DropzoneTitle.textContent = `✅ Key uploaded — drop a new file to replace`;

        // Show status badge
        setupEls.p8UploadStatus.dataset.status = 'valid';
        setupEls.p8UploadStatus.textContent =
            `✅ Key ID: ${res.key_id}  •  Stored at: ${res.stored_path}`;
        setupEls.p8UploadStatus.style.display = 'block';

        // Show persistent key info line
        setupEls.p8CurrentKeyInfo.style.display = 'block';
        setupEls.p8CurrentKeyId.textContent = res.key_id;
        setupEls.p8CurrentKeyPath.textContent = res.stored_path;

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
// Utilities
// ─────────────────────────────────────────────────────────────────────────────

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
