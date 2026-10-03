/**
 * app_cache_warmer.js — Smart Silent Cache Warmer Module
 * Handles:
 * 1. Navbar badge status monitoring (idle/warming/warm/error)
 * 2. Background dependency pre-fetch trigger (flutter pub get)
 * 3. 30s auto-refresh polling
 */

async function refreshCacheWarmerStatus() {
    try {
        const res = await fetch(api('/api/deployment/cache-warmer/status'));
        const data = await res.json();
        if (data.success && els.cacheWarmerBadgeText) {
            const st = data.status || 'idle';
            if (st === 'warming') {
                els.cacheWarmerBadgeText.textContent = 'Cache: Warming...';
            } else if (st === 'warm') {
                els.cacheWarmerBadgeText.textContent = `Cache: Warm (${data.lastBranch || 'main'})`;
            } else if (st === 'error') {
                els.cacheWarmerBadgeText.textContent = 'Cache: Error';
            } else {
                els.cacheWarmerBadgeText.textContent = 'Cache: Idle';
            }
        }
    } catch (_) {}
}

async function triggerCacheWarmer() {
    showToast('Starting silent background dependency pre-fetch...');
    try {
        const res = await fetch(api('/api/deployment/cache-warmer/warm'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({force: true}),
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Dependencies warmed in ${data.durationSeconds}s!`, 'success');
            refreshCacheWarmerStatus();
        } else {
            showToast(data.error || 'Cache warming failed', 'error');
        }
    } catch (err) {
        showToast(`Cache warmer error: ${err.message}`, 'error');
    }
}

// ═════════════════════════════════════════════════════════════════════
// Wire Events
// ═════════════════════════════════════════════════════════════════════
if (els.cacheWarmerHeaderBadge) {
    els.cacheWarmerHeaderBadge.addEventListener('click', triggerCacheWarmer);
}
refreshCacheWarmerStatus();
setInterval(refreshCacheWarmerStatus, 30000);

// Global exports
window.refreshCacheWarmerStatus = refreshCacheWarmerStatus;
window.triggerCacheWarmer = triggerCacheWarmer;
