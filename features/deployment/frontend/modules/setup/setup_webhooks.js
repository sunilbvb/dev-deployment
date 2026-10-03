/**
 * setup_webhooks.js — Setup Webhooks Module
 * Manages outgoing multi-channel notification webhooks (Slack, Discord, MS Teams, WhatsApp, Google Chat, Custom HTTP)
 * and incoming webhook execution snippets (cURL, GitHub Actions, GitLab CI, Slack slash commands).
 */

async function postJson(url, body) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return res.json();
}
window.postJson = postJson;

async function runWebhookTest() {
    if (!setupEls.testWebhookBtn) return;
    const appUrl = setupEls.webhookUrl ? setupEls.webhookUrl.value.trim() : '';
    const wsUrl = setupEls.wsWebhookUrl ? setupEls.wsWebhookUrl.value.trim() : '';
    const url = appUrl || wsUrl;
    if (!url) {
        showToast('Please enter a Webhook URL (app or workspace) to test.', 'warning');
        return;
    }
    const provider = appUrl ? setupEls.webhookProvider.value : setupEls.wsWebhookProvider.value;
    setupEls.testWebhookBtn.disabled = true;
    setupEls.testWebhookBtn.querySelector('span').textContent = 'Testing...';
    if (setupEls.testWebhookResult) {
        setupEls.testWebhookResult.style.display = 'block';
        setupEls.testWebhookResult.dataset.status = 'unknown';
        setupEls.testWebhookResult.textContent = 'Posting test notification card...';
    }

    try {
        const res = await postJson('/api/deployment/notifications/test', {
            url,
            provider,
            app: setupState.selectedAppId || '',
        });
        if (res.success) {
            if (setupEls.testWebhookResult) {
                setupEls.testWebhookResult.dataset.status = 'valid';
                setupEls.testWebhookResult.innerHTML = `✅ Delivered to <strong>${escapeHtml((res.provider || provider).toUpperCase())}</strong> (HTTP ${res.statusCode})! Check your channel.`;
            }
            showToast('✅ Webhook test card delivered!');
        } else {
            if (setupEls.testWebhookResult) {
                setupEls.testWebhookResult.dataset.status = 'error';
                setupEls.testWebhookResult.innerHTML = `❌ Delivery failed: ${escapeHtml(res.error || ('HTTP ' + res.statusCode))}`;
            }
            showToast('Webhook test failed: ' + (res.error || 'HTTP error'));
        }
    } catch (err) {
        if (setupEls.testWebhookResult) {
            setupEls.testWebhookResult.dataset.status = 'error';
            setupEls.testWebhookResult.innerHTML = `❌ Network error: ${escapeHtml(err.message)}`;
        }
        showToast('Network error: ' + err.message);
    } finally {
        setupEls.testWebhookBtn.disabled = false;
        setupEls.testWebhookBtn.querySelector('span').textContent = 'Test Webhook';
    }
}

function getProviderBadgeVariant(provider) {
    switch ((provider || '').toLowerCase()) {
        case 'slack': return 'primary';
        case 'discord': return 'info';
        case 'teams': return 'primary';
        case 'google_chat': return 'success';
        case 'whatsapp': return 'success';
        case 'custom': return 'warning';
        default: return 'secondary';
    }
}

function getProviderDisplayName(provider) {
    switch ((provider || '').toLowerCase()) {
        case 'slack': return 'Slack';
        case 'discord': return 'Discord';
        case 'teams': return 'MS Teams';
        case 'google_chat': return 'Google Chat';
        case 'whatsapp': return 'WhatsApp';
        case 'custom': return 'Custom Template';
        case 'generic': return 'Generic JSON';
        default: return 'Auto-Detect';
    }
}

function renderWebhookChannels() {
    if (!setupEls.webhookChannelsList) return;
    const channels = setupState.currentWebhooks || [];
    if (setupEls.webhookChannelsCountBadge) {
        setupEls.webhookChannelsCountBadge.textContent = `${channels.length} Channel${channels.length === 1 ? '' : 's'}`;
    }

    if (channels.length === 0) {
        setupEls.webhookChannelsList.innerHTML = `
            <div style="padding: 14px; text-align: center; background: rgba(0,0,0,0.02); border: 1px dashed var(--ui-border-color); border-radius: 6px; font-size: 0.82rem; color: var(--ui-text-muted);">
                <span>No webhook channels configured yet. Click <strong>+ Add Channel</strong> to broadcast deployment notifications to Slack, Discord, WhatsApp, Teams, Google Chat, or custom HTTP templates simultaneously.</span>
            </div>
        `;
        return;
    }

    setupEls.webhookChannelsList.innerHTML = channels.map((ch, idx) => {
        const providerName = getProviderDisplayName(ch.provider);
        const badgeVariant = getProviderBadgeVariant(ch.provider);
        const name = escapeHtml(ch.name || `Channel #${idx + 1}`);
        const url = escapeHtml(ch.url || '');
        const isEnabled = ch.enabled !== false;
        const successBadge = ch.notify_on_success !== false ? '<span class="ui-badge" data-variant="success" style="font-size:0.65rem;">✅ Success</span>' : '';
        const failBadge = ch.notify_on_failure !== false ? '<span class="ui-badge" data-variant="error" style="font-size:0.65rem;">❌ Failure</span>' : '';
        const disabledBadge = !isEnabled ? '<span class="ui-badge" data-variant="secondary" style="font-size:0.65rem;">Disabled</span>' : '';
        const phoneBadge = ch.phone ? `<span class="ui-badge" data-variant="info" style="font-size:0.65rem;">📱 ${escapeHtml(ch.phone)}</span>` : '';

        return `
            <div class="ui-card" style="padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 0;">
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
                        <strong style="font-size: 0.88rem; color: var(--ui-text-primary);">${name}</strong>
                        <span class="ui-badge" data-variant="${badgeVariant}">${providerName}</span>
                        ${successBadge}
                        ${failBadge}
                        ${phoneBadge}
                        ${disabledBadge}
                    </div>
                    <div style="font-size: 0.76rem; color: var(--ui-text-muted); font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${url}
                    </div>
                </div>
                <div style="display: flex; gap: 6px; align-items: center; flex-shrink: 0;">
                    <button type="button" class="ui-button" data-variant="secondary" data-size="xs" data-action="test-channel" data-idx="${idx}" title="Test Channel">
                        <i data-lucide="send"></i>
                        <span>Test</span>
                    </button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-action="edit-channel" data-idx="${idx}" title="Edit Channel">
                        <i data-lucide="edit-2"></i>
                        <span>Edit</span>
                    </button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-action="delete-channel" data-idx="${idx}" title="Delete Channel" style="color: var(--ui-danger, #ef4444);">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
}

function syncChannelModalProviderSections() {
    const provider = setupEls.channelModalProvider ? setupEls.channelModalProvider.value : 'auto';
    if (setupEls.channelModalWhatsAppSection) {
        setupEls.channelModalWhatsAppSection.style.display = provider === 'whatsapp' ? 'block' : 'none';
    }
    if (setupEls.channelModalCustomSection) {
        setupEls.channelModalCustomSection.style.display = (provider === 'custom' || provider === 'generic') ? 'block' : 'none';
    }
}

function openWebhookChannelModal(idx = null) {
    if (!setupEls.webhookChannelModal) return;
    const channels = setupState.currentWebhooks || [];
    const isEdit = idx !== null && channels[idx];
    const ch = isEdit ? channels[idx] : null;

    if (setupEls.channelModalId) setupEls.channelModalId.value = isEdit ? String(idx) : '';
    if (setupEls.channelModalTitle) setupEls.channelModalTitle.textContent = isEdit ? 'Edit Webhook Channel' : 'Add Webhook Channel';
    if (setupEls.channelModalName) setupEls.channelModalName.value = ch ? (ch.name || '') : '';
    if (setupEls.channelModalUrl) setupEls.channelModalUrl.value = ch ? (ch.url || '') : '';
    if (setupEls.channelModalProvider) setupEls.channelModalProvider.value = ch ? (ch.provider || 'auto') : 'auto';
    if (setupEls.channelModalPhone) setupEls.channelModalPhone.value = ch ? (ch.phone || '') : '';
    if (setupEls.channelModalTemplate) setupEls.channelModalTemplate.value = ch ? (ch.custom_template || '') : '';

    if (setupEls.channelModalHeaders) {
        if (ch && ch.custom_headers) {
            if (typeof ch.custom_headers === 'object') {
                setupEls.channelModalHeaders.value = Object.entries(ch.custom_headers).map(([k, v]) => `${k}: ${v}`).join('\n');
            } else {
                setupEls.channelModalHeaders.value = String(ch.custom_headers);
            }
        } else {
            setupEls.channelModalHeaders.value = '';
        }
    }

    if (setupEls.channelModalSuccess) setupEls.channelModalSuccess.checked = ch ? ch.notify_on_success !== false : true;
    if (setupEls.channelModalFailure) setupEls.channelModalFailure.checked = ch ? ch.notify_on_failure !== false : true;
    if (setupEls.channelModalEnabled) setupEls.channelModalEnabled.checked = ch ? ch.enabled !== false : true;

    if (setupEls.channelModalTestFeedback) {
        setupEls.channelModalTestFeedback.style.display = 'none';
    }

    syncChannelModalProviderSections();
    setupEls.webhookChannelModal.classList.add('ui-active');
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
}

function closeWebhookChannelModal() {
    if (!setupEls.webhookChannelModal) return;
    setupEls.webhookChannelModal.classList.remove('ui-active');
}

function parseHeadersFromInput(text) {
    const raw = (text || '').trim();
    if (!raw) return null;
    if (raw.startsWith('{')) {
        try { return JSON.parse(raw); } catch (e) {}
    }
    const headers = {};
    raw.split('\n').forEach(line => {
        const colon = line.indexOf(':');
        if (colon > 0) {
            const k = line.substring(0, colon).trim();
            const v = line.substring(colon + 1).trim();
            if (k) headers[k] = v;
        }
    });
    return Object.keys(headers).length > 0 ? headers : null;
}

function saveWebhookChannel() {
    const url = setupEls.channelModalUrl ? setupEls.channelModalUrl.value.trim() : '';
    if (!url) {
        showToast('Webhook destination URL is required.', 'warning');
        return;
    }

    const provider = setupEls.channelModalProvider ? setupEls.channelModalProvider.value : 'auto';
    const name = (setupEls.channelModalName ? setupEls.channelModalName.value.trim() : '') || `${getProviderDisplayName(provider)} Channel`;
    const phone = setupEls.channelModalPhone ? setupEls.channelModalPhone.value.trim() : '';
    const template = setupEls.channelModalTemplate ? setupEls.channelModalTemplate.value.trim() : '';
    const headers = parseHeadersFromInput(setupEls.channelModalHeaders ? setupEls.channelModalHeaders.value : '');
    const notifyOnSuccess = setupEls.channelModalSuccess ? setupEls.channelModalSuccess.checked : true;
    const notifyOnFailure = setupEls.channelModalFailure ? setupEls.channelModalFailure.checked : true;
    const enabled = setupEls.channelModalEnabled ? setupEls.channelModalEnabled.checked : true;

    const channelObj = {
        name,
        url,
        provider,
        notify_on_success: notifyOnSuccess,
        notify_on_failure: notifyOnFailure,
        enabled,
    };
    if (phone) channelObj.phone = phone;
    if (template) channelObj.custom_template = template;
    if (headers) channelObj.custom_headers = headers;

    if (!Array.isArray(setupState.currentWebhooks)) {
        setupState.currentWebhooks = [];
    }

    const idVal = setupEls.channelModalId ? setupEls.channelModalId.value : '';
    if (idVal !== '') {
        const idx = parseInt(idVal, 10);
        if (!isNaN(idx) && idx >= 0 && idx < setupState.currentWebhooks.length) {
            setupState.currentWebhooks[idx] = channelObj;
        } else {
            setupState.currentWebhooks.push(channelObj);
        }
    } else {
        setupState.currentWebhooks.push(channelObj);
    }

    renderWebhookChannels();
    closeWebhookChannelModal();
    showToast(`Saved channel "${name}"`);
}

async function testModalWebhookChannel() {
    const url = setupEls.channelModalUrl ? setupEls.channelModalUrl.value.trim() : '';
    if (!url) {
        showToast('Enter a destination URL to test.', 'warning');
        return;
    }

    const provider = setupEls.channelModalProvider ? setupEls.channelModalProvider.value : 'auto';
    const phone = setupEls.channelModalPhone ? setupEls.channelModalPhone.value.trim() : '';
    const customTemplate = setupEls.channelModalTemplate ? setupEls.channelModalTemplate.value.trim() : '';
    const customHeaders = parseHeadersFromInput(setupEls.channelModalHeaders ? setupEls.channelModalHeaders.value : '');

    const btn = setupEls.channelModalTestBtn;
    const fb = setupEls.channelModalTestFeedback;

    if (btn) {
        btn.disabled = true;
        btn.querySelector('span').textContent = 'Testing...';
    }
    if (fb) {
        fb.style.display = 'block';
        fb.dataset.status = 'unknown';
        fb.textContent = 'Sending test notification...';
    }

    try {
        const res = await postJson('/api/deployment/notifications/test', {
            url,
            provider,
            app: setupState.selectedAppId || '',
            custom_template: customTemplate,
            custom_headers: customHeaders,
            phone,
        });

        if (res.success) {
            if (fb) {
                fb.dataset.status = 'valid';
                fb.innerHTML = `✅ Delivered to <strong>${escapeHtml((res.provider || provider).toUpperCase())}</strong> (HTTP ${res.statusCode})!`;
            }
            showToast('✅ Webhook channel test succeeded!');
        } else {
            if (fb) {
                fb.dataset.status = 'error';
                fb.innerHTML = `❌ Failed: ${escapeHtml(res.error || ('HTTP ' + res.statusCode))}`;
            }
            showToast('Channel test failed: ' + (res.error || 'HTTP error'), 'warning');
        }
    } catch (err) {
        if (fb) {
            fb.dataset.status = 'error';
            fb.innerHTML = `❌ Network error: ${escapeHtml(err.message)}`;
        }
        showToast('Network error: ' + err.message, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.querySelector('span').textContent = 'Test Channel';
        }
    }
}

async function testIndividualChannel(idx) {
    const ch = (setupState.currentWebhooks || [])[idx];
    if (!ch || !ch.url) {
        showToast('Invalid channel configuration', 'warning');
        return;
    }
    showToast(`Testing "${ch.name || ch.url}"...`);
    try {
        const res = await postJson('/api/deployment/notifications/test', {
            url: ch.url,
            provider: ch.provider || 'auto',
            app: setupState.selectedAppId || '',
            custom_template: ch.custom_template || '',
            custom_headers: ch.custom_headers || null,
            phone: ch.phone || '',
        });
        if (res.success) {
            showToast(`✅ "${ch.name || 'Channel'}" delivered successfully (HTTP ${res.statusCode})!`);
        } else {
            showToast(`❌ Test failed: ${res.error || ('HTTP ' + res.statusCode)}`, 'warning');
        }
    } catch (err) {
        showToast(`❌ Error: ${err.message}`, 'error');
    }
}

let activeSnippetTab = 'curl';

function updateIncomingWebhookSnippets(tab = activeSnippetTab) {
    activeSnippetTab = tab;
    const appId = setupState.selectedAppId || 'my_app';
    const baseUrl = `${window.location.origin}/api/deployment/webhook/incoming`;
    if (setupEls.incomingWebhookUrlDisplay) {
        setupEls.incomingWebhookUrlDisplay.value = baseUrl;
    }

    if (!setupEls.incomingWebhookSnippetCode) return;

    let snippet = '';
    switch (tab) {
        case 'curl':
            snippet = `# Trigger standard build command via cURL:\ncurl -X POST "${baseUrl}" \\\n  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \\\n  -H "Content-Type: application/json" \\\n  -d '{"app": "${appId}", "flavor": "prod", "templateId": "build_aab"}'`;
            break;
        case 'pipeline':
            snippet = `# Trigger an automated multi-step pipeline:\ncurl -X POST "${baseUrl}" \\\n  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \\\n  -H "Content-Type: application/json" \\\n  -d '{"app": "${appId}", "pipeline": "full_release", "flavor": "prod"}'`;
            break;
        case 'github':
            snippet = `# In GitHub Actions Workflow (.github/workflows/deploy.yml):\n- name: Trigger Deploy Pipeline\n  run: |\n    curl -s -X POST "${baseUrl}" \\\n      -H "X-Webhook-Secret: \${{ secrets.WEBHOOK_SECRET }}" \\\n      -H "Content-Type: application/json" \\\n      -d '{"app": "${appId}", "pipeline": "full_release"}'`;
            break;
        case 'gitlab':
            snippet = `# In GitLab CI (.gitlab-ci.yml):\ndeploy_step:\n  script:\n    - 'curl -s -X POST "${baseUrl}" -H "X-Gitlab-Token: $WEBHOOK_SECRET" -H "Content-Type: application/json" -d "{\\"app\\": \\"${appId}\\", \\"flavor\\": \\"prod\\", \\"templateId\\": \\"build_aab\\"}"'`;
            break;
        case 'slack':
            snippet = `# Slack Slash Command Integration (/deploy):\n# Request URL: ${baseUrl}\n# Method: POST\n# Usage in Slack:\n/deploy ${appId} prod build_aab\n# Or to trigger pipeline:\n/deploy pipeline full_release ${appId}`;
            break;
        default:
            snippet = `curl -X POST "${baseUrl}" -H "X-Webhook-Secret: $WEBHOOK_SECRET" -d '{"app": "${appId}"}'`;
    }

    setupEls.incomingWebhookSnippetCode.textContent = snippet;
}

// Wire Webhook Events
if (setupEls.testWebhookBtn) {
    setupEls.testWebhookBtn.addEventListener('click', runWebhookTest);
}
if (setupEls.openAddWebhookChannelBtn) {
    setupEls.openAddWebhookChannelBtn.addEventListener('click', () => openWebhookChannelModal(null));
}
if (setupEls.closeWebhookChannelModalBtn) {
    setupEls.closeWebhookChannelModalBtn.addEventListener('click', closeWebhookChannelModal);
}
if (setupEls.cancelWebhookChannelBtn) {
    setupEls.cancelWebhookChannelBtn.addEventListener('click', closeWebhookChannelModal);
}
if (setupEls.saveWebhookChannelBtn) {
    setupEls.saveWebhookChannelBtn.addEventListener('click', saveWebhookChannel);
}
if (setupEls.channelModalTestBtn) {
    setupEls.channelModalTestBtn.addEventListener('click', testModalWebhookChannel);
}
if (setupEls.channelModalProvider) {
    setupEls.channelModalProvider.addEventListener('change', syncChannelModalProviderSections);
}

if (setupEls.webhookChannelsList) {
    setupEls.webhookChannelsList.addEventListener('click', e => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        const idx = parseInt(btn.dataset.idx, 10);
        if (isNaN(idx)) return;

        if (action === 'test-channel') {
            testIndividualChannel(idx);
        } else if (action === 'edit-channel') {
            openWebhookChannelModal(idx);
        } else if (action === 'delete-channel') {
            const ch = (setupState.currentWebhooks || [])[idx];
            if (confirm(`Remove webhook channel "${ch ? (ch.name || 'Channel') : 'Channel'}"?`)) {
                setupState.currentWebhooks.splice(idx, 1);
                renderWebhookChannels();
                showToast('Channel removed');
            }
        }
    });
}

document.querySelectorAll('.template-chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tag = btn.dataset.tag;
        if (!tag || !setupEls.channelModalTemplate) return;
        const textarea = setupEls.channelModalTemplate;
        const start = textarea.selectionStart || 0;
        const end = textarea.selectionEnd || 0;
        const val = textarea.value;
        textarea.value = val.substring(0, start) + tag + val.substring(end);
        textarea.focus();
        textarea.selectionStart = textarea.selectionEnd = start + tag.length;
    });
});

if (setupEls.incomingWebhookSnippetTabs) {
    setupEls.incomingWebhookSnippetTabs.addEventListener('click', e => {
        const btn = e.target.closest('button[data-snippet-tab]');
        if (!btn) return;
        setupEls.incomingWebhookSnippetTabs.querySelectorAll('button').forEach(b => {
            b.dataset.variant = 'secondary';
        });
        btn.dataset.variant = 'primary';
        updateIncomingWebhookSnippets(btn.dataset.snippetTab);
    });
}

if (setupEls.copyIncomingWebhookUrlBtn) {
    setupEls.copyIncomingWebhookUrlBtn.addEventListener('click', () => {
        const url = setupEls.incomingWebhookUrlDisplay ? setupEls.incomingWebhookUrlDisplay.value : '';
        if (url) {
            navigator.clipboard.writeText(url).then(() => {
                showToast('📋 Webhook URL copied to clipboard!');
            }).catch(() => {
                showToast('Failed to copy URL');
            });
        }
    });
}

// Attach to window
window.runWebhookTest = runWebhookTest;
window.getProviderBadgeVariant = getProviderBadgeVariant;
window.getProviderDisplayName = getProviderDisplayName;
window.renderWebhookChannels = renderWebhookChannels;
window.syncChannelModalProviderSections = syncChannelModalProviderSections;
window.openWebhookChannelModal = openWebhookChannelModal;
window.closeWebhookChannelModal = closeWebhookChannelModal;
window.parseHeadersFromInput = parseHeadersFromInput;
window.saveWebhookChannel = saveWebhookChannel;
window.testModalWebhookChannel = testModalWebhookChannel;
window.testIndividualChannel = testIndividualChannel;
window.updateIncomingWebhookSnippets = updateIncomingWebhookSnippets;
