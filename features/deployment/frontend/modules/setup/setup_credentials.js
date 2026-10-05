/**
 * setup_credentials.js — Setup Credentials Module
 * Manages Apple .p8 file dropzone and uploads, Google Play service-account JSON,
 * folder credential scanning, and native folder picker integrations.
 */

const credEls = {
    playStatus: document.getElementById('playKeyStatus'),
    playChoose: document.getElementById('playKeyChooseBtn'),
    playFile: document.getElementById('playKeyFileInput'),
    playAllApps: document.getElementById('playKeyAllApps'),
    playRemove: document.getElementById('playKeyRemoveBtn'),
    scanFolder: document.getElementById('credScanFolder'),
    scanBtn: document.getElementById('credScanBtn'),
    pickFolderBtn: document.getElementById('credPickFolderBtn'),
    scanWorkspaceBtn: document.getElementById('credScanWorkspaceBtn'),
    scanManual: document.getElementById('credScanManual'),
    scanResults: document.getElementById('credScanResults'),
};

const CRED_KIND_LABELS = {
    play_service_account: 'Google Play service account',
    apple_p8: 'App Store Connect API key (.p8)',
    firebase_android: 'Firebase google-services.json',
    firebase_ios: 'Firebase GoogleService-Info.plist',
    apple_other_p8: 'Other Apple key (.p8) — not for uploads',
};

const PLAY_HINT_BADGES = {
    likely: '<span class="ui-badge" data-variant="success" style="font-size:0.62rem;">likely Play uploader</span>',
    unlikely: '<span class="ui-badge" data-variant="secondary" style="font-size:0.62rem;">likely Firebase / other service</span>',
};

const IMPORTED_SOURCES = new Set(['app', 'workspace']);

function scopeLabel(source) {
    if (source === 'workspace') return 'all apps';
    if (source === 'deploy_config') return 'path from deploy config';
    if (source === 'auto') return 'auto-detected';
    if (source && source.startsWith('env file')) return `from app ${source}`;
    return 'this app';
}

async function uploadP8File(file) {
    if (!setupState.selectedAppId) {
        showToast('Please select an app first.');
        return;
    }
    if (!file || !file.name.toLowerCase().endsWith('.p8')) {
        showToast('Please select a valid .p8 file.');
        return;
    }

    setupEls.p8DropzoneTitle.textContent = `⏳ Uploading ${file.name}…`;
    setupEls.p8UploadStatus.style.display = 'none';
    setupEls.p8Dropzone.classList.add('ui-dropzone--active');

    const formData = new FormData();
    formData.append('app_id', setupState.selectedAppId);
    formData.append('issuer_id', setupEls.issuerId.value.trim());
    formData.append('file', file, file.name);

    let res;
    try {
        res = await fetch('/api/deployment/p8/upload', {
            method: 'POST',
            body: formData,
        }).then(r => r.json());
    } catch (err) {
        setupEls.p8Dropzone.classList.remove('ui-dropzone--active');
        setupEls.p8DropzoneTitle.textContent = '❌ Upload failed — network error';
        showToast('Upload failed: ' + err.message);
        return;
    }

    setupEls.p8Dropzone.classList.remove('ui-dropzone--active');

    if (res.success) {
        await loadCredentialStatus(setupState.selectedAppId);
        setupEls.p8UploadStatus.dataset.status = 'valid';
        setupEls.p8UploadStatus.textContent =
            `✅ Key ID: ${res.key_id}  •  Stored at: ${res.stored_path}`;
        setupEls.p8UploadStatus.style.display = 'block';
        showToast(`✅ Key ID ${res.key_id} uploaded and stored.`);
    } else {
        setupEls.p8DropzoneTitle.textContent = '❌ Upload failed — try again';
        setupEls.p8UploadStatus.dataset.status = 'error';
        setupEls.p8UploadStatus.textContent = `❌ ${res.error || 'Unknown error'}`;
        setupEls.p8UploadStatus.style.display = 'block';
        showToast('Upload error: ' + (res.error || 'Unknown'));
    }
}

async function importP8Path(path) {
    if (!path.toLowerCase().endsWith('.p8')) { showToast('Please select a valid .p8 file.'); return; }
    const name = path.split('/').pop();
    setupEls.p8DropzoneTitle.textContent = `⏳ Importing ${name}…`;
    setupEls.p8UploadStatus.style.display = 'none';
    let res;
    try {
        res = await postJson('/api/deployment/credentials/import', {
            path, app: setupState.selectedAppId, issuerId: setupEls.issuerId.value.trim(),
        });
    } catch (err) {
        res = { success: false, error: err.message };
    }
    showP8Result(res);
}

/** Shared result display for drag/drop upload and native-picker import. */
async function showP8Result(res) {
    if (res.success) {
        await loadCredentialStatus(setupState.selectedAppId);
        setupEls.p8DropzoneTitle.textContent = 'Drag & drop AuthKey_XXXXXXXXXX.p8 or click to browse';
        setupEls.p8UploadStatus.dataset.status = 'valid';
        setupEls.p8UploadStatus.textContent = `✅ Key ID: ${res.key_id || '?'}  •  Stored at: ${res.stored_path || res.path || '~/.appstoreconnect'}`;
        showToast(`✅ Key ID ${res.key_id || ''} imported.`);
    } else {
        setupEls.p8DropzoneTitle.textContent = '❌ Import failed — try again';
        setupEls.p8UploadStatus.dataset.status = 'error';
        setupEls.p8UploadStatus.textContent = `❌ ${res.error || 'Unknown error'}`;
        showToast('Import error: ' + (res.error || 'Unknown'));
    }
    setupEls.p8UploadStatus.style.display = 'block';
}

// Click-to-browse & Drag-and-drop for p8
if (setupEls.p8Dropzone) {
    // Use the server's native Finder/zenity dialog: embedded browsers (e.g. desktop
    // app panes) often never open a dialog for <input type=file>. Fall back to the
    // browser picker only where no native dialog exists.
    setupEls.p8Dropzone.addEventListener('click', async () => {
        if (!setupState.selectedAppId) { showToast('Please select an app first.'); return; }
        const picked = await pickNativePath({ kind: 'file', prompt: 'Choose an App Store Connect API key (.p8)', extensions: ['p8'] });
        if (picked.path) {
            importP8Path(picked.path);
        } else if (picked.unsupported && setupEls.p8FileInput) {
            setupEls.p8FileInput.value = '';
            setupEls.p8FileInput.click();
        } else if (picked.error) {
            showToast(picked.error);
        }
    });

    setupEls.p8Dropzone.addEventListener('dragover', e => {
        e.preventDefault();
        setupEls.p8Dropzone.classList.add('ui-dropzone--active');
    });

    setupEls.p8Dropzone.addEventListener('dragleave', () => {
        setupEls.p8Dropzone.classList.remove('ui-dropzone--active');
    });

    setupEls.p8Dropzone.addEventListener('drop', e => {
        e.preventDefault();
        setupEls.p8Dropzone.classList.remove('ui-dropzone--active');
        const file = e.dataTransfer?.files?.[0];
        if (file) { uploadP8File(file); }
    });
}

if (setupEls.p8FileInput) {
    setupEls.p8FileInput.addEventListener('change', () => {
        const file = setupEls.p8FileInput.files?.[0];
        if (file) { uploadP8File(file); }
    });
}

async function loadCredentialStatus(appId) {
    if (!appId || !credEls.playStatus) return;
    let status;
    try {
        status = await fetch(`/api/deployment/credentials?app=${encodeURIComponent(appId)}`).then(r => r.json());
    } catch (err) {
        credEls.playStatus.dataset.status = 'error';
        credEls.playStatus.textContent = `Could not load credentials: ${err.message}`;
        return;
    }
    if (appId !== setupState.selectedAppId) return;

    const play = status.play;
    if (!play) {
        credEls.playStatus.dataset.status = 'warning';
        credEls.playStatus.textContent = 'No key configured — Android uploads will fail until you choose or import one.';
    } else if (!play.exists || !play.valid) {
        credEls.playStatus.dataset.status = 'error';
        credEls.playStatus.textContent = `${play.exists ? 'Not a service-account key' : 'File missing'}: ${play.path}`;
    } else {
        credEls.playStatus.dataset.status = 'valid';
        credEls.playStatus.textContent = `✅ ${play.client_email} • ${scopeLabel(play.source)} • ${play.path}`;
    }
    if (credEls.playRemove) {
        credEls.playRemove.hidden = !play || !IMPORTED_SOURCES.has(play.source);
        credEls.playRemove.dataset.app = play && play.source === 'workspace' ? '' : appId;
    }
    if (typeof setTabStatus === 'function') {
        setTabStatus('android', !!(play && play.exists && play.valid));
        setTabStatus('ios', !!(status.apple && status.apple.exists));
    }

    if (typeof renderP8KeyInfo === 'function') {
        renderP8KeyInfo(status.apple);
    }
}

async function uploadCredentialFile(file, { appId, issuerId = '' }) {
    const buf = new Uint8Array(await file.arrayBuffer());
    let binary = '';
    for (let i = 0; i < buf.length; i += 0x8000) {
        binary += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    }
    return postJson('/api/deployment/credentials/upload', {
        filename: file.name, contentBase64: btoa(binary), app: appId, issuerId,
    });
}

if (credEls.playChoose) {
    credEls.playChoose.addEventListener('click', () => {
        if (!setupState.selectedAppId) { showToast('Please select an app first.'); return; }
        if (credEls.playFile) {
            credEls.playFile.value = '';
            credEls.playFile.click();
        }
    });
}

if (credEls.playFile) {
    credEls.playFile.addEventListener('change', async () => {
        const file = credEls.playFile.files?.[0];
        if (!file) return;
        const appId = credEls.playAllApps && credEls.playAllApps.checked ? '' : setupState.selectedAppId;
        const res = await uploadCredentialFile(file, { appId });
        if (res.success && res.kind === 'play_service_account') {
            showToast(`✅ Play key for ${res.client_email} imported.`);
        } else if (res.success) {
            showToast(`That file is a ${CRED_KIND_LABELS[res.kind] || res.kind}, not a Play service account — imported as such.`);
        } else {
            showToast('Import failed: ' + (res.error || 'Unknown error'));
        }
        loadCredentialStatus(setupState.selectedAppId);
    });
}

if (credEls.playRemove) {
    credEls.playRemove.addEventListener('click', async () => {
        const res = await postJson('/api/deployment/credentials/remove', {
            kind: 'play_service_account', app: credEls.playRemove.dataset.app || '',
        });
        showToast(res.success ? 'Play key removed (the file itself was not deleted).' : 'Remove failed: ' + res.error);
        loadCredentialStatus(setupState.selectedAppId);
    });
}

function describeFound(item) {
    if (item.kind === 'play_service_account') return item.client_email;
    if (item.kind === 'apple_p8') return item.key_id ? `Key ID ${item.key_id}` : 'Key ID unknown — rename to AuthKey_<KEYID>.p8';
    if (item.kind === 'firebase_android') return (item.packages || []).join(', ') || item.project_id;
    if (item.kind === 'firebase_ios') return item.bundle_id;
    return item.note || '';
}

// Kinds that are chosen once and applied to apps (they hold no bundle ID, so the
// developer picks); Firebase configs are matched to apps by their own IDs.
const PICK_KINDS = ['apple_p8', 'play_service_account'];

function pickDefaultIndex(items, appId) {
    const score = it => ((it.in_use_by || []).includes(appId) ? 1000 : 0)
        + (it.in_use_by || []).length * 10
        + (it.play_hint === 'likely' ? 5 : it.play_hint === 'unlikely' ? -5 : 0);
    let best = 0;
    items.forEach((it, i) => { if (score(it) > score(items[best])) best = i; });
    return best;
}

function renderFoundBadges(item) {
    const used = item.in_use_by || [];
    const badges = [];
    if (used.length) {
        badges.push(`<span class="ui-badge" data-variant="success" title="${escapeHtml(used.join(', '))}">in use · ${used.length === setupState.apps.length ? 'all apps' : escapeHtml(used.join(', '))}</span>`);
    }
    if (PLAY_HINT_BADGES[item.play_hint]) badges.push(PLAY_HINT_BADGES[item.play_hint]);
    if ((item.paths || []).length > 1) badges.push(`<span class="ui-badge" data-variant="secondary">found in ${item.paths.length} places</span>`);
    return badges.join(' ');
}

function renderPickGroup(kind, items, gi) {
    const appId = setupState.selectedAppId;
    const def = pickDefaultIndex(items, appId);
    const rows = items.map((item, i) => `
        <label class="cred-pick-row" style="display:flex; gap:10px; align-items:flex-start; padding:8px; border-radius:6px; cursor:pointer;">
            <input type="radio" name="credPick_${gi}" value="${i}" ${i === def ? 'checked' : ''} style="margin-top:3px;">
            <span style="flex:1; min-width:0;">
                <span style="display:block; font-size:0.82rem; font-weight:600;">${escapeHtml(describeFound(item))} ${renderFoundBadges(item)}</span>
                ${item.project_id ? `<span style="display:block; font-size:0.72rem; color:var(--ui-text-muted);">Project: ${escapeHtml(item.project_id)}</span>` : ''}
                ${(item.paths || [item.path]).map(pth => `<span style="display:block; font-size:0.72rem; color:var(--ui-text-muted); overflow-wrap:anywhere;">${escapeHtml(pth)}</span>`).join('')}
            </span>
        </label>`).join('');
    const appChecks = setupState.apps.map(app => `
        <label style="display:inline-flex; gap:6px; align-items:center; font-size:0.78rem; margin:0 12px 6px 0; cursor:pointer;">
            <input type="checkbox" data-pick-app="${gi}" value="${escapeHtml(app.id)}" ${app.id === appId ? 'checked' : ''}>
            ${escapeHtml(app.name || app.id)}
        </label>`).join('');
    const issuer = kind === 'apple_p8' ? `
        <div class="ui-form-group" style="margin-top:10px;">
            <label class="ui-label" for="credPickIssuer_${gi}">Issuer ID</label>
            <input type="text" class="ui-input" id="credPickIssuer_${gi}" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" value="${escapeHtml(setupEls.issuerId ? setupEls.issuerId.value.trim() : '')}">
        </div>` : '';
    return `
        <div class="ui-card" data-pick-group="${gi}" style="margin-top:12px;">
            <div class="ui-card-header" style="display:flex; justify-content:space-between; align-items:center;">
                <h4 class="ui-card-title">${escapeHtml(CRED_KIND_LABELS[kind])}</h4>
                <span class="ui-badge" data-variant="secondary">${items.length} found</span>
            </div>
            <div class="ui-card-body">
                ${items.length > 1 ? '<div style="font-size:0.78rem; color:var(--ui-text-muted); margin-bottom:6px;">Several keys found. Choose the one to use:</div>' : ''}
                ${rows}
                ${issuer}
                <div style="margin-top:12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span class="ui-label">Use for apps</span>
                        <button type="button" class="ui-button" data-variant="ghost" data-size="sm" data-pick-all="${gi}">Select all</button>
                    </div>
                    ${appChecks}
                </div>
                <div style="display:flex; gap:10px; align-items:center; margin-top:8px;">
                    <button type="button" class="ui-button" data-variant="primary" data-size="sm" data-pick-apply="${gi}">Use selected key</button>
                    <span data-pick-status="${gi}" style="font-size:0.78rem; color:var(--ui-text-muted);"></span>
                </div>
            </div>
        </div>`;
}

function renderFirebaseRow(item, idx) {
    const appId = setupState.selectedAppId;
    const forThisApp = (item.matches || []).filter(m => m.app === appId);
    const matchText = (item.matches || []).length
        ? item.matches.map(m => `${m.app}${m.flavor !== 'default' ? ` (${m.flavor})` : ''}`).join(', ')
        : 'no matching app';
    const flavorOptions = (forThisApp.length ? forThisApp.map(m => m.flavor) : ['default', ...getActiveFlavors()])
        .filter((f, i, arr) => arr.indexOf(f) === i)
        .map(f => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`).join('');
    return `
        <div style="display:flex; gap:10px; align-items:center; padding:8px 0; border-top:1px solid var(--ui-border-color);">
            <div style="flex:1; min-width:0;">
                <div style="font-size:0.82rem; font-weight:600;">${escapeHtml(CRED_KIND_LABELS[item.kind])} ${renderFoundBadges(item)}</div>
                <div style="font-size:0.78rem;">${escapeHtml(describeFound(item))}</div>
                <div style="font-size:0.72rem; color:var(--ui-text-muted); overflow-wrap:anywhere;">${escapeHtml(item.path)}</div>
                <div style="font-size:0.72rem; color:var(--ui-text-muted);">Matches: ${escapeHtml(matchText)}</div>
            </div>
            <select class="ui-select" data-cred-flavor="${idx}" style="width:auto;">${flavorOptions}</select>
            <button type="button" class="ui-button" data-variant="secondary" data-size="sm" data-cred-import="${idx}">Import</button>
        </div>`;
}

async function applyPickedKey(group, items, gi) {
    const box = credEls.scanResults.querySelector(`[data-pick-group="${gi}"]`);
    const item = items[Number(box.querySelector(`input[name="credPick_${gi}"]:checked`)?.value ?? -1)];
    const apps = [...box.querySelectorAll(`[data-pick-app="${gi}"]:checked`)].map(c => c.value);
    const status = box.querySelector(`[data-pick-status="${gi}"]`);
    if (!item) { showToast('Choose a key first.'); return; }
    if (!apps.length) { showToast('Choose at least one app.'); return; }
    const issuerId = group === 'apple_p8' ? (box.querySelector(`#credPickIssuer_${gi}`)?.value.trim() || '') : '';
    const btn = box.querySelector(`[data-pick-apply="${gi}"]`);
    btn.disabled = true;
    const failed = [];
    for (const app of apps) {
        status.textContent = `Applying to ${app}…`;
        let res;
        try {
            res = await postJson('/api/deployment/credentials/import', { path: item.path, app, issuerId });
        } catch (err) {
            res = { success: false, error: err.message };
        }
        if (!res.success) failed.push(`${app}: ${res.error || 'failed'}`);
    }
    btn.disabled = false;
    if (failed.length) {
        status.textContent = `❌ ${failed.join('; ')}`;
        showToast('Some apps failed: ' + failed.join('; '));
    } else {
        status.textContent = `✅ Applied to ${apps.length} app${apps.length === 1 ? '' : 's'}`;
        showToast(`✅ ${describeFound(item)} set for ${apps.length} app${apps.length === 1 ? '' : 's'}.`);
        if (issuerId && setupEls.issuerId) setupEls.issuerId.value = issuerId;
    }
    loadCredentialStatus(setupState.selectedAppId);
}

function renderScanResults(res) {
    if (!credEls.scanResults) return;
    if (!res.success) {
        credEls.scanResults.innerHTML = `<div class="cert-status-box" data-status="error">${escapeHtml(res.error || 'Scan failed')}</div>`;
        return;
    }
    if (!res.found.length) {
        credEls.scanResults.innerHTML = `<div class="cert-status-box" data-status="unknown">No keys found in ${escapeHtml(res.folder)}.</div>`;
        return;
    }
    const groups = PICK_KINDS.map(kind => ({ kind, items: res.found.filter(f => f.kind === kind) })).filter(g => g.items.length);
    const firebase = res.found.map((item, idx) => ({ item, idx })).filter(({ item }) => item.kind.startsWith('firebase'));
    const hidden = res.hidden_other_p8
        ? ` · ${res.hidden_other_p8} non-API .p8 key${res.hidden_other_p8 === 1 ? '' : 's'} (In-App Purchase / APNs) hidden`
        : '';
    credEls.scanResults.innerHTML = `
        <div style="font-size:0.78rem; color:var(--ui-text-muted);">
            Found ${res.found.length} in ${escapeHtml(res.folder)}${hidden}${res.truncated ? ' (scan stopped early — choose a narrower folder)' : ''}
        </div>
        ${groups.map((g, gi) => renderPickGroup(g.kind, g.items, gi)).join('')}
        ${firebase.length ? `
            <div class="ui-card" style="margin-top:12px;">
                <div class="ui-card-header"><h4 class="ui-card-title">Firebase configs</h4></div>
                <div class="ui-card-body">
                    <div style="font-size:0.78rem; color:var(--ui-text-muted);">Matched to apps by package / bundle ID.</div>
                    ${firebase.map(({ item, idx }) => renderFirebaseRow(item, idx)).join('')}
                </div>
            </div>` : ''}`;

    groups.forEach((g, gi) => {
        credEls.scanResults.querySelector(`[data-pick-apply="${gi}"]`)
            .addEventListener('click', () => applyPickedKey(g.kind, g.items, gi));
        credEls.scanResults.querySelector(`[data-pick-all="${gi}"]`).addEventListener('click', () => {
            const boxes = [...credEls.scanResults.querySelectorAll(`[data-pick-app="${gi}"]`)];
            const all = boxes.every(b => b.checked);
            boxes.forEach(b => { b.checked = !all; });
        });
    });
    credEls.scanResults.querySelectorAll('[data-cred-import]').forEach(btn => {
        btn.addEventListener('click', () => importScanned(res.found[Number(btn.dataset.credImport)], Number(btn.dataset.credImport), btn));
    });
}

async function importScanned(item, idx, btn) {
    const appId = setupState.selectedAppId;
    if (!appId) { showToast('Please select an app first.'); return; }
    const scope = credEls.scanResults.querySelector(`[data-cred-scope="${idx}"]`)?.value || 'app';
    const flavor = credEls.scanResults.querySelector(`[data-cred-flavor="${idx}"]`)?.value || '';
    btn.disabled = true;
    const res = await postJson('/api/deployment/credentials/import', {
        path: item.path,
        app: item.kind.startsWith('firebase') || scope === 'app' ? appId : '',
        flavor,
        issuerId: item.kind === 'apple_p8' ? setupEls.issuerId.value.trim() : '',
    });
    btn.disabled = false;
    if (res.success) {
        btn.textContent = 'Imported ✓';
        showToast(`✅ ${CRED_KIND_LABELS[res.kind]} imported.`);
        if (res.field) {
            const app = (setupState.deployConfig.apps[appId] = setupState.deployConfig.apps[appId] || {});
            app[res.field] = res.stored_path;
            renderDynamicFields(getActiveFlavors(), app);
        }
        loadCredentialStatus(appId);
    } else {
        showToast('Import failed: ' + (res.error || 'Unknown error'));
    }
}

async function runCredentialScan(folder) {
    const buttons = [credEls.scanBtn, credEls.pickFolderBtn, credEls.scanWorkspaceBtn].filter(Boolean);
    buttons.forEach(b => { b.disabled = true; });
    if (credEls.scanResults) {
        credEls.scanResults.innerHTML = `<div class="cert-status-box" data-status="unknown">Scanning ${escapeHtml(folder || 'workspace')}…</div>`;
    }
    try {
        renderScanResults(await postJson('/api/deployment/credentials/scan', { folder }));
    } catch (err) {
        renderScanResults({ success: false, error: err.message });
    } finally {
        buttons.forEach(b => { b.disabled = false; });
    }
}

async function pickNativePath({ kind = 'folder', prompt = '', extensions = [] } = {}) {
    const res = await postJson('/api/deployment/pick', { kind, prompt, extensions });
    if (res.success) return { path: res.path };
    return { path: null, unsupported: res.supported === false, error: res.cancelled ? '' : res.error };
}

if (credEls.pickFolderBtn) {
    credEls.pickFolderBtn.addEventListener('click', async () => {
        credEls.pickFolderBtn.disabled = true;
        if (credEls.scanResults) {
            credEls.scanResults.innerHTML = '<div class="cert-status-box" data-status="unknown">Waiting for you to choose a folder in the dialog…</div>';
        }
        const picked = await pickNativePath({ kind: 'folder', prompt: 'Choose a folder to scan for signing keys' });
        credEls.pickFolderBtn.disabled = false;
        if (picked.path) {
            if (credEls.scanFolder) credEls.scanFolder.value = picked.path;
            runCredentialScan(picked.path);
        } else if (picked.unsupported) {
            if (credEls.scanManual) credEls.scanManual.hidden = false;
            if (credEls.scanResults) {
                credEls.scanResults.innerHTML = '<div class="cert-status-box" data-status="warning">No folder dialog is available on this system. Type the folder path below.</div>';
            }
            if (credEls.scanFolder) credEls.scanFolder.focus();
        } else if (credEls.scanResults) {
            credEls.scanResults.innerHTML = picked.error
                ? `<div class="cert-status-box" data-status="error">${escapeHtml(picked.error)}</div>` : '';
        }
    });
}

if (credEls.scanWorkspaceBtn) credEls.scanWorkspaceBtn.addEventListener('click', () => runCredentialScan(''));
if (credEls.scanBtn) credEls.scanBtn.addEventListener('click', () => runCredentialScan(credEls.scanFolder ? credEls.scanFolder.value.trim() : ''));

// Attach to window
window.uploadP8File = uploadP8File;
window.loadCredentialStatus = loadCredentialStatus;
window.uploadCredentialFile = uploadCredentialFile;
window.describeFound = describeFound;
window.renderScanResults = renderScanResults;
window.importScanned = importScanned;
window.runCredentialScan = runCredentialScan;
window.pickNativePath = pickNativePath;
