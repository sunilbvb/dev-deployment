/**
 * app_deep_links.js — Pre-Release Deep Link & Universal Link Validator
 * Queries domain assetlinks.json and apple-app-site-association, validating
 * keystore SHA-256 fingerprints and Apple Team IDs before store submission.
 */

const deepLinksState = {
    appId: null,
    loading: false,
    data: null,
};

function openDeepLinksModal(appId = null) {
    deepLinksState.appId = appId || (window.state && window.state.selectedApp) || '';
    const overlay = document.getElementById('deepLinksOverlay');
    if (overlay) overlay.classList.add('ui-active');
    const subtitle = document.getElementById('deepLinksSubtitle');
    if (subtitle) {
        subtitle.textContent = deepLinksState.appId ? `Validating deep links for app: ${deepLinksState.appId}` : 'Validating workspace domains';
    }
    loadDeepLinksValidation();
}

function closeDeepLinksModal() {
    const overlay = document.getElementById('deepLinksOverlay');
    if (overlay) overlay.classList.remove('ui-active');
}

async function loadDeepLinksValidation() {
    const resultsContainer = document.getElementById('deepLinksResults');
    const domainInput = document.getElementById('deepLinksDomainInput');
    const domainOverride = domainInput ? domainInput.value.trim() : '';

    if (!resultsContainer) return;
    resultsContainer.innerHTML = '<div class="empty-state" style="padding: 24px; text-align: center;"><div class="ui-spinner" style="margin: 0 auto 12px;"></div>Scanning manifests &amp; testing live domain endpoints...</div>';

    const appId = deepLinksState.appId || (window.state && window.state.selectedApp) || '';
    const qApp = appId ? `app=${encodeURIComponent(appId)}` : '';
    const qDomain = domainOverride ? `&domain=${encodeURIComponent(domainOverride)}` : '';

    try {
        const url = (typeof api === 'function') ? api(`/api/deployment/deep-links?${qApp}${qDomain}`) : `/api/deployment/deep-links?${qApp}${qDomain}`;
        const token = window.__DEPLOYMENT_TOKEN__ || '';
        const headers = token ? { 'X-API-Token': token } : {};
        const res = await fetch(url, { headers });
        const data = await res.json();

        deepLinksState.data = data;
        renderDeepLinksResults(data);
    } catch (err) {
        resultsContainer.innerHTML = `<div class="ui-alert" data-variant="danger" style="margin: 12px 0;">Failed to validate deep links: ${escapeHtml(err.message)}</div>`;
    }
}

function renderDeepLinksResults(data) {
    const container = document.getElementById('deepLinksResults');
    if (!container) return;

    if (!data.domains || data.domains.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 30px; text-align: center; border: 1px dashed var(--ui-border-color); border-radius: 8px;">
                <div style="font-size: 1.8rem; margin-bottom: 8px;">🔗</div>
                <div style="font-weight: 600; margin-bottom: 4px;">No Deep Link Domains Found</div>
                <div style="font-size: 0.8rem; color: var(--ui-text-muted); max-width: 440px; margin: 0 auto 16px;">
                    No autoVerify intent-filters in AndroidManifest.xml or Associated Domains in Runner.entitlements.
                </div>
                <div style="font-size: 0.78rem;">You can test a specific domain using the input box above.</div>
            </div>`;
        return;
    }

    let html = `<div style="display: flex; flex-direction: column; gap: 14px;">`;

    data.domains.forEach(d => {
        const a = d.android || {};
        const i = d.ios || {};

        const aBadge = a.status === 'valid'
            ? '<span class="ui-badge" data-variant="success">Android AssetLinks: Valid ✓</span>'
            : (a.status === 'unreachable' ? '<span class="ui-badge" data-variant="warning">Android: Unreachable</span>' : '<span class="ui-badge" data-variant="danger">Android: Mismatch ⚠</span>');

        const iBadge = i.status === 'valid'
            ? '<span class="ui-badge" data-variant="success">iOS AASA: Valid ✓</span>'
            : (i.status === 'unreachable' ? '<span class="ui-badge" data-variant="warning">iOS: Unreachable</span>' : '<span class="ui-badge" data-variant="danger">iOS: Mismatch ⚠</span>');

        html += `
            <div class="ui-card" style="padding: 14px; border: 1px solid var(--ui-border-color); border-radius: 8px; background: var(--ui-card-bg);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                    <div style="font-weight: 700; font-size: 0.95rem; display: flex; align-items: center; gap: 6px;">
                        <span>🌐 ${escapeHtml(d.domain)}</span>
                    </div>
                    <div style="display: flex; gap: 6px; align-items: center;">
                        ${aBadge}
                        ${iBadge}
                    </div>
                </div>

                <!-- Android Details -->
                <div style="background: rgba(0,0,0,0.03); padding: 10px; border-radius: 6px; margin-bottom: 8px; font-size: 0.78rem;">
                    <div style="font-weight: 600; margin-bottom: 4px; display: flex; justify-content: space-between;">
                        <span>Android App Links (.well-known/assetlinks.json)</span>
                        <a href="${escapeHtml(a.url || '')}" target="_blank" rel="noopener noreferrer" style="color: var(--ui-primary-color); text-decoration: underline;">View JSON ↗</a>
                    </div>
                    <div style="color: var(--ui-text-muted);">${escapeHtml(a.message || '')}</div>
                    ${a.foundFingerprints && a.foundFingerprints.length > 0 ? `<div style="margin-top: 4px; font-family: monospace; font-size: 0.72rem; word-break: break-all;">Found SHA256: ${escapeHtml(a.foundFingerprints[0])}</div>` : ''}
                </div>

                <!-- iOS Details -->
                <div style="background: rgba(0,0,0,0.03); padding: 10px; border-radius: 6px; font-size: 0.78rem;">
                    <div style="font-weight: 600; margin-bottom: 4px; display: flex; justify-content: space-between;">
                        <span>Apple Universal Links (.well-known/apple-app-site-association)</span>
                        <a href="${escapeHtml(i.url || '')}" target="_blank" rel="noopener noreferrer" style="color: var(--ui-primary-color); text-decoration: underline;">View AASA ↗</a>
                    </div>
                    <div style="color: var(--ui-text-muted);">${escapeHtml(i.message || '')}</div>
                    ${i.foundAppIds && i.foundAppIds.length > 0 ? `<div style="margin-top: 4px; font-family: monospace; font-size: 0.72rem;">Found App IDs: ${escapeHtml(i.foundAppIds.join(', '))}</div>` : ''}
                </div>
            </div>`;
    });

    html += `</div>`;
    container.innerHTML = html;
}

// Global button listener registration
document.addEventListener('DOMContentLoaded', () => {
    const openBtn = document.getElementById('openDeepLinksBtn');
    if (openBtn) openBtn.addEventListener('click', () => openDeepLinksModal());
    const closeBtn = document.getElementById('closeDeepLinksBtn');
    if (closeBtn) closeBtn.addEventListener('click', closeDeepLinksModal);
    const recheckBtn = document.getElementById('recheckDeepLinksBtn');
    if (recheckBtn) recheckBtn.addEventListener('click', loadDeepLinksValidation);
    const domainInput = document.getElementById('deepLinksDomainInput');
    if (domainInput) {
        domainInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                loadDeepLinksValidation();
            }
        });
    }
});
