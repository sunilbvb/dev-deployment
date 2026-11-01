/**
 * Deployment & Build Queue Frontend Module.
 *
 * Provides sequential FIFO multi-app build management, live queue timeline,
 * reordering, pause/resume, and instant add-to-queue capabilities.
 */

(function () {
    let queueData = {
        queue: [],
        activeItem: null,
        isPaused: false,
        counts: { total: 0, pending: 0, running: 0, completed: 0, failed: 0 }
    };
    let queuePollInterval = null;
    let timerInterval = null;

    function getAuthHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        const token = window.__DEPLOYMENT_TOKEN__ || (() => {
            try { return localStorage.getItem('deployment_auth_token') || ''; } catch (_) { return ''; }
        })();
        if (token) headers['X-API-Token'] = token;
        if (window.state && state.activeWorkspace) headers['X-Workspace'] = state.activeWorkspace;
        return headers;
    }

    async function fetchQueue() {
        try {
            const url = typeof api === 'function' ? api('/api/deployment/queue') : '/api/deployment/queue';
            const res = await fetch(url, { headers: getAuthHeaders() });
            if (!res.ok) return;
            const data = await res.json();
            if (data.success) {
                queueData = data;
                renderQueueUI();
            }
        } catch (e) {
            console.debug('Failed to fetch deployment queue:', e);
        }
    }

    function renderQueueUI() {
        const badge = document.getElementById('navQueueBadge');
        if (badge) {
            const pendingAndRunning = (queueData.counts.pending || 0) + (queueData.counts.running || 0);
            badge.textContent = pendingAndRunning;
            if (queueData.counts.running > 0) {
                badge.style.color = '#38bdf8';
                badge.style.fontWeight = 'bold';
            } else {
                badge.style.color = '';
                badge.style.fontWeight = '';
            }
        }

        const workerBadge = document.getElementById('queueWorkerBadge');
        if (workerBadge) {
            if (queueData.isPaused) {
                workerBadge.textContent = 'PAUSED';
                workerBadge.dataset.variant = 'warning';
            } else if (queueData.counts.running > 0) {
                workerBadge.textContent = 'BUILDING';
                workerBadge.dataset.variant = 'primary';
            } else {
                workerBadge.textContent = 'IDLE';
                workerBadge.dataset.variant = 'neutral';
            }
        }

        const pauseBtn = document.getElementById('queuePauseResumeBtn');
        const pauseText = document.getElementById('queuePauseResumeText');
        if (pauseBtn && pauseText) {
            if (queueData.isPaused) {
                pauseText.textContent = 'Resume Queue';
                pauseBtn.dataset.variant = 'primary';
            } else {
                pauseText.textContent = 'Pause Queue';
                pauseBtn.dataset.variant = 'secondary';
            }
        }

        const stats = document.getElementById('queueSummaryStats');
        if (stats) {
            const c = queueData.counts;
            stats.textContent = `${c.pending} pending • ${c.running} running • ${c.completed} done`;
        }

        // Active running box
        const activeBox = document.getElementById('queueActiveItemBox');
        const active = queueData.activeItem;
        if (activeBox) {
            if (active && active.status === 'running') {
                activeBox.classList.remove('hidden');
                document.getElementById('queueActiveItemTitle').textContent = active.title || `${active.app} (${active.flavor})`;
                document.getElementById('queueActiveItemCommand').textContent = active.command;
            } else {
                activeBox.classList.add('hidden');
            }
        }

        // Items list & empty state
        const emptyState = document.getElementById('queueEmptyState');
        const list = document.getElementById('queueItemsList');
        if (list && emptyState) {
            if (!queueData.queue || queueData.queue.length === 0) {
                emptyState.style.display = 'block';
                list.innerHTML = '';
            } else {
                emptyState.style.display = 'none';
                renderItemsList(list, queueData.queue);
            }
        }

        if (typeof lucide !== 'undefined' && lucide.createIcons) {
            lucide.createIcons();
        }
    }

    function renderItemsList(container, items) {
        container.innerHTML = '';

        items.forEach((item, index) => {
            const row = document.createElement('div');
            row.className = 'queue-item-card';
            row.style.display = 'flex';
            row.style.alignItems = 'center';
            row.style.justifyContent = 'space-between';
            row.style.padding = '10px 14px';
            row.style.background = 'var(--ui-bg-surface, rgba(255,255,255,0.02))';
            row.style.border = '1px solid var(--ui-border)';
            row.style.borderRadius = '6px';
            row.style.gap = '12px';

            let statusPill = '';
            let statusBorder = 'transparent';
            if (item.status === 'running') {
                statusPill = '<span class="ui-badge" data-variant="primary" style="font-size:0.7rem;">BUILDING</span>';
                statusBorder = '#38bdf8';
                row.style.borderColor = 'rgba(56, 189, 248, 0.4)';
                row.style.background = 'rgba(56, 189, 248, 0.04)';
            } else if (item.status === 'pending') {
                statusPill = `<span class="ui-badge" data-variant="neutral" style="font-size:0.7rem;">#${index + 1} QUEUED</span>`;
            } else if (item.status === 'completed') {
                statusPill = '<span class="ui-badge" data-variant="success" style="font-size:0.7rem;">DONE</span>';
            } else if (item.status === 'failed') {
                statusPill = '<span class="ui-badge" data-variant="danger" style="font-size:0.7rem;">FAILED</span>';
            } else if (item.status === 'cancelled') {
                statusPill = '<span class="ui-badge" data-variant="warning" style="font-size:0.7rem;">STOPPED</span>';
            }

            const durationStr = item.durationSeconds != null ? `${item.durationSeconds}s` : '';
            const typePill = item.type === 'pipeline' ? '<span style="font-size:0.68rem; background:rgba(99,102,241,0.15); color:#818cf8; padding:1px 6px; border-radius:4px;">Pipeline</span>' : '';
            let wsPill = '';
            if (item.workspace) {
                const wsParts = item.workspace.replace(/\\/g, '/').split('/');
                const wsBase = wsParts[wsParts.length - 1] || item.workspace;
                wsPill = `<span style="font-size:0.68rem; background:rgba(255,255,255,0.06); color:var(--ui-text-muted); padding:1px 6px; border-radius:4px;" title="Workspace: ${escapeHtml(item.workspace)}">📁 ${escapeHtml(wsBase)}</span>`;
            }

            row.innerHTML = `
                <div style="display:flex; align-items:center; gap:12px; min-width:0; flex:1;">
                    <div style="flex-shrink:0;">${statusPill}</div>
                    <div style="min-width:0; flex:1;">
                        <div style="font-weight:600; font-size:0.86rem; display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                            <span style="color:var(--ui-text);">${escapeHtml(item.title || item.app)}</span>
                            <span style="font-size:0.7rem; color:var(--ui-text-muted); text-transform:uppercase; background:rgba(255,255,255,0.06); padding:1px 5px; border-radius:3px;">${escapeHtml(item.flavor || 'prod')}</span>
                            ${typePill}
                            ${wsPill}
                        </div>
                        <div style="font-size:0.75rem; color:var(--ui-text-muted); font-family:monospace; margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(item.command)}">
                            ${escapeHtml(item.command)}
                        </div>
                        ${item.error ? `<div style="font-size:0.72rem; color:#ef4444; margin-top:2px;">⚠️ ${escapeHtml(item.error)}</div>` : ''}
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:6px; flex-shrink:0;">
                    ${durationStr ? `<span style="font-size:0.75rem; color:var(--ui-text-muted); margin-right:4px;">${durationStr}</span>` : ''}
                    ${item.status === 'pending' ? `
                        <button type="button" class="ui-button queue-move-up-btn" data-variant="ghost" data-size="xs" title="Move Up" data-id="${item.id}" ${index === 0 ? 'disabled' : ''}>
                            ↑
                        </button>
                        <button type="button" class="ui-button queue-move-down-btn" data-variant="ghost" data-size="xs" title="Move Down" data-id="${item.id}" ${index === items.length - 1 ? 'disabled' : ''}>
                            ↓
                        </button>
                    ` : ''}
                    ${(item.status === 'failed' || item.status === 'cancelled') ? `
                        <button type="button" class="ui-button queue-retry-btn" data-variant="secondary" data-size="xs" title="Retry this build" data-id="${item.id}">
                            ↻ Retry
                        </button>
                    ` : ''}
                    ${item.status !== 'running' ? `
                        <button type="button" class="ui-button queue-remove-btn" data-variant="ghost" data-size="xs" title="Remove" data-id="${item.id}" style="color:var(--ui-danger, #ef4444); padding: 2px 6px;">
                            &times;
                        </button>
                    ` : ''}
                </div>
            `;

            container.appendChild(row);
        });

        // Attach action handlers
        container.querySelectorAll('.queue-move-up-btn').forEach(btn => {
            btn.addEventListener('click', () => moveItem(btn.dataset.id, -1));
        });
        container.querySelectorAll('.queue-move-down-btn').forEach(btn => {
            btn.addEventListener('click', () => moveItem(btn.dataset.id, 1));
        });
        container.querySelectorAll('.queue-remove-btn').forEach(btn => {
            btn.addEventListener('click', () => removeItem(btn.dataset.id));
        });
        container.querySelectorAll('.queue-retry-btn').forEach(btn => {
            btn.addEventListener('click', () => retryItem(btn.dataset.id));
        });
    }

    async function moveItem(itemId, direction) {
        const pendingItems = queueData.queue.filter(it => it.status === 'pending');
        const idx = pendingItems.findIndex(it => it.id === itemId);
        if (idx === -1) return;
        const targetIdx = idx + direction;
        if (targetIdx < 0 || targetIdx >= pendingItems.length) return;

        const temp = pendingItems[idx];
        pendingItems[idx] = pendingItems[targetIdx];
        pendingItems[targetIdx] = temp;

        const reorderedIds = pendingItems.map(it => it.id);
        try {
            const url = typeof api === 'function' ? api('/api/deployment/queue/reorder') : '/api/deployment/queue/reorder';
            await fetch(url, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ itemIds: reorderedIds })
            });
            fetchQueue();
        } catch (e) {
            console.error('Failed to reorder queue:', e);
        }
    }

    async function removeItem(itemId) {
        try {
            const url = typeof api === 'function' ? api('/api/deployment/queue/remove') : '/api/deployment/queue/remove';
            await fetch(url, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ itemId })
            });
            fetchQueue();
            if (typeof showToast === 'function') showToast('Queue item removed');
        } catch (e) {
            console.error('Failed to remove queue item:', e);
        }
    }

    async function retryItem(itemId) {
        try {
            const url = typeof api === 'function' ? api('/api/deployment/queue/retry') : '/api/deployment/queue/retry';
            const res = await fetch(url, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ itemId })
            });
            const data = await res.json();
            if (data.success) {
                fetchQueue();
                if (typeof showToast === 'function') showToast('Build re-enqueued to runner');
            }
        } catch (e) {
            console.error('Failed to retry queue item:', e);
        }
    }

    async function addToQueueCurrent() {
        if (!window.state || !state.selectedApp) {
            if (typeof showToast === 'function') showToast('Please select an app first');
            return;
        }

        const isPipeline = !!state.selectedPipeline;
        let payload = {};

        if (isPipeline) {
            payload = {
                app: state.selectedApp,
                type: 'pipeline',
                command: state.selectedPipeline.id,
                flavor: state.selectedPipeline.flavor || 'prod',
                title: `${state.selectedApp} • Pipeline: ${state.selectedPipeline.name}`
            };
        } else {
            if (!state.selectedCommand) {
                if (typeof showToast === 'function') showToast('Please select a command to queue');
                return;
            }
            const cmd = state.selectedCommand;
            const commandKey = typeof resolvedCommandForExecution === 'function' ? resolvedCommandForExecution() : (cmd.key || cmd.id);
            const canUseCloud = cmd.platform === 'android' || ['build_aab', 'build_apk', 'deploy_aab', 'upload_aab'].includes(cmd.templateId);
            const runner = (canUseCloud && state.selectedRunner === 'github_actions') ? 'github_actions' : (cmd.runner || 'make');
            const cleanBuildToggle = document.getElementById('cleanBuildToggle');
            const cleanBuild = cleanBuildToggle ? cleanBuildToggle.checked : null;
            const stopOnErrorToggle = document.getElementById('queueStopOnErrorToggle');
            const stopOnError = stopOnErrorToggle ? stopOnErrorToggle.checked : true;

            let releaseNotes = null;
            if (typeof getRunReleaseNotes === 'function') {
                try { releaseNotes = getRunReleaseNotes(); } catch (_) {}
            }

            payload = {
                app: state.selectedApp,
                type: 'command',
                command: commandKey,
                runner: runner,
                flavor: typeof selectedEnvForExecution === 'function' ? selectedEnvForExecution() : (cmd.flavor || 'prod'),
                templateId: cmd.templateId || '',
                title: `${state.selectedApp} • ${cmd.title || cmd.name || commandKey}`,
                cleanBuild: cleanBuild,
                releaseNotes: releaseNotes,
                stopOnError: stopOnError
            };
        }

        try {
            const url = typeof api === 'function' ? api('/api/deployment/queue/add') : '/api/deployment/queue/add';
            const res = await fetch(url, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                if (typeof showToast === 'function') {
                    showToast(`Queued build for ${state.selectedApp}`);
                }
                fetchQueue();
            } else {
                if (typeof showToast === 'function') {
                    showToast(`Failed to queue: ${data.error || 'Unknown error'}`);
                }
            }
        } catch (e) {
            console.error('Error enqueuing build:', e);
            if (typeof showToast === 'function') showToast(`Failed to queue: ${e.message}`);
        }
    }

    function openQueueModal() {
        const overlay = document.getElementById('queueModalOverlay');
        if (overlay) {
            overlay.classList.add('ui-active');
            fetchQueue();
        }
    }

    function closeQueueModal() {
        const overlay = document.getElementById('queueModalOverlay');
        if (overlay) overlay.classList.remove('ui-active');
    }

    function initQueueModule() {
        // Nav Link open modal
        const navLink = document.getElementById('navLinkQueue');
        if (navLink) navLink.addEventListener('click', openQueueModal);

        // Add to queue button in execution panel
        const addBtn = document.getElementById('addToQueueBtn');
        if (addBtn) addBtn.addEventListener('click', addToQueueCurrent);

        // Close modal buttons
        const closeBtn = document.getElementById('closeQueueModalBtn');
        if (closeBtn) closeBtn.addEventListener('click', closeQueueModal);

        const closeFooterBtn = document.getElementById('closeQueueModalFooterBtn');
        if (closeFooterBtn) closeFooterBtn.addEventListener('click', closeQueueModal);

        const overlay = document.getElementById('queueModalOverlay');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) closeQueueModal();
            });
        }

        // Pause / Resume button
        const pauseBtn = document.getElementById('queuePauseResumeBtn');
        if (pauseBtn) {
            pauseBtn.addEventListener('click', async () => {
                const endpoint = queueData.isPaused ? '/api/deployment/queue/resume' : '/api/deployment/queue/pause';
                const url = typeof api === 'function' ? api(endpoint) : endpoint;
                try {
                    await fetch(url, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({}) });
                    fetchQueue();
                } catch (e) {
                    console.error('Error toggling queue pause state:', e);
                }
            });
        }

        // Clear completed
        const clearCompletedBtn = document.getElementById('queueClearCompletedBtn');
        if (clearCompletedBtn) {
            clearCompletedBtn.addEventListener('click', async () => {
                const url = typeof api === 'function' ? api('/api/deployment/queue/clear') : '/api/deployment/queue/clear';
                try {
                    await fetch(url, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ clearAll: false }) });
                    fetchQueue();
                } catch (e) {
                    console.error('Error clearing completed queue items:', e);
                }
            });
        }

        // Clear all pending
        const clearAllBtn = document.getElementById('queueClearAllBtn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', async () => {
                const url = typeof api === 'function' ? api('/api/deployment/queue/clear') : '/api/deployment/queue/clear';
                try {
                    await fetch(url, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ clearAll: true }) });
                    fetchQueue();
                } catch (e) {
                    console.error('Error clearing all queue items:', e);
                }
            });
        }

        // Stop active item
        const stopActiveBtn = document.getElementById('queueStopActiveBtn');
        if (stopActiveBtn) {
            stopActiveBtn.addEventListener('click', async () => {
                const url = typeof api === 'function' ? api('/api/deployment/queue/stop-current') : '/api/deployment/queue/stop-current';
                try {
                    await fetch(url, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({}) });
                    fetchQueue();
                } catch (e) {
                    console.error('Error stopping active queue item:', e);
                }
            });
        }

        // Polling loop for active queue updates
        if (queuePollInterval) clearInterval(queuePollInterval);
        queuePollInterval = setInterval(fetchQueue, 3000);

        // Timer updater for active item
        if (timerInterval) clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            if (queueData.activeItem && queueData.activeItem.startedAt) {
                const timerEl = document.getElementById('queueActiveItemTimer');
                if (timerEl) {
                    const elapsed = Math.floor(Date.now() / 1000 - queueData.activeItem.startedAt);
                    const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
                    const s = String(elapsed % 60).padStart(2, '0');
                    timerEl.textContent = `${m}:${s}`;
                }
            }
        }, 1000);

        // Initial fetch
        fetchQueue();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initQueueModule);
    } else {
        initQueueModule();
    }

    window.openQueueModal = openQueueModal;
    window.closeQueueModal = closeQueueModal;
    window.fetchQueue = fetchQueue;
})();
