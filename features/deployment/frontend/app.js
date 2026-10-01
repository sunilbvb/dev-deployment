
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
    pipelines: [],
    selectedPipeline: null,
    activePipelineRunId: null,
    pipelineLastStepIndex: 0,
    activeJobId: null,
    timerId: null,
    timerStartedAt: 0,
    stdoutLength: 0,
    stderrLength: 0,
    activeOutputView: 'live',
    historyEntries: [],
    sentinelWorkspace: null,
    sentinelApp: null,
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
    // App Doctor Diagnostics modal
    openDoctorBtn: document.getElementById('openDoctorBtn'),
    doctorPanelBtn: document.getElementById('doctorPanelBtn'),
    doctorOverlay: document.getElementById('doctorOverlay'),
    closeDoctorModalBtn: document.getElementById('closeDoctorModalBtn'),
    doctorSubtitle: document.getElementById('doctorSubtitle'),
    doctorStatusBanner: document.getElementById('doctorStatusBanner'),
    doctorOverallIcon: document.getElementById('doctorOverallIcon'),
    doctorOverallTitle: document.getElementById('doctorOverallTitle'),
    doctorOverallSummary: document.getElementById('doctorOverallSummary'),
    doctorScorePills: document.getElementById('doctorScorePills'),
    doctorChecklistContainer: document.getElementById('doctorChecklistContainer'),
    doctorFooterDuration: document.getElementById('doctorFooterDuration'),
    copyDoctorReportBtn: document.getElementById('copyDoctorReportBtn'),
    recheckDoctorBtn: document.getElementById('recheckDoctorBtn'),
    // APK banner & QR Modal
    apkInstallBanner: document.getElementById('apkInstallBanner'),
    apkBannerFilename: document.getElementById('apkBannerFilename'),
    apkBannerSize: document.getElementById('apkBannerSize'),
    openQrModalBtn: document.getElementById('openQrModalBtn'),
    bannerDownloadBtn: document.getElementById('bannerDownloadBtn'),
    qrModalOverlay: document.getElementById('qrModalOverlay'),
    closeQrModalBtn: document.getElementById('closeQrModalBtn'),
    qrCodeContainer: document.getElementById('qrCodeContainer'),
    qrApkSize: document.getElementById('qrApkSize'),
    qrApkFilename: document.getElementById('qrApkFilename'),
    qrApkPath: document.getElementById('qrApkPath'),
    qrDownloadUrlInput: document.getElementById('qrDownloadUrlInput'),
    copyQrUrlBtn: document.getElementById('copyQrUrlBtn'),
    directDownloadApkBtn: document.getElementById('directDownloadApkBtn'),
    qrLanIpLabel: document.getElementById('qrLanIpLabel'),
    // Sentinel Elements
    sentinelHeaderBadge: document.getElementById('sentinelHeaderBadge'),
    sentinelHeaderBadgeText: document.getElementById('sentinelHeaderBadgeText'),
    sentinelAlertBanner: document.getElementById('sentinelAlertBanner'),
    sentinelModalOverlay: document.getElementById('sentinelModalOverlay'),
    closeSentinelModalBtn: document.getElementById('closeSentinelModalBtn'),
    closeSentinelBtn: document.getElementById('closeSentinelBtn'),
    recheckSentinelBtn: document.getElementById('recheckSentinelBtn'),
    sentinelModalBadge: document.getElementById('sentinelModalBadge'),
    sentinelModalAlerts: document.getElementById('sentinelModalAlerts'),
    sentinelAppleStatusBadge: document.getElementById('sentinelAppleStatusBadge'),
    sentinelAppleDetails: document.getElementById('sentinelAppleDetails'),
    sentinelAndroidStatusBadge: document.getElementById('sentinelAndroidStatusBadge'),
    sentinelAndroidDetails: document.getElementById('sentinelAndroidDetails'),
    sentinelFirebaseStatusBadge: document.getElementById('sentinelFirebaseStatusBadge'),
    sentinelFirebaseDetails: document.getElementById('sentinelFirebaseDetails'),
    // Build Size Elements
    buildSizeBanner: document.getElementById('buildSizeBanner'),
    buildSizeSummaryText: document.getElementById('buildSizeSummaryText'),
    buildSizeSubtext: document.getElementById('buildSizeSubtext'),
    buildSizeBadge: document.getElementById('buildSizeBadge'),
    buildSizeModalOverlay: document.getElementById('buildSizeModalOverlay'),
    closeBuildSizeModalBtn: document.getElementById('closeBuildSizeModalBtn'),
    closeBuildSizeBtn: document.getElementById('closeBuildSizeBtn'),
    buildSizeModalBadge: document.getElementById('buildSizeModalBadge'),
    buildSizeModalSubtitle: document.getElementById('buildSizeModalSubtitle'),
    bsStatCurrentSize: document.getElementById('bsStatCurrentSize'),
    bsStatCurrentType: document.getElementById('bsStatCurrentType'),
    bsStatPreviousSize: document.getElementById('bsStatPreviousSize'),
    bsStatPreviousMeta: document.getElementById('bsStatPreviousMeta'),
    bsStatDelta: document.getElementById('bsStatDelta'),
    bsStatPercent: document.getElementById('bsStatPercent'),
    bsStatCompression: document.getElementById('bsStatCompression'),
    bsStatUncompressed: document.getElementById('bsStatUncompressed'),
    buildSizeWarningsContainer: document.getElementById('buildSizeWarningsContainer'),
    bsTabDiffBtn: document.getElementById('bsTabDiffBtn'),
    bsTabLargestBtn: document.getElementById('bsTabLargestBtn'),
    bsDiffTableView: document.getElementById('bsDiffTableView'),
    bsLargestTableView: document.getElementById('bsLargestTableView'),
    bsDiffTableContainer: document.getElementById('bsDiffTableContainer'),
    bsLargestTableContainer: document.getElementById('bsLargestTableContainer'),
    bsModalFooterPath: document.getElementById('bsModalFooterPath'),
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

        const appSentinel = state.sentinelWorkspace?.apps?.[app.id];
        const sentinelAlertBadge = (appSentinel && appSentinel.hasAlert)
            ? `<span class="ui-badge" data-variant="${appSentinel.badge.variant || 'warning'}" style="position: absolute; top: -5px; right: -5px; font-size: 10px; padding: 1px 5px; border-radius: 999px; box-shadow: 0 1px 3px rgba(0,0,0,0.3); z-index: 2;" title="${escapeHtml(appSentinel.badge.label)}">⚠️</span>`
            : '';

        return `
            <div class="compact-app-card ${activeState}" data-state="${activeState}" data-app="${escapeHtml(app.id)}" style="--app-color:${escapeHtml(app.color || '#6366f1')}; position: relative;">
                ${sentinelAlertBadge}
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
    await loadAppSentinel(appId);
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
        const [cmdRes, pipeRes] = await Promise.all([
            fetch(api(`/api/deployment/commands?app=${encodeURIComponent(appId)}`)).then(r => r.json()),
            fetch(api(`/api/deployment/pipelines?app=${encodeURIComponent(appId)}`)).then(r => r.json()).catch(() => ({ pipelines: [] })),
        ]);
        data = cmdRes;
        state.pipelines = pipeRes.pipelines || [];
        if (!data || data.success === false) throw new Error(data?.error || 'Failed to load commands');
    } catch (err) {
        state.commands = [];
        state.pipelines = [];
        els.commandGrid.innerHTML = `<div class="empty-state">Could not load commands: ${escapeHtml(err.message)}.
            Check that the console server is still running (<code>./start.sh</code>), then reload this page.</div>`;
        return;
    }
    state.commands = data.commands || [];
    renderEnvTabs();
    renderCommands();
}

function renderCommands() {
    let html = '';
    const visiblePipelines = (state.pipelines || []).filter(p => !p.flavor || !state.hasMultipleEnvs || p.flavor === state.selectedEnv || p.flavor === 'any');
    if (visiblePipelines.length > 0) {
        html += `<div class="ui-section-header" style="margin: 10px 0 10px 0;"><span class="ui-section-title">Pipelines</span></div>`;
        html += `<div class="compact-app-grid compact-app-grid--commands">`;
        html += visiblePipelines.map(p => {
            const isSelected = state.selectedPipeline && state.selectedPipeline.id === p.id;
            const selectedClass = isSelected ? 'active' : '';
            const stepCount = (p.steps || []).length;
            const flavorBadge = p.flavor ? `<span class="ui-badge" data-variant="info" style="margin-left:4px;">${escapeHtml(p.flavor.toUpperCase())}</span>` : '';
            return `
                <div class="compact-app-card ${selectedClass}" data-state="${isSelected ? 'selected' : ''}" data-pipeline-id="${escapeHtml(p.id)}" style="--app-color: #6366f1;">
                    <div class="compact-app-card-icon"><i data-lucide="layers"></i></div>
                    <div style="min-width: 0; flex: 1;">
                        <h3 title="${escapeHtml(p.name)}">${escapeHtml(p.name)} ${flavorBadge}</h3>
                        <div class="compact-app-meta">${stepCount} step${stepCount === 1 ? '' : 's'}</div>
                    </div>
                </div>
            `;
        }).join('');
        html += `</div>`;
    }

    const visible = state.commands.filter(cmd => matchesEnv(cmd));
    if (!visible.length && !visiblePipelines.length) {
        els.commandGrid.innerHTML = '<div class="empty-state">No deployment commands found for this selection.</div>';
        return;
    }

    const groups = new Map();
    visible.forEach(cmd => {
        const meta = getCommandMeta(cmd);
        if (!groups.has(meta.group)) groups.set(meta.group, []);
        groups.get(meta.group).push({cmd, meta});
    });

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

function selectPipeline(id) {
    const pipe = (state.pipelines || []).find(p => p.id === id) || null;
    state.selectedPipeline = pipe;
    state.selectedCommand = null;
    renderCommands();
    updateExecutionPanel();
}

function selectCommand(id) {
    const cmd = state.commands.find(c => c.id === id) || null;
    // block selection of unconfigured commands
    if (cmd && cmd.configured === false) return;
    state.selectedCommand = cmd;
    state.selectedPipeline = null;
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
    if (!state.selectedApp || (!state.selectedCommand && !state.selectedPipeline)) {
        els.executionPanel.classList.add('hidden');
        els.runButton.disabled = true;
        els.iosCertBanner.classList.add('hidden');
        return;
    }

    if (state.selectedPipeline) {
        els.executionPanel.classList.remove('hidden');
        const pipeFlavor = state.selectedPipeline.flavor ? ` (${state.selectedPipeline.flavor.toUpperCase()})` : '';
        els.selectedCommandTitle.textContent = state.selectedPipeline.name + pipeFlavor;
        const steps = state.selectedPipeline.steps || [];
        const lines = steps.map((s, idx) => {
            const cont = s.continueOnFailure ? ' [continue on error]' : '';
            const custom = s.isCustom ? ' (custom shell)' : '';
            return `${idx + 1}. ${s.name || s.templateId || 'Custom'}: ${s.command}${cont}${custom}`;
        });
        els.selectedCommandPreview.textContent = lines.join('\n');
        els.runButton.disabled = false;
        els.runButton.querySelector('span').textContent = 'Run Pipeline';
        els.iosCertBanner.classList.add('hidden');
        return;
    }

    els.runButton.querySelector('span').textContent = 'Run';
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

let isConfirmingPipeline = false;

function openProdConfirmModal() {
    isConfirmingPipeline = false;
    const app = state.apps.find(a => a.id === state.selectedApp);
    els.prodConfirmAppName.textContent = app ? (app.name || app.id) : state.selectedApp;
    els.prodConfirmCommandPreview.textContent = els.selectedCommandPreview.textContent;
    els.prodConfirmOverlay.classList.add('ui-active');
}

function openPipelineConfirmModal(commandsList) {
    isConfirmingPipeline = true;
    const app = state.apps.find(a => a.id === state.selectedApp);
    els.prodConfirmAppName.textContent = app ? (app.name || app.id) : state.selectedApp;
    const preview = commandsList.map(c => `• ${c.step}: ${c.command}`).join('\n');
    els.prodConfirmCommandPreview.textContent = preview;
    els.prodConfirmOverlay.classList.add('ui-active');
}

function closeProdConfirmModal() {
    isConfirmingPipeline = false;
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
    if (els.apkInstallBanner) els.apkInstallBanner.classList.add('hidden');
    if (els.buildSizeBanner) {
        els.buildSizeBanner.classList.add('hidden');
        els.buildSizeBanner.style.display = 'none';
    }
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
            checkAndDisplayApk(jobId, job.app, job.flavor || job.env);
            checkAndDisplayBuildSize(jobId, job.app, job.flavor || job.env);
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
    state.activePipelineRunId = null;
    state.pipelineLastStepIndex = 0;
    els.runButton.disabled = false;
    els.stopJobBtn.disabled = true;
    stopTimer();
}

async function executePipelineSelected(confirmed = false) {
    if (!state.selectedApp || !state.selectedPipeline) return;
    const pipelineId = state.selectedPipeline.id;
    state.activePipelineRunId = null;
    state.pipelineLastStepIndex = 0;
    state.stdoutLength = 0;
    state.stderrLength = 0;
    if (els.apkInstallBanner) els.apkInstallBanner.classList.add('hidden');
    if (els.buildSizeBanner) {
        els.buildSizeBanner.classList.add('hidden');
        els.buildSizeBanner.style.display = 'none';
    }
    els.runButton.disabled = true;
    els.stopJobBtn.disabled = true;
    startTimer();
    writeTerminal(`Starting pipeline: ${state.selectedPipeline.name}`);

    try {
        const res = await fetch(api('/api/deployment/pipelines/run'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                app: state.selectedApp,
                pipelineId: pipelineId,
                flavor: state.selectedPipeline.flavor || state.selectedEnv || '',
                confirmed: !!confirmed,
            }),
        });
        const data = await res.json();
        if (!data.success && data.needsConfirmation) {
            finishExecution();
            openPipelineConfirmModal(data.commands || []);
            return;
        }
        if (!data.success || !data.runId) {
            const err = new Error(data.error || 'Pipeline could not start');
            err.code = data.code || '';
            throw err;
        }
        state.activePipelineRunId = data.runId;
        els.stopJobBtn.disabled = false;
        pollPipelineRun(data.runId);
    } catch (error) {
        writeTerminal(`Failed to start pipeline: ${error.message}`, 'error');
        showToast(error.message || 'Failed to start pipeline', 'error');
        finishExecution();
    }
}

async function pollPipelineRun(runId) {
    try {
        const res = await fetch(api(`/api/deployment/pipelines/run?id=${encodeURIComponent(runId)}`));
        const data = await res.json();
        if (!data.success || !data.run) throw new Error(data.error || 'Failed to read pipeline run');

        const run = data.run;

        // Check if step changed to print header
        if (run.currentStep && run.currentStep !== state.pipelineLastStepIndex) {
            state.pipelineLastStepIndex = run.currentStep;
            const stepObj = (run.steps || [])[run.currentStep - 1];
            const stepName = stepObj ? (stepObj.name || stepObj.templateId || `Step ${run.currentStep}`) : `Step ${run.currentStep}`;
            const total = (run.steps || []).length;
            writeTerminal(`════ Step ${run.currentStep}/${total} · ${stepName} ════`);
            state.stdoutLength = 0;
            state.stderrLength = 0;
        }

        // Stream output of current step job if available
        if (run.currentJobId) {
            try {
                const jRes = await fetch(api(`/api/deployment/job?id=${encodeURIComponent(run.currentJobId)}`));
                const jData = await jRes.json();
                if (jData.success && jData.job) {
                    const job = jData.job;
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
                }
            } catch (_) {}
        }

        if (run.status === 'running' || run.status === 'stopping') {
            setTimeout(() => pollPipelineRun(runId), 900);
            return;
        }

        if (run.status === 'success') {
            writeTerminal(`Pipeline completed successfully: ${run.name}`, 'success');
            showToast('Pipeline completed successfully');
            checkAndDisplayApk(run.currentJobId || '', run.app, run.flavor);
            checkAndDisplayBuildSize(run.currentJobId || '', run.app, run.flavor);
        } else if (run.status === 'stopped') {
            writeTerminal(`Pipeline stopped: ${run.name}`, 'warning');
            showToast('Pipeline stopped');
        } else {
            const failedStepMsg = run.failedStep ? ` (failed at step ${run.failedStep})` : '';
            writeTerminal(`Pipeline failed${failedStepMsg}: ${run.name}`, 'error');
            showToast('Pipeline failed', 'error');
        }
        finishExecution();
        loadCommands(state.selectedApp);
    } catch (error) {
        writeTerminal(`Pipeline polling failed: ${error.message}`, 'error');
        finishExecution();
    }
}

async function stopActiveJob() {
    if (state.activePipelineRunId) {
        els.stopJobBtn.disabled = true;
        writeTerminal('Stopping pipeline...', 'warning');
        await fetch(api('/api/deployment/pipelines/stop'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({runId: state.activePipelineRunId}),
        }).catch(() => {});
        return;
    }
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
        if (entry.type === 'pipeline') {
            const statusClass = entry.status === 'success' ? 'success' : (entry.status === 'stopped' ? 'warning' : 'error');
            const time = entry.completedAt ? new Date(entry.completedAt).toLocaleString() : '';
            const duration = entry.durationSeconds != null ? `${entry.durationSeconds}s` : '—';
            const stepsCount = (entry.steps || []).length;
            const stepsSummary = (entry.steps || []).map((s, idx) => {
                const sColor = s.status === 'success' ? 'var(--ui-success)' : (s.status === 'skipped' ? 'var(--ui-text-muted)' : 'var(--ui-danger)');
                return `<span style="color: ${sColor}; font-weight: 500;">Step ${idx + 1} (${escapeHtml(s.name || s.templateId || 'Custom')}): ${escapeHtml(s.status || 'unknown')}</span>`;
            }).join(' &nbsp;·&nbsp; ');
            const failedInfo = entry.failedStep ? ` · failed at step #${entry.failedStep}` : '';
            const apkBtn = entry.artifact ? ` &nbsp;·&nbsp; <button type="button" class="ui-button" data-variant="secondary" data-size="xs" style="padding:1px 6px; font-size:11px; color:#10b981;" onclick="openQrModalForTarget('${escapeHtml(entry.id)}', '${escapeHtml(entry.app || '')}', '${escapeHtml(entry.flavor || '')}')"><i data-lucide="qr-code" style="width:12px;height:12px;"></i> APK QR</button>` : '';
            const bsBtn = (entry.buildSize || entry.artifact) ? ` &nbsp;·&nbsp; <button type="button" class="ui-button" data-variant="secondary" data-size="xs" style="padding:1px 6px; font-size:11px;" onclick="openBuildSizeModalForTarget('${escapeHtml(entry.id)}', '${escapeHtml(entry.app || '')}', '${escapeHtml(entry.flavor || '')}')"><i data-lucide="package" style="width:12px;height:12px;"></i> ${escapeHtml(entry.buildSize ? entry.buildSize.summary : ((entry.artifact.type || 'Size') + ': ' + (entry.artifact.sizeFormatted || '')))}</button>` : '';
            return `
                <div class="terminal-line history-row pipeline-history-row" style="flex-direction: column; align-items: flex-start; gap: 4px;">
                    <div>
                        <span class="${statusClass}">PIPELINE ${escapeHtml((entry.status || '').toUpperCase())}</span>
                        &nbsp;${escapeHtml(time)} · ${escapeHtml(entry.app || '')} · <strong>${escapeHtml(entry.name || entry.pipelineId || 'Pipeline')}</strong> (${stepsCount} steps) · ${escapeHtml(entry.flavor || '')} · ${duration} · #${escapeHtml(entry.id || '')}${failedInfo}${apkBtn}${bsBtn}
                    </div>
                    ${stepsSummary ? `<div style="font-size: 0.78rem; padding-left: 12px; opacity: 0.9;">${stepsSummary}</div>` : ''}
                </div>
            `;
        }
        const statusClass = entry.status === 'success' ? 'success' : (entry.status === 'stopped' ? 'warning' : 'error');
        const time = entry.completedAt ? new Date(entry.completedAt).toLocaleString() : '';
        const duration = entry.durationSeconds != null ? `${entry.durationSeconds}s` : '—';
        const chained = entry.chainedJobId ? ` · chained → ${escapeHtml(entry.chainedJobId)}` : '';
        const excerpt = entry.errorExcerpt || entry.outputExcerpt || '';
        const apkBtn = entry.artifact ? ` · <button type="button" class="ui-button" data-variant="secondary" data-size="xs" style="padding:1px 6px; font-size:11px; color:#10b981;" onclick="openQrModalForTarget('${escapeHtml(entry.id)}', '${escapeHtml(entry.app || '')}', '${escapeHtml(entry.flavor || '')}')"><i data-lucide="qr-code" style="width:12px;height:12px;"></i> APK QR</button>` : '';
        const bsBtn = (entry.buildSize || entry.artifact) ? ` · <button type="button" class="ui-button" data-variant="secondary" data-size="xs" style="padding:1px 6px; font-size:11px;" onclick="openBuildSizeModalForTarget('${escapeHtml(entry.id)}', '${escapeHtml(entry.app || '')}', '${escapeHtml(entry.flavor || '')}')"><i data-lucide="package" style="width:12px;height:12px;"></i> ${escapeHtml(entry.buildSize ? entry.buildSize.summary : ((entry.artifact.type || 'Size') + ': ' + (entry.artifact.sizeFormatted || '')))}</button>` : '';
        return `
            <div class="terminal-line history-row">
                <span class="${statusClass}">${escapeHtml((entry.status || '').toUpperCase())}</span>
                &nbsp;${escapeHtml(time)} · ${escapeHtml(entry.app || '')} · ${escapeHtml(entry.templateId || '')} · ${escapeHtml(entry.flavor || '')} · ${duration} · #${escapeHtml(entry.id || '')}${chained}${apkBtn}${bsBtn}
                ${excerpt ? `<pre class="history-excerpt">${escapeHtml(excerpt)}</pre>` : ''}
            </div>
        `;
    }).join('');
    refreshIcons();
}

els.appGrid.addEventListener('click', event => {
    const card = event.target.closest('.compact-app-card') || event.target.closest('.ui-app-card');
    if (card) selectApp(card.dataset.app);
});

els.commandGrid.addEventListener('click', event => {
    const pipeCard = event.target.closest('.compact-app-card[data-pipeline-id]');
    if (pipeCard) {
        selectPipeline(pipeCard.dataset.pipelineId);
        return;
    }
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
    if (state.selectedApp) {
        loadAppSentinel(state.selectedApp);
    }
    loadWorkspaceSentinel();
});

els.runButton.addEventListener('click', () => {
    if (state.selectedPipeline) {
        executePipelineSelected(false);
        return;
    }
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
    if (isConfirmingPipeline) {
        executePipelineSelected(true).finally(() => { els.confirmProdDeployBtn.disabled = false; });
    } else {
        executeSelected(true).finally(() => { els.confirmProdDeployBtn.disabled = false; });
    }
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

// ═══════════════════════════ App Doctor Diagnostics ═══════════════════════════

const doctorState = {
    appId: null,
    flavor: 'prod',
    lastReportMarkdown: '',
};

function openDoctorModal(appId = null, flavor = null) {
    doctorState.appId = appId || state.selectedApp || '';
    doctorState.flavor = flavor || state.selectedEnv || 'prod';
    if (els.doctorOverlay) els.doctorOverlay.classList.add('ui-active');
    const displayTarget = doctorState.appId ? `App: ${doctorState.appId}` : 'Current Workspace';
    if (els.doctorSubtitle) {
        els.doctorSubtitle.textContent = `Pre-flight diagnostics for ${displayTarget} (${doctorState.flavor.toUpperCase()})`;
    }
    runDoctorDiagnostics();
}

function closeDoctorModal() {
    if (els.doctorOverlay) els.doctorOverlay.classList.remove('ui-active');
}

async function runDoctorDiagnostics() {
    if (!els.doctorStatusBanner) return;
    els.doctorStatusBanner.dataset.status = 'pending';
    els.doctorOverallIcon.textContent = '🩺';
    els.doctorOverallTitle.textContent = 'Diagnosing Environment...';
    els.doctorOverallSummary.textContent = 'Running pre-flight checks across toolchains, SDKs, and credentials';
    els.doctorScorePills.innerHTML = '<span class="ui-badge" data-variant="secondary">Running...</span>';
    els.doctorChecklistContainer.innerHTML = '<div class="empty-state">Running diagnostics...</div>';
    if (els.recheckDoctorBtn) els.recheckDoctorBtn.disabled = true;

    try {
        const queryApp = doctorState.appId ? `app=${encodeURIComponent(doctorState.appId)}&` : '';
        const queryFlavor = doctorState.flavor ? `flavor=${encodeURIComponent(doctorState.flavor)}` : 'flavor=prod';
        const res = await fetch(api(`/api/deployment/doctor?${queryApp}${queryFlavor}`));
        const data = await res.json();
        if (!data || !data.success) {
            throw new Error(data?.error || 'Diagnostic check failed');
        }

        doctorState.lastReportMarkdown = data.reportMarkdown || '';

        // Status banner
        els.doctorStatusBanner.dataset.status = data.overallStatus;
        if (data.overallStatus === 'pass') {
            els.doctorOverallIcon.textContent = '✅';
            els.doctorOverallTitle.textContent = 'All Systems Go · Ready to Build';
        } else if (data.overallStatus === 'warn') {
            els.doctorOverallIcon.textContent = '⚠️';
            els.doctorOverallTitle.textContent = 'Environment Warnings Detected';
        } else {
            els.doctorOverallIcon.textContent = '❌';
            els.doctorOverallTitle.textContent = 'Build-Breaking Issues Found';
        }
        els.doctorOverallSummary.textContent = data.summary;

        // Score pills
        let pillsHtml = `<span class="ui-badge" data-variant="success">${data.passCount} Passed</span>`;
        if (data.warnCount > 0) {
            pillsHtml += `<span class="ui-badge" data-variant="warning">${data.warnCount} Warnings</span>`;
        }
        if (data.failCount > 0) {
            pillsHtml += `<span class="ui-badge" data-variant="danger">${data.failCount} Failures</span>`;
        }
        els.doctorScorePills.innerHTML = pillsHtml;

        // Group checklist by category
        const categories = [
            { key: 'toolchain', title: 'SDK & Core Toolchain' },
            { key: 'project', title: 'Project Structure & Dependencies' },
            { key: 'android', title: 'Android Build Environment' },
            { key: 'ios', title: 'iOS Environment & Signing' },
            { key: 'credentials', title: 'Store Deployment Credentials' },
            { key: 'git', title: 'Git & Release Readiness' },
        ];

        const checks = data.checks || [];
        let html = '';

        categories.forEach(cat => {
            const catChecks = checks.filter(c => c.category === cat.key);
            if (!catChecks.length) return;

            html += `
                <div class="doctor-category-card">
                    <div class="doctor-category-header">
                        <span>${escapeHtml(cat.title)}</span>
                        <span style="font-size: 0.72rem; opacity: 0.8;">${catChecks.length} check${catChecks.length === 1 ? '' : 's'}</span>
                    </div>
                    <div>
            `;

            catChecks.forEach(c => {
                let badgeVariant = 'secondary';
                let badgeText = (c.status || '').toUpperCase();
                let statusIcon = 'check';

                if (c.status === 'pass') {
                    badgeVariant = 'success';
                    statusIcon = 'check-circle';
                } else if (c.status === 'warn') {
                    badgeVariant = 'warning';
                    statusIcon = 'alert-triangle';
                } else if (c.status === 'fail') {
                    badgeVariant = 'danger';
                    statusIcon = 'x-circle';
                } else if (c.status === 'info') {
                    badgeVariant = 'secondary';
                    statusIcon = 'info';
                }

                const hintBox = c.hint ? `
                    <div class="doctor-hint-box ${c.status === 'fail' ? 'fail' : ''}">
                        <strong>💡 Actionable Hint:</strong> ${escapeHtml(c.hint)}
                    </div>
                ` : '';

                html += `
                    <div class="doctor-check-row">
                        <div class="doctor-check-main">
                            <div class="doctor-check-name">
                                <i data-lucide="${statusIcon}" style="width:14px;height:14px;"></i>
                                <span>${escapeHtml(c.name)}</span>
                            </div>
                            <span class="ui-badge" data-variant="${badgeVariant}" style="font-size:0.68rem; text-transform:uppercase;">${badgeText}</span>
                        </div>
                        <div class="doctor-check-message">${escapeHtml(c.message)}</div>
                        ${hintBox}
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        });

        els.doctorChecklistContainer.innerHTML = html || '<div class="empty-state">No checks available.</div>';
        if (els.doctorFooterDuration) {
            els.doctorFooterDuration.textContent = `Diagnostics completed in ${data.durationMs}ms`;
        }
        refreshIcons();
    } catch (err) {
        els.doctorStatusBanner.dataset.status = 'fail';
        els.doctorOverallIcon.textContent = '❌';
        els.doctorOverallTitle.textContent = 'Diagnostic Execution Failed';
        els.doctorOverallSummary.textContent = err.message || 'Could not connect to backend';
        els.doctorChecklistContainer.innerHTML = `<div class="empty-state" style="color:var(--ui-danger);">${escapeHtml(err.message)}</div>`;
        showToast('App Doctor failed: ' + err.message, 'error');
    } finally {
        if (els.recheckDoctorBtn) els.recheckDoctorBtn.disabled = false;
    }
}

async function copyDoctorReport() {
    if (!doctorState.lastReportMarkdown) {
        showToast('No diagnostic report available to copy.');
        return;
    }
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(doctorState.lastReportMarkdown);
        } else {
            const ta = document.createElement('textarea');
            ta.value = doctorState.lastReportMarkdown;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
        showToast('Diagnostic report copied to clipboard!');
    } catch (err) {
        showToast('Could not copy report: ' + err.message);
    }
}

if (els.openDoctorBtn) els.openDoctorBtn.addEventListener('click', () => openDoctorModal(state.selectedApp));
if (els.doctorPanelBtn) els.doctorPanelBtn.addEventListener('click', () => openDoctorModal(state.selectedApp));
if (els.closeDoctorModalBtn) els.closeDoctorModalBtn.addEventListener('click', closeDoctorModal);
if (els.recheckDoctorBtn) els.recheckDoctorBtn.addEventListener('click', runDoctorDiagnostics);
if (els.copyDoctorReportBtn) els.copyDoctorReportBtn.addEventListener('click', copyDoctorReport);
if (els.doctorOverlay) els.doctorOverlay.addEventListener('click', event => {
    if (event.target === els.doctorOverlay) closeDoctorModal();
});

// ═══════════════════════════ Certificate & Keystore Sentinel ═══════════════════════════

async function loadWorkspaceSentinel() {
    try {
        const flavor = state.selectedEnv || 'prod';
        const res = await fetch(api(`/api/deployment/sentinel?flavor=${encodeURIComponent(flavor)}`));
        const data = await res.json();
        if (!data || !data.success) return;
        state.sentinelWorkspace = data;

        if (els.sentinelHeaderBadge) {
            if (data.hasAlert) {
                els.sentinelHeaderBadge.style.display = 'inline-flex';
                els.sentinelHeaderBadge.dataset.variant = data.badge.variant || 'warning';
                if (els.sentinelHeaderBadgeText) {
                    els.sentinelHeaderBadgeText.textContent = data.badge.label || 'Sentinel Alert';
                }
                els.sentinelHeaderBadge.classList.remove('hidden');
            } else {
                els.sentinelHeaderBadge.style.display = 'none';
                els.sentinelHeaderBadge.classList.add('hidden');
            }
        }
        renderApps();
    } catch (err) {
        console.warn('Could not load workspace sentinel:', err);
    }
}

async function loadAppSentinel(appId = null, flavor = null) {
    const targetApp = appId || state.selectedApp;
    if (!targetApp) {
        if (els.sentinelAlertBanner) {
            els.sentinelAlertBanner.style.display = 'none';
            els.sentinelAlertBanner.classList.add('hidden');
        }
        return;
    }
    const targetFlavor = flavor || state.selectedEnv || 'prod';
    try {
        const res = await fetch(api(`/api/deployment/sentinel?app=${encodeURIComponent(targetApp)}&flavor=${encodeURIComponent(targetFlavor)}`));
        const data = await res.json();
        if (!data || !data.success) return;
        state.sentinelApp = data;

        if (els.sentinelAlertBanner) {
            if (data.hasAlert) {
                const count = data.alerts.length;
                const crit = data.badge.criticalCount;
                const statusType = crit > 0 ? 'critical' : 'warning';
                els.sentinelAlertBanner.dataset.status = statusType;
                els.sentinelAlertBanner.style.display = 'flex';
                els.sentinelAlertBanner.style.alignItems = 'center';
                els.sentinelAlertBanner.style.justifyContent = 'space-between';
                els.sentinelAlertBanner.style.padding = '10px 14px';
                els.sentinelAlertBanner.classList.remove('hidden');

                const alertItems = data.alerts.map(a => `<div style="font-size:0.78rem; margin-top:2px;"><strong>${escapeHtml(a.title)}:</strong> ${escapeHtml(a.message)}</div>`).join('');
                els.sentinelAlertBanner.innerHTML = `
                    <div style="display:flex; align-items:flex-start; gap:8px;">
                        <span style="font-size:1.1rem; line-height:1;">⚠️</span>
                        <div>
                            <div style="font-weight:600; font-size:0.82rem;">Sentinel Expiry &amp; Config Alert (${count} issue${count > 1 ? 's' : ''})</div>
                            ${alertItems}
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span class="ui-badge" data-variant="${data.badge.variant}">${escapeHtml(data.badge.label)}</span>
                        <span style="font-size:0.75rem; text-decoration:underline; opacity:0.85;">Details &rarr;</span>
                    </div>
                `;
            } else {
                els.sentinelAlertBanner.style.display = 'none';
                els.sentinelAlertBanner.classList.add('hidden');
            }
        }

        // If modal open, refresh modal contents
        if (els.sentinelModalOverlay && els.sentinelModalOverlay.classList.contains('ui-active')) {
            renderSentinelModalData(data);
        }
    } catch (err) {
        console.warn('Could not load app sentinel:', err);
    }
}

function renderSentinelModalData(data) {
    if (!data) return;
    if (els.sentinelModalBadge) {
        els.sentinelModalBadge.setAttribute('data-variant', data.badge?.variant || 'secondary');
        els.sentinelModalBadge.textContent = data.badge?.label || 'Sentinel Alert';
    }

    // Alerts list
    if (els.sentinelModalAlerts) {
        if (!data.alerts || data.alerts.length === 0) {
            els.sentinelModalAlerts.innerHTML = `
                <div class="ui-card" style="padding:14px; background: rgba(34, 197, 94, 0.08); border-left: 4px solid var(--ui-success, #22c55e);">
                    <div style="display:flex; align-items:center; gap:8px; font-weight:600; color:var(--ui-success, #22c55e);">
                        <i data-lucide="check-circle" style="width:16px;height:16px;"></i>
                        <span>No panic release risks detected. Certificates and configurations are sound.</span>
                    </div>
                </div>
            `;
        } else {
            els.sentinelModalAlerts.innerHTML = data.alerts.map(a => {
                const borderCol = a.severity === 'critical' ? 'var(--ui-danger, #ef4444)' : 'var(--ui-warning, #f59e0b)';
                const bgCol = a.severity === 'critical' ? 'rgba(239, 68, 68, 0.08)' : 'rgba(245, 158, 11, 0.08)';
                const badgeVariant = a.severity === 'critical' ? 'danger' : 'warning';
                return `
                    <div class="ui-card" style="padding:12px; background:${bgCol}; border-left: 4px solid ${borderCol};">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <strong style="font-size:0.85rem; display:flex; align-items:center; gap:6px;">
                                <i data-lucide="alert-triangle" style="width:14px;height:14px;"></i>
                                ${escapeHtml(a.title)}
                            </strong>
                            <span class="ui-badge" data-variant="${badgeVariant}" style="font-size:0.7rem; text-transform:uppercase;">${escapeHtml(a.severity)}</span>
                        </div>
                        <p style="margin:0 0 6px 0; font-size:0.8rem; color:var(--ui-text);">${escapeHtml(a.message)}</p>
                        ${a.hint ? `<div style="font-size:0.75rem; color:var(--ui-text-muted); background:rgba(0,0,0,0.15); padding:6px 10px; border-radius:4px;"><strong>💡 Action:</strong> ${escapeHtml(a.hint)}</div>` : ''}
                    </div>
                `;
            }).join('');
        }
    }

    // 1. Apple Section
    const apple = data.checks?.apple || {};
    if (els.sentinelAppleStatusBadge) {
        const varMap = { ok: 'success', warning: 'warning', critical: 'danger', not_configured: 'secondary' };
        els.sentinelAppleStatusBadge.setAttribute('data-variant', varMap[apple.status] || 'secondary');
        els.sentinelAppleStatusBadge.textContent = (apple.status || 'unknown').toUpperCase();
    }
    if (els.sentinelAppleDetails) {
        if (!apple.applicable) {
            els.sentinelAppleDetails.innerHTML = `<span style="font-size:0.8rem; color:var(--ui-text-muted);">Not an iOS project or Apple configuration absent.</span>`;
        } else {
            const cert = apple.certificate || {};
            const prof = apple.provisioningProfile || {};
            els.sentinelAppleDetails.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:6px; font-size:0.8rem;">
                    <div><strong>App Store Connect .p8 Key:</strong> ${apple.p8Configured ? `<span style="color:var(--ui-success);">Configured (Key ID: ${escapeHtml(apple.p8KeyId || 'Detected')})</span>` : '<span style="color:var(--ui-text-muted);">Not found</span>'}</div>
                    <div><strong>Distribution Certificate:</strong> ${cert.status ? `<span class="ui-badge" data-variant="${cert.status === 'ok' ? 'success' : (cert.status === 'expired' ? 'danger' : 'warning')}">${escapeHtml(cert.status.toUpperCase())}</span> ${escapeHtml(cert.name || cert.type || '')} ${cert.expiresOn ? `(Expires: ${escapeHtml(cert.expiresOn)}, ${cert.daysRemaining} days left)` : ''}` : '<span style="color:var(--ui-text-muted);">None inspected</span>'}</div>
                    <div><strong>Provisioning Profile:</strong> ${prof.status ? `<span class="ui-badge" data-variant="${prof.status === 'ok' ? 'success' : (prof.status === 'expired' ? 'danger' : 'warning')}">${escapeHtml(prof.status.toUpperCase())}</span> ${escapeHtml(prof.name || '')} ${prof.expiresOn ? `(Expires: ${escapeHtml(prof.expiresOn)}, ${prof.daysRemaining} days left)` : ''}` : '<span style="color:var(--ui-text-muted);">None inspected</span>'}</div>
                </div>
            `;
        }
    }

    // 2. Android Section
    const android = data.checks?.android || {};
    if (els.sentinelAndroidStatusBadge) {
        const varMap = { ok: 'success', warning: 'warning', critical: 'danger', not_configured: 'secondary' };
        els.sentinelAndroidStatusBadge.setAttribute('data-variant', varMap[android.status] || 'secondary');
        els.sentinelAndroidStatusBadge.textContent = (android.status || 'unknown').toUpperCase();
    }
    if (els.sentinelAndroidDetails) {
        if (!android.applicable) {
            els.sentinelAndroidDetails.innerHTML = `<span style="font-size:0.8rem; color:var(--ui-text-muted);">Not an Android project.</span>`;
        } else if (!android.keystorePath) {
            els.sentinelAndroidDetails.innerHTML = `<span style="font-size:0.8rem; color:var(--ui-text-muted);">No keystore file discovered in key.properties or standard paths.</span>`;
        } else {
            els.sentinelAndroidDetails.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:6px; font-size:0.8rem;">
                    <div><strong>Keystore Path:</strong> <code>${escapeHtml(android.keystorePath)}</code></div>
                    <div><strong>Validity:</strong> ${android.validTo ? `<span class="ui-badge" data-variant="${android.status === 'ok' ? 'success' : (android.status === 'critical' ? 'danger' : 'warning')}">${android.daysRemaining <= 0 ? 'EXPIRED' : `${android.daysRemaining} days left`}</span> (Expires: ${escapeHtml(android.validTo)})` : '<span style="color:var(--ui-text-muted);">Could not read validity</span>'}</div>
                    ${android.source ? `<div><strong>Inspection Source:</strong> ${escapeHtml(android.source)}</div>` : ''}
                </div>
            `;
        }
    }

    // 3. Firebase Section
    const firebase = data.checks?.firebase || {};
    if (els.sentinelFirebaseStatusBadge) {
        const varMap = { ok: 'success', warning: 'warning', critical: 'danger', not_configured: 'secondary' };
        els.sentinelFirebaseStatusBadge.setAttribute('data-variant', varMap[firebase.status] || 'secondary');
        els.sentinelFirebaseStatusBadge.textContent = (firebase.status || 'unknown').toUpperCase();
    }
    if (els.sentinelFirebaseDetails) {
        if (!firebase.applicable) {
            els.sentinelFirebaseDetails.innerHTML = `<span style="font-size:0.8rem; color:var(--ui-text-muted);">No Firebase configuration files found.</span>`;
        } else {
            const afb = firebase.android || {};
            const ifb = firebase.ios || {};
            els.sentinelFirebaseDetails.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:6px; font-size:0.8rem;">
                    <div><strong>Android (google-services.json):</strong> ${afb.exists ? `Project: <code>${escapeHtml(afb.projectId || 'N/A')}</code> (${escapeHtml(afb.path)})` : '<span style="color:var(--ui-text-muted);">Not present</span>'}</div>
                    <div><strong>iOS (GoogleService-Info.plist):</strong> ${ifb.exists ? `Project: <code>${escapeHtml(ifb.projectId || 'N/A')}</code> (${escapeHtml(ifb.path)})` : '<span style="color:var(--ui-text-muted);">Not present</span>'}</div>
                </div>
            `;
        }
    }

    refreshIcons();
}

async function openSentinelModal(appId = null) {
    const targetApp = appId || state.selectedApp || '';
    if (els.sentinelModalOverlay) els.sentinelModalOverlay.classList.add('ui-active');
    if (els.sentinelModalBadge) els.sentinelModalBadge.textContent = 'Checking...';
    try {
        const queryApp = targetApp ? `app=${encodeURIComponent(targetApp)}&` : '';
        const queryFlavor = `flavor=${encodeURIComponent(state.selectedEnv || 'prod')}`;
        const res = await fetch(api(`/api/deployment/sentinel?${queryApp}${queryFlavor}`));
        const data = await res.json();
        renderSentinelModalData(data);
    } catch (err) {
        showToast('Failed to check Sentinel: ' + err.message, 'error');
    }
}

function closeSentinelModal() {
    if (els.sentinelModalOverlay) els.sentinelModalOverlay.classList.remove('ui-active');
}

if (els.sentinelHeaderBadge) {
    els.sentinelHeaderBadge.addEventListener('click', () => openSentinelModal(state.selectedApp));
}
if (els.sentinelAlertBanner) {
    els.sentinelAlertBanner.addEventListener('click', () => openSentinelModal(state.selectedApp));
}
if (els.closeSentinelModalBtn) {
    els.closeSentinelModalBtn.addEventListener('click', closeSentinelModal);
}
if (els.closeSentinelBtn) {
    els.closeSentinelBtn.addEventListener('click', closeSentinelModal);
}
if (els.recheckSentinelBtn) {
    els.recheckSentinelBtn.addEventListener('click', () => {
        openSentinelModal(state.selectedApp);
        loadWorkspaceSentinel();
        loadAppSentinel(state.selectedApp);
    });
}
if (els.sentinelModalOverlay) {
    els.sentinelModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.sentinelModalOverlay) closeSentinelModal();
    });
}


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
    await loadWorkspaceSentinel();
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

// ═══════════════════════════ Local APK & QR Code ═══════════════════════════

let currentApkInfo = null;

function writeTerminalBox(content, title = '') {
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

            // 1. Update banner in UI
            if (els.apkInstallBanner) {
                if (els.apkBannerFilename) els.apkBannerFilename.textContent = data.filename;
                if (els.apkBannerSize) els.apkBannerSize.textContent = data.sizeFormatted;
                if (els.bannerDownloadBtn) {
                    els.bannerDownloadBtn.href = data.localUrl || data.downloadUrl;
                    els.bannerDownloadBtn.setAttribute('download', data.filename);
                }
                els.apkInstallBanner.classList.remove('hidden');
                refreshIcons();
            }

            // 2. Write info and ASCII QR code to terminal
            writeTerminal(`📲 Android APK ready: ${data.filename} (${data.sizeFormatted})`, 'success');
            writeTerminal(`📥 Wi-Fi Download Link: ${data.downloadUrl}`);
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
    refreshIcons();
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

window.openQrModalForTarget = openQrModalForTarget;

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

// ═══════════════════════════ Build Size Inspector & Diff ═══════════════════════════

let currentBuildSizeInfo = null;

async function checkAndDisplayBuildSize(jobId, app = '', flavor = '') {
    if (!els.buildSizeBanner) return;
    try {
        const res = await fetch(api(`/api/deployment/build-size?jobId=${encodeURIComponent(jobId || '')}&app=${encodeURIComponent(app || '')}&flavor=${encodeURIComponent(flavor || '')}`));
        const data = await res.json();
        if (data.success && data.buildSize) {
            currentBuildSizeInfo = data.buildSize;
            renderBuildSizeBanner(data.buildSize);
        } else {
            els.buildSizeBanner.style.display = 'none';
            els.buildSizeBanner.classList.add('hidden');
        }
    } catch (err) {
        console.warn('Could not inspect build size:', err);
    }
}

function renderBuildSizeBanner(bs) {
    if (!els.buildSizeBanner || !bs) return;
    const severity = bs.severity || 'ok';
    els.buildSizeBanner.dataset.status = severity === 'critical' ? 'error' : (severity === 'warning' ? 'warning' : 'ok');
    if (els.buildSizeSummaryText) {
        els.buildSizeSummaryText.textContent = `Build Size: ${bs.summary || (bs.artifactType + ': ' + bs.currentSizeFormatted)}`;
    }
    if (els.buildSizeSubtext) {
        const alertNote = (bs.warnings && bs.warnings.length > 0) ? bs.warnings[0] : (bs.hasBaseline ? `Compared to previous build (${bs.previousBuild?.sizeFormatted || ''})` : 'First recorded baseline for this app');
        els.buildSizeSubtext.textContent = alertNote;
    }
    if (els.buildSizeBadge) {
        els.buildSizeBadge.setAttribute('data-variant', bs.badgeVariant || 'secondary');
        els.buildSizeBadge.textContent = severity === 'critical' ? '🚨 Inspect Bloat' : (severity === 'warning' ? '⚠️ Inspect Diff' : 'Inspect Size & Diff →');
    }
    els.buildSizeBanner.style.display = 'block';
    els.buildSizeBanner.classList.remove('hidden');
}

function openBuildSizeModal(bs = null) {
    const info = bs || currentBuildSizeInfo;
    if (!info || !els.buildSizeModalOverlay) return;

    if (els.buildSizeModalBadge) {
        els.buildSizeModalBadge.setAttribute('data-variant', info.badgeVariant || 'secondary');
        els.buildSizeModalBadge.textContent = (info.severity || 'ok').toUpperCase();
    }
    if (els.buildSizeModalSubtitle) {
        els.buildSizeModalSubtitle.textContent = `${info.artifactType || 'Artifact'} · ${info.currentFilename || ''}`;
    }

    if (els.bsStatCurrentSize) els.bsStatCurrentSize.textContent = info.currentSizeFormatted || '-';
    if (els.bsStatCurrentType) els.bsStatCurrentType.textContent = info.artifactType || '-';
    if (els.bsStatPreviousSize) els.bsStatPreviousSize.textContent = info.previousBuild ? info.previousBuild.sizeFormatted : 'None';
    if (els.bsStatPreviousMeta) els.bsStatPreviousMeta.textContent = info.previousBuild ? (info.previousBuild.jobId ? `Job #${info.previousBuild.jobId}` : 'Previous run') : 'First baseline';
    if (els.bsStatDelta) els.bsStatDelta.textContent = info.hasBaseline ? info.deltaFormatted : '0 B';
    if (els.bsStatPercent) {
        els.bsStatPercent.textContent = info.hasBaseline ? info.deltaPercentFormatted : 'Baseline';
        if (info.deltaBytes > 0) {
            els.bsStatPercent.style.color = info.severity === 'critical' ? 'var(--ui-danger, #ef4444)' : (info.severity === 'warning' ? 'var(--ui-warning, #f59e0b)' : 'var(--ui-text-muted)');
        } else if (info.deltaBytes < 0) {
            els.bsStatPercent.style.color = 'var(--ui-success, #22c55e)';
        } else {
            els.bsStatPercent.style.color = 'var(--ui-text-muted)';
        }
    }
    if (els.bsStatCompression) {
        els.bsStatCompression.textContent = (info.inspection && info.inspection.compressionRatio != null) ? `${info.inspection.compressionRatio}%` : '—';
    }
    if (els.bsStatUncompressed) {
        els.bsStatUncompressed.textContent = (info.inspection && info.inspection.totalUncompressedFormatted) ? `${info.inspection.totalUncompressedFormatted} uncompressed` : '—';
    }

    // Warnings and Bloat alerts
    if (els.buildSizeWarningsContainer) {
        const warnings = info.warnings || [];
        const uncompressed = info.inspection?.uncompressedAssets || [];
        if (warnings.length === 0 && uncompressed.length === 0) {
            els.buildSizeWarningsContainer.innerHTML = `
                <div class="ui-card" style="padding:10px 14px; background: rgba(34, 197, 94, 0.08); border-left: 4px solid var(--ui-success, #22c55e); font-size:0.82rem; color:var(--ui-success, #22c55e); display:flex; align-items:center; gap:8px;">
                    <i data-lucide="check-circle" style="width:16px;height:16px;"></i>
                    <span>No size bloat or uncompressed asset warnings detected.</span>
                </div>
            `;
        } else {
            let warnHtml = '';
            warnings.forEach(w => {
                const isCrit = info.severity === 'critical';
                const borderCol = isCrit ? 'var(--ui-danger, #ef4444)' : 'var(--ui-warning, #f59e0b)';
                const bgCol = isCrit ? 'rgba(239, 68, 68, 0.08)' : 'rgba(245, 158, 11, 0.08)';
                warnHtml += `
                    <div class="ui-card" style="padding:10px 14px; background:${bgCol}; border-left: 4px solid ${borderCol}; font-size:0.82rem; display:flex; align-items:center; gap:8px;">
                        <span style="font-size:1.1rem; line-height:1;">${isCrit ? '🚨' : '⚠️'}</span>
                        <div><strong>${escapeHtml(w)}</strong></div>
                    </div>
                `;
            });
            if (uncompressed.length > 0) {
                const filesList = uncompressed.map(u => `<li><code>${escapeHtml(u.name)}</code> (${escapeHtml(u.sizeFormatted)}) - <em>uncompressed (STORED)</em></li>`).join('');
                warnHtml += `
                    <div class="ui-card" style="padding:10px 14px; background: rgba(245, 158, 11, 0.08); border-left: 4px solid var(--ui-warning, #f59e0b); font-size:0.82rem;">
                        <div style="font-weight:600; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                            <span>⚠️ Huge Uncompressed Asset Bloat Detected</span>
                        </div>
                        <div style="opacity:0.9; margin-bottom:6px;">These files were packaged with zero compression (stored raw) inside the archive:</div>
                        <ul style="margin:0; padding-left:18px;">${filesList}</ul>
                    </div>
                `;
            }
            els.buildSizeWarningsContainer.innerHTML = warnHtml;
        }
    }

    renderBuildSizeDiffTable(info.diff);
    renderBuildSizeLargestTable(info.inspection?.largestFiles || []);

    if (els.bsModalFooterPath) {
        els.bsModalFooterPath.textContent = info.currentArtifactPath || '-';
        els.bsModalFooterPath.title = info.currentArtifactPath || '';
    }

    switchBuildSizeTab('diff');
    els.buildSizeModalOverlay.classList.add('ui-active');
    refreshIcons();
}

function renderBuildSizeDiffTable(diff) {
    if (!els.bsDiffTableContainer) return;
    if (!diff || !diff.hasDiff || (!diff.addedAssets.length && !diff.removedAssets.length && !diff.grownAssets.length)) {
        els.bsDiffTableContainer.innerHTML = `
            <div style="padding: 24px; text-align: center; color: var(--ui-muted, #9aa6b8); font-size: 0.85rem;">
                No file-level archive diff available (either this is the first baseline build, or previous build artifact was removed from disk).
            </div>
        `;
        return;
    }

    let rowsHtml = '';

    (diff.grownAssets || []).forEach(item => {
        const isGrowth = item.deltaBytes > 0;
        const badgeVar = isGrowth ? 'warning' : 'success';
        const sign = isGrowth ? '+' : '';
        rowsHtml += `
            <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.8rem;">
                <td style="padding: 8px 12px; font-family: monospace; word-break: break-all;">${escapeHtml(item.name)}</td>
                <td style="padding: 8px 12px;"><span class="ui-badge" data-variant="${badgeVar}">${isGrowth ? 'MODIFIED (+)' : 'SHRUNK (-)'}</span></td>
                <td style="padding: 8px 12px; font-family: monospace;">${escapeHtml(item.currSizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; color: var(--ui-muted, #9aa6b8);">${escapeHtml(item.prevSizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; font-weight: 600; color: ${isGrowth ? 'var(--ui-warning, #f59e0b)' : 'var(--ui-success, #22c55e)'};">${sign}${escapeHtml(item.deltaFormatted)}</td>
            </tr>
        `;
    });

    (diff.addedAssets || []).forEach(item => {
        rowsHtml += `
            <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.8rem;">
                <td style="padding: 8px 12px; font-family: monospace; word-break: break-all;">${escapeHtml(item.name)}</td>
                <td style="padding: 8px 12px;"><span class="ui-badge" data-variant="info">NEW ASSET</span></td>
                <td style="padding: 8px 12px; font-family: monospace;">${escapeHtml(item.sizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; color: var(--ui-muted, #9aa6b8);">—</td>
                <td style="padding: 8px 12px; font-family: monospace; font-weight: 600; color: var(--ui-info, #0ea5e9);">+${escapeHtml(item.sizeFormatted)}</td>
            </tr>
        `;
    });

    (diff.removedAssets || []).forEach(item => {
        rowsHtml += `
            <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.8rem;">
                <td style="padding: 8px 12px; font-family: monospace; word-break: break-all; opacity: 0.7;">${escapeHtml(item.name)}</td>
                <td style="padding: 8px 12px;"><span class="ui-badge" data-variant="secondary">REMOVED</span></td>
                <td style="padding: 8px 12px; font-family: monospace; opacity: 0.7;">—</td>
                <td style="padding: 8px 12px; font-family: monospace; color: var(--ui-muted, #9aa6b8);">${escapeHtml(item.sizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; font-weight: 600; color: var(--ui-success, #22c55e); italic;">-${escapeHtml(item.sizeFormatted)}</td>
            </tr>
        `;
    });

    els.bsDiffTableContainer.innerHTML = `
        <div style="max-height: 280px; overflow-y: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.72rem; text-transform: uppercase; color: var(--ui-muted, #9aa6b8);">
                        <th style="padding: 8px 12px;">Asset / File Path</th>
                        <th style="padding: 8px 12px; width: 110px;">Status</th>
                        <th style="padding: 8px 12px; width: 90px;">Current</th>
                        <th style="padding: 8px 12px; width: 90px;">Previous</th>
                        <th style="padding: 8px 12px; width: 90px;">Delta</th>
                    </tr>
                </thead>
                <tbody>${rowsHtml}</tbody>
            </table>
        </div>
    `;
}

function renderBuildSizeLargestTable(files) {
    if (!els.bsLargestTableContainer) return;
    if (!files || files.length === 0) {
        els.bsLargestTableContainer.innerHTML = `
            <div style="padding: 24px; text-align: center; color: var(--ui-muted, #9aa6b8); font-size: 0.85rem;">
                No archive asset details available.
            </div>
        `;
        return;
    }

    let rowsHtml = '';
    files.forEach((f, idx) => {
        const isStored = f.compressType === 'stored';
        const methodBadge = isStored ? '<span class="ui-badge" data-variant="warning">STORED (0%)</span>' : '<span class="ui-badge" data-variant="secondary">Deflated</span>';
        rowsHtml += `
            <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.8rem;">
                <td style="padding: 8px 12px; color: var(--ui-muted, #9aa6b8); width: 30px;">#${idx + 1}</td>
                <td style="padding: 8px 12px; font-family: monospace; word-break: break-all;">${escapeHtml(f.name)}</td>
                <td style="padding: 8px 12px; font-family: monospace; font-weight: 600;">${escapeHtml(f.compressedSizeFormatted)}</td>
                <td style="padding: 8px 12px; font-family: monospace; color: var(--ui-muted, #9aa6b8);">${escapeHtml(f.uncompressedSizeFormatted)}</td>
                <td style="padding: 8px 12px;">${methodBadge}</td>
            </tr>
        `;
    });

    els.bsLargestTableContainer.innerHTML = `
        <div style="max-height: 280px; overflow-y: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--ui-border-color); font-size: 0.72rem; text-transform: uppercase; color: var(--ui-muted, #9aa6b8);">
                        <th style="padding: 8px 12px; width: 30px;">#</th>
                        <th style="padding: 8px 12px;">File Inside Archive</th>
                        <th style="padding: 8px 12px; width: 110px;">Compressed</th>
                        <th style="padding: 8px 12px; width: 110px;">Uncompressed</th>
                        <th style="padding: 8px 12px; width: 110px;">Storage</th>
                    </tr>
                </thead>
                <tbody>${rowsHtml}</tbody>
            </table>
        </div>
    `;
}

function switchBuildSizeTab(tab) {
    if (tab === 'diff') {
        if (els.bsTabDiffBtn) els.bsTabDiffBtn.setAttribute('data-variant', 'primary');
        if (els.bsTabLargestBtn) els.bsTabLargestBtn.setAttribute('data-variant', 'secondary');
        if (els.bsDiffTableView) els.bsDiffTableView.style.display = 'block';
        if (els.bsLargestTableView) els.bsLargestTableView.style.display = 'none';
    } else {
        if (els.bsTabDiffBtn) els.bsTabDiffBtn.setAttribute('data-variant', 'secondary');
        if (els.bsTabLargestBtn) els.bsTabLargestBtn.setAttribute('data-variant', 'primary');
        if (els.bsDiffTableView) els.bsDiffTableView.style.display = 'none';
        if (els.bsLargestTableView) els.bsLargestTableView.style.display = 'block';
    }
}

function closeBuildSizeModal() {
    if (els.buildSizeModalOverlay) {
        els.buildSizeModalOverlay.classList.remove('ui-active');
    }
}

async function openBuildSizeModalForTarget(targetId, app = '', flavor = '') {
    try {
        const res = await fetch(api(`/api/deployment/build-size?jobId=${encodeURIComponent(targetId || '')}&app=${encodeURIComponent(app || '')}&flavor=${encodeURIComponent(flavor || '')}`));
        const data = await res.json();
        if (data.success && data.buildSize) {
            currentBuildSizeInfo = data.buildSize;
            openBuildSizeModal(data.buildSize);
        } else {
            showToast(data.error || data.message || 'No build size data found for this run', 'error');
        }
    } catch (err) {
        showToast('Failed to load build size details', 'error');
    }
}

window.openBuildSizeModalForTarget = openBuildSizeModalForTarget;

if (els.buildSizeBanner) {
    els.buildSizeBanner.addEventListener('click', () => openBuildSizeModal());
}
if (els.closeBuildSizeModalBtn) {
    els.closeBuildSizeModalBtn.addEventListener('click', closeBuildSizeModal);
}
if (els.closeBuildSizeBtn) {
    els.closeBuildSizeBtn.addEventListener('click', closeBuildSizeModal);
}
if (els.buildSizeModalOverlay) {
    els.buildSizeModalOverlay.addEventListener('click', (e) => {
        if (e.target === els.buildSizeModalOverlay) closeBuildSizeModal();
    });
}
if (els.bsTabDiffBtn) {
    els.bsTabDiffBtn.addEventListener('click', () => switchBuildSizeTab('diff'));
}
if (els.bsTabLargestBtn) {
    els.bsTabLargestBtn.addEventListener('click', () => switchBuildSizeTab('largest'));
}

(async () => {
    await loadWorkspaceInfo();
    await loadApps();
    await loadWorkspaceSentinel();
})().catch(error => {
    els.appGrid.innerHTML = `<div class="empty-state">Failed to load apps: ${escapeHtml(error.message)}</div>`;
});
refreshIcons();

