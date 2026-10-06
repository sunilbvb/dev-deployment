/**
 * app_workspace.js — App Workspace & Multi-Project Module
 * Manages project switching, tab segmented controls, workspace imports,
 * folder inspection, and authorized project roots.
 */

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

async function selectProject(path) {
    if (!path || path === state.activeWorkspace) return;
    try { sessionStorage.setItem('active_workspace', path); } catch (_) {}
    state.activeWorkspace = path;
    state.selectedApp = null;
    renderActiveProject();
    if (typeof loadApps === 'function') await loadApps();
    if (typeof loadWorkspaceSentinel === 'function') await loadWorkspaceSentinel();
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

        if (data.workspaceMissing) {
            showToast(`⚠️ Configured workspace path "${data.workspaceMissing}" was not found on disk.`);
            let missingBanner = document.getElementById('workspaceMissingBanner');
            if (!missingBanner) {
                missingBanner = document.createElement('div');
                missingBanner.id = 'workspaceMissingBanner';
                missingBanner.className = 'ui-alert cert-status-box';
                missingBanner.dataset.variant = 'warning';
                missingBanner.dataset.status = 'warning';
                missingBanner.style.cssText = 'margin: 0 0 16px 0; font-size: 0.82rem;';
                (document.querySelector('.deployment-shell') || document.querySelector('.ui-page-shell') || document.body)?.prepend(missingBanner);
            }
            missingBanner.textContent = `⚠️ Workspace folder "${data.workspaceMissing}" was not found on disk. Dashboard fell back to "${data.active}". Please select a valid project folder.`;
            missingBanner.style.display = 'block';
        } else {
            const missingBanner = document.getElementById('workspaceMissingBanner');
            if (missingBanner) missingBanner.style.display = 'none';
        }

        currentWorkspacesList = data.workspaces || [];
        let stored = '';
        try { stored = sessionStorage.getItem('active_workspace') || ''; } catch (_) {}
        const known = currentWorkspacesList.some(w => w.path === stored);
        state.activeWorkspace = known ? stored : data.active;
        if (!known) {
            try { sessionStorage.setItem('active_workspace', state.activeWorkspace); } catch (_) {}
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

async function pickNativeFolder(prompt = 'Choose your project folder') {
    if (typeof window.pickNativePath === 'function') {
        try {
            return await window.pickNativePath({ kind: 'folder', prompt });
        } catch (_) {}
    }
    try {
        const pickUrl = typeof api === 'function' ? api('/api/deployment/pick') : '/api/deployment/pick';
        const res = await fetch(pickUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kind: 'folder', prompt }),
        }).then(r => r.json());
        if (res && res.success) return { path: res.path };
        return {
            path: null,
            unsupported: res ? res.supported === false : true,
            error: res && res.cancelled ? '' : ((res && res.error) || ''),
        };
    } catch (err) {
        return { path: null, unsupported: true, error: err.message || 'Picker service error' };
    }
}

function resetImportDialog() {
    importCandidate = null;
    if (wsModalEls.result) wsModalEls.result.classList.add('hidden');
    if (wsModalEls.error) wsModalEls.error.classList.add('hidden');
    if (wsModalEls.manual) wsModalEls.manual.hidden = false;
    if (wsModalEls.pathInput) wsModalEls.pathInput.value = '';
    if (wsModalEls.confirmBtn) wsModalEls.confirmBtn.disabled = true;
}

function openWorkspaceModal() {
    resetImportDialog();
    if (wsModalEls.overlay) wsModalEls.overlay.classList.add('ui-active');
    if (typeof refreshIcons === 'function') refreshIcons();
}

function closeWorkspaceModal() {
    if (wsModalEls.overlay) wsModalEls.overlay.classList.remove('ui-active');
}

function renderChips(container, items) {
    if (!container) return;
    container.innerHTML = items
        .map(item => `<span class="ui-badge" data-variant="secondary" title="${escapeHtml(item.path || '')}">${escapeHtml(item.name || item.id)}</span>`)
        .join('');
}

function showImportError(message) {
    importCandidate = null;
    if (wsModalEls.confirmBtn) wsModalEls.confirmBtn.disabled = true;
    if (wsModalEls.result) wsModalEls.result.classList.add('hidden');
    if (wsModalEls.error) {
        wsModalEls.error.textContent = message;
        wsModalEls.error.classList.remove('hidden');
    }
}

async function inspectImportFolder(pathStr) {
    if (!pathStr) return;
    if (wsModalEls.error) wsModalEls.error.classList.add('hidden');
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
    if (wsModalEls.name) wsModalEls.name.textContent = data.name;
    if (wsModalEls.layout) wsModalEls.layout.textContent = data.layout || '';
    if (wsModalEls.path) wsModalEls.path.textContent = data.path;
    if (wsModalEls.appsLabel) wsModalEls.appsLabel.textContent = `${apps.length} app${apps.length === 1 ? '' : 's'}`;
    renderChips(wsModalEls.apps, apps);
    if (wsModalEls.packagesGroup) wsModalEls.packagesGroup.hidden = packages.length === 0;
    if (wsModalEls.packagesLabel) wsModalEls.packagesLabel.textContent = `${packages.length} package${packages.length === 1 ? '' : 's'}`;
    renderChips(wsModalEls.packages, packages);
    if (wsModalEls.result) wsModalEls.result.classList.remove('hidden');
    const alreadyAdded = currentWorkspacesList.some(w => w.path === data.path);
    if (wsModalEls.confirmBtn) {
        wsModalEls.confirmBtn.querySelector('span').textContent = alreadyAdded ? 'Already added — open it' : 'Add project';
        wsModalEls.confirmBtn.disabled = false;
    }
}

// Wire Workspace Events
if (wsModalEls.openBtn) wsModalEls.openBtn.addEventListener('click', openWorkspaceModal);
if (wsModalEls.closeBtn) wsModalEls.closeBtn.addEventListener('click', closeWorkspaceModal);
if (wsModalEls.cancelBtn) wsModalEls.cancelBtn.addEventListener('click', closeWorkspaceModal);
if (wsModalEls.overlay) {
    wsModalEls.overlay.addEventListener('click', e => {
        if (e.target === wsModalEls.overlay) closeWorkspaceModal();
    });
}

if (wsModalEls.browseBtn) {
    wsModalEls.browseBtn.addEventListener('click', async () => {
        const originalText = wsModalEls.browseBtn.innerHTML;
        wsModalEls.browseBtn.disabled = true;
        wsModalEls.browseBtn.innerHTML = '<span class="loading-spinner-inline" style="width:14px;height:14px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;display:inline-block;animation:spin 1s linear infinite;"></span><span>Opening folder dialog…</span>';
        try {
            if (wsModalEls.error) wsModalEls.error.classList.add('hidden');
            const picked = await pickNativeFolder('Choose your project folder');
            if (picked.path) {
                if (wsModalEls.pathInput) wsModalEls.pathInput.value = picked.path;
                inspectImportFolder(picked.path);
            } else if (picked.unsupported) {
                if (wsModalEls.manual) wsModalEls.manual.hidden = false;
                if (wsModalEls.pathInput) wsModalEls.pathInput.focus();
                showImportError('No native desktop folder dialog detected. Enter folder path manually below.');
            } else if (picked.error) {
                showImportError(picked.error);
                if (wsModalEls.manual) wsModalEls.manual.hidden = false;
            } else {
                if (wsModalEls.manual) wsModalEls.manual.hidden = false;
            }
        } catch (err) {
            showImportError(err.message || 'Could not open folder picker.');
            if (wsModalEls.manual) wsModalEls.manual.hidden = false;
        } finally {
            wsModalEls.browseBtn.disabled = false;
            wsModalEls.browseBtn.innerHTML = originalText;
            if (typeof refreshIcons === 'function') refreshIcons();
        }
    });
}

let inspectDebounceTimer = null;
if (wsModalEls.pathInput) {
    wsModalEls.pathInput.addEventListener('input', () => {
        clearTimeout(inspectDebounceTimer);
        inspectDebounceTimer = setTimeout(() => inspectImportFolder(wsModalEls.pathInput.value.trim()), 400);
    });
}

if (wsModalEls.confirmBtn) {
    wsModalEls.confirmBtn.addEventListener('click', async () => {
        if (!importCandidate) return;
        const path = importCandidate;
        wsModalEls.confirmBtn.disabled = true;
        try {
            if (!currentWorkspacesList.some(w => w.path === path)) {
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
}

// Attach to window
window.currentWorkspacesList = currentWorkspacesList;
window.renderProjectSegments = renderProjectSegments;
window.removeProject = removeProject;
window.selectProject = selectProject;
window.renderActiveProject = renderActiveProject;
window.loadWorkspaceInfo = loadWorkspaceInfo;
window.openWorkspaceModal = openWorkspaceModal;
window.closeWorkspaceModal = closeWorkspaceModal;
window.inspectImportFolder = inspectImportFolder;
