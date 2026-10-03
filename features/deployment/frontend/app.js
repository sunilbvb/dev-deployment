
// Keep in sync with router.py's STORE_UPLOAD_TEMPLATE_IDS - the template ids whose
// success means a build actually reached TestFlight/Play Store, not just a local
// artifact or a git tag/push.
const STORE_SHIPPING_TEMPLATE_IDS = new Set(['deploy_ipa', 'upload_ipa', 'deploy_aab', 'upload_aab', 'deploy_both']);


const state = window.state = {
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
    isServerOnline: null,
    isDemoMode: false,
    activeDocId: 'overview',
    cachedDocs: {},
};

const els = window.els = {
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
    // iOS OTA IPA Elements
    ipaInstallBanner: document.getElementById('ipaInstallBanner'),
    ipaBannerFilename: document.getElementById('ipaBannerFilename'),
    ipaBannerSize: document.getElementById('ipaBannerSize'),
    openIpaQrModalBtn: document.getElementById('openIpaQrModalBtn'),
    bannerIpaDownloadBtn: document.getElementById('bannerIpaDownloadBtn'),
    ipaQrModalOverlay: document.getElementById('ipaQrModalOverlay'),
    closeIpaQrModalBtn: document.getElementById('closeIpaQrModalBtn'),
    ipaQrCodeContainer: document.getElementById('ipaQrCodeContainer'),
    qrIpaSize: document.getElementById('qrIpaSize'),
    qrIpaFilename: document.getElementById('qrIpaFilename'),
    qrIpaBundleId: document.getElementById('qrIpaBundleId'),
    qrIpaUrlInput: document.getElementById('qrIpaUrlInput'),
    copyIpaQrUrlBtn: document.getElementById('copyIpaQrUrlBtn'),
    directDownloadIpaBtn: document.getElementById('directDownloadIpaBtn'),
    // Wireless ADB Elements
    adbPushBtn: document.getElementById('adbPushBtn'),
    adbModalOverlay: document.getElementById('adbModalOverlay'),
    closeAdbModalBtn: document.getElementById('closeAdbModalBtn'),
    adbConnectAddressInput: document.getElementById('adbConnectAddressInput'),
    adbConnectBtn: document.getElementById('adbConnectBtn'),
    adbDeviceCount: document.getElementById('adbDeviceCount'),
    adbRefreshDevicesBtn: document.getElementById('adbRefreshDevicesBtn'),
    adbDeviceListContainer: document.getElementById('adbDeviceListContainer'),
    adbInstallResults: document.getElementById('adbInstallResults'),
    adbModalApkInfo: document.getElementById('adbModalApkInfo'),
    adbInstallSubmitBtn: document.getElementById('adbInstallSubmitBtn'),
    // Build Time Profiler Elements
    buildProfilerBanner: document.getElementById('buildProfilerBanner'),
    buildProfilerSummaryText: document.getElementById('buildProfilerSummaryText'),
    buildProfilerSubtext: document.getElementById('buildProfilerSubtext'),
    buildProfilerBadge: document.getElementById('buildProfilerBadge'),
    buildProfilerModalOverlay: document.getElementById('buildProfilerModalOverlay'),
    closeBuildProfilerModalBtn: document.getElementById('closeBuildProfilerModalBtn'),
    closeBuildProfilerBtn: document.getElementById('closeBuildProfilerBtn'),
    bpTotalDurationText: document.getElementById('bpTotalDurationText'),
    bpSummaryText: document.getElementById('bpSummaryText'),
    bpProgressBar: document.getElementById('bpProgressBar'),
    bpBottlenecksContainer: document.getElementById('bpBottlenecksContainer'),
    bpTableBody: document.getElementById('bpTableBody'),
    bpFooterJobInfo: document.getElementById('bpFooterJobInfo'),
    // Cache Warmer Elements
    cacheWarmerHeaderBadge: document.getElementById('cacheWarmerHeaderBadge'),
    cacheWarmerBadgeText: document.getElementById('cacheWarmerBadgeText'),
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
    // Documentation Hub & Server Status Elements
    serverStatusBadge: document.getElementById('serverStatusBadge'),
    serverStatusDot: document.getElementById('serverStatusDot'),
    serverStatusText: document.getElementById('serverStatusText'),
    openDocsBtn: document.getElementById('openDocsBtn'),
    serverOfflineBanner: document.getElementById('serverOfflineBanner'),
    copyStartCommandBtn: document.getElementById('copyStartCommandBtn'),
    startDemoModeBtn: document.getElementById('startDemoModeBtn'),
    bannerOpenDocsBtn: document.getElementById('bannerOpenDocsBtn'),
    demoModeBanner: document.getElementById('demoModeBanner'),
    exitDemoModeBtn: document.getElementById('exitDemoModeBtn'),
    docsModalOverlay: document.getElementById('docsModalOverlay'),
    closeDocsModalBtn: document.getElementById('closeDocsModalBtn'),
    closeDocsBtn: document.getElementById('closeDocsBtn'),
    docsCurrentCategory: document.getElementById('docsCurrentCategory'),
    docsCurrentTitle: document.getElementById('docsCurrentTitle'),
    docsCurrentFilename: document.getElementById('docsCurrentFilename'),
    docsContentArea: document.getElementById('docsContentArea'),
    docsFooterPath: document.getElementById('docsFooterPath'),
    serverConsoleModalOverlay: document.getElementById('serverConsoleModalOverlay'),
    closeServerConsoleModalBtn: document.getElementById('closeServerConsoleModalBtn'),
    closeServerConsoleBtn: document.getElementById('closeServerConsoleBtn'),
    serverModalStatusTitle: document.getElementById('serverModalStatusTitle'),
    serverModalStatusBadge: document.getElementById('serverModalStatusBadge'),
    serverModalUrl: document.getElementById('serverModalUrl'),
    serverModalPort: document.getElementById('serverModalPort'),
    serverModalPid: document.getElementById('serverModalPid'),
    serverModalPython: document.getElementById('serverModalPython'),
    serverModalUptimeRow: document.getElementById('serverModalUptimeRow'),
    serverModalUptime: document.getElementById('serverModalUptime'),
    copyServerSnippetBtn: document.getElementById('copyServerSnippetBtn'),
    testServerReconnectBtn: document.getElementById('testServerReconnectBtn'),
    serverStartBtn: document.getElementById('serverStartBtn'),
    serverRestartBtn: document.getElementById('serverRestartBtn'),
    serverStopBtn: document.getElementById('serverStopBtn'),
    serverEndBtn: document.getElementById('serverEndBtn'),
    serverInstallDesktopBtn: document.getElementById('serverInstallDesktopBtn'),
    serverInstallServiceBtn: document.getElementById('serverInstallServiceBtn'),
    launcherStatusMsg: document.getElementById('launcherStatusMsg'),
    cfgServerStatusBadge: document.getElementById('cfgServerStatusBadge'),
    cfgServerStatusText: document.getElementById('cfgServerStatusText'),
    cfgServerPortText: document.getElementById('cfgServerPortText'),
    cfgServerPidText: document.getElementById('cfgServerPidText'),
    cfgServerUptimeText: document.getElementById('cfgServerUptimeText'),
    cfgServerStartBtn: document.getElementById('cfgServerStartBtn'),
    cfgServerRestartBtn: document.getElementById('cfgServerRestartBtn'),
    cfgServerStopBtn: document.getElementById('cfgServerStopBtn'),
    cfgServerEndBtn: document.getElementById('cfgServerEndBtn'),
    cfgServerInstallDesktopBtn: document.getElementById('cfgServerInstallDesktopBtn'),
    cfgServerInstallServiceBtn: document.getElementById('cfgServerInstallServiceBtn'),
    cfgLauncherStatusMsg: document.getElementById('cfgLauncherStatusMsg'),
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
    if (state.isDemoMode) {
        setupDemoCommands(appId);
        return;
    }
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

    const runnerSelectRow = document.getElementById('runnerSelectRow');
    if (state.selectedPipeline) {
        if (runnerSelectRow) runnerSelectRow.style.display = 'none';
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
    const canUseCloudRunner = state.selectedCommand.platform === 'android' ||
        ['build_aab', 'build_apk', 'deploy_aab', 'upload_aab'].includes(state.selectedCommand.templateId);

    if (runnerSelectRow) {
        runnerSelectRow.style.display = canUseCloudRunner ? '' : 'none';
    }

    const isCloudRunner = canUseCloudRunner && state.selectedRunner === 'github_actions';
    const runner = isCloudRunner ? 'github_actions' : (state.selectedCommand.runner || 'make');
    const isLocked = state.selectedCommand.configured === false;
    els.executionPanel.classList.remove('hidden');
    els.selectedCommandTitle.textContent = (state.selectedCommand.name || prettyCommandTitle(command)) + (isCloudRunner ? ' [☁️ GitHub Actions]' : '');

    if (isCloudRunner) {
        const buildType = (state.selectedCommand.templateId || '').includes('aab') ? 'aab' : 'apk';
        const flv = state.selectedCommand.flavor || selectedEnvForExecution() || 'prod';
        els.selectedCommandPreview.textContent = `github-actions dispatch deploy-android.yml --flavor ${flv} --build-type ${buildType}\n# Cloud runner: Ubuntu Linux (runs in parallel with local iOS builds)`;
    } else if (runner === 'custom') {
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
    const canUseCloudRunner = state.selectedCommand.platform === 'android' ||
        ['build_aab', 'build_apk', 'deploy_aab', 'upload_aab'].includes(state.selectedCommand.templateId);
    const isCloudRunner = canUseCloudRunner && state.selectedRunner === 'github_actions';
    const runner = isCloudRunner ? 'github_actions' : (state.selectedCommand.runner || 'make');
    const env = selectedEnvForExecution();

    state.activeJobId = null;
    state.stdoutLength = 0;
    if (els.apkInstallBanner) els.apkInstallBanner.classList.add('hidden');
    if (els.ipaInstallBanner) els.ipaInstallBanner.classList.add('hidden');
    if (els.buildSizeBanner) {
        els.buildSizeBanner.classList.add('hidden');
        els.buildSizeBanner.style.display = 'none';
    }
    if (els.buildProfilerBanner) {
        els.buildProfilerBanner.classList.add('hidden');
        els.buildProfilerBanner.style.display = 'none';
    }
    els.runButton.disabled = true;
    els.stopJobBtn.disabled = true;
    startTimer();
    writeTerminal(`Executing: ${els.selectedCommandPreview.textContent}`);

    if (state.isDemoMode) {
        runSimulatedDemoExecution(els.selectedCommandPreview.textContent);
        return;
    }

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
            checkAndDisplayIpa(jobId, job.app, job.flavor || job.env);
            checkAndDisplayBuildSize(jobId, job.app, job.flavor || job.env);
            checkAndDisplayBuildProfile(jobId);
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
            if (typeof checkAndDisplayIpa === 'function') checkAndDisplayIpa(run.currentJobId || '', run.app, run.flavor);
            checkAndDisplayBuildSize(run.currentJobId || '', run.app, run.flavor);
            if (typeof checkAndDisplayBuildProfile === 'function') checkAndDisplayBuildProfile(run.currentJobId || '');
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

const runnerTabs = document.getElementById('runnerTabs');
if (runnerTabs) {
    runnerTabs.addEventListener('click', (e) => {
        const btn = e.target.closest('.ui-segment');
        if (!btn || !btn.dataset.runner) return;
        runnerTabs.querySelectorAll('.ui-segment').forEach(s => s.classList.toggle('active', s === btn));
        state.selectedRunner = btn.dataset.runner;
        updateExecutionPanel();
    });
}

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


// ═══════════════════════════ Application Initialization ═══════════════════════════

window.addEventListener('DOMContentLoaded', async () => {
    const isOnline = typeof checkServerStatus === 'function' ? await checkServerStatus(true) : false;
    if (isOnline) {
        try {
            if (typeof loadWorkspaceInfo === 'function') await loadWorkspaceInfo();
            if (typeof loadApps === 'function') await loadApps();
            if (typeof loadWorkspaceSentinel === 'function') await loadWorkspaceSentinel();
        } catch (err) {
            console.warn('Initial project load error:', err);
        }
    } else {
        if (els.appGrid && !state.isDemoMode) {
            els.appGrid.innerHTML = `
                <div class="empty-state" style="padding: 24px 16px; text-align: center;">
                    <div style="font-size: 1.6rem; margin-bottom: 8px;">🖥️</div>
                    <div style="font-weight: 700; font-size: 0.92rem; margin-bottom: 4px;">Server Not Connected</div>
                    <p style="font-size: 0.78rem; color: var(--ui-text-muted); margin-bottom: 14px; line-height: 1.4;">
                        Start backend via <code>./start.sh</code> or explore interactive demo mode.
                    </p>
                    <div style="display: flex; gap: 8px; justify-content: center;">
                        <button type="button" class="ui-button" data-variant="primary" data-size="xs" onclick="startDemoMode()">
                            <span>Launch Demo</span>
                        </button>
                        <button type="button" class="ui-button" data-variant="secondary" data-size="xs" onclick="openDocsModal('overview')">
                            <span>Open Docs</span>
                        </button>
                    </div>
                </div>
            `;
        }
    }
    if (typeof startServerHeartbeat === 'function') startServerHeartbeat();
    if (typeof refreshIcons === 'function') refreshIcons();
});
