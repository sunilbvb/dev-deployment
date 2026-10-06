/**
 * app_version_bump.js — Semantic Version Bumper & Git Conventional Commit Changelog
 * Safely edits pubspec.yaml version numbers and formats git commit history into
 * Markdown changelogs and concise Play Store release notes.
 */

const versionState = {
    appId: null,
    data: null,
    changelog: null,
};

function openVersionModal(appId = null) {
    versionState.appId = appId || (window.state && window.state.selectedApp) || '';
    const overlay = document.getElementById('versionBumperOverlay');
    if (overlay) overlay.classList.add('ui-active');
    const subtitle = document.getElementById('versionBumperSubtitle');
    if (subtitle) {
        subtitle.textContent = versionState.appId ? `App: ${versionState.appId}` : 'Workspace Version & Git Changelog';
    }
    loadVersionData();
    loadChangelogData();
}

function closeVersionModal() {
    const overlay = document.getElementById('versionBumperOverlay');
    if (overlay) overlay.classList.remove('ui-active');
}

async function loadVersionData() {
    const currBadge = document.getElementById('versionCurrentBadge');
    if (currBadge) currBadge.textContent = 'Loading...';

    const appId = versionState.appId || (window.state && window.state.selectedApp) || '';
    const qApp = appId ? `app=${encodeURIComponent(appId)}` : '';
    const url = (typeof api === 'function') ? api(`/api/deployment/version?${qApp}`) : `/api/deployment/version?${qApp}`;
    const token = window.__DEPLOYMENT_TOKEN__ || '';
    const headers = token ? { 'X-API-Token': token } : {};

    try {
        const res = await fetch(url, { headers });
        const data = await res.json();
        versionState.data = data;
        renderVersionCard(data);
    } catch (err) {
        if (currBadge) currBadge.textContent = 'Error loading version';
    }
}

function renderVersionCard(data) {
    const currBadge = document.getElementById('versionCurrentBadge');
    const previewPatch = document.getElementById('versionPreviewPatch');
    const previewMinor = document.getElementById('versionPreviewMinor');
    const previewMajor = document.getElementById('versionPreviewMajor');
    const previewBuild = document.getElementById('versionPreviewBuild');

    if (currBadge && data.current) {
        currBadge.textContent = `v${data.current.raw || '1.0.0+1'}`;
    }
    if (data.previews) {
        if (previewPatch) previewPatch.textContent = `→ ${data.previews.patch}`;
        if (previewMinor) previewMinor.textContent = `→ ${data.previews.minor}`;
        if (previewMajor) previewMajor.textContent = `→ ${data.previews.major}`;
        if (previewBuild) previewBuild.textContent = `→ ${data.previews.build}`;
    }
}

async function triggerVersionBump(bumpType) {
    const appId = versionState.appId || (window.state && window.state.selectedApp) || '';
    const url = (typeof api === 'function') ? api('/api/deployment/version/bump') : '/api/deployment/version/bump';
    const token = window.__DEPLOYMENT_TOKEN__ || '';
    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { 'X-API-Token': token } : {}),
    };

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers,
            body: JSON.stringify({ app: appId, bumpType: bumpType }),
        });
        const data = await res.json();
        if (data.success) {
            if (typeof showToast === 'function') {
                showToast(`🚀 Version bumped: ${data.oldVersion} → ${data.newVersion}`);
            }
            await loadVersionData();
        } else {
            throw new Error(data.error || 'Failed to bump version');
        }
    } catch (err) {
        if (typeof showToast === 'function') showToast('❌ ' + err.message);
    }
}

async function loadChangelogData() {
    const changelogContainer = document.getElementById('versionChangelogContent');
    const notesContainer = document.getElementById('versionStoreNotesPreview');
    if (changelogContainer) changelogContainer.textContent = 'Generating changelog from git commits...';

    const appId = versionState.appId || (window.state && window.state.selectedApp) || '';
    const qApp = appId ? `app=${encodeURIComponent(appId)}` : '';
    const url = (typeof api === 'function') ? api(`/api/deployment/version/changelog?${qApp}`) : `/api/deployment/version/changelog?${qApp}`;
    const token = window.__DEPLOYMENT_TOKEN__ || '';
    const headers = token ? { 'X-API-Token': token } : {};

    try {
        const res = await fetch(url, { headers });
        const data = await res.json();
        versionState.changelog = data;

        if (changelogContainer) changelogContainer.textContent = data.markdownChangelog || 'No recent commits found.';
        if (notesContainer) notesContainer.textContent = data.storeNotes || '• Bug fixes and performance improvements.';
    } catch (err) {
        if (changelogContainer) changelogContainer.textContent = 'Error: ' + err.message;
    }
}

function copyChangelogText(text) {
    navigator.clipboard.writeText(text).then(() => {
        if (typeof showToast === 'function') showToast('📋 Copied to clipboard!');
    }).catch(() => {
        if (typeof showToast === 'function') showToast('Failed to copy.');
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const openBtn = document.getElementById('openVersionBtn');
    if (openBtn) openBtn.addEventListener('click', () => openVersionModal());
    const closeBtn = document.getElementById('closeVersionBtn');
    if (closeBtn) closeBtn.addEventListener('click', closeVersionModal);

    const btnPatch = document.getElementById('bumpPatchBtn');
    if (btnPatch) btnPatch.addEventListener('click', () => triggerVersionBump('patch'));
    const btnMinor = document.getElementById('bumpMinorBtn');
    if (btnMinor) btnMinor.addEventListener('click', () => triggerVersionBump('minor'));
    const btnMajor = document.getElementById('bumpMajorBtn');
    if (btnMajor) btnMajor.addEventListener('click', () => triggerVersionBump('major'));
    const btnBuild = document.getElementById('bumpBuildBtn');
    if (btnBuild) btnBuild.addEventListener('click', () => triggerVersionBump('build'));

    const copyNotesBtn = document.getElementById('copyStoreNotesBtn');
    if (copyNotesBtn) {
        copyNotesBtn.addEventListener('click', () => {
            const notes = document.getElementById('versionStoreNotesPreview');
            if (notes) copyChangelogText(notes.textContent);
        });
    }

    const copyMarkdownBtn = document.getElementById('copyMarkdownChangelogBtn');
    if (copyMarkdownBtn) {
        copyMarkdownBtn.addEventListener('click', () => {
            const md = document.getElementById('versionChangelogContent');
            if (md) copyChangelogText(md.textContent);
        });
    }
});
