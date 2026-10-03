/**
 * setup_pipelines.js — Setup Pipelines Module
 * Manages the multi-step deployment pipeline builder, step catalog picker,
 * custom shell steps, step reordering, and pipeline persistence/deletion.
 */

const pipelineEls = {
    list: document.getElementById('setupPipelinesList'),
    newBtn: document.getElementById('newPipelineBtn'),
    card: document.getElementById('pipelineEditorCard'),
    title: document.getElementById('pipelineEditorTitle'),
    name: document.getElementById('pipelineEditName'),
    flavor: document.getElementById('pipelineEditFlavor'),
    addStepBtn: document.getElementById('addStepBtn'),
    addCustomStepBtn: document.getElementById('addCustomStepBtn'),
    stepsContainer: document.getElementById('pipelineEditStepsContainer'),
    cancelBtn: document.getElementById('cancelPipelineEditBtn'),
    saveBtn: document.getElementById('savePipelineBtn'),
    // Visual Step Picker Modal elements
    stepPickerModal: document.getElementById('stepPickerModal'),
    closeStepPickerModalBtn: document.getElementById('closeStepPickerModalBtn'),
    cancelStepPickerBtn: document.getElementById('cancelStepPickerBtn'),
    stepPickerFilterTabs: document.getElementById('stepPickerFilterTabs'),
    stepPickerSearch: document.getElementById('stepPickerSearch'),
    stepPickerTilesContainer: document.getElementById('stepPickerTilesContainer'),
    // Custom Shell Step Modal elements
    customStepModal: document.getElementById('customStepModal'),
    closeCustomStepModalBtn: document.getElementById('closeCustomStepModalBtn'),
    cancelCustomStepBtn: document.getElementById('cancelCustomStepBtn'),
    confirmAddCustomStepBtn: document.getElementById('confirmAddCustomStepBtn'),
    customStepLabelInput: document.getElementById('customStepLabelInput'),
    customStepCmdInput: document.getElementById('customStepCmdInput'),
    customStepContinueChk: document.getElementById('customStepContinueChk'),
};

let currentEditingPipeline = null;
let currentEditingSteps = [];
let availableAppCommands = [];
let currentStepFilterCat = 'all';

const STEP_TEMPLATES_CATALOG = [
    // Build
    { id: 'build_apk', category: 'build', name: 'Build Android APK', icon: 'smartphone', desc: 'Compile Android APK install package for local distribution or device testing.' },
    { id: 'build_aab', category: 'build', name: 'Build Android App Bundle (AAB)', icon: 'package', desc: 'Compile optimized Google Play Store release bundle ready for store upload.' },
    { id: 'build_ipa', category: 'build', name: 'Build iOS IPA', icon: 'apple', desc: 'Archive and codesign iOS IPA application for TestFlight or App Store.' },

    // Deploy & Upload
    { id: 'deploy_aab', category: 'deploy', name: 'Upload to Google Play', icon: 'upload-cloud', desc: 'Deploy App Bundle to Google Play Console track (Internal, Closed Beta, or Production).' },
    { id: 'deploy_ipa', category: 'deploy', name: 'Upload to TestFlight', icon: 'send', desc: 'Upload signed IPA to Apple App Store Connect TestFlight via API key.' },
    { id: 'deploy_both', category: 'deploy', name: 'Deploy Both Platforms', icon: 'rocket', desc: 'Sequentially build and deploy both Android AAB and iOS IPA.' },

    // Diagnostics & Health
    { id: 'sentinel', category: 'diagnostics', name: 'Deployment Sentinel Check', icon: 'shield-check', desc: 'Pre-flight check: validate keystores, bundle IDs, and certificates.', customCmd: 'python3 tool/sentinel.py' },
    { id: 'doctor', category: 'diagnostics', name: 'App Health Doctor', icon: 'activity', desc: 'Run diagnostics to verify local build toolchains & prerequisites.', customCmd: 'python3 -m unittest discover tests' },
    { id: 'unit_tests', category: 'diagnostics', name: 'Run Automated Tests', icon: 'check-circle-2', desc: 'Execute automated test suite before building artifacts.', customCmd: 'flutter test' },

    // Release Automation
    { id: 'release_changelog', category: 'release', name: 'Generate Changelog', icon: 'file-text', desc: 'Collate recent git commits into structured release notes.' },
    { id: 'release_bump_patch', category: 'release', name: 'Bump Patch Version', icon: 'hash', desc: 'Increment patch version (e.g. v1.0.0 → v1.0.1).' },
    { id: 'release_bump_minor', category: 'release', name: 'Bump Minor Version', icon: 'arrow-up-circle', desc: 'Increment minor version (e.g. v1.0.0 → v1.1.0).' },
    { id: 'release_bump_major', category: 'release', name: 'Bump Major Version', icon: 'award', desc: 'Increment major version (e.g. v1.0.0 → v2.0.0).' },
    { id: 'release_tag', category: 'release', name: 'Create Git Release Tag', icon: 'tag', desc: 'Tag git commit with current semantic version string.' },
    { id: 'release_push', category: 'release', name: 'Push to Remote Git', icon: 'git-pull-request', desc: 'Push current branch commits and newly created release tags.' },
];

async function renderSetupPipelines(appId) {
    if (!appId || !pipelineEls.list) return;
    const cfg = setupState.deployConfig.apps?.[appId] || {};
    const pipelines = cfg.pipelines || [];

    if (!pipelines.length) {
        pipelineEls.list.innerHTML = `
            <div style="padding: 16px; text-align: center; color: var(--ui-text-muted); font-size: 0.85rem; border: 1px dashed var(--ui-border-color); border-radius: 6px;">
                No pipelines created for this app yet. Click <strong>New Pipeline</strong> above to create your first automated workflow.
            </div>
        `;
        return;
    }

    pipelineEls.list.innerHTML = pipelines.map(pipe => {
        const stepCount = (pipe.steps || []).length;
        const flavorLabel = pipe.flavor ? `<span class="ui-badge" data-variant="info">${escapeHtml(pipe.flavor.toUpperCase())}</span>` : '<span class="ui-badge" data-variant="ghost">ANY FLAVOR</span>';
        const stepsPreview = (pipe.steps || []).map(s => escapeHtml(s.name || s.templateId || 'Custom')).join(' → ');

        return `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--ui-card-bg, #1e293b); border: 1px solid var(--ui-border-color); border-radius: 8px;">
                <div style="min-width: 0; flex: 1; margin-right: 12px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <strong style="font-size: 0.95rem;">${escapeHtml(pipe.name)}</strong>
                        ${flavorLabel}
                        <span style="font-size: 0.75rem; color: var(--ui-text-muted);">${stepCount} step${stepCount === 1 ? '' : 's'}</span>
                    </div>
                    <div style="font-size: 0.78rem; color: var(--ui-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${stepsPreview}">
                        ${stepsPreview || 'No steps configured'}
                    </div>
                </div>
                <div style="display: flex; gap: 6px; flex-shrink: 0;">
                    <button type="button" class="ui-button" data-variant="primary" data-size="sm" data-pipe-run="${escapeHtml(pipe.id)}" title="Run this pipeline on Dashboard">
                        <i data-lucide="play" style="width:12px;height:12px;"></i>
                        <span>Run</span>
                    </button>
                    <button type="button" class="ui-button" data-variant="secondary" data-size="sm" data-pipe-edit="${escapeHtml(pipe.id)}">Edit</button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="sm" data-pipe-dup="${escapeHtml(pipe.id)}" title="Duplicate">Duplicate</button>
                    <button type="button" class="ui-button" data-variant="danger" data-size="sm" data-pipe-del="${escapeHtml(pipe.id)}" title="Delete">Delete</button>
                </div>
            </div>
        `;
    }).join('');

    pipelineEls.list.querySelectorAll('[data-pipe-run]').forEach(btn => {
        btn.addEventListener('click', () => {
            const pipeId = btn.dataset.pipeRun;
            closeSetupModal();
            const pipeCard = document.querySelector(`[data-pipeline-id="${pipeId}"]`);
            if (pipeCard) {
                pipeCard.click();
                pipeCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                showToast(`Selected pipeline on dashboard. Click 'Run Pipeline' to execute.`);
            } else {
                showToast(`Pipeline selected. Switch to dashboard to run.`);
            }
        });
    });

    pipelineEls.list.querySelectorAll('[data-pipe-edit]').forEach(btn => {
        btn.addEventListener('click', () => {
            const p = pipelines.find(x => x.id === btn.dataset.pipeEdit);
            if (p) openPipelineEditor(p);
        });
    });

    pipelineEls.list.querySelectorAll('[data-pipe-dup]').forEach(btn => {
        btn.addEventListener('click', () => duplicatePipeline(btn.dataset.pipeDup));
    });

    pipelineEls.list.querySelectorAll('[data-pipe-del]').forEach(btn => {
        btn.addEventListener('click', () => deletePipeline(btn.dataset.pipeDel));
    });

    if (window.lucide && typeof lucide.createIcons === 'function') window.lucide.createIcons();
}

async function openPipelineEditor(pipe = null) {
    currentEditingPipeline = pipe ? JSON.parse(JSON.stringify(pipe)) : null;
    currentEditingSteps = pipe ? (pipe.steps || []).map(s => ({...s})) : [];

    pipelineEls.title.textContent = pipe ? `Edit Pipeline: ${pipe.name}` : 'New Pipeline';
    pipelineEls.name.value = pipe ? pipe.name : '';

    const flavors = getActiveFlavors();
    pipelineEls.flavor.innerHTML = '<option value="">Any / Selected Flavor</option>' +
        flavors.map(f => `<option value="${escapeHtml(f)}" ${pipe && pipe.flavor === f ? 'selected' : ''}>${escapeHtml(f.toUpperCase())}</option>`).join('');

    try {
        const cmdRes = await fetch(`/api/deployment/commands?app=${encodeURIComponent(setupState.selectedAppId)}`).then(r => r.json());
        availableAppCommands = cmdRes.commands || [];
    } catch (_) {
        availableAppCommands = [];
    }

    renderPipelineEditingSteps();
    pipelineEls.card.classList.remove('hidden');
    pipelineEls.name.focus();
}

function closePipelineEditor() {
    currentEditingPipeline = null;
    currentEditingSteps = [];
    pipelineEls.card.classList.add('hidden');
}

function renderPipelineEditingSteps() {
    if (!currentEditingSteps.length) {
        pipelineEls.stepsContainer.innerHTML = `
            <div style="padding: 12px; text-align: center; color: var(--ui-text-muted); font-size: 0.8rem; border: 1px dashed var(--ui-border-color); border-radius: 6px;">
                No steps added yet. Click <strong>Add Template Step</strong> or <strong>Add Custom Shell Step</strong> above.
            </div>
        `;
        return;
    }

    const flavors = getActiveFlavors();

    pipelineEls.stepsContainer.innerHTML = currentEditingSteps.map((step, idx) => {
        const isCustom = !!step.command;
        const title = step.name || (isCustom ? step.command : step.templateId);
        const subtitle = isCustom ? `Custom: ${escapeHtml(step.command)}` : `Template: ${escapeHtml(step.templateId)}`;
        const badge = isCustom ? '<span class="ui-badge" data-variant="warning" style="margin-left:6px;">Custom</span>' : '';

        const flavorOptions = ['<option value="">Default (Inherit)</option>']
            .concat(flavors.map(f => `<option value="${escapeHtml(f)}" ${step.flavor === f ? 'selected' : ''}>${escapeHtml(f.toUpperCase())}</option>`))
            .join('');

        return `
            <div class="pipeline-step-item" data-step-idx="${idx}" style="display:flex; align-items:center; gap:10px; padding:10px 12px; background:var(--ui-card-bg, #1e293b); border:1px solid var(--ui-border-color); border-radius:6px;">
                <div class="pipeline-step-index" style="width:24px; height:24px; border-radius:50%; background:var(--ui-surface-2, rgba(255,255,255,0.06)); display:flex; align-items:center; justify-content:center; font-weight:700; font-size:0.75rem;">${idx + 1}</div>
                <div style="min-width: 0; flex: 1;">
                    <div style="font-weight: 600; font-size: 0.88rem; display:flex; align-items:center;">
                        ${escapeHtml(title)} ${badge}
                    </div>
                    <div style="font-size: 0.72rem; color: var(--ui-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${subtitle}
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:8px; flex-shrink:0;">
                    <select class="ui-select" data-step-flavor="${idx}" style="font-size:0.75rem; padding:3px 8px; height:28px; width:auto;" title="Step-specific flavor override">
                        ${flavorOptions}
                    </select>
                    <label class="ui-control" style="font-size: 0.75rem; margin: 0; display: flex; align-items: center; gap: 4px;" title="Continue running later steps even if this step fails">
                        <input type="checkbox" class="ui-checkbox" data-step-continue="${idx}" ${step.continueOnFailure ? 'checked' : ''}>
                        <span>Continue on fail</span>
                    </label>
                </div>
                <div class="step-actions" style="display:flex; gap:2px; flex-shrink:0;">
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-step-up="${idx}" ${idx === 0 ? 'disabled' : ''} title="Move Up">↑</button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-step-down="${idx}" ${idx === currentEditingSteps.length - 1 ? 'disabled' : ''} title="Move Down">↓</button>
                    <button type="button" class="ui-button" data-variant="ghost" data-size="xs" data-step-rm="${idx}" title="Remove Step">×</button>
                </div>
            </div>
        `;
    }).join('');

    pipelineEls.stepsContainer.querySelectorAll('[data-step-flavor]').forEach(sel => {
        sel.addEventListener('change', () => {
            const idx = Number(sel.dataset.stepFlavor);
            if (currentEditingSteps[idx]) currentEditingSteps[idx].flavor = sel.value;
        });
    });

    pipelineEls.stepsContainer.querySelectorAll('[data-step-continue]').forEach(chk => {
        chk.addEventListener('change', () => {
            const idx = Number(chk.dataset.stepContinue);
            if (currentEditingSteps[idx]) currentEditingSteps[idx].continueOnFailure = chk.checked;
        });
    });

    pipelineEls.stepsContainer.querySelectorAll('[data-step-up]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = Number(btn.dataset.stepUp);
            if (idx > 0) {
                const temp = currentEditingSteps[idx];
                currentEditingSteps[idx] = currentEditingSteps[idx - 1];
                currentEditingSteps[idx - 1] = temp;
                renderPipelineEditingSteps();
            }
        });
    });

    pipelineEls.stepsContainer.querySelectorAll('[data-step-down]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = Number(btn.dataset.stepDown);
            if (idx < currentEditingSteps.length - 1) {
                const temp = currentEditingSteps[idx];
                currentEditingSteps[idx] = currentEditingSteps[idx + 1];
                currentEditingSteps[idx + 1] = temp;
                renderPipelineEditingSteps();
            }
        });
    });

    pipelineEls.stepsContainer.querySelectorAll('[data-step-rm]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = Number(btn.dataset.stepRm);
            currentEditingSteps.splice(idx, 1);
            renderPipelineEditingSteps();
        });
    });
}

function renderStepPickerTiles(filterCat = 'all', searchQuery = '') {
    if (!pipelineEls.stepPickerTilesContainer) return;
    currentStepFilterCat = filterCat;
    const query = searchQuery.trim().toLowerCase();

    const filtered = STEP_TEMPLATES_CATALOG.filter(item => {
        if (filterCat !== 'all' && item.category !== filterCat) return false;
        if (query) {
            const matchName = item.name.toLowerCase().includes(query);
            const matchDesc = item.desc.toLowerCase().includes(query);
            const matchId = item.id.toLowerCase().includes(query);
            if (!matchName && !matchDesc && !matchId) return false;
        }
        return true;
    });

    if (!filtered.length) {
        pipelineEls.stepPickerTilesContainer.innerHTML = `
            <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--ui-text-muted); font-size: 0.85rem;">
                No matching steps found for "${escapeHtml(searchQuery)}".
            </div>
        `;
        return;
    }

    const catBadges = {
        build: '<span class="ui-badge" data-variant="primary" style="font-size:0.65rem;">Build</span>',
        deploy: '<span class="ui-badge" data-variant="success" style="font-size:0.65rem;">Deploy</span>',
        diagnostics: '<span class="ui-badge" data-variant="warning" style="font-size:0.65rem;">Quality</span>',
        release: '<span class="ui-badge" data-variant="info" style="font-size:0.65rem;">Release</span>',
    };

    pipelineEls.stepPickerTilesContainer.innerHTML = filtered.map(item => {
        const badge = catBadges[item.category] || '';
        return `
            <div class="ui-card step-picker-tile" data-template-id="${escapeHtml(item.id)}" style="padding: 14px; cursor: pointer; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid var(--ui-border-color); border-radius: 8px; transition: border-color 0.15s, background 0.15s;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i data-lucide="${escapeHtml(item.icon)}" style="width: 18px; height: 18px; color: var(--ui-primary, #6366f1);"></i>
                            <strong style="font-size: 0.88rem;">${escapeHtml(item.name)}</strong>
                        </div>
                        ${badge}
                    </div>
                    <p style="font-size: 0.76rem; color: var(--ui-text-muted); margin: 0 0 10px 0; line-height: 1.35;">${escapeHtml(item.desc)}</p>
                </div>
                <div style="display: flex; justify-content: flex-end; align-items: center; margin-top: 6px;">
                    <button type="button" class="ui-button" data-variant="secondary" data-size="xs" style="pointer-events: none;">
                        <i data-lucide="plus"></i>
                        <span>Add</span>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    pipelineEls.stepPickerTilesContainer.querySelectorAll('.step-picker-tile').forEach(tile => {
        tile.addEventListener('click', () => {
            const tmplId = tile.dataset.templateId;
            const def = STEP_TEMPLATES_CATALOG.find(x => x.id === tmplId);
            if (!def) return;

            if (def.customCmd) {
                currentEditingSteps.push({
                    name: def.name,
                    command: def.customCmd,
                    continueOnFailure: false,
                });
            } else {
                currentEditingSteps.push({
                    templateId: def.id,
                    name: def.name,
                    continueOnFailure: false,
                });
            }

            closeStepPickerModal();
            renderPipelineEditingSteps();
            showToast(`Added step: ${def.name}`);
        });
    });

    if (window.lucide && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
}

function openStepPickerModal() {
    if (!pipelineEls.stepPickerModal) return;
    if (pipelineEls.stepPickerSearch) pipelineEls.stepPickerSearch.value = '';
    if (pipelineEls.stepPickerFilterTabs) {
        pipelineEls.stepPickerFilterTabs.querySelectorAll('button').forEach(b => {
            b.dataset.variant = b.dataset.stepCat === 'all' ? 'primary' : 'secondary';
        });
    }
    renderStepPickerTiles('all', '');
    pipelineEls.stepPickerModal.classList.add('ui-active');
    if (pipelineEls.stepPickerSearch) pipelineEls.stepPickerSearch.focus();
}

function closeStepPickerModal() {
    if (pipelineEls.stepPickerModal) pipelineEls.stepPickerModal.classList.remove('ui-active');
}

function openCustomStepModal() {
    if (!pipelineEls.customStepModal) return;
    if (pipelineEls.customStepLabelInput) pipelineEls.customStepLabelInput.value = '';
    if (pipelineEls.customStepCmdInput) pipelineEls.customStepCmdInput.value = '';
    if (pipelineEls.customStepContinueChk) pipelineEls.customStepContinueChk.checked = false;
    pipelineEls.customStepModal.classList.add('ui-active');
    if (pipelineEls.customStepLabelInput) pipelineEls.customStepLabelInput.focus();
}

function closeCustomStepModal() {
    if (pipelineEls.customStepModal) pipelineEls.customStepModal.classList.remove('ui-active');
}

function addCustomStepFromModal() {
    const cmd = pipelineEls.customStepCmdInput ? pipelineEls.customStepCmdInput.value.trim() : '';
    if (!cmd) {
        showToast('Please enter a shell command.', 'warning');
        return;
    }
    const label = (pipelineEls.customStepLabelInput ? pipelineEls.customStepLabelInput.value.trim() : '') || cmd;
    const cont = pipelineEls.customStepContinueChk ? pipelineEls.customStepContinueChk.checked : false;

    currentEditingSteps.push({
        name: label,
        command: cmd,
        continueOnFailure: cont,
    });

    closeCustomStepModal();
    renderPipelineEditingSteps();
    showToast(`Added custom step: ${label}`);
}

async function savePipelineFromEditor() {
    const name = pipelineEls.name.value.trim();
    if (!name || name.length > 60) {
        showToast('Pipeline name is required (1–60 characters).', 'error');
        return;
    }

    if (!currentEditingSteps.length) {
        showToast('Pipeline must have at least 1 step.', 'error');
        return;
    }
    if (currentEditingSteps.length > 20) {
        showToast('Maximum 20 steps allowed per pipeline.', 'error');
        return;
    }

    const appId = setupState.selectedAppId;
    if (!appId) return;

    const flavor = pipelineEls.flavor.value || undefined;
    let pipeId = currentEditingPipeline?.id;
    if (!pipeId) {
        pipeId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
        if (!pipeId) pipeId = 'pipeline-' + Date.now();
    }

    const pipelineObj = {
        id: pipeId,
        name,
        flavor,
        steps: currentEditingSteps,
    };

    pipelineEls.saveBtn.disabled = true;
    try {
        const res = await fetch('/api/deployment/pipelines/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app: appId, pipeline: pipelineObj }),
        }).then(r => r.json());

        if (res.success) {
            showToast('Pipeline saved successfully!');
            closePipelineEditor();
            if (setupState.deployConfig.apps?.[appId]) {
                setupState.deployConfig.apps[appId].pipelines = res.pipelines;
            }
            renderSetupPipelines(appId);
            if (typeof loadCommands === 'function') {
                loadCommands(appId);
            }
        } else {
            showToast('Failed to save pipeline: ' + (res.error || 'unknown error'), 'error');
        }
    } catch (err) {
        showToast('Error saving pipeline: ' + err.message, 'error');
    } finally {
        pipelineEls.saveBtn.disabled = false;
    }
}

async function duplicatePipeline(pipeId) {
    const appId = setupState.selectedAppId;
    if (!appId) return;
    const cfg = setupState.deployConfig.apps?.[appId];
    if (!cfg || !cfg.pipelines) return;

    const source = cfg.pipelines.find(p => p.id === pipeId);
    if (!source) return;

    const copy = JSON.parse(JSON.stringify(source));
    copy.id = `${source.id}-copy`;
    let suffix = 1;
    while (cfg.pipelines.some(p => p.id === copy.id)) {
        copy.id = `${source.id}-copy-${suffix++}`;
    }
    copy.name = `${source.name} (Copy)`;

    try {
        const res = await fetch('/api/deployment/pipelines/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app: appId, pipeline: copy }),
        }).then(r => r.json());

        if (res.success) {
            showToast('Pipeline duplicated!');
            if (setupState.deployConfig.apps?.[appId]) {
                setupState.deployConfig.apps[appId].pipelines = res.pipelines;
            }
            renderSetupPipelines(appId);
            if (typeof loadCommands === 'function') loadCommands(appId);
        } else {
            showToast('Duplicate failed: ' + (res.error || ''), 'error');
        }
    } catch (err) {
        showToast('Duplicate failed: ' + err.message, 'error');
    }
}

async function deletePipeline(pipeId) {
    if (!confirm('Are you sure you want to delete this pipeline?')) return;
    const appId = setupState.selectedAppId;
    if (!appId) return;

    try {
        const res = await fetch('/api/deployment/pipelines/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app: appId, pipelineId: pipeId }),
        }).then(r => r.json());

        if (res.success) {
            showToast('Pipeline deleted.');
            if (currentEditingPipeline && currentEditingPipeline.id === pipeId) {
                closePipelineEditor();
            }
            if (setupState.deployConfig.apps?.[appId]) {
                setupState.deployConfig.apps[appId].pipelines = res.pipelines;
            }
            renderSetupPipelines(appId);
            if (typeof loadCommands === 'function') loadCommands(appId);
        } else {
            showToast('Delete failed: ' + (res.error || ''), 'error');
        }
    } catch (err) {
        showToast('Delete failed: ' + err.message, 'error');
    }
}

// Wire Pipeline Events
if (pipelineEls.newBtn) pipelineEls.newBtn.addEventListener('click', () => openPipelineEditor(null));
if (pipelineEls.cancelBtn) pipelineEls.cancelBtn.addEventListener('click', closePipelineEditor);
if (pipelineEls.saveBtn) pipelineEls.saveBtn.addEventListener('click', savePipelineFromEditor);
if (pipelineEls.addStepBtn) pipelineEls.addStepBtn.addEventListener('click', openStepPickerModal);
if (pipelineEls.addCustomStepBtn) pipelineEls.addCustomStepBtn.addEventListener('click', openCustomStepModal);
if (pipelineEls.closeStepPickerModalBtn) pipelineEls.closeStepPickerModalBtn.addEventListener('click', closeStepPickerModal);
if (pipelineEls.cancelStepPickerBtn) pipelineEls.cancelStepPickerBtn.addEventListener('click', closeStepPickerModal);
if (pipelineEls.stepPickerSearch) {
    pipelineEls.stepPickerSearch.addEventListener('input', e => renderStepPickerTiles(currentStepFilterCat, e.target.value));
}
if (pipelineEls.stepPickerFilterTabs) {
    pipelineEls.stepPickerFilterTabs.addEventListener('click', e => {
        const btn = e.target.closest('button[data-step-cat]');
        if (!btn) return;
        pipelineEls.stepPickerFilterTabs.querySelectorAll('button').forEach(b => { b.dataset.variant = 'secondary'; });
        btn.dataset.variant = 'primary';
        renderStepPickerTiles(btn.dataset.stepCat, pipelineEls.stepPickerSearch ? pipelineEls.stepPickerSearch.value : '');
    });
}
if (pipelineEls.closeCustomStepModalBtn) pipelineEls.closeCustomStepModalBtn.addEventListener('click', closeCustomStepModal);
if (pipelineEls.cancelCustomStepBtn) pipelineEls.cancelCustomStepBtn.addEventListener('click', closeCustomStepModal);
if (pipelineEls.confirmAddCustomStepBtn) pipelineEls.confirmAddCustomStepBtn.addEventListener('click', addCustomStepFromModal);

// Attach to window
window.renderSetupPipelines = renderSetupPipelines;
window.openPipelineEditor = openPipelineEditor;
window.closePipelineEditor = closePipelineEditor;
window.renderPipelineEditingSteps = renderPipelineEditingSteps;
window.renderStepPickerTiles = renderStepPickerTiles;
window.openStepPickerModal = openStepPickerModal;
window.closeStepPickerModal = closeStepPickerModal;
window.openCustomStepModal = openCustomStepModal;
window.closeCustomStepModal = closeCustomStepModal;
window.addCustomStepFromModal = addCustomStepFromModal;
window.savePipelineFromEditor = savePipelineFromEditor;
window.duplicatePipeline = duplicatePipeline;
window.deletePipeline = deletePipeline;
