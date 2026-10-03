/**
 * GitHub Actions Hybrid Cloud CI Setup Module.
 * Manages GitHub PAT, detected repository, and workflow template installation.
 */

async function loadGitHubConfig() {
    const repoInput = document.getElementById('cfgGithubRepo');
    const tokenBadge = document.getElementById('githubTokenBadge');
    const wfBadge = document.getElementById('githubWfBadge');
    const branchBadge = document.getElementById('githubBranchBadge');

    try {
        const res = await fetch(api('/api/deployment/github/status')).then(r => r.json());
        if (!res || !res.success) return;

        if (repoInput && !repoInput.value) {
            repoInput.value = res.repo || '';
        }
        if (branchBadge) {
            branchBadge.textContent = res.branch || 'develop';
        }
        if (tokenBadge) {
            if (res.tokenConfigured) {
                tokenBadge.dataset.variant = 'success';
                tokenBadge.textContent = `Configured (${res.tokenMasked || '✓'})`;
            } else {
                tokenBadge.dataset.variant = 'warning';
                tokenBadge.textContent = 'Missing Token';
            }
        }
        if (wfBadge) {
            if (res.workflowExists) {
                wfBadge.dataset.variant = 'success';
                wfBadge.textContent = `Installed (${res.workflowFile})`;
            } else {
                wfBadge.dataset.variant = 'neutral';
                wfBadge.textContent = 'Not Installed';
            }
        }
    } catch (err) {
        console.error('Failed to load GitHub config:', err);
    }
}

async function saveGitHubConfig() {
    const repoInput = document.getElementById('cfgGithubRepo');
    const tokenInput = document.getElementById('cfgGithubToken');
    const token = tokenInput ? tokenInput.value.trim() : '';
    const repo = repoInput ? repoInput.value.trim() : '';

    try {
        const payload = {};
        if (token) payload.token = token;
        if (repo) payload.repo = repo;

        const res = await fetch(api('/api/deployment/github/config'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }).then(r => r.json());

        if (res.success) {
            if (tokenInput) tokenInput.value = '';
            showToast('GitHub Cloud CI settings saved!');
            loadGitHubConfig();
        } else {
            showToast('Failed to save GitHub settings: ' + (res.error || 'unknown'), 'error');
        }
    } catch (err) {
        showToast('Error saving GitHub settings', 'error');
    }
}

async function installGitHubWorkflow() {
    try {
        const res = await fetch(api('/api/deployment/github/install-template'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        }).then(r => r.json());

        if (res.success) {
            showToast(res.message || 'Workflow template installed!');
            loadGitHubConfig();
        } else {
            showToast('Failed to install workflow: ' + (res.error || 'unknown'), 'error');
        }
    } catch (err) {
        showToast('Error installing workflow template', 'error');
    }
}

function initGitHubSetup() {
    const saveBtn = document.getElementById('saveGithubConfigBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveGitHubConfig);
    }
    const installBtn = document.getElementById('installGithubWfBtn');
    if (installBtn) {
        installBtn.addEventListener('click', installGitHubWorkflow);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGitHubSetup);
} else {
    initGitHubSetup();
}

window.loadGitHubConfig = loadGitHubConfig;
window.saveGitHubConfig = saveGitHubConfig;
window.installGitHubWorkflow = installGitHubWorkflow;
