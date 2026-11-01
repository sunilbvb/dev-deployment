/**
 * app_symbols.js — Crash Symbol Vault (dSYM & ProGuard Mappings)
 * Discovers obfuscation mappings and iOS dSYMs, computes SHA-256 digests,
 * and allows 1-click zip export for Firebase Crashlytics & Sentry.
 */

const symbolsState = {
    appId: null,
    flavor: 'prod',
    data: null,
};

function openSymbolsModal(appId = null, flavor = null) {
    symbolsState.appId = appId || (window.state && window.state.selectedApp) || '';
    symbolsState.flavor = flavor || (window.state && window.state.selectedEnv) || 'prod';
    const overlay = document.getElementById('symbolsVaultOverlay');
    if (overlay) overlay.classList.add('ui-active');
    const subtitle = document.getElementById('symbolsVaultSubtitle');
    if (subtitle) {
        subtitle.textContent = symbolsState.appId ? `Crash symbols for app: ${symbolsState.appId} (${symbolsState.flavor})` : 'Workspace Crash Symbol Vault';
    }
    loadSymbolsList();
}

function closeSymbolsModal() {
    const overlay = document.getElementById('symbolsVaultOverlay');
    if (overlay) overlay.classList.remove('ui-active');
}

async function loadSymbolsList() {
    const container = document.getElementById('symbolsTableBody');
    const exportBtn = document.getElementById('downloadSymbolsZipBtn');
    if (container) {
        container.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px;">Scanning build output directories for symbol files...</td></tr>';
    }

    const appId = symbolsState.appId || (window.state && window.state.selectedApp) || '';
    const qApp = appId ? `app=${encodeURIComponent(appId)}` : '';
    const qFlavor = `flavor=${encodeURIComponent(symbolsState.flavor || 'prod')}`;
    const url = (typeof api === 'function') ? api(`/api/deployment/symbols?${qApp}&${qFlavor}`) : `/api/deployment/symbols?${qApp}&${qFlavor}`;
    const token = window.__DEPLOYMENT_TOKEN__ || '';
    const headers = token ? { 'X-API-Token': token } : {};

    try {
        const res = await fetch(url, { headers });
        const data = await res.json();
        symbolsState.data = data;
        renderSymbolsTable(data);

        if (exportBtn && data.downloadUrl) {
            exportBtn.onclick = () => {
                window.location.href = data.downloadUrl;
            };
        }
    } catch (err) {
        if (container) {
            container.innerHTML = `<tr><td colspan="5" style="color: #ef4444; padding: 14px;">Error: ${escapeHtml(err.message)}</td></tr>`;
        }
    }
}

function renderSymbolsTable(data) {
    const container = document.getElementById('symbolsTableBody');
    if (!container) return;

    const allItems = [...(data.mappings || []), ...(data.dsyms || [])];
    if (allItems.length === 0) {
        container.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 32px; color: var(--ui-text-muted);">
                    <div style="font-size: 1.6rem; margin-bottom: 6px;">🛡️</div>
                    <div style="font-weight: 600;">No Crash Symbols Found</div>
                    <div style="font-size: 0.78rem; margin-top: 4px;">
                        Run a release build (e.g., <code>build_aab</code> or <code>build_ipa</code>) to generate ProGuard mappings or Xcode dSYMs.
                    </div>
                </td>
            </tr>`;
        return;
    }

    let html = '';
    allItems.forEach(item => {
        const isMapping = item.type === 'mapping';
        const typeBadge = isMapping
            ? '<span class="ui-badge" data-variant="secondary">Android R8 / ProGuard</span>'
            : '<span class="ui-badge" data-variant="primary">Apple .dSYM</span>';

        const sizeStr = item.sizeBytes ? (item.sizeBytes > 1024 * 1024 ? (item.sizeBytes / 1024 / 1024).toFixed(2) + ' MB' : (item.sizeBytes / 1024).toFixed(1) + ' KB') : '0 KB';
        const detailStr = isMapping ? `${item.lineCount || 0} mapping lines` : (item.isZip ? 'Zipped archive' : 'dSYM bundle');
        const hashDisplay = item.sha256 ? item.sha256.substring(0, 12) + '…' : '—';

        html += `
            <tr>
                <td>${typeBadge}</td>
                <td><strong>${escapeHtml(item.filename)}</strong><br><span style="font-size: 0.72rem; color: var(--ui-text-muted); font-family: monospace;">${escapeHtml(item.relativePath || '')}</span></td>
                <td>${escapeHtml(sizeStr)}</td>
                <td>${escapeHtml(detailStr)}</td>
                <td style="font-family: monospace; font-size: 0.75rem;">${escapeHtml(hashDisplay)}</td>
            </tr>`;
    });

    container.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', () => {
    const openBtn = document.getElementById('openSymbolsBtn');
    if (openBtn) openBtn.addEventListener('click', () => openSymbolsModal());
    const closeBtn = document.getElementById('closeSymbolsBtn');
    if (closeBtn) closeBtn.addEventListener('click', closeSymbolsModal);
    const rescanBtn = document.getElementById('rescanSymbolsBtn');
    if (rescanBtn) rescanBtn.addEventListener('click', loadSymbolsList);
});
