/**
 * app_security.js — APK / IPA Security & Dangerous Permissions Inspector
 * Flags restricted Android permissions, cleartext HTTP, exported components,
 * and missing Apple privacy disclosures before store review.
 */

const securityState = {
    appId: null,
    data: null,
};

function openSecurityModal(appId = null) {
    securityState.appId = appId || (window.state && window.state.selectedApp) || '';
    const overlay = document.getElementById('securityInspectorOverlay');
    if (overlay) overlay.classList.add('ui-active');
    const subtitle = document.getElementById('securityInspectorSubtitle');
    if (subtitle) {
        subtitle.textContent = securityState.appId ? `Security Profile for App: ${securityState.appId}` : 'Workspace Mobile Security Profile';
    }
    loadSecurityProfile();
}

function closeSecurityModal() {
    const overlay = document.getElementById('securityInspectorOverlay');
    if (overlay) overlay.classList.remove('ui-active');
}

async function loadSecurityProfile() {
    const container = document.getElementById('securityReportContainer');
    if (container) {
        container.innerHTML = '<div class="empty-state" style="padding: 24px; text-align: center;"><div class="ui-spinner" style="margin: 0 auto 12px;"></div>Analyzing Android manifests and iOS privacy manifests...</div>';
    }

    const appId = securityState.appId || (window.state && window.state.selectedApp) || '';
    const qApp = appId ? `app=${encodeURIComponent(appId)}` : '';
    const url = (typeof api === 'function') ? api(`/api/deployment/security/permissions?${qApp}`) : `/api/deployment/security/permissions?${qApp}`;
    const token = window.__DEPLOYMENT_TOKEN__ || '';
    const headers = token ? { 'X-API-Token': token } : {};

    try {
        const res = await fetch(url, { headers });
        const data = await res.json();
        securityState.data = data;
        renderSecurityProfile(data);
    } catch (err) {
        if (container) {
            container.innerHTML = `<div class="ui-alert" data-variant="danger">Failed to scan security profile: ${escapeHtml(err.message)}</div>`;
        }
    }
}

function renderSecurityProfile(data) {
    const container = document.getElementById('securityReportContainer');
    if (!container) return;

    const riskVariant = data.riskLevel === 'HIGH' ? 'danger' : (data.riskLevel === 'MEDIUM' ? 'warning' : 'success');
    const riskBadge = `<span class="ui-badge" data-variant="${riskVariant}" style="font-size: 0.85rem; padding: 4px 10px;">Risk Level: ${data.riskLevel}</span>`;

    const android = data.android || {};
    const ios = data.ios || {};

    let html = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
            <div>
                <span style="font-size: 0.8rem; color: var(--ui-text-muted);">Overall Security Score:</span>
            </div>
            <div>${riskBadge}</div>
        </div>`;

    // Warnings Banner if any
    const allWarnings = [...(android.warnings || []), ...(ios.warnings || [])];
    if (allWarnings.length > 0) {
        html += `<div class="ui-alert" data-variant="warning" style="margin-bottom: 16px;">
            <div style="font-weight: 700; margin-bottom: 4px;">⚠️ Security &amp; Compliance Alerts:</div>
            <ul style="margin: 0; padding-left: 18px; font-size: 0.8rem;">
                ${allWarnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}
            </ul>
        </div>`;
    }

    // Android Permissions Card
    html += `
        <div class="ui-card" style="margin-bottom: 16px; border: 1px solid var(--ui-border-color); border-radius: 8px; padding: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h4 style="margin: 0; font-size: 0.9rem;">🤖 Android Permissions (${android.totalPermissions || 0} total, ${android.dangerousCount || 0} high-risk)</h4>
            </div>`;

    if (!android.permissions || android.permissions.length === 0) {
        html += `<div style="font-size: 0.8rem; color: var(--ui-text-muted);">No permissions declared in AndroidManifest.xml.</div>`;
    } else {
        html += `<div style="display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow-y: auto;">`;
        android.permissions.forEach(p => {
            const sevVariant = p.severity === 'CRITICAL' ? 'danger' : (p.severity === 'HIGH' ? 'warning' : 'secondary');
            html += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-radius: 4px; background: rgba(0,0,0,0.02); font-size: 0.78rem;">
                    <div>
                        <strong>${escapeHtml(p.shortName || p.name)}</strong>
                        <span style="color: var(--ui-text-muted); font-size: 0.72rem; margin-left: 6px;">(${escapeHtml(p.category)})</span>
                        <div style="font-size: 0.72rem; color: var(--ui-text-muted);">${escapeHtml(p.description)}</div>
                    </div>
                    <span class="ui-badge" data-variant="${sevVariant}" data-size="xs">${p.severity}</span>
                </div>`;
        });
        html += `</div>`;
    }
    html += `</div>`;

    // iOS Privacy Manifest Card
    html += `
        <div class="ui-card" style="border: 1px solid var(--ui-border-color); border-radius: 8px; padding: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h4 style="margin: 0; font-size: 0.9rem;">🍎 Apple Privacy Usage Strings (${ios.configuredPrivacyCount || 0} configured)</h4>
            </div>`;

    if (!ios.configuredPrivacy || ios.configuredPrivacy.length === 0) {
        html += `<div style="font-size: 0.8rem; color: var(--ui-text-muted);">No privacy usage strings configured in Info.plist.</div>`;
    } else {
        html += `<div style="display: flex; flex-direction: column; gap: 6px;">`;
        ios.configuredPrivacy.forEach(item => {
            const warnIcon = item.isSuspicious ? '⚠️' : '✓';
            html += `
                <div style="padding: 6px 8px; border-radius: 4px; background: rgba(0,0,0,0.02); font-size: 0.78rem;">
                    <div style="font-weight: 600;">${warnIcon} <code>${escapeHtml(item.key)}</code></div>
                    <div style="color: var(--ui-text-muted); margin-top: 2px;">Value: <em>"${escapeHtml(item.value)}"</em></div>
                </div>`;
        });
        html += `</div>`;
    }
    html += `</div>`;

    container.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', () => {
    const openBtn = document.getElementById('openSecurityBtn');
    if (openBtn) openBtn.addEventListener('click', () => openSecurityModal());
    const closeBtn = document.getElementById('closeSecurityBtn');
    if (closeBtn) closeBtn.addEventListener('click', closeSecurityModal);
    const recheckBtn = document.getElementById('recheckSecurityBtn');
    if (recheckBtn) recheckBtn.addEventListener('click', loadSecurityProfile);
});
