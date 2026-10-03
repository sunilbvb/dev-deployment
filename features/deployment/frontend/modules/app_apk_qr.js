/**
 * app_apk_qr.js — Mobile Artifacts & QR Scan-to-Install Module
 * Handles:
 * 1. Android APK detection, banner display & QR modal
 * 2. Instant Apple iOS OTA (itms-services) detection & Camera QR modal
 */

let currentApkInfo = null;
let currentIpaInfo = null;

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
// Wire Events
// ═════════════════════════════════════════════════════════════════════
// Android APK
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
                showToast('APK Download URL copied!');
            } catch (_) {
                els.qrDownloadUrlInput.select();
                document.execCommand('copy');
                showToast('APK Download URL copied!');
            }
        }
    });
}

// iOS IPA
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

// Global exports
window.currentApkInfo = currentApkInfo;
window.currentIpaInfo = currentIpaInfo;
window.writeTerminalBox = writeTerminalBox;
window.checkAndDisplayApk = checkAndDisplayApk;
window.checkAndDisplayIpa = checkAndDisplayIpa;
window.openQrModal = openQrModal;
window.closeQrModal = closeQrModal;
window.openIpaQrModal = openIpaQrModal;
window.closeIpaQrModal = closeIpaQrModal;
