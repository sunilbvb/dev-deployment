/**
 * app_apk_qr.js — Local APK & QR Code Distribution Module
 * Handles local APK detection after build, ASCII and SVG QR code rendering,
 * Wi-Fi direct download generation, and modal display.
 */

let currentApkInfo = null;

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

async function openQrModalForTarget(targetId, app = '', flavor = '') {
    try {
        const res = await fetch(api(`/api/deployment/apk-info?jobId=${encodeURIComponent(targetId)}&app=${encodeURIComponent(app)}&flavor=${encodeURIComponent(flavor)}`));
        const data = await res.json();
        if (data.success && data.hasApk) {
            currentApkInfo = data;
            openQrModal(data);
        } else {
            showToast(data.message || 'No APK found for this build', 'error');
        }
    } catch (err) {
        showToast('Failed to load APK details', 'error');
    }
}

// Wire APK/QR Events
if (els.openQrModalBtn) {
    els.openQrModalBtn.addEventListener('click', () => openQrModal());
}
if (els.closeQrModalBtn) {
    els.closeQrModalBtn.addEventListener('click', closeQrModal);
}
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

// Attach to window
window.currentApkInfo = currentApkInfo;
window.writeTerminalBox = writeTerminalBox;
window.checkAndDisplayApk = checkAndDisplayApk;
window.openQrModal = openQrModal;
window.closeQrModal = closeQrModal;
window.openQrModalForTarget = openQrModalForTarget;
