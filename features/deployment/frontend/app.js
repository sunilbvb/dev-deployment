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
    batch: { active: false, flavor: '', templateId: 'auto', plan: [], results: [], index: -1, stopRequested: false },
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
    deployAllBtn: document.getElementById('deployAllBtn'),
    batchDeployOverlay: document.getElementById('batchDeployOverlay'),
    batchTemplateSelect: document.getElementById('batchTemplateSelect'),
    batchPlanList: document.getElementById('batchPlanList'),
    batchCancelBtn: document.getElementById('batchCancelBtn'),
    closeBatchModalBtn: document.getElementById('closeBatchModalBtn'),
    batchStartBtn: document.getElementById('batchStartBtn'),
    batchProgressPanel: document.getElementById('batchProgressPanel'),
    batchPillRow: document.getElementById('batchPillRow'),
    batchSummaryLine: document.getElementById('batchSummaryLine'),
    batchStopBtn: document.getElementById('batchStopBtn'),
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

function getCommandMeta(key) {
    const k = String(key || '').toLowerCase();
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
    state.apps = data.apps || [];
    renderApps();
    els.historyAppFilter.innerHTML = '<option value="">All apps</option>' +
        state.apps.map(a => `<option value="${escapeHtml(a.id)}">${escapeHtml(a.name || a.id)}</option>`).join('');
    if (state.apps.length) {
        selectApp(state.apps[0].id);
    }
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
        if (cmd.flavor && cmd.flavor !== 'any' && cmd.flavor !== 'all') {
            flavors.add(cmd.flavor.toLowerCase());
        }
    });
    const sortedFlavors = Array.from(flavors).sort((a, b) => {
        const order = { dev: 1, qa: 2, prod: 3 };
        return (order[a] || 99) - (order[b] || 99);
    });
    // Whether this app genuinely has more than one distinct environment configured.
    // Release actions only get an env forwarded (and thus a tag suffix) when this is
    // true — an app with zero or one real flavor has nothing to disambiguate, so its
    // releases stay unsuffixed exactly like before this feature existed.
    state.hasMultipleEnvs = sortedFlavors.length > 1;
    if (sortedFlavors.length === 0) {
        sortedFlavors.push('dev');
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
    const res = await fetch(api(`/api/deployment/commands?app=${encodeURIComponent(appId)}`));
    const data = await res.json();
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
        const meta = getCommandMeta(cmd.key || cmd.id);
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
    const flavor = String(state.selectedCommand.flavor || '').toLowerCase();
    if (flavor !== 'prod') return false;
    return STORE_SHIPPING_TEMPLATE_IDS.has(state.selectedCommand.templateId);
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
        showToast(error.code === 'APP_BUSY'
            ? `Already running for ${state.selectedApp} — wait for it to finish or stop it first`
            : 'Failed to start deployment command');
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

// ═══════════════════════════ Deploy All Apps (batch) ═══════════════════════════

function openBatchModal() {
    state.batch.templateId = els.batchTemplateSelect.value || 'auto';
    els.batchDeployOverlay.classList.add('ui-active');
    refreshBatchPlan();
}

function closeBatchModal() {
    els.batchDeployOverlay.classList.remove('ui-active');
}

async function refreshBatchPlan() {
    const flavor = state.selectedEnv;
    state.batch.flavor = flavor;
    els.batchPlanList.innerHTML = '<div class="empty-state">Loading plan...</div>';
    try {
        const res = await fetch(api(`/api/deployment/batch-plan?flavor=${encodeURIComponent(flavor)}&templateId=${encodeURIComponent(state.batch.templateId)}`));
        const data = await res.json();
        state.batch.plan = data.plan || [];
        renderBatchPlanList();
    } catch (error) {
        els.batchPlanList.innerHTML = `<div class="empty-state">Failed to load plan: ${escapeHtml(error.message)}</div>`;
    }
}

function renderBatchPlanList() {
    if (!state.batch.plan.length) {
        els.batchPlanList.innerHTML = '<div class="empty-state">No apps configured.</div>';
        els.batchStartBtn.disabled = true;
        return;
    }
    const anyWillRun = state.batch.plan.some(p => p.willRun);
    els.batchStartBtn.disabled = !anyWillRun;
    els.batchPlanList.innerHTML = state.batch.plan.map(p => `
        <div class="batch-plan-row">
            <span class="app-dot" style="background:${escapeHtml(p.color || '#6366f1')}"></span>
            <strong>${escapeHtml(p.appName || p.appId)}</strong>
            ${p.willRun
                ? `<span class="ui-badge" data-variant="success">${escapeHtml(p.templateName || p.templateId)}</span>`
                : `<span class="ui-badge" data-variant="warning">Skipped: ${escapeHtml(p.skipReason || 'not configured')}</span>`}
        </div>
    `).join('');
}

function startBatchDeploy() {
    closeBatchModal();
    state.batch.results = state.batch.plan.map(p => ({ status: p.willRun ? 'pending' : 'skipped', error: '' }));
    state.batch.active = true;
    state.batch.index = -1;
    state.batch.stopRequested = false;
    els.batchProgressPanel.classList.remove('hidden');
    els.batchStopBtn.disabled = false;
    els.batchSummaryLine.textContent = `Deploying ${state.batch.plan.filter(p => p.willRun).length} app(s) for ${state.batch.flavor}...`;
    renderBatchPills();
    advanceBatch();
}

function advanceBatch() {
    const idx = state.batch.results.findIndex(r => r.status === 'pending');
    if (idx === -1 || state.batch.stopRequested) return finishBatch();
    state.batch.index = idx;
    state.batch.results[idx].status = 'running';
    renderBatchPills();
    const p = state.batch.plan[idx];
    writeTerminal(`── Now deploying: ${p.appName} (${p.templateName}) ──`);
    fetch(api('/api/deployment/execute'), {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ app: p.appId, command: p.command, runner: p.runner, env: state.batch.flavor, templateId: p.templateId, flavor: state.batch.flavor, confirmed: true }),
    }).then(r => r.json()).then(data => {
        if (!data.success && data.needsConfirmation) {
            // Shouldn't normally happen (batch always sends confirmed:true), but if the
            // server-side gate rejects anyway, don't silently hang - mark it and move on.
            state.batch.results[idx].status = 'error';
            state.batch.results[idx].error = 'Needs confirmation';
            renderBatchPills();
            return advanceBatch();
        }
        if (!data.success || !data.jobId) {
            state.batch.results[idx].status = 'error';
            state.batch.results[idx].error = data.error || 'Could not start';
            renderBatchPills();
            return advanceBatch();
        }
        state.activeJobId = data.jobId;
        pollBatchJob(data.jobId, idx);
    }).catch(error => {
        state.batch.results[idx].status = 'error';
        state.batch.results[idx].error = error.message;
        renderBatchPills();
        advanceBatch();
    });
}

function pollBatchJob(jobId, idx) {
    fetch(api(`/api/deployment/job?id=${encodeURIComponent(jobId)}`)).then(r => r.json()).then(data => {
        if (!data.success || !data.job) {
            state.batch.results[idx].status = 'error';
            renderBatchPills();
            return advanceBatch();
        }
        const job = data.job;
        if (job.status === 'running' || job.status === 'stopping' || job.status === 'chaining') {
            return setTimeout(() => pollBatchJob(jobId, idx), 900);
        }
        if (job.status === 'success' && job.chainedJobId) {
            return setTimeout(() => pollBatchJob(job.chainedJobId, idx), 900); // ride the release chain first
        }
        state.batch.results[idx].status = job.status; // success | error | stopped
        writeTerminal(`── ${state.batch.plan[idx].appName}: ${job.status} ──`, job.status === 'success' ? 'success' : 'error');
        renderBatchPills();
        advanceBatch();
    }).catch(() => {
        state.batch.results[idx].status = 'error';
        renderBatchPills();
        advanceBatch();
    });
}

function stopBatchDeploy() {
    state.batch.stopRequested = true;
    els.batchStopBtn.disabled = true;
    if (state.activeJobId) {
        fetch(api('/api/deployment/job/stop'), {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jobId: state.activeJobId}),
        }).catch(() => {});
    }
}

function finishBatch() {
    state.batch.active = false;
    state.batch.results.forEach(r => { if (r.status === 'pending') r.status = 'skipped'; });
    renderBatchPills();
    const succeeded = state.batch.results.filter(r => r.status === 'success').length;
    const failed = state.batch.results.filter(r => r.status === 'error').length;
    els.batchSummaryLine.textContent = `Batch complete: ${succeeded} succeeded, ${failed} failed`;
    els.batchStopBtn.disabled = true;
    showToast('Deploy All Apps: batch finished');
    loadCommands(state.selectedApp);
}

function renderBatchPills() {
    els.batchPillRow.innerHTML = state.batch.plan.map((p, i) => {
        const result = state.batch.results[i] || { status: 'pending' };
        return `<span class="batch-pill" data-status="${escapeHtml(result.status)}" title="${escapeHtml(result.error || '')}">${escapeHtml(p.appName || p.appId)}</span>`;
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

// Deploy All Apps (batch)
els.deployAllBtn.addEventListener('click', openBatchModal);
els.batchCancelBtn.addEventListener('click', closeBatchModal);
els.closeBatchModalBtn.addEventListener('click', closeBatchModal);
els.batchDeployOverlay.addEventListener('click', event => {
    if (event.target === els.batchDeployOverlay) closeBatchModal();
});
els.batchTemplateSelect.addEventListener('change', () => {
    state.batch.templateId = els.batchTemplateSelect.value || 'auto';
    refreshBatchPlan();
});
els.batchStartBtn.addEventListener('click', startBatchDeploy);
els.batchStopBtn.addEventListener('click', stopBatchDeploy);

let currentWorkspacesList = [];

async function loadWorkspaceInfo() {
    try {
        const res = await fetch(api('/api/deployment/workspaces'));
        const data = await res.json();
        const label = document.getElementById('workspaceLabel');
        if (label && data.activeName) {
            label.textContent = `WORKSPACE: ${data.activeName.toUpperCase()}`;
            label.title = data.active || '';
        }
        currentWorkspacesList = data.workspaces || [];
        const dropdown = document.getElementById('workspaceSelectDropdown');
        if (dropdown) {
            dropdown.innerHTML = '<option value="">-- Select a saved project --</option>' +
                currentWorkspacesList.map(w => `<option value="${escapeHtml(w.path)}" ${w.path === data.active ? 'selected' : ''}>${escapeHtml(w.name || w.path)} (${escapeHtml(w.path)})</option>`).join('');
        }
        const pathInput = document.getElementById('workspacePathInput');
        if (pathInput && !pathInput.value) {
            pathInput.value = data.active || '';
        }
    } catch (_) {}
}

const wsModalEls = {
    overlay: document.getElementById('workspaceSwitchOverlay'),
    openBtn: document.getElementById('switchWorkspaceBtn'),
    closeBtn: document.getElementById('closeWorkspaceModalBtn'),
    cancelBtn: document.getElementById('cancelWorkspaceBtn'),
    confirmBtn: document.getElementById('confirmWorkspaceBtn'),
    dropdown: document.getElementById('workspaceSelectDropdown'),
    pathInput: document.getElementById('workspacePathInput'),
};

function openWorkspaceModal() {
    if (!wsModalEls.overlay) return;
    wsModalEls.overlay.classList.add('ui-active');
    loadWorkspaceInfo();
    if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
}

function closeWorkspaceModal() {
    if (!wsModalEls.overlay) return;
    wsModalEls.overlay.classList.remove('ui-active');
}

if (wsModalEls.openBtn) wsModalEls.openBtn.addEventListener('click', openWorkspaceModal);
if (wsModalEls.closeBtn) wsModalEls.closeBtn.addEventListener('click', closeWorkspaceModal);
if (wsModalEls.cancelBtn) wsModalEls.cancelBtn.addEventListener('click', closeWorkspaceModal);
if (wsModalEls.overlay) {
    wsModalEls.overlay.addEventListener('click', e => {
        if (e.target === wsModalEls.overlay) closeWorkspaceModal();
    });
}

if (wsModalEls.dropdown) {
    wsModalEls.dropdown.addEventListener('change', () => {
        if (wsModalEls.dropdown.value) {
            wsModalEls.pathInput.value = wsModalEls.dropdown.value;
        }
    });
}

if (wsModalEls.confirmBtn) {
    wsModalEls.confirmBtn.addEventListener('click', async () => {
        const path = (wsModalEls.pathInput?.value || '').trim();
        if (!path) {
            showToast('Please enter or select a project directory path');
            return;
        }
        wsModalEls.confirmBtn.disabled = true;
        try {
            const res = await fetch(api('/api/deployment/workspace/select'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path }),
            }).then(r => r.json());

            if (!res.success) {
                showToast('Failed to switch workspace: ' + (res.error || 'Unknown error'));
                return;
            }

            showToast(`Switched workspace to: ${res.activeName || path}`);
            closeWorkspaceModal();
            await loadWorkspaceInfo();
            await loadApps();
            if (typeof loadSetupData === 'function' && document.getElementById('setupOverlay')?.classList.contains('ui-active')) {
                await loadSetupData();
            }
        } catch (err) {
            showToast('Error switching workspace: ' + err.message);
        } finally {
            wsModalEls.confirmBtn.disabled = false;
        }
    });
}

loadWorkspaceInfo();
loadApps().catch(error => {
    els.appGrid.innerHTML = `<div class="empty-state">Failed to load apps: ${escapeHtml(error.message)}</div>`;
});
refreshIcons();

