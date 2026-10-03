/**
 * app_adb.js — Wireless & Multi-Device ADB Management Module
 * Handles:
 * 1. Discovering USB, Wi-Fi, and emulator Android devices
 * 2. Pairing wireless devices via adb connect <ip>:<port>
 * 3. Parallel APK installation across multiple selected test phones
 */

let connectedAdbDevices = [];

async function loadAdbDevices() {
    if (!els.adbDeviceListContainer) return;
    els.adbDeviceListContainer.innerHTML = '<div style="text-align:center; color:var(--ui-text-muted); font-size:0.82rem; padding:12px;">Querying ADB devices...</div>';
    try {
        const res = await fetch(api('/api/deployment/adb/devices'));
        const data = await res.json();
        connectedAdbDevices = data.devices || [];

        if (els.adbDeviceCount) {
            els.adbDeviceCount.textContent = connectedAdbDevices.length;
        }

        if (!data.adbAvailable) {
            els.adbDeviceListContainer.innerHTML = `<div style="color:#ef4444; font-size:0.8rem; padding:8px;">⚠️ ${escapeHtml(data.message || 'ADB binary not found')}</div>`;
            return;
        }

        if (connectedAdbDevices.length === 0) {
            els.adbDeviceListContainer.innerHTML = `
                <div style="text-align:center; color:var(--ui-text-muted); font-size:0.8rem; padding:16px;">
                    No Android devices found.<br>
                    Connect via USB or enter Wi-Fi target IP:port above.
                </div>`;
            return;
        }

        els.adbDeviceListContainer.innerHTML = connectedAdbDevices.map(d => {
            const isReady = d.isReady;
            const badgeBg = d.type === 'wifi' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(16, 185, 129, 0.2)';
            const badgeColor = d.type === 'wifi' ? '#38bdf8' : '#34d399';
            const typeLabel = d.type === 'wifi' ? '📶 Wi-Fi' : (d.type === 'emulator' ? '💻 Emulator' : '🔌 USB');
            const statusLabel = isReady ? 'Ready' : d.status;

            return `
                <label style="display:flex; align-items:center; justify-content:space-between; padding:10px 12px; background:var(--ui-bg-secondary, #1e293b); border:1px solid var(--ui-border-color); border-radius:6px; cursor:${isReady ? 'pointer' : 'not-allowed'}; opacity:${isReady ? '1' : '0.6'};">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <input type="checkbox" name="adbDeviceSelect" value="${escapeHtml(d.serial)}" ${isReady ? 'checked' : 'disabled'}>
                        <div>
                            <div style="font-weight:600; font-size:0.85rem;">${escapeHtml(d.model)}</div>
                            <div style="font-size:0.72rem; color:var(--ui-text-muted); font-family:monospace;">${escapeHtml(d.serial)}</div>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="font-size:0.7rem; font-weight:600; padding:2px 8px; border-radius:12px; background:${badgeBg}; color:${badgeColor};">${typeLabel}</span>
                        <span style="font-size:0.7rem; color:${isReady ? '#10b981' : '#f59e0b'}; font-weight:600;">${statusLabel}</span>
                    </div>
                </label>`;
        }).join('');
    } catch (err) {
        els.adbDeviceListContainer.innerHTML = `<div style="color:#ef4444; font-size:0.8rem; padding:8px;">Failed to load devices: ${escapeHtml(err.message)}</div>`;
    }
}

function openAdbModal() {
    if (els.adbModalOverlay) {
        els.adbModalOverlay.classList.add('ui-active');
    }
    const apkData = window.currentApkInfo || null;
    if (els.adbModalApkInfo && apkData) {
        els.adbModalApkInfo.textContent = `APK: ${apkData.filename} (${apkData.sizeFormatted})`;
    }
    if (els.adbInstallResults) {
        els.adbInstallResults.classList.add('hidden');
        els.adbInstallResults.innerHTML = '';
    }
    loadAdbDevices();
    if (typeof refreshIcons === 'function') refreshIcons();
}

function closeAdbModal() {
    if (els.adbModalOverlay) {
        els.adbModalOverlay.classList.remove('ui-active');
    }
}

async function connectWirelessAdb() {
    const input = els.adbConnectAddressInput;
    if (!input || !input.value.trim()) return;
    const address = input.value.trim();
    showToast(`Connecting to ${address}...`);
    try {
        const res = await fetch(api('/api/deployment/adb/connect'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({address}),
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Connected to ${address}!`, 'success');
            input.value = '';
            loadAdbDevices();
        } else {
            showToast(data.error || 'Connection failed', 'error');
        }
    } catch (err) {
        showToast(`Connection error: ${err.message}`, 'error');
    }
}

async function pushApkToAdb() {
    const selectedCheckboxes = document.querySelectorAll('input[name="adbDeviceSelect"]:checked');
    const serials = Array.from(selectedCheckboxes).map(cb => cb.value);

    if (serials.length === 0) {
        showToast('Please select at least one ready device', 'error');
        return;
    }

    const apkData = window.currentApkInfo || null;
    const target = apkData ? (apkData.jobId || apkData.app || 'latest') : 'latest';

    if (els.adbInstallSubmitBtn) {
        els.adbInstallSubmitBtn.disabled = true;
        els.adbInstallSubmitBtn.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Pushing APK in parallel...';
    }

    if (els.adbInstallResults) {
        els.adbInstallResults.classList.remove('hidden');
        els.adbInstallResults.innerHTML = '<div style="color:var(--ui-text-muted); font-size:0.8rem; text-align:center;">Pushing APK simultaneously to all selected devices...</div>';
    }

    try {
        const res = await fetch(api('/api/deployment/adb/push'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({target, devices: serials}),
        });
        const data = await res.json();

        if (els.adbInstallSubmitBtn) {
            els.adbInstallSubmitBtn.disabled = false;
            els.adbInstallSubmitBtn.innerHTML = '<i data-lucide="upload-cloud"></i> Push APK to Selected';
        }

        if (data.success) {
            showToast(`Pushed to ${data.successCount}/${data.totalDevices} devices!`, 'success');
            if (els.adbInstallResults) {
                els.adbInstallResults.innerHTML = `
                    <div style="font-weight:700; font-size:0.85rem; margin-bottom:8px; color:${data.failedCount === 0 ? '#10b981' : '#f59e0b'};">
                        ✓ Installed on ${data.successCount} of ${data.totalDevices} device(s)
                    </div>
                    <div style="display:flex; flex-direction:column; gap:6px;">
                        ${(data.results || []).map(r => `
                            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.78rem; background:rgba(255,255,255,0.05); padding:6px 10px; border-radius:4px;">
                                <span><strong>${escapeHtml(r.model)}</strong> (${escapeHtml(r.serial)})</span>
                                <span style="color:${r.status === 'success' ? '#10b981' : '#ef4444'}; font-weight:600;">
                                    ${r.status === 'success' ? `✓ Installed in ${r.durationSeconds}s` : `✗ ${escapeHtml(r.output)}`}
                                </span>
                            </div>
                        `).join('')}
                    </div>`;
            }
        } else {
            showToast(data.error || 'Push failed', 'error');
            if (els.adbInstallResults) {
                els.adbInstallResults.innerHTML = `<div style="color:#ef4444; font-size:0.8rem;">❌ ${escapeHtml(data.error || 'Push failed')}</div>`;
            }
        }
    } catch (err) {
        if (els.adbInstallSubmitBtn) {
            els.adbInstallSubmitBtn.disabled = false;
            els.adbInstallSubmitBtn.innerHTML = '<i data-lucide="upload-cloud"></i> Push APK to Selected';
        }
        showToast(`Failed: ${err.message}`, 'error');
    }
    if (typeof refreshIcons === 'function') refreshIcons();
}

// ═════════════════════════════════════════════════════════════════════
// Wire Events
// ═════════════════════════════════════════════════════════════════════
if (els.adbPushBtn) els.adbPushBtn.addEventListener('click', openAdbModal);
if (els.closeAdbModalBtn) els.closeAdbModalBtn.addEventListener('click', closeAdbModal);
if (els.adbModalOverlay) {
    els.adbModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.adbModalOverlay) closeAdbModal();
    });
}
if (els.adbRefreshDevicesBtn) els.adbRefreshDevicesBtn.addEventListener('click', loadAdbDevices);
if (els.adbConnectBtn) els.adbConnectBtn.addEventListener('click', connectWirelessAdb);
if (els.adbInstallSubmitBtn) els.adbInstallSubmitBtn.addEventListener('click', pushApkToAdb);

// Global exports
window.connectedAdbDevices = connectedAdbDevices;
window.openAdbModal = openAdbModal;
window.closeAdbModal = closeAdbModal;
window.loadAdbDevices = loadAdbDevices;
window.connectWirelessAdb = connectWirelessAdb;
window.pushApkToAdb = pushApkToAdb;
