/**
 * app_apk_qr.js — Mobile Artifacts, Wireless ADB, Profiler & Cache Warmer Module
 * Handles:
 * 1. Android APK detection & QR modal
 * 2. Instant Apple iOS OTA (itms-services) detection & QR modal
 * 3. Wireless ADB 1-click multi-device push & target connect
 * 4. Build Time Profiler & Compilation Bottleneck Heatmap
 * 5. Smart Silent Cache Warmer status & manual trigger
 */

let currentApkInfo = null;
let currentIpaInfo = null;
let currentProfileInfo = null;
let connectedAdbDevices = [];

function writeTerminalBox(content, title = '') {
    if (!els.terminalOutput) return;
    const box = document.createElement('div');
    box.className = 'qr-terminal-box';
    if (title) {
        const header = document.createElement('div');
        header.style.cssText = 'font-weight:700; margin-bottom:6px; color:#34d399; font-size:12px;';
        header.textContent = title;
        box.appendChild(header);
    }
    const pre = document.createElement('pre');
    pre.style.cssText = 'margin:0; font-family:monospace; font-size:11px; line-height:1.15;';
    pre.textContent = content;
    box.appendChild(pre);
    els.terminalOutput.appendChild(box);
    els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;
}

// ═════════════════════════════════════════════════════════════════════
// 1. Android APK & QR
// ═════════════════════════════════════════════════════════════════════
async function checkAndDisplayApk(jobId, app, flavor) {
    try {
        const targetApp = app || state.selectedApp || '';
        const targetFlavor = flavor || state.selectedEnv || '';
        const res = await fetch(api(`/api/deployment/apk-info?jobId=${encodeURIComponent(jobId || '')}&app=${encodeURIComponent(targetApp)}&flavor=${encodeURIComponent(targetFlavor)}`));
        const data = await res.json();
        if (data.success && data.hasApk) {
            currentApkInfo = data;

            if (els.apkInstallBanner) {
                if (els.apkBannerFilename) els.apkBannerFilename.textContent = data.filename;
                if (els.apkBannerSize) els.apkBannerSize.textContent = data.sizeFormatted;
                if (els.bannerDownloadBtn) {
                    els.bannerDownloadBtn.href = data.localUrl || data.downloadUrl;
                    els.bannerDownloadBtn.setAttribute('download', data.filename);
                }
                els.apkInstallBanner.classList.remove('hidden');
                if (typeof refreshIcons === 'function') refreshIcons();
            }

            if (typeof writeTerminal === 'function') {
                writeTerminal(`📲 Android APK ready: ${data.filename} (${data.sizeFormatted})`, 'success');
                writeTerminal(`📥 Wi-Fi Download Link: ${data.downloadUrl}`);
            }
            if (data.qrAscii) {
                writeTerminalBox(data.qrAscii, `Scan on Wi-Fi (${data.lanIp}) to Install:`);
            }
        }
    } catch (err) {
        console.warn('Could not inspect APK artifacts:', err);
    }
}

function openQrModal(apkData = currentApkInfo) {
    if (!apkData) return;
    if (els.qrCodeContainer) {
        els.qrCodeContainer.innerHTML = apkData.qrSvg || '<p>QR Code unavailable</p>';
    }
    if (els.qrApkFilename) els.qrApkFilename.textContent = apkData.filename || '-';
    if (els.qrApkSize) els.qrApkSize.textContent = apkData.sizeFormatted || '-';
    if (els.qrApkPath) els.qrApkPath.textContent = apkData.path || '-';
    if (els.qrDownloadUrlInput) els.qrDownloadUrlInput.value = apkData.downloadUrl || '';
    if (els.directDownloadApkBtn) {
        els.directDownloadApkBtn.href = apkData.localUrl || apkData.downloadUrl || '#';
        els.directDownloadApkBtn.setAttribute('download', apkData.filename || 'app.apk');
    }
    if (els.qrLanIpLabel) els.qrLanIpLabel.textContent = apkData.lanIp || 'local Wi-Fi';

    if (els.qrModalOverlay) {
        els.qrModalOverlay.classList.add('ui-active');
    }
    if (typeof refreshIcons === 'function') refreshIcons();
}

function closeQrModal() {
    if (els.qrModalOverlay) {
        els.qrModalOverlay.classList.remove('ui-active');
    }
}

// ═════════════════════════════════════════════════════════════════════
// 2. iOS Instant OTA QR Install
// ═════════════════════════════════════════════════════════════════════
async function checkAndDisplayIpa(jobId, app, flavor) {
    try {
        const targetApp = app || state.selectedApp || '';
        const targetFlavor = flavor || state.selectedEnv || '';
        const res = await fetch(api(`/api/deployment/ipa-info?jobId=${encodeURIComponent(jobId || '')}&app=${encodeURIComponent(targetApp)}&flavor=${encodeURIComponent(targetFlavor)}`));
        const data = await res.json();
        if (data.success && data.hasIpa) {
            currentIpaInfo = data;

            if (els.ipaInstallBanner) {
                if (els.ipaBannerFilename) els.ipaBannerFilename.textContent = data.filename;
                if (els.ipaBannerSize) els.ipaBannerSize.textContent = data.sizeFormatted;
                if (els.bannerIpaDownloadBtn) {
                    els.bannerIpaDownloadBtn.href = data.ipaDownloadUrl;
                    els.bannerIpaDownloadBtn.setAttribute('download', data.filename);
                }
                els.ipaInstallBanner.classList.remove('hidden');
                if (typeof refreshIcons === 'function') refreshIcons();
            }

            if (typeof writeTerminal === 'function') {
                writeTerminal(`🍎 iOS IPA ready: ${data.filename} (${data.sizeFormatted})`, 'success');
                writeTerminal(`⚡ Instant Apple OTA URL: ${data.itmsUrl}`);
            }
            if (data.qrAscii) {
                writeTerminalBox(data.qrAscii, `Scan with iPhone Camera (${data.lanIp}) for 10s OTA Install:`);
            }
        }
    } catch (err) {
        console.warn('Could not inspect iOS IPA artifacts:', err);
    }
}

function openIpaQrModal(ipaData = currentIpaInfo) {
    if (!ipaData) return;
    if (els.ipaQrCodeContainer) {
        els.ipaQrCodeContainer.innerHTML = ipaData.qrSvg || '<p>QR Code unavailable</p>';
    }
    if (els.qrIpaFilename) els.qrIpaFilename.textContent = ipaData.filename || '-';
    if (els.qrIpaSize) els.qrIpaSize.textContent = ipaData.sizeFormatted || '-';
    if (els.qrIpaBundleId) els.qrIpaBundleId.textContent = `Bundle ID: ${ipaData.bundleId || '-'}`;
    if (els.qrIpaUrlInput) els.qrIpaUrlInput.value = ipaData.itmsUrl || ipaData.ipaDownloadUrl || '';
    if (els.directDownloadIpaBtn) {
        els.directDownloadIpaBtn.href = ipaData.ipaDownloadUrl || '#';
        els.directDownloadIpaBtn.setAttribute('download', ipaData.filename || 'app.ipa');
    }

    if (els.ipaQrModalOverlay) {
        els.ipaQrModalOverlay.classList.add('ui-active');
    }
    if (typeof refreshIcons === 'function') refreshIcons();
}

function closeIpaQrModal() {
    if (els.ipaQrModalOverlay) {
        els.ipaQrModalOverlay.classList.remove('ui-active');
    }
}

// ═════════════════════════════════════════════════════════════════════
// 3. Wireless ADB Multi-Device Push
// ═════════════════════════════════════════════════════════════════════
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
    if (els.adbModalApkInfo && currentApkInfo) {
        els.adbModalApkInfo.textContent = `APK: ${currentApkInfo.filename} (${currentApkInfo.sizeFormatted})`;
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

    const target = currentApkInfo ? (currentApkInfo.jobId || currentApkInfo.app || 'latest') : 'latest';

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
// 4. Build Time Profiler & Compilation Bottleneck Heatmap
// ═════════════════════════════════════════════════════════════════════
async function checkAndDisplayBuildProfile(jobId) {
    try {
        const res = await fetch(api(`/api/deployment/build-profile?id=${encodeURIComponent(jobId || '')}`));
        const data = await res.json();
        if (data.success && data.phases) {
            currentProfileInfo = data;
            if (els.buildProfilerBanner) {
                if (els.buildProfilerSummaryText) {
                    els.buildProfilerSummaryText.textContent = `Build Profile: ${data.summary}`;
                }
                if (els.buildProfilerSubtext) {
                    els.buildProfilerSubtext.textContent = `Total Time: ${data.totalDurationSeconds}s · ${data.phases.length} phases profiled`;
                }
                els.buildProfilerBanner.classList.remove('hidden');
                els.buildProfilerBanner.style.display = 'block';
                if (typeof refreshIcons === 'function') refreshIcons();
            }
        }
    } catch (err) {
        console.warn('Could not inspect build profile:', err);
    }
}

function openBuildProfilerModal(profileData = currentProfileInfo) {
    if (!profileData) return;
    if (els.bpTotalDurationText) {
        els.bpTotalDurationText.textContent = `${profileData.totalDurationSeconds}s Total`;
    }
    if (els.bpSummaryText) {
        els.bpSummaryText.textContent = profileData.summary || 'Build timings';
    }
    if (els.bpFooterJobInfo) {
        els.bpFooterJobInfo.textContent = `Job: ${profileData.jobId || 'latest'} · ${profileData.app || ''} (${profileData.flavor || ''})`;
    }

    // Render horizontal progress bar segments
    if (els.bpProgressBar && profileData.phases) {
        els.bpProgressBar.innerHTML = profileData.phases.map(p => {
            if (p.percentage <= 0) return '';
            return `<div style="width:${p.percentage}%; background:${p.color}; height:100%; transition:width 0.3s;" title="${escapeHtml(p.name)}: ${p.durationSeconds}s (${p.percentage}%)"></div>`;
        }).join('');
    }

    // Render bottleneck cards
    if (els.bpBottlenecksContainer) {
        if (profileData.bottlenecks && profileData.bottlenecks.length > 0) {
            els.bpBottlenecksContainer.innerHTML = profileData.bottlenecks.map(b => `
                <div style="background:rgba(245, 158, 11, 0.1); border:1px solid #f59e0b; border-radius:6px; padding:10px 14px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-weight:700; font-size:0.85rem; color:#f59e0b;">⚠️ Bottleneck: ${escapeHtml(b.phaseName)} (${b.percentage}%)</span>
                        <span class="ui-badge" data-variant="warning">${b.severity.toUpperCase()}</span>
                    </div>
                    <div style="font-size:0.78rem; color:var(--ui-text-muted); line-height:1.4;">
                        💡 <strong>Optimization Tip:</strong> ${escapeHtml(b.tip)}
                    </div>
                </div>
            `).join('');
        } else {
            els.bpBottlenecksContainer.innerHTML = `
                <div style="background:rgba(16, 185, 129, 0.1); border:1px solid #10b981; border-radius:6px; padding:10px 14px; font-size:0.82rem; color:#10b981;">
                    ✓ No significant compile bottlenecks detected. Timing is balanced across build phases.
                </div>`;
        }
    }

    // Render phase table
    if (els.bpTableBody && profileData.phases) {
        els.bpTableBody.innerHTML = profileData.phases.map(p => `
            <tr style="border-top:1px solid var(--ui-border-color);">
                <td style="padding:10px 14px; font-weight:600; display:flex; align-items:center; gap:8px;">
                    <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${p.color};"></span>
                    <span>${escapeHtml(p.name)}</span>
                </td>
                <td style="padding:10px 14px; font-family:monospace;">${p.durationSeconds}s</td>
                <td style="padding:10px 14px; font-weight:700;">${p.percentage}%</td>
                <td style="padding:10px 14px; color:var(--ui-text-muted); font-size:0.78rem;">${escapeHtml(p.tip || '-')}</td>
            </tr>
        `).join('');
    }

    if (els.buildProfilerModalOverlay) {
        els.buildProfilerModalOverlay.classList.add('ui-active');
    }
    if (typeof refreshIcons === 'function') refreshIcons();
}

function closeBuildProfilerModal() {
    if (els.buildProfilerModalOverlay) {
        els.buildProfilerModalOverlay.classList.remove('ui-active');
    }
}

// ═════════════════════════════════════════════════════════════════════
// 5. Smart Silent Cache Warmer
// ═════════════════════════════════════════════════════════════════════
async function refreshCacheWarmerStatus() {
    try {
        const res = await fetch(api('/api/deployment/cache-warmer/status'));
        const data = await res.json();
        if (data.success && els.cacheWarmerBadgeText) {
            const st = data.status || 'idle';
            if (st === 'warming') {
                els.cacheWarmerBadgeText.textContent = 'Cache: Warming...';
            } else if (st === 'warm') {
                els.cacheWarmerBadgeText.textContent = `Cache: Warm (${data.lastBranch || 'main'})`;
            } else if (st === 'error') {
                els.cacheWarmerBadgeText.textContent = 'Cache: Error';
            } else {
                els.cacheWarmerBadgeText.textContent = 'Cache: Idle';
            }
        }
    } catch (_) {}
}

async function triggerCacheWarmer() {
    showToast('Starting silent background dependency pre-fetch...');
    try {
        const res = await fetch(api('/api/deployment/cache-warmer/warm'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({force: true}),
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Dependencies warmed in ${data.durationSeconds}s!`, 'success');
            refreshCacheWarmerStatus();
        } else {
            showToast(data.error || 'Cache warming failed', 'error');
        }
    } catch (err) {
        showToast(`Cache warmer error: ${err.message}`, 'error');
    }
}

// ═════════════════════════════════════════════════════════════════════
// Wire Events
// ═════════════════════════════════════════════════════════════════════
// APK
if (els.openQrModalBtn) els.openQrModalBtn.addEventListener('click', () => openQrModal());
if (els.closeQrModalBtn) els.closeQrModalBtn.addEventListener('click', closeQrModal);
if (els.qrModalOverlay) {
    els.qrModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.qrModalOverlay) closeQrModal();
    });
}
if (els.copyQrUrlBtn) {
    els.copyQrUrlBtn.addEventListener('click', async () => {
        if (els.qrDownloadUrlInput && els.qrDownloadUrlInput.value) {
            try {
                await navigator.clipboard.writeText(els.qrDownloadUrlInput.value);
                showToast('Wi-Fi download URL copied!');
            } catch (_) {
                els.qrDownloadUrlInput.select();
                document.execCommand('copy');
                showToast('Wi-Fi download URL copied!');
            }
        }
    });
}

// iOS OTA
if (els.openIpaQrModalBtn) els.openIpaQrModalBtn.addEventListener('click', () => openIpaQrModal());
if (els.closeIpaQrModalBtn) els.closeIpaQrModalBtn.addEventListener('click', closeIpaQrModal);
if (els.ipaQrModalOverlay) {
    els.ipaQrModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.ipaQrModalOverlay) closeIpaQrModal();
    });
}
if (els.copyIpaQrUrlBtn) {
    els.copyIpaQrUrlBtn.addEventListener('click', async () => {
        if (els.qrIpaUrlInput && els.qrIpaUrlInput.value) {
            try {
                await navigator.clipboard.writeText(els.qrIpaUrlInput.value);
                showToast('Apple OTA itms-services URL copied!');
            } catch (_) {
                els.qrIpaUrlInput.select();
                document.execCommand('copy');
                showToast('Apple OTA itms-services URL copied!');
            }
        }
    });
}

// ADB
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

// Build Profiler
if (els.buildProfilerBanner) els.buildProfilerBanner.addEventListener('click', () => openBuildProfilerModal());
if (els.closeBuildProfilerModalBtn) els.closeBuildProfilerModalBtn.addEventListener('click', closeBuildProfilerModal);
if (els.closeBuildProfilerBtn) els.closeBuildProfilerBtn.addEventListener('click', closeBuildProfilerModal);
if (els.buildProfilerModalOverlay) {
    els.buildProfilerModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.buildProfilerModalOverlay) closeBuildProfilerModal();
    });
}

// Cache Warmer
if (els.cacheWarmerHeaderBadge) {
    els.cacheWarmerHeaderBadge.addEventListener('click', triggerCacheWarmer);
}
refreshCacheWarmerStatus();
setInterval(refreshCacheWarmerStatus, 30000);

// Attach to window
window.currentApkInfo = currentApkInfo;
window.currentIpaInfo = currentIpaInfo;
window.currentProfileInfo = currentProfileInfo;
window.writeTerminalBox = writeTerminalBox;
window.checkAndDisplayApk = checkAndDisplayApk;
window.checkAndDisplayIpa = checkAndDisplayIpa;
window.checkAndDisplayBuildProfile = checkAndDisplayBuildProfile;
window.openQrModal = openQrModal;
window.closeQrModal = closeQrModal;
window.openIpaQrModal = openIpaQrModal;
window.closeIpaQrModal = closeIpaQrModal;
window.openAdbModal = openAdbModal;
window.closeAdbModal = closeAdbModal;
window.openBuildProfilerModal = openBuildProfilerModal;
window.closeBuildProfilerModal = closeBuildProfilerModal;
window.refreshCacheWarmerStatus = refreshCacheWarmerStatus;
window.triggerCacheWarmer = triggerCacheWarmer;
