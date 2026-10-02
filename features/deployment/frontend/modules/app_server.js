/**
 * app_server.js — Server Status & Console Controller Module
 * Handles server heartbeat, status UI indicator, start / restart / stop actions,
 * desktop launcher installation, systemd service setup, and server console modal.
 */

let serverHeartbeatTimer = null;

function formatUptime(sec) {
    if (!sec || isNaN(sec)) return '-';
    sec = Math.floor(sec);
    if (sec < 60) return `${sec}s`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    if (m < 60) return `${m}m ${s}s`;
    const h = Math.floor(m / 60);
    const rm = m % 60;
    return `${h}h ${rm}m`;
}

function updateServerStatusUI(isOnline, info = {}) {
    state.isServerOnline = isOnline;
    const uptimeStr = formatUptime(info.uptimeSeconds);

    if (els.serverStatusDot && els.serverStatusText && els.serverStatusBadge) {
        if (isOnline) {
            els.serverStatusDot.style.background = 'var(--ui-success, #22c55e)';
            const portText = info.port ? ` (${info.port})` : '';
            els.serverStatusText.textContent = `Server: Online${portText}`;
            els.serverStatusBadge.setAttribute('data-variant', 'success');
            els.serverStatusBadge.title = `Connected to local server on port ${info.port || 18112}. Click for server console.`;

            // Hide offline banner if online
            if (els.serverOfflineBanner) {
                els.serverOfflineBanner.style.display = 'none';
                els.serverOfflineBanner.classList.add('hidden');
            }
        } else {
            els.serverStatusDot.style.background = 'var(--ui-warning, #f59e0b)';
            els.serverStatusText.textContent = 'Server: Offline';
            els.serverStatusBadge.setAttribute('data-variant', 'warning');
            els.serverStatusBadge.title = 'Server offline. Click to view launch commands.';

            // Show offline banner unless demo mode is active
            if (els.serverOfflineBanner && !state.isDemoMode) {
                els.serverOfflineBanner.style.display = 'block';
                els.serverOfflineBanner.classList.remove('hidden');
            }
        }
    }

    // Update Server Console Modal details if present
    if (els.serverModalStatusTitle && els.serverModalStatusBadge) {
        if (isOnline) {
            els.serverModalStatusTitle.textContent = '🟢 Server Online & Connected';
            els.serverModalStatusBadge.setAttribute('data-variant', 'success');
            els.serverModalStatusBadge.textContent = 'ONLINE';
            if (els.serverModalUrl) els.serverModalUrl.textContent = `http://localhost:${info.port || 18112}`;
            if (els.serverModalPort) els.serverModalPort.textContent = info.port || 18112;
            if (els.serverModalPid) els.serverModalPid.textContent = info.pid || 'Active';
            if (els.serverModalPython) els.serverModalPython.textContent = info.pythonVersion || 'Python 3';
            if (els.serverModalUptimeRow && els.serverModalUptime) {
                els.serverModalUptimeRow.style.display = 'block';
                els.serverModalUptime.textContent = uptimeStr;
            }
        } else {
            els.serverModalStatusTitle.textContent = '🟠 Server Offline';
            els.serverModalStatusBadge.setAttribute('data-variant', 'warning');
            els.serverModalStatusBadge.textContent = 'OFFLINE';
            if (els.serverModalUrl) els.serverModalUrl.textContent = 'http://localhost:18112 (not responding)';
            if (els.serverModalPort) els.serverModalPort.textContent = '18112 (default)';
            if (els.serverModalPid) els.serverModalPid.textContent = 'Not running';
            if (els.serverModalPython) els.serverModalPython.textContent = 'Requires Python 3.10+';
            if (els.serverModalUptimeRow) els.serverModalUptimeRow.style.display = 'none';
        }
    }

    // Update Configure Server Panel if present
    if (els.cfgServerStatusBadge) {
        els.cfgServerStatusBadge.setAttribute('data-variant', isOnline ? 'success' : 'warning');
        els.cfgServerStatusBadge.textContent = isOnline ? 'ONLINE' : 'OFFLINE';
    }
    if (els.cfgServerStatusText) {
        els.cfgServerStatusText.textContent = isOnline ? '🟢 Online' : '🟠 Offline';
        els.cfgServerStatusText.style.color = isOnline ? 'var(--ui-success, #22c55e)' : 'var(--ui-warning, #f59e0b)';
    }
    if (els.cfgServerPortText) els.cfgServerPortText.textContent = info.port || '18112';
    if (els.cfgServerPidText) els.cfgServerPidText.textContent = isOnline ? (info.pid || 'Active') : 'Not running';
    if (els.cfgServerUptimeText) els.cfgServerUptimeText.textContent = isOnline ? uptimeStr : '-';

    // Update lifecycle button states
    const updateButtons = (startBtn, restartBtn, stopBtn, endBtn) => {
        if (startBtn) {
            startBtn.disabled = isOnline;
            startBtn.innerHTML = isOnline ? '<i data-lucide="check"></i><span>Running</span>' : '<i data-lucide="play"></i><span>Start</span>';
        }
        if (restartBtn) restartBtn.disabled = !isOnline;
        if (stopBtn) stopBtn.disabled = !isOnline;
        if (endBtn) endBtn.disabled = !isOnline;
    };
    updateButtons(els.serverStartBtn, els.serverRestartBtn, els.serverStopBtn, els.serverEndBtn);
    updateButtons(els.cfgServerStartBtn, els.cfgServerRestartBtn, els.cfgServerStopBtn, els.cfgServerEndBtn);
    refreshIcons();
}

async function handleServerStart() {
    if (state.isServerOnline) {
        showToast('Server is already active and healthy!');
        return;
    }
    showToast('Checking connection to deployment server...');
    const ok = await checkServerStatus();
    if (ok) {
        showToast('Connected to local deployment server!');
    } else {
        showToast('Server is offline. Click "Create Desktop Shortcut" below or launch via terminal.', 'warning');
    }
}

async function handleServerRestart() {
    if (!state.isServerOnline) {
        showToast('Cannot restart: server is offline.', 'warning');
        return;
    }
    try {
        showToast('Restarting deployment server in-place...');
        if (els.serverRestartBtn) els.serverRestartBtn.disabled = true;
        if (els.cfgServerRestartBtn) els.cfgServerRestartBtn.disabled = true;

        await fetch(api('/api/deployment/server/restart'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });

        // Poll for server coming back online
        let attempts = 0;
        const pollInterval = setInterval(async () => {
            attempts++;
            const backOnline = await checkServerStatus(true);
            if (backOnline || attempts > 15) {
                clearInterval(pollInterval);
                if (backOnline) {
                    showToast('Server restarted successfully!');
                } else {
                    showToast('Server restart taking longer than expected.', 'warning');
                }
            }
        }, 600);
    } catch (_) {
        showToast('Restart initiated. Reconnecting...');
    }
}

async function handleServerStop() {
    if (!state.isServerOnline) {
        showToast('Server is already offline.');
        return;
    }
    try {
        showToast('Stopping deployment server...');
        await fetch(api('/api/deployment/server/stop'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        setTimeout(() => {
            updateServerStatusUI(false);
            showToast('Server stopped.');
        }, 500);
    } catch (_) {
        updateServerStatusUI(false);
    }
}

async function handleServerEnd() {
    if (!state.isServerOnline) {
        showToast('Server is already offline.');
        return;
    }
    try {
        showToast('Terminating server process...');
        await fetch(api('/api/deployment/server/end'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: true }),
        });
        setTimeout(() => {
            updateServerStatusUI(false);
            showToast('Server process terminated.');
        }, 400);
    } catch (_) {
        updateServerStatusUI(false);
    }
}

async function handleInstallDesktopShortcut(isFromCfg = false) {
    const statusEl = isFromCfg ? els.cfgLauncherStatusMsg : els.launcherStatusMsg;
    try {
        showToast('Creating desktop shortcut...');
        const res = await fetch(api('/api/deployment/server/install-desktop'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const data = await res.json();
        if (data && data.success) {
            showToast('Desktop shortcut created!');
            if (statusEl) {
                statusEl.style.display = 'block';
                statusEl.textContent = '✓ Desktop application launcher installed. Launch anytime without terminal!';
            }
        } else {
            showToast((data && data.error) || 'Failed to create shortcut', 'warning');
        }
    } catch (_) {
        showToast('Server must be active to create desktop integration.', 'warning');
    }
}

async function handleInstallSystemdService(isFromCfg = false) {
    const statusEl = isFromCfg ? els.cfgLauncherStatusMsg : els.launcherStatusMsg;
    try {
        showToast('Installing background systemd service...');
        const res = await fetch(api('/api/deployment/server/install-service'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const data = await res.json();
        if (data && data.success) {
            showToast('Background service installed and enabled!');
            if (statusEl) {
                statusEl.style.display = 'block';
                statusEl.textContent = '✓ Systemd user service active. Server runs automatically on login!';
            }
            await checkServerStatus();
        } else {
            showToast((data && (data.error || data.warning)) || 'Failed to install service', 'warning');
        }
    } catch (_) {
        showToast('Server must be active to configure service.', 'warning');
    }
}

async function checkServerStatus(silent = false) {
    try {
        const res = await fetch(api('/api/deployment/server-status'), {
            headers: { 'Cache-Control': 'no-cache' },
            signal: AbortSignal.timeout(2200),
        });
        const data = await res.json();
        if (data && data.status === 'online') {
            const wasOffline = state.isServerOnline === false;
            updateServerStatusUI(true, data);
            if (wasOffline && !state.isDemoMode) {
                showToast('Connected to local deployment server!');
                await loadWorkspaceInfo();
                await loadApps();
                await loadWorkspaceSentinel();
            }
            return true;
        }
    } catch (_) {}

    updateServerStatusUI(false);
    return false;
}

function startServerHeartbeat() {
    if (serverHeartbeatTimer) clearInterval(serverHeartbeatTimer);
    serverHeartbeatTimer = setInterval(() => {
        checkServerStatus(true);
    }, 3000);
}

function openServerConsoleModal() {
    if (els.serverConsoleModalOverlay) {
        els.serverConsoleModalOverlay.classList.add('ui-active');
        checkServerStatus();
    }
}

function closeServerConsoleModal() {
    if (els.serverConsoleModalOverlay) {
        els.serverConsoleModalOverlay.classList.remove('ui-active');
    }
}

// Wire Event Listeners
if (els.serverStatusBadge) {
    els.serverStatusBadge.addEventListener('click', openServerConsoleModal);
}
if (els.closeServerConsoleModalBtn) {
    els.closeServerConsoleModalBtn.addEventListener('click', closeServerConsoleModal);
}
if (els.closeServerConsoleBtn) {
    els.closeServerConsoleBtn.addEventListener('click', closeServerConsoleModal);
}
if (els.serverConsoleModalOverlay) {
    els.serverConsoleModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.serverConsoleModalOverlay) closeServerConsoleModal();
    });
}
if (els.copyStartCommandBtn) {
    els.copyStartCommandBtn.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText('./start.sh');
            showToast('Start command copied to clipboard!');
        } catch (_) {
            showToast('Start command: ./start.sh');
        }
    });
}
if (els.copyServerSnippetBtn) {
    els.copyServerSnippetBtn.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText('./start.sh');
            showToast('Launch command copied!');
        } catch (_) {
            showToast('Launch command: ./start.sh');
        }
    });
}
if (els.testServerReconnectBtn) {
    els.testServerReconnectBtn.addEventListener('click', async () => {
        showToast('Checking connection...');
        const ok = await checkServerStatus();
        if (ok) showToast('Server is online and responding!');
        else showToast('Server is still offline', 'warning');
    });
}

// Server Console & Configure Dialog Server Action Listeners
if (els.serverStartBtn) els.serverStartBtn.addEventListener('click', handleServerStart);
if (els.serverRestartBtn) els.serverRestartBtn.addEventListener('click', handleServerRestart);
if (els.serverStopBtn) els.serverStopBtn.addEventListener('click', handleServerStop);
if (els.serverEndBtn) els.serverEndBtn.addEventListener('click', handleServerEnd);
if (els.serverInstallDesktopBtn) els.serverInstallDesktopBtn.addEventListener('click', () => handleInstallDesktopShortcut(false));
if (els.serverInstallServiceBtn) els.serverInstallServiceBtn.addEventListener('click', () => handleInstallSystemdService(false));

if (els.cfgServerStartBtn) els.cfgServerStartBtn.addEventListener('click', handleServerStart);
if (els.cfgServerRestartBtn) els.cfgServerRestartBtn.addEventListener('click', handleServerRestart);
if (els.cfgServerStopBtn) els.cfgServerStopBtn.addEventListener('click', handleServerStop);
if (els.cfgServerEndBtn) els.cfgServerEndBtn.addEventListener('click', handleServerEnd);
if (els.cfgServerInstallDesktopBtn) els.cfgServerInstallDesktopBtn.addEventListener('click', () => handleInstallDesktopShortcut(true));
if (els.cfgServerInstallServiceBtn) els.cfgServerInstallServiceBtn.addEventListener('click', () => handleInstallSystemdService(true));

// Window exports
window.formatUptime = formatUptime;
window.updateServerStatusUI = updateServerStatusUI;
window.handleServerStart = handleServerStart;
window.handleServerRestart = handleServerRestart;
window.handleServerStop = handleServerStop;
window.handleServerEnd = handleServerEnd;
window.handleInstallDesktopShortcut = handleInstallDesktopShortcut;
window.handleInstallSystemdService = handleInstallSystemdService;
window.checkServerStatus = checkServerStatus;
window.startServerHeartbeat = startServerHeartbeat;
window.openServerConsoleModal = openServerConsoleModal;
window.closeServerConsoleModal = closeServerConsoleModal;
