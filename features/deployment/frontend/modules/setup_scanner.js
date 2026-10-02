/**
 * setup_scanner.js — Setup Scanner Module
 * Handles auto-scanning configuration from project files (flavors, bundle IDs,
 * Android package names, google-services), rescanning workspace, and inspecting new app paths.
 */

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

async function detectAppFromPath() {
    const newAppPath = document.getElementById('newAppPath');
    const pathDetectBadge = document.getElementById('pathDetectBadge');
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

// Attach to window
window.autoScanConfig = autoScanConfig;
window.autoScanAllConfig = autoScanAllConfig;
window.rescanWorkspace = rescanWorkspace;
window.detectAppFromPath = detectAppFromPath;
