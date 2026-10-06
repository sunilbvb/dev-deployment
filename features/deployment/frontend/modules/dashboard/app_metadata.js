/**
 * app_metadata.js — Store Metadata & Localized Release Notes Previewer
 * Real-time character counting against store policies (Play Store 500-char limit)
 * and visual update card mockup.
 */

const metadataState = {
    appId: null,
    platform: 'android',
    locale: 'en-US',
    data: null,
};

function openMetadataModal(appId = null) {
    metadataState.appId = appId || (window.state && window.state.selectedApp) || '';
    const overlay = document.getElementById('storeMetadataOverlay');
    if (overlay) overlay.classList.add('ui-active');
    const subtitle = document.getElementById('storeMetadataSubtitle');
    if (subtitle) {
        subtitle.textContent = metadataState.appId ? `Managing Store Metadata for App: ${metadataState.appId}` : 'Store Metadata Management';
    }
    loadStoreMetadata();
}

function closeMetadataModal() {
    const overlay = document.getElementById('storeMetadataOverlay');
    if (overlay) overlay.classList.remove('ui-active');
}

async function loadStoreMetadata() {
    const appId = metadataState.appId || (window.state && window.state.selectedApp) || '';
    const qApp = appId ? `app=${encodeURIComponent(appId)}` : '';
    const url = (typeof api === 'function') ? api(`/api/deployment/metadata?${qApp}`) : `/api/deployment/metadata?${qApp}`;
    const token = window.__DEPLOYMENT_TOKEN__ || '';
    const headers = token ? { 'X-API-Token': token } : {};

    try {
        const res = await fetch(url, { headers });
        const data = await res.json();
        metadataState.data = data;
        renderMetadataEditor();
    } catch (err) {
        if (typeof showToast === 'function') showToast('Failed to load metadata: ' + err.message);
    }
}

function renderMetadataEditor() {
    const data = metadataState.data;
    if (!data) return;

    const platform = metadataState.platform;
    const locale = metadataState.locale;
    const platformData = data[platform] || {};
    const localesObj = platformData.locales || {};
    const currentMeta = localesObj[locale] || localesObj['en-US'] || {};

    const notesText = platform === 'android' ? (currentMeta.changelog || '') : (currentMeta.releaseNotes || '');
    const titleText = platform === 'android' ? (currentMeta.title || '') : (currentMeta.name || '');
    const limit = platform === 'android' ? 500 : 4000;

    const textarea = document.getElementById('metaNotesTextarea');
    const titleInput = document.getElementById('metaTitleInput');
    const charCounter = document.getElementById('metaCharCounter');
    const previewWhatsNew = document.getElementById('metaPreviewWhatsNew');
    const previewTitle = document.getElementById('metaPreviewTitle');

    if (textarea) textarea.value = notesText;
    if (titleInput) titleInput.value = titleText;

    updateCharCountDisplay(notesText.length, limit);

    if (previewWhatsNew) previewWhatsNew.textContent = notesText || 'Bug fixes and performance improvements.';
    if (previewTitle) previewTitle.textContent = titleText || (metadataState.appId || 'My App');
}

function updateCharCountDisplay(len, limit) {
    const counter = document.getElementById('metaCharCounter');
    if (!counter) return;

    counter.textContent = `${len} / ${limit} characters`;
    if (len > limit) {
        counter.style.color = '#ef4444';
        counter.style.fontWeight = '700';
    } else {
        counter.style.color = 'var(--ui-text-muted)';
        counter.style.fontWeight = 'normal';
    }
}

async function saveCurrentMetadata() {
    const textarea = document.getElementById('metaNotesTextarea');
    const titleInput = document.getElementById('metaTitleInput');
    const saveBtn = document.getElementById('saveMetadataBtn');

    const notes = textarea ? textarea.value : '';
    const title = titleInput ? titleInput.value : '';
    const appId = metadataState.appId || (window.state && window.state.selectedApp) || '';

    if (saveBtn) saveBtn.disabled = true;

    try {
        const url = (typeof api === 'function') ? api('/api/deployment/metadata/save') : '/api/deployment/metadata/save';
        const token = window.__DEPLOYMENT_TOKEN__ || '';
        const headers = {
            'Content-Type': 'application/json',
            ...(token ? { 'X-API-Token': token } : {}),
        };

        const res = await fetch(url, {
            method: 'POST',
            headers,
            body: jsonPayload({
                app: appId,
                platform: metadataState.platform,
                locale: metadataState.locale,
                releaseNotes: notes,
                title: title,
            }),
        });
        const data = await res.json();
        if (data.success) {
            if (typeof showToast === 'function') showToast(`✅ Metadata saved for ${metadataState.platform} (${metadataState.locale})`);
            await loadStoreMetadata();
        } else {
            throw new Error(data.error || 'Failed to save');
        }
    } catch (err) {
        if (typeof showToast === 'function') showToast('❌ ' + err.message);
    } finally {
        if (saveBtn) saveBtn.disabled = false;
    }
}

function jsonPayload(obj) {
    return JSON.stringify(obj);
}

document.addEventListener('DOMContentLoaded', () => {
    const openBtn = document.getElementById('openMetadataBtn');
    if (openBtn) openBtn.addEventListener('click', () => openMetadataModal());
    const closeBtn = document.getElementById('closeMetadataBtn');
    if (closeBtn) closeBtn.addEventListener('click', closeMetadataModal);
    const saveBtn = document.getElementById('saveMetadataBtn');
    if (saveBtn) saveBtn.addEventListener('click', saveCurrentMetadata);

    const platformSelect = document.getElementById('metaPlatformSelect');
    if (platformSelect) {
        platformSelect.addEventListener('change', (e) => {
            metadataState.platform = e.target.value;
            renderMetadataEditor();
        });
    }

    const localeSelect = document.getElementById('metaLocaleSelect');
    if (localeSelect) {
        localeSelect.addEventListener('change', (e) => {
            metadataState.locale = e.target.value;
            renderMetadataEditor();
        });
    }

    const textarea = document.getElementById('metaNotesTextarea');
    if (textarea) {
        textarea.addEventListener('input', (e) => {
            const limit = metadataState.platform === 'android' ? 500 : 4000;
            updateCharCountDisplay(e.target.value.length, limit);
            const previewWhatsNew = document.getElementById('metaPreviewWhatsNew');
            if (previewWhatsNew) previewWhatsNew.textContent = e.target.value || 'Bug fixes and performance improvements.';
        });
    }

    const titleInput = document.getElementById('metaTitleInput');
    if (titleInput) {
        titleInput.addEventListener('input', (e) => {
            const previewTitle = document.getElementById('metaPreviewTitle');
            if (previewTitle) previewTitle.textContent = e.target.value || (metadataState.appId || 'My App');
        });
    }
});
