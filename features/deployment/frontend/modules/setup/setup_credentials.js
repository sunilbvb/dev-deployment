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
    const appId = setupState.selectedAppId;
    const rows = res.found.map((item, idx) => {
        const forThisApp = (item.matches || []).filter(m => m.app === appId);
        const matchText = (item.matches || []).length
            ? item.matches.map(m => `${m.app}${m.flavor !== 'default' ? ` (${m.flavor})` : ''}`).join(', ')
            : 'no matching app';
        const isFirebase = item.kind.startsWith('firebase');
        const flavorOptions = isFirebase
            ? (forThisApp.length ? forThisApp.map(m => m.flavor) : ['default', ...getActiveFlavors()])
                .filter((f, i, arr) => arr.indexOf(f) === i)
                .map(f => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`).join('')
            : '';
        const importable = item.kind !== 'apple_other_p8';
        const scopeControl = !importable ? '' : isFirebase
            ? `<select class="ui-input" data-cred-flavor="${idx}" style="width:auto;">${flavorOptions}</select>`
            : `<select class="ui-input" data-cred-scope="${idx}" style="width:auto;">
                   <option value="app">This app</option>
                   <option value="workspace">All apps</option>
               </select>`;
        const importBtn = importable
            ? `<button type="button" class="ui-button" data-variant="secondary" data-size="sm" data-cred-import="${idx}">Import</button>`
            : '';
        return `
            <div style="display:flex; gap:10px; align-items:center; padding:8px 0; border-top:1px solid var(--ui-border-color);${importable ? '' : ' opacity:0.6;'}">
                <div style="flex:1; min-width:0;">
                    <div style="font-size:0.82rem; font-weight:600;">${escapeHtml(CRED_KIND_LABELS[item.kind] || item.kind)} ${PLAY_HINT_BADGES[item.play_hint] || ''}</div>
                    <div style="font-size:0.78rem;">${escapeHtml(describeFound(item))}</div>
                    <div style="font-size:0.72rem; color:var(--ui-text-muted); overflow-wrap:anywhere;" title="${escapeHtml(item.path)}">${escapeHtml(item.path)}</div>
                    ${isFirebase ? `<div style="font-size:0.72rem; color:var(--ui-text-muted);">Matches: ${escapeHtml(matchText)}</div>` : ''}
                </div>
                ${scopeControl}
                ${importBtn}
            </div>`;
    }).join('');
    credEls.scanResults.innerHTML = `
        <div style="font-size:0.78rem; color:var(--ui-text-muted); margin-bottom:4px;">
            Found ${res.found.length} in ${escapeHtml(res.folder)}${res.truncated ? ' (scan stopped early — choose a narrower folder)' : ''}
        </div>${rows}`;
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
