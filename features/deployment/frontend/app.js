
// Keep in sync with router.py's STORE_UPLOAD_TEMPLATE_IDS - the template ids whose
// success means a build actually reached TestFlight/Play Store, not just a local
// artifact or a git tag/push.
const STORE_SHIPPING_TEMPLATE_IDS = new Set(['deploy_ipa', 'upload_ipa', 'deploy_aab', 'upload_aab', 'deploy_both']);


const state = {
    apps: [],
    commands: [],
    selectedApp: '',
    selectedCommand: null,
    selectedEnv: 'dev',
    hasMultipleEnvs: false,
    activeJobId: null,
    timerId: null,
    timerStartedAt: 0,
    stdoutLength: 0,
    stderrLength: 0,
    activeOutputView: 'live',
    historyEntries: [],
};

const els = {
    appGrid: document.getElementById('appGrid'),
    commandGrid: document.getElementById('commandGrid'),
    envTabs: document.getElementById('envTabs'),
    selectedAppName: document.getElementById('selectedAppName'),
    executionPanel: document.getElementById('executionPanel'),
    selectedCommandTitle: document.getElementById('selectedCommandTitle'),
    selectedCommandPreview: document.getElementById('selectedCommandPreview'),
    runButton: document.getElementById('runButton'),
    stopJobBtn: document.getElementById('stopJobBtn'),
    executionTimer: document.getElementById('executionTimer'),
    terminalOutput: document.getElementById('terminalOutput'),
    clearTerminalBtn: document.getElementById('clearTerminalBtn'),
    toast: document.getElementById('toast'),
    iosCertBanner: document.getElementById('iosCertBanner'),
    // History tab
    outputTabs: document.getElementById('outputTabs'),
    terminalView: document.getElementById('terminalView'),
    historyView: document.getElementById('historyView'),
    historyOutput: document.getElementById('historyOutput'),
    historyAppFilter: document.getElementById('historyAppFilter'),
    historyFlavorFilter: document.getElementById('historyFlavorFilter'),
    historyStatusFilter: document.getElementById('historyStatusFilter'),
    historyRefreshBtn: document.getElementById('historyRefreshBtn'),
    // Prod confirm modal
    prodConfirmOverlay: document.getElementById('prodConfirmOverlay'),
    prodConfirmAppName: document.getElementById('prodConfirmAppName'),
    prodConfirmCommandPreview: document.getElementById('prodConfirmCommandPreview'),
    cancelProdConfirmBtn: document.getElementById('cancelProdConfirmBtn'),
    closeProdConfirmBtn: document.getElementById('closeProdConfirmBtn'),
    confirmProdDeployBtn: document.getElementById('confirmProdDeployBtn'),
    // Deploy All Apps
};

// C9: Tab-isolated workspace - attach X-Workspace header to all fetch requests
const _nativeFetch = window.fetch;
window.fetch = function(input, init) {
    const opts = init || {};
    opts.headers = new Headers(opts.headers || {});
    if (window.__DEPLOYMENT_TOKEN__ && !opts.headers.has('X-API-Token')) {
        opts.headers.set('X-API-Token', window.__DEPLOYMENT_TOKEN__);
    }
    let curWs = state.activeWorkspace || '';
    if (!curWs) {
        try { curWs = sessionStorage.getItem('active_workspace') || ''; } catch (_) { /* storage may be blocked */ }
    }
    if (curWs && !opts.headers.has('X-Workspace')) {
        opts.headers.set('X-Workspace', curWs);
    }
    return _nativeFetch(input, opts);
};

function api(path) {
    return (typeof window.apiUrl === 'function') ? window.apiUrl(path) : path;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function showToast(message) {
    els.toast.textContent = message;
    els.toast.classList.remove('hidden');
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => els.toast.classList.add('hidden'), 2400);
}

function prettyCommandTitle(commandKey) {
    const key = String(commandKey || '');
    return key.split('-').filter(Boolean).map(part => {
        const lower = part.toLowerCase();
        if (lower === 'dev') return 'DEV';
        if (lower === 'qa' || lower === 'test') return 'QA';
        if (lower === 'prod') return 'PROD';
        if (lower === 'ipa') return 'IPA';
        if (lower === 'aab') return 'AAB';
        if (lower === 'apk') return 'APK';
        if (lower === 'ios') return 'iOS';
        return lower.charAt(0).toUpperCase() + lower.slice(1);
    }).join(' ');
}

const PLATFORM_META = {
    ios: {group: 'iOS', icon: 'apple', color: '#64748b'},
    android: {group: 'Android', icon: 'smartphone', color: '#22c55e'},
    combined: {group: 'Combined Deploy', icon: 'rocket', color: '#3b82f6'},
    release: {group: 'Release', icon: 'tag', color: '#8b5cf6'},
    utility: {group: 'Utilities', icon: 'wrench', color: '#94a3b8'},
};

function getCommandMeta(cmd) {
    // Group by the template's declared platform; the command text (e.g. "flutter build ipa --release") is ambiguous.
    if (cmd && typeof cmd === 'object') {
        if (PLATFORM_META[cmd.platform]) return PLATFORM_META[cmd.platform];
        cmd = cmd.key || cmd.id;
    }
    const k = String(cmd || '').toLowerCase();
    if (k.includes('release') || k.includes('tag')) return {group: 'Release', icon: 'tag', color: '#8b5cf6'};
    if (k.includes('ipa') || k.includes('ios')) return {group: 'iOS', icon: 'apple', color: '#64748b'};
    if (k.includes('aab') || k.includes('apk') || k.includes('android')) return {group: 'Android', icon: 'smartphone', color: '#22c55e'};
    if (k.includes('upload')) return {group: 'Upload', icon: 'upload-cloud', color: '#06b6d4'};
    if (k.includes('deploy')) return {group: 'Combined Deploy', icon: 'rocket', color: '#3b82f6'};
    if (k.includes('build')) return {group: 'Build', icon: 'hammer', color: '#eab308'};
    return {group: 'Other', icon: 'terminal', color: '#94a3b8'};
}

function matchesEnv(cmd) {
    if (state.selectedEnv === 'all') return true;
    const flavor = String(cmd.flavor || '').toLowerCase();
    if (flavor) {
        if (flavor === 'any' || flavor === 'all') return true;
        return state.selectedEnv === flavor;
    }
    const key = String(cmd.id || cmd.key || '').toLowerCase();
    const hasDev = key.includes('-dev-') || key.endsWith('-dev') || key.includes('_dev_') || key.endsWith('_dev');
    const hasQa = key.includes('-qa-') || key.endsWith('-qa') || key.includes('-test-') || key.endsWith('-test') || key.includes('_qa_') || key.endsWith('_qa') || key.includes('_test_') || key.endsWith('_test');
    const hasProd = key.includes('-prod-') || key.endsWith('-prod') || key.includes('_prod_') || key.endsWith('_prod');
    const hasEnv = hasDev || hasQa || hasProd;
    if (!hasEnv) return true;
    if (state.selectedEnv === 'dev') return hasDev;
    if (state.selectedEnv === 'qa') return hasQa;
    if (state.selectedEnv === 'prod') return hasProd;
    return true;
}

async function loadApps() {
    const res = await fetch(api('/api/deployment/apps'));
    const data = await res.json();
    const all = data.apps || [];
    state.apps = all.filter(a => !a.is_package);
    renderPackages(all.filter(a => a.is_package));
    renderApps();
    els.historyAppFilter.innerHTML = '<option value="">All apps</option>' +
        state.apps.map(a => `<option value="${escapeHtml(a.id)}">${escapeHtml(a.name || a.id)}</option>`).join('');
    if (state.apps.length) {
        selectApp(state.apps[0].id);
    }
}

function renderPackages(packages) {
    const panel = document.getElementById('packagePanel');
    if (!panel) return;
    panel.hidden = packages.length === 0;
    document.getElementById('packageSummary').textContent = `${packages.length} package${packages.length === 1 ? '' : 's'} (not deployable)`;
    document.getElementById('packageList').innerHTML = packages
        .map(p => `<li title="${escapeHtml(p.path || '')}">${escapeHtml(p.name || p.id)}</li>`)
        .join('');
}

function renderApps() {
    if (!state.apps.length) {
        els.appGrid.innerHTML = `
            <div class="empty-state" style="padding: 24px; text-align: center; border: 1px dashed var(--ui-border-color); border-radius: 8px;">
                <p style="margin: 0 0 6px 0; font-weight: 600; color: var(--ui-text-secondary); font-size: 0.85rem;">No apps detected in this workspace</p>
                <p style="margin: 0; font-size: 0.78rem; color: var(--ui-text-muted);">Click <strong>Switch / Add Project Folder</strong> above or <strong>Configure (⚙️)</strong>.</p>
            </div>
        `;
        if (els.commandList) {
            els.commandList.innerHTML = `<div class="empty-state" style="padding: 24px; text-align: center; color: var(--ui-text-muted); font-size: 0.85rem;">Select an app to view commands.</div>`;
        }
        return;
    }
    els.appGrid.innerHTML = state.apps.map(app => {
        const isActive = app.id === state.selectedApp;
        const activeState = isActive ? 'active' : '';
        const iconUrl = String(app.customIconUrl || '');
        const canRenderImage = iconUrl.length > 0;
        const resolvedIconUrl = canRenderImage ? (iconUrl.startsWith('/api/') ? iconUrl : api(`/api/app-icon?url=${encodeURIComponent(iconUrl)}`)) : '';
        const fallbackIcon = escapeHtml(app.icon || 'box');
        const icon = canRenderImage
            ? `<img src="${escapeHtml(resolvedIconUrl)}" alt="" data-fallback-icon="${fallbackIcon}" onerror="this.outerHTML='<i data-lucide=&quot;${fallbackIcon}&quot;></i>'; refreshIcons();" style="width:24px;height:24px;object-fit:cover;border-radius:6px;">`
            : `<i data-lucide="${fallbackIcon}"></i>`;
        return `
            <div class="compact-app-card ${activeState}" data-state="${activeState}" data-app="${escapeHtml(app.id)}" style="--app-color:${escapeHtml(app.color || '#6366f1')}">
                <div class="app-card-badge"><i data-lucide="check"></i></div>
                <div class="compact-app-card-icon" style="width:32px !important;height:32px !important;margin:0 !important;background:transparent !important;border:none !important;">${icon}</div>
                <h3 style="font-size: 12px; font-weight: 600;" title="${escapeHtml(app.name || app.id)}">${escapeHtml(app.name || app.id)}</h3>
            </div>
        `;
    }).join('');
    refreshIcons();
}

async function selectApp(appId) {
    state.selectedApp = appId;
    state.selectedCommand = null;
    const app = state.apps.find(item => item.id === appId);
    els.selectedAppName.textContent = app ? app.name : appId;
    renderApps();
    updateExecutionPanel();
    await loadCommands(appId);
}

function renderEnvTabs() {
    const flavors = new Set();
    state.commands.forEach(cmd => {
        if (cmd.flavor && cmd.flavor !== 'any' && cmd.flavor !== 'all' && cmd.flavor !== 'default' && cmd.flavor !== 'none') {
            flavors.add(cmd.flavor.toLowerCase());
        }
    });
    const sortedFlavors = Array.from(flavors).sort((a, b) => {
        const order = { dev: 1, qa: 2, prod: 3 };
        return (order[a] || 99) - (order[b] || 99);
    });
    state.hasMultipleEnvs = sortedFlavors.length > 1;

    if (sortedFlavors.length === 0) {
        // The UI kit styles .ui-segmented-control with !important, so match its priority.
        if (els.envTabs) els.envTabs.style.setProperty('display', 'none', 'important');
        state.selectedEnv = 'default';
        return;
    } else {
        if (els.envTabs) els.envTabs.style.setProperty('display', 'flex', 'important');
    }

    if (!sortedFlavors.includes(state.selectedEnv)) {
        state.selectedEnv = sortedFlavors[0];
    }
    els.envTabs.innerHTML = sortedFlavors.map(flavor => {
        const activeClass = state.selectedEnv === flavor ? 'active' : '';
        const title = flavor.charAt(0).toUpperCase() + flavor.slice(1);
        return `<button class="ui-segment ${activeClass}" type="button" data-env="${escapeHtml(flavor)}">${escapeHtml(title)}</button>`;
    }).join('');
}

async function loadCommands(appId) {
    els.commandGrid.innerHTML = '<div class="empty-state">Loading deployment commands...</div>';
    let data;
    try {
        const res = await fetch(api(`/api/deployment/commands?app=${encodeURIComponent(appId)}`));
        data = await res.json();
        if (!res.ok || data.success === false) throw new Error(data.error || `HTTP ${res.status}`);
    } catch (err) {
        state.commands = [];
        els.commandGrid.innerHTML = `<div class="empty-state">Could not load commands: ${escapeHtml(err.message)}.
            Check that the console server is still running (<code>./start.sh</code>), then reload this page.</div>`;
        return;
    }
    state.commands = data.commands || [];
    renderEnvTabs();
    renderCommands();
}

function renderCommands() {
    const visible = state.commands.filter(cmd => matchesEnv(cmd));
    if (!visible.length) {
        els.commandGrid.innerHTML = '<div class="empty-state">No deployment commands found for this selection.</div>';
        return;
    }

    const groups = new Map();
    visible.forEach(cmd => {
        const meta = getCommandMeta(cmd);
        if (!groups.has(meta.group)) groups.set(meta.group, []);
        groups.get(meta.group).push({cmd, meta});
    });

    let html = '';
    groups.forEach((items, group) => {
        html += `<div class="ui-section-header" style="margin: 20px 0 10px 0;"><span class="ui-section-title">${escapeHtml(group)}</span></div>`;
        html += `<div class="compact-app-grid compact-app-grid--commands">`;
        html += items.map(({cmd, meta}) => {
            const isLocked = cmd.configured === false;
            const isSelected = state.selectedCommand && state.selectedCommand.id === cmd.id;
            const selectedClass = isSelected ? 'active' : '';
            const lockBadge = isLocked
                ? `<span class="ui-badge" data-variant="warning" style="flex-shrink: 0;"><i data-lucide="lock" style="width:10px;height:10px;margin-right:4px;"></i>Locked</span>`
                : '';
            return `
                <div class="compact-app-card ${selectedClass}" data-state="${isSelected ? 'selected' : ''}" data-id="${escapeHtml(cmd.id)}" data-locked="${isLocked}" style="--app-color: ${meta.color};">
                    <div class="compact-app-card-icon"><i data-lucide="${meta.icon}"></i></div>
                    <div style="min-width: 0; flex: 1;">
                        <h3 title="${escapeHtml(cmd.name || prettyCommandTitle(cmd.key || cmd.id))}">${escapeHtml(cmd.name || prettyCommandTitle(cmd.key || cmd.id))}</h3>
                        <div class="compact-app-meta" title="${escapeHtml(cmd.desc || '')}">${escapeHtml(cmd.desc || '')}</div>
                    </div>
                    ${lockBadge}
                </div>
            `;
        }).join('');
        html += `</div>`;
    });
    els.commandGrid.innerHTML = html;
    refreshIcons();
}

function selectCommand(id) {
    const cmd = state.commands.find(c => c.id === id) || null;
    // block selection of unconfigured commands
    if (cmd && cmd.configured === false) return;
    state.selectedCommand = cmd;
    renderCommands();
    updateExecutionPanel();
}

/** The env value to forward for release/utility commands, or '' when this app has
 *  no more than one real flavor (nothing to disambiguate — mirrors the backend's
 *  execute_command substitution rule, kept in sync so the preview matches reality). */
function selectedEnvForExecution() {
    return state.hasMultipleEnvs ? state.selectedEnv : '';
}

/** Release/utility command templates end in a literal trailing "any" placeholder
 *  (see backend _build_commands_from_templates) since one card covers every env.
 *  Show what will ACTUALLY run — with the active env substituted in — rather than
 *  the raw placeholder, so the preview never lies about the tag/changelog it'll produce. */
function resolvedCommandForExecution() {
    const raw = state.selectedCommand.key || state.selectedCommand.id;
    const env = selectedEnvForExecution();
    if (env && typeof raw === 'string' && raw.endsWith(' any')) {
        return raw.slice(0, -' any'.length) + ' ' + env;
    }
    return raw;
}

function updateExecutionPanel() {
    if (!state.selectedApp || !state.selectedCommand) {
        els.executionPanel.classList.add('hidden');
        els.runButton.disabled = true;
        els.iosCertBanner.classList.add('hidden');
        return;
    }

    const command = resolvedCommandForExecution();
    const runner = state.selectedCommand.runner || 'make';
    const isLocked = state.selectedCommand.configured === false;
    els.executionPanel.classList.remove('hidden');
    els.selectedCommandTitle.textContent = state.selectedCommand.name || prettyCommandTitle(command);
    if (runner === 'custom') {
        els.selectedCommandPreview.textContent = command;
    } else if (runner === 'melos') {
        els.selectedCommandPreview.textContent = `melos run ${command}`;
    } else {
        els.selectedCommandPreview.textContent = `make -C tool/makefiles/${state.selectedApp} ${command}`;
    }
    // lock run button for unconfigured flavors
    els.runButton.disabled = isLocked;

    const isProdIos = state.selectedCommand.platform === 'ios' && state.selectedCommand.flavor === 'prod';
    renderCertExpiryBanner(isProdIos ? state.selectedApp : null);
}

const SEVERITY_RANK = { expired: 3, warning: 2, unknown: 1, ok: 0, not_ios_app: -1 };

function renderCertExpiryBanner(appId) {
    if (!appId) {
        els.iosCertBanner.classList.add('hidden');
        return;
    }
    // Reuse setup.js's cache when it already has a fresh-enough result for this app;
    // otherwise fetch directly (advisory only — never blocks Run).
    const cached = (typeof getCachedCertCheck === 'function') ? getCachedCertCheck(appId) : null;
    if (cached) {
        renderCertBannerFromResult(cached);
        return;
    }
    els.iosCertBanner.classList.add('hidden');
    fetch(api(`/api/deployment/ios-cert-check?app=${encodeURIComponent(appId)}&flavor=prod`))
        .then(r => r.json())
        .then(result => {
            if (typeof setCachedCertCheck === 'function') setCachedCertCheck(appId, result);
            // Only render if the user hasn't switched away from this app/command meanwhile
            if (state.selectedApp === appId && state.selectedCommand && state.selectedCommand.platform === 'ios' && state.selectedCommand.flavor === 'prod') {
                renderCertBannerFromResult(result);
            }
        })
        .catch(() => {});
}

function renderCertBannerFromResult(result) {
    if (!result || !result.success || result.status === 'not_ios_app') {
        els.iosCertBanner.classList.add('hidden');
        return;
    }
    const cert = result.certificate || {};
    const profile = result.provisioningProfile || {};
    const worst = [cert, profile].reduce((a, b) => (SEVERITY_RANK[b.status] || 0) > (SEVERITY_RANK[a.status] || 0) ? b : a, { status: 'unknown' });
    if (worst.status === 'unknown' || worst.status === 'ok') {
        els.iosCertBanner.classList.add('hidden');
        return;
    }
    const label = worst.status === 'expired' ? 'EXPIRED' : 'expiring soon';
    const expiresOn = worst.expiresOn ? ` (${escapeHtml(worst.expiresOn)})` : '';
    const bestEffort = worst.bestEffort ? ' — from last build, best-effort' : '';
    els.iosCertBanner.dataset.status = worst.status;
    els.iosCertBanner.textContent = `⚠️ Prod cert/profile ${label}${expiresOn}${bestEffort}`;
    els.iosCertBanner.classList.remove('hidden');
}

/** Mirrors router.py's _is_prod_store_deploy() scope: a "prod" flavor selection whose
 *  template actually ships a build to a real app store (not a local build, not a
 *  git release tag/push). Used to decide whether Run needs a second, explicit click. */
function isProdStoreDeploy() {
    if (!state.selectedCommand) return false;
    if (!STORE_SHIPPING_TEMPLATE_IDS.has(state.selectedCommand.templateId)) return false;
    const flavor = String(state.selectedCommand.flavor || '').toLowerCase().trim();
    // "prod", "default" (single-app = the one prod environment), or "" all require confirmation
    return flavor === 'prod' || flavor === 'default' || flavor === '';
}

function openProdConfirmModal() {
    const app = state.apps.find(a => a.id === state.selectedApp);
    els.prodConfirmAppName.textContent = app ? (app.name || app.id) : state.selectedApp;
    els.prodConfirmCommandPreview.textContent = els.selectedCommandPreview.textContent;
    els.prodConfirmOverlay.classList.add('ui-active');
}

function closeProdConfirmModal() {
    els.prodConfirmOverlay.classList.remove('ui-active');
}

function writeTerminal(text, type = '') {
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`.trim();
    const time = new Date().toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
    line.textContent = `${time}  ${text}`;
    els.terminalOutput.appendChild(line);
    els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;
}

function clearTerminal() {
    els.terminalOutput.innerHTML = '<div class="terminal-line muted">Deployment logs will appear here.</div>';
}

function startTimer() {
    stopTimer();
    state.timerStartedAt = Date.now();
    state.timerId = setInterval(() => {
        const seconds = Math.floor((Date.now() - state.timerStartedAt) / 1000);
        const min = String(Math.floor(seconds / 60)).padStart(2, '0');
        const sec = String(seconds % 60).padStart(2, '0');
        els.executionTimer.textContent = `${min}:${sec}`;
    }, 500);
}

function stopTimer() {
    if (state.timerId) clearInterval(state.timerId);
    state.timerId = null;
}

async function executeSelected(confirmed = false) {
    if (!state.selectedApp || !state.selectedCommand) return;
    const command = state.selectedCommand.key || state.selectedCommand.id;
    const runner = state.selectedCommand.runner || 'make';
    const env = selectedEnvForExecution();

    state.activeJobId = null;
    state.stdoutLength = 0;
    state.stderrLength = 0;
    els.runButton.disabled = true;
    els.stopJobBtn.disabled = true;
    startTimer();
    writeTerminal(`Executing: ${els.selectedCommandPreview.textContent}`);

    try {
        const res = await fetch(api('/api/deployment/execute'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                app: state.selectedApp, command, runner, env,
                templateId: state.selectedCommand.templateId || '',
                flavor: state.selectedCommand.flavor || '',
                confirmed: !!confirmed,
            }),
        });
        const data = await res.json();
        if (!data.success && data.needsConfirmation) {
            // Server-side backstop caught a prod store deploy the client didn't gate
            // for (stale selection, race, etc.) - fall back to the confirm modal
            // rather than showing this as a generic failure.
            finishExecution();
            openProdConfirmModal();
            return;
        }
        if (!data.success || !data.jobId) {
            const err = new Error(data.error || 'Command could not start');
            err.code = data.code || '';
            throw err;
        }
        state.activeJobId = data.jobId;
        els.stopJobBtn.disabled = false;
        pollJob(data.jobId);
    } catch (error) {
        writeTerminal(`Failed to start: ${error.message}`, 'error');
        showToast(error.message || 'Failed to start deployment command', 'error');
        finishExecution();
    }
}

async function pollJob(jobId) {
    try {
        const res = await fetch(api(`/api/deployment/job?id=${encodeURIComponent(jobId)}`));
        const data = await res.json();
        if (!data.success || !data.job) throw new Error(data.error || 'Failed to read job');

        const job = data.job;
        if (job.output && job.output.length > state.stdoutLength) {
            job.output.slice(state.stdoutLength).split('\n').forEach(line => {
                if (line.trim()) writeTerminal(line);
            });
            state.stdoutLength = job.output.length;
        }
        if (job.error && job.error.length > state.stderrLength) {
            job.error.slice(state.stderrLength).split('\n').forEach(line => {
                if (line.trim()) writeTerminal(`[stderr] ${line}`, 'error');
            });
            state.stderrLength = job.error.length;
        }

        if (job.status === 'running' || job.status === 'stopping' || job.status === 'chaining') {
            setTimeout(() => pollJob(jobId), 900);
            return;
        }

        if (job.status === 'success' && job.chainedJobId) {
            writeTerminal(`Completed successfully: ${job.command}`, 'success');
            state.activeJobId = job.chainedJobId;
            state.stdoutLength = 0;
            state.stderrLength = 0;
            setTimeout(() => pollJob(job.chainedJobId), 900);
            return;
        }

        if (job.status === 'success') {
            writeTerminal(`Completed successfully: ${job.command}`, 'success');
            showToast('Deployment command completed');
        } else if (job.status === 'stopped') {
            writeTerminal(`Stopped: ${job.command}`, 'error');
            showToast('Deployment command stopped');
        } else {
            writeTerminal(`Failed: ${job.command}`, 'error');
            showToast('Deployment command failed');
        }
        finishExecution();
        loadCommands(state.selectedApp);
    } catch (error) {
        writeTerminal(`Polling failed: ${error.message}`, 'error');
        finishExecution();
    }
}

function finishExecution() {
    state.activeJobId = null;
    els.runButton.disabled = false;
    els.stopJobBtn.disabled = true;
    stopTimer();
}

async function stopActiveJob() {
    if (!state.activeJobId) return;
    els.stopJobBtn.disabled = true;
    await fetch(api('/api/deployment/job/stop'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({jobId: state.activeJobId}),
    }).catch(() => {});
}

function refreshIcons() {
    if (window.lucide) window.lucide.createIcons();
}

// ═══════════════════════════ History tab ═══════════════════════════

function switchOutputView(view) {
    state.activeOutputView = view;
    els.outputTabs.querySelectorAll('button').forEach(btn => btn.classList.toggle('active', btn.dataset.view === view));
    els.terminalView.classList.toggle('hidden', view !== 'live');
    els.historyView.classList.toggle('hidden', view !== 'history');
    els.clearTerminalBtn.classList.toggle('hidden', view !== 'live');
    els.historyRefreshBtn.classList.toggle('hidden', view !== 'history');
    if (view === 'history') loadHistory();
}

async function loadHistory() {
    const params = new URLSearchParams({limit: '50'});
    if (els.historyAppFilter.value) params.set('app', els.historyAppFilter.value);
    if (els.historyFlavorFilter.value) params.set('flavor', els.historyFlavorFilter.value);
    if (els.historyStatusFilter.value) params.set('status', els.historyStatusFilter.value);
    els.historyOutput.innerHTML = '<div class="terminal-line muted">Loading history...</div>';
    try {
        const res = await fetch(api(`/api/deployment/history?${params}`));
        const data = await res.json();
        state.historyEntries = data.entries || [];
        renderHistory();
    } catch (error) {
        els.historyOutput.innerHTML = `<div class="terminal-line error">Failed to load history: ${escapeHtml(error.message)}</div>`;
    }
}

function renderHistory() {
    if (!state.historyEntries.length) {
        els.historyOutput.innerHTML = '<div class="terminal-line muted">No deployment history yet.</div>';
        return;
    }
    els.historyOutput.innerHTML = state.historyEntries.map(entry => {
        const statusClass = entry.status === 'success' ? 'success' : (entry.status === 'stopped' ? 'warning' : 'error');
        const time = entry.completedAt ? new Date(entry.completedAt).toLocaleString() : '';
        const duration = entry.durationSeconds != null ? `${entry.durationSeconds}s` : '—';
        const chained = entry.chainedJobId ? ` · chained → ${escapeHtml(entry.chainedJobId)}` : '';
        const excerpt = entry.errorExcerpt || entry.outputExcerpt || '';
        return `
            <div class="terminal-line history-row">
                <span class="${statusClass}">${escapeHtml((entry.status || '').toUpperCase())}</span>
                &nbsp;${escapeHtml(time)} · ${escapeHtml(entry.app || '')} · ${escapeHtml(entry.templateId || '')} · ${escapeHtml(entry.flavor || '')} · ${duration} · #${escapeHtml(entry.id || '')}${chained}
                ${excerpt ? `<pre class="history-excerpt">${escapeHtml(excerpt)}</pre>` : ''}
            </div>
        `;
    }).join('');
}

els.appGrid.addEventListener('click', event => {
    const card = event.target.closest('.compact-app-card') || event.target.closest('.ui-app-card');
    if (card) selectApp(card.dataset.app);
});

els.commandGrid.addEventListener('click', event => {
    const button = event.target.closest('.compact-app-card');
    // ignore clicks on locked (unconfigured) commands
    if (button && button.dataset.locked !== 'true') selectCommand(button.dataset.id);
});

els.envTabs.addEventListener('click', event => {
    const button = event.target.closest('button[data-env]');
    if (!button) return;
    state.selectedEnv = button.dataset.env;
    els.envTabs.querySelectorAll('button').forEach(btn => btn.classList.toggle('active', btn === button));
    if (state.selectedCommand && !matchesEnv(state.selectedCommand)) {
        state.selectedCommand = null;
    }
    renderCommands();
    // Refresh the preview even when the same command stays selected — a release
    // command's substituted command (and thus its tag/changelog behavior) depends
    // on which env tab is active.
    updateExecutionPanel();
});

els.runButton.addEventListener('click', () => {
    if (isProdStoreDeploy()) {
        openProdConfirmModal();
    } else {
        executeSelected(false);
    }
});
els.stopJobBtn.addEventListener('click', stopActiveJob);
els.clearTerminalBtn.addEventListener('click', clearTerminal);

// Prod confirm modal
els.confirmProdDeployBtn.addEventListener('click', () => {
    els.confirmProdDeployBtn.disabled = true; // guard against a rapid double-click
    closeProdConfirmModal();
    executeSelected(true).finally(() => { els.confirmProdDeployBtn.disabled = false; });
});
els.cancelProdConfirmBtn.addEventListener('click', closeProdConfirmModal);
els.closeProdConfirmBtn.addEventListener('click', closeProdConfirmModal);
els.prodConfirmOverlay.addEventListener('click', event => {
    if (event.target === els.prodConfirmOverlay) closeProdConfirmModal();
});

// History tab
els.outputTabs.addEventListener('click', event => {
    const btn = event.target.closest('button[data-view]');
    if (btn) switchOutputView(btn.dataset.view);
});
els.historyRefreshBtn.addEventListener('click', loadHistory);
els.historyAppFilter.addEventListener('change', loadHistory);
els.historyFlavorFilter.addEventListener('change', loadHistory);
els.historyStatusFilter.addEventListener('change', loadHistory);


let currentWorkspacesList = [];

function renderProjectSegments(workspaces, activePath) {
    const container = document.getElementById('projectSegmentedControl');
    if (!container) return;

    if (!workspaces || workspaces.length === 0) {
        container.innerHTML = '<span style="font-size:0.8rem; color:var(--ui-text-muted);">No projects imported</span>';
        return;
    }

    container.innerHTML = workspaces.map(w => {
        const isActive = w.path === activePath;
        const name = w.name || w.path.split('/').pop() || 'Project';
        const remove = w.isDefault ? '' :
            `<button class="project-tab-remove" type="button" data-remove="${escapeHtml(w.path)}" title="Remove ${escapeHtml(name)} from the list" aria-label="Remove ${escapeHtml(name)}">×</button>`;
        return `<span class="project-tab ${isActive ? 'active' : ''}">` +
            `<button class="ui-segment ${isActive ? 'active' : ''}" type="button" data-path="${escapeHtml(w.path)}" title="${escapeHtml(w.path)}">${escapeHtml(name)}</button>` +
            remove + '</span>';
    }).join('');

    container.querySelectorAll('.ui-segment').forEach(btn => {
        btn.addEventListener('click', () => selectProject(btn.getAttribute('data-path')));
    });
    container.querySelectorAll('.project-tab-remove').forEach(btn => {
        btn.addEventListener('click', () => removeProject(btn.getAttribute('data-remove')));
    });
}

/** Remove a project tab. Only the list entry goes; the folder and its settings stay. */
async function removeProject(path) {
    const project = currentWorkspacesList.find(w => w.path === path);
    const name = project?.name || path.split('/').pop();
    if (!confirm(`Remove "${name}" from the project list?\n\nThe folder and its settings are not deleted — import it again to bring it back.`)) return;
    let res;
    try {
        res = await fetch(api('/api/deployment/workspace/remove'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        }).then(r => r.json());
    } catch (err) {
        showToast('Could not remove project: ' + err.message);
        return;
    }
    if (!res.success) {
        showToast(res.error || 'Could not remove project');
        return;
    }
    showToast(`Removed "${name}" from the project list`);
    const wasActive = state.activeWorkspace === path;
    await loadWorkspaceInfo();
    if (wasActive) {
        const fallback = currentWorkspacesList.find(w => w.isDefault) || currentWorkspacesList[0];
        state.activeWorkspace = '';
        if (fallback) await selectProject(fallback.path);
    }
}

/**
 * Show a project. Purely client-side: every request carries the project in the
 * X-Workspace header, so other browser tabs and running jobs are unaffected.
 */
async function selectProject(path) {
    if (!path || path === state.activeWorkspace) return;
    try { sessionStorage.setItem('active_workspace', path); } catch (_) { /* storage may be blocked */ }
    state.activeWorkspace = path;
    state.selectedApp = null;
    renderActiveProject();
    await loadApps();
    if (typeof loadSetupData === 'function' && document.getElementById('setupOverlay')?.classList.contains('ui-active')) {
        await loadSetupData();
    }
}

function renderActiveProject() {
    const active = currentWorkspacesList.find(w => w.path === state.activeWorkspace);
    const label = document.getElementById('workspaceLabel');
    if (label && active) {
        label.textContent = `WORKSPACE: ${(active.name || active.path.split('/').pop()).toUpperCase()}`;
        label.title = active.path;
    }
    renderProjectSegments(currentWorkspacesList, state.activeWorkspace);
}

async function loadWorkspaceInfo() {
    try {
        const res = await fetch(api('/api/deployment/workspaces'));
        const data = await res.json();

        // C12: Missing workspace warning banner
        if (data.workspaceMissing) {
            showToast(`⚠️ Configured workspace path "${data.workspaceMissing}" was not found on disk.`);
            let missingBanner = document.getElementById('workspaceMissingBanner');
            if (!missingBanner) {
                missingBanner = document.createElement('div');
                missingBanner.id = 'workspaceMissingBanner';
                missingBanner.className = 'cert-status-box';
                missingBanner.dataset.status = 'warning';
                missingBanner.style.cssText = 'margin: 12px 24px 0 24px; font-size: 0.82rem;';
                document.querySelector('.dashboard-container')?.prepend(missingBanner);
            }
            missingBanner.textContent = `⚠️ Workspace folder "${data.workspaceMissing}" was not found on disk. Dashboard fell back to "${data.active}". Please select a valid project folder.`;
            missingBanner.style.display = 'block';
        } else {
            const missingBanner = document.getElementById('workspaceMissingBanner');
            if (missingBanner) missingBanner.style.display = 'none';
        }

        currentWorkspacesList = data.workspaces || [];
        let stored = '';
        try { stored = sessionStorage.getItem('active_workspace') || ''; } catch (_) { /* ignore */ }
        const known = currentWorkspacesList.some(w => w.path === stored);
        state.activeWorkspace = known ? stored : data.active;
        if (!known) {
            try { sessionStorage.setItem('active_workspace', state.activeWorkspace); } catch (_) { /* ignore */ }
        }
        renderActiveProject();

    } catch (_) {}
}

const wsModalEls = {
    overlay: document.getElementById('workspaceSwitchOverlay'),
    openBtn: document.getElementById('switchWorkspaceBtn'),
    closeBtn: document.getElementById('closeWorkspaceModalBtn'),
    cancelBtn: document.getElementById('cancelWorkspaceBtn'),
    confirmBtn: document.getElementById('confirmWorkspaceBtn'),
    browseBtn: document.getElementById('browseFolderBtn'),
    manual: document.getElementById('workspaceManualPath'),
    pathInput: document.getElementById('workspacePathInput'),
    result: document.getElementById('workspaceInspectionBox'),
    error: document.getElementById('workspaceInspectError'),
    name: document.getElementById('inspectTitle'),
    layout: document.getElementById('inspectMonorepoBadge'),
    path: document.getElementById('inspectPath'),
    appsLabel: document.getElementById('inspectAppsLabel'),
    apps: document.getElementById('inspectBadges'),
    packagesGroup: document.getElementById('inspectPackagesGroup'),
    packagesLabel: document.getElementById('inspectPackagesLabel'),
    packages: document.getElementById('inspectPackageBadges'),
};

/** Folder chosen and inspected in the Import Project dialog; null until it has at least one app. */
let importCandidate = null;

function resetImportDialog() {
    importCandidate = null;
    wsModalEls.result.classList.add('hidden');
    wsModalEls.error.classList.add('hidden');
    wsModalEls.manual.hidden = true;
    wsModalEls.pathInput.value = '';
    wsModalEls.confirmBtn.disabled = true;
}

function openWorkspaceModal() {
    resetImportDialog();
    wsModalEls.overlay.classList.add('ui-active');
    refreshIcons();
}

function closeWorkspaceModal() {
    wsModalEls.overlay.classList.remove('ui-active');
}

wsModalEls.openBtn.addEventListener('click', openWorkspaceModal);
wsModalEls.closeBtn.addEventListener('click', closeWorkspaceModal);
wsModalEls.cancelBtn.addEventListener('click', closeWorkspaceModal);
wsModalEls.overlay.addEventListener('click', e => {
    if (e.target === wsModalEls.overlay) closeWorkspaceModal();
});

function renderChips(container, items) {
    container.innerHTML = items
        .map(item => `<span class="ui-badge" data-variant="secondary" title="${escapeHtml(item.path || '')}">${escapeHtml(item.name || item.id)}</span>`)
        .join('');
}

function showImportError(message) {
    importCandidate = null;
    wsModalEls.confirmBtn.disabled = true;
    wsModalEls.result.classList.add('hidden');
    wsModalEls.error.textContent = message;
    wsModalEls.error.classList.remove('hidden');
}

async function inspectImportFolder(pathStr) {
    if (!pathStr) return;
    wsModalEls.error.classList.add('hidden');
    let data;
    try {
        data = await fetch(api(`/api/deployment/inspect-path?path=${encodeURIComponent(pathStr)}`)).then(r => r.json());
    } catch (err) {
        showImportError(`Could not inspect the folder: ${err.message}`);
        return;
    }
    if (!data.success) {
        showImportError(data.error || 'Could not inspect the folder.');
        return;
    }
    const apps = (data.apps || []).filter(a => !a.is_package);
    const packages = (data.apps || []).filter(a => a.is_package);
    if (!apps.length) {
        showImportError(`No app found in "${data.name}". Choose the folder that contains your Flutter app(s).`);
        return;
    }
    importCandidate = data.path;
    wsModalEls.name.textContent = data.name;
    wsModalEls.layout.textContent = data.layout || '';
    wsModalEls.path.textContent = data.path;
    wsModalEls.appsLabel.textContent = `${apps.length} app${apps.length === 1 ? '' : 's'}`;
    renderChips(wsModalEls.apps, apps);
    wsModalEls.packagesGroup.hidden = packages.length === 0;
    wsModalEls.packagesLabel.textContent = `${packages.length} package${packages.length === 1 ? '' : 's'}`;
    renderChips(wsModalEls.packages, packages);
    wsModalEls.result.classList.remove('hidden');
    const alreadyAdded = currentWorkspacesList.some(w => w.path === data.path);
    wsModalEls.confirmBtn.querySelector('span').textContent = alreadyAdded ? 'Already added — open it' : 'Add project';
    wsModalEls.confirmBtn.disabled = false;
}

wsModalEls.browseBtn.addEventListener('click', async () => {
    wsModalEls.browseBtn.disabled = true;
    const picked = typeof window.pickNativePath === 'function'
        ? await window.pickNativePath({ kind: 'folder', prompt: 'Choose your project folder' })
        : { unsupported: true };
    wsModalEls.browseBtn.disabled = false;
    if (picked.path) {
        inspectImportFolder(picked.path);
    } else if (picked.unsupported) {
        wsModalEls.manual.hidden = false;
        wsModalEls.pathInput.focus();
    } else if (picked.error) {
        showImportError(picked.error);
    }
});

let inspectDebounceTimer = null;
wsModalEls.pathInput.addEventListener('input', () => {
    clearTimeout(inspectDebounceTimer);
    inspectDebounceTimer = setTimeout(() => inspectImportFolder(wsModalEls.pathInput.value.trim()), 400);
});

wsModalEls.confirmBtn.addEventListener('click', async () => {
    if (!importCandidate) return;
    const path = importCandidate;
    wsModalEls.confirmBtn.disabled = true;
    try {
        if (!currentWorkspacesList.some(w => w.path === path)) {
            // Choosing the folder is the user's explicit grant, so authorise it without a second prompt.
            const allowRes = await fetch(api('/api/deployment/workspace/allow'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path }),
            }).then(r => r.json());
            if (!allowRes.success) {
                showImportError(allowRes.error || 'Could not add the project.');
                return;
            }
            await loadWorkspaceInfo();
            showToast(`Added project "${allowRes.name || path}"`);
        }
        closeWorkspaceModal();
        await selectProject(path);
    } finally {
        wsModalEls.confirmBtn.disabled = !importCandidate;
    }
});

(async () => {
    await loadWorkspaceInfo();
    await loadApps();
})().catch(error => {
    els.appGrid.innerHTML = `<div class="empty-state">Failed to load apps: ${escapeHtml(error.message)}</div>`;
});
refreshIcons();

