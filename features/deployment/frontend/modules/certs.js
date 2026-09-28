import { api } from './api.js';
import { escapeHtml } from './utils.js';

const SEVERITY_RANK = { expired: 3, warning: 2, unknown: 1, ok: 0, not_ios_app: -1 };

export function renderCertExpiryBanner(appId, bannerEl, currentSelectedApp, currentCommand) {
    if (!bannerEl) return;
    if (!appId) {
        bannerEl.classList.add('hidden');
        return;
    }

    const cached = (typeof window.getCachedCertCheck === 'function') ? window.getCachedCertCheck(appId) : null;
    if (cached) {
        renderCertBannerFromResult(cached, bannerEl);
        return;
    }

    bannerEl.classList.add('hidden');
    fetch(api(`/api/deployment/ios-cert-check?app=${encodeURIComponent(appId)}&flavor=prod`))
        .then(r => r.json())
        .then(result => {
            if (typeof window.setCachedCertCheck === 'function') window.setCachedCertCheck(appId, result);
            if (currentSelectedApp === appId && currentCommand && currentCommand.platform === 'ios' && currentCommand.flavor === 'prod') {
                renderCertBannerFromResult(result, bannerEl);
            }
        })
        .catch(() => {});
}

export function renderCertBannerFromResult(result, bannerEl) {
    if (!bannerEl || !result || !result.success || result.status === 'not_ios_app') {
        if (bannerEl) bannerEl.classList.add('hidden');
        return;
    }
    const cert = result.certificate || {};
    const profile = result.provisioningProfile || {};
    const worst = [cert, profile].reduce((a, b) => (SEVERITY_RANK[b.status] || 0) > (SEVERITY_RANK[a.status] || 0) ? b : a, { status: 'unknown' });
    if (worst.status === 'unknown' || worst.status === 'ok') {
        bannerEl.classList.add('hidden');
        return;
    }
    const label = worst.status === 'expired' ? 'EXPIRED' : 'expiring soon';
    const expiresOn = worst.expiresOn ? ` (${escapeHtml(worst.expiresOn)})` : '';
    const bestEffort = worst.bestEffort ? ' — from last build, best-effort' : '';
    bannerEl.dataset.status = worst.status;
    bannerEl.textContent = `⚠️ Prod cert/profile ${label}${expiresOn}${bestEffort}`;
    bannerEl.classList.remove('hidden');
}
