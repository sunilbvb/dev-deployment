/**
 * app_sentinel.js — App Sentinel Module
 * Handles certificate expiry monitoring, keystore validation, Firebase consistency,
 * advisory expiry banners, and the sentinel diagnostics modal.
 */

const SEVERITY_RANK = { expired: 3, warning: 2, unknown: 1, ok: 0, not_ios_app: -1 };

function renderCertExpiryBanner(appId) {
    if (!els.iosCertBanner) return;
    if (!appId) {
        els.iosCertBanner.classList.add('hidden');
        return;
    }
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
            if (state.selectedApp === appId && state.selectedCommand && state.selectedCommand.platform === 'ios' && state.selectedCommand.flavor === 'prod') {
                renderCertBannerFromResult(result);
            }
        })
        .catch(() => {});
}

function renderCertBannerFromResult(result) {
    if (!els.iosCertBanner) return;
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
                els.sentinelHeaderBadge.dataset.variant = data.badge?.variant || 'warning';
                if (els.sentinelHeaderBadgeText) {
                    els.sentinelHeaderBadgeText.textContent = data.badge?.label || 'Sentinel Alert';
                }
                els.sentinelHeaderBadge.classList.remove('hidden');
            } else {
                els.sentinelHeaderBadge.style.display = 'none';
                els.sentinelHeaderBadge.classList.add('hidden');
            }
        }
        if (typeof renderApps === 'function') renderApps();
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
                const crit = data.badge?.criticalCount || 0;
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
                        <span class="ui-badge" data-variant="${data.badge?.variant || 'warning'}">${escapeHtml(data.badge?.label || 'Alert')}</span>
                        <span style="font-size:0.75rem; text-decoration:underline; opacity:0.85;">Details &rarr;</span>
                    </div>
                `;
            } else {
                els.sentinelAlertBanner.style.display = 'none';
                els.sentinelAlertBanner.classList.add('hidden');
            }
        }

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

    if (typeof refreshIcons === 'function') refreshIcons();
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

// Wire Sentinel Events
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

// Attach to window
window.renderCertExpiryBanner = renderCertExpiryBanner;
window.renderCertBannerFromResult = renderCertBannerFromResult;
window.loadWorkspaceSentinel = loadWorkspaceSentinel;
window.loadAppSentinel = loadAppSentinel;
window.renderSentinelModalData = renderSentinelModalData;
window.openSentinelModal = openSentinelModal;
window.closeSentinelModal = closeSentinelModal;
