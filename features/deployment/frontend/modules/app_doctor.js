/**
 * app_doctor.js — App Doctor Diagnostics Module
 * Runs pre-flight diagnostics across toolchains, SDKs, project structures, and credentials.
 * Formats checklist reports, scores, and markdown exports.
 */

const doctorState = {
    appId: null,
    flavor: 'prod',
    lastReportMarkdown: '',
};

function openDoctorModal(appId = null, flavor = null) {
    doctorState.appId = appId || state.selectedApp || '';
    doctorState.flavor = flavor || state.selectedEnv || 'prod';
    if (els.doctorOverlay) els.doctorOverlay.classList.add('ui-active');
    const displayTarget = doctorState.appId ? `App: ${doctorState.appId}` : 'Current Workspace';
    if (els.doctorSubtitle) {
        els.doctorSubtitle.textContent = `Pre-flight diagnostics for ${displayTarget} (${doctorState.flavor.toUpperCase()})`;
    }
    runDoctorDiagnostics();
}

function closeDoctorModal() {
    if (els.doctorOverlay) els.doctorOverlay.classList.remove('ui-active');
}

async function runDoctorDiagnostics() {
    if (!els.doctorStatusBanner) return;
    els.doctorStatusBanner.dataset.status = 'pending';
    els.doctorOverallIcon.textContent = '🩺';
    els.doctorOverallTitle.textContent = 'Diagnosing Environment...';
    els.doctorOverallSummary.textContent = 'Running pre-flight checks across toolchains, SDKs, and credentials';
    els.doctorScorePills.innerHTML = '<span class="ui-badge" data-variant="secondary">Running...</span>';
    els.doctorChecklistContainer.innerHTML = '<div class="empty-state">Running diagnostics...</div>';
    if (els.recheckDoctorBtn) els.recheckDoctorBtn.disabled = true;

    if (state.isDemoMode) {
        if (typeof renderDemoDoctorDiagnostics === 'function') {
            renderDemoDoctorDiagnostics();
        }
        return;
    }

    try {
        const queryApp = doctorState.appId ? `app=${encodeURIComponent(doctorState.appId)}&` : '';
        const queryFlavor = doctorState.flavor ? `flavor=${encodeURIComponent(doctorState.flavor)}` : 'flavor=prod';
        const res = await fetch(api(`/api/deployment/doctor?${queryApp}${queryFlavor}`));
        const data = await res.json();
        if (!data || !data.success) {
            throw new Error(data?.error || 'Diagnostic check failed');
        }

        doctorState.lastReportMarkdown = data.reportMarkdown || '';

        // Status banner
        els.doctorStatusBanner.dataset.status = data.overallStatus;
        if (data.overallStatus === 'pass') {
            els.doctorOverallIcon.textContent = '✅';
            els.doctorOverallTitle.textContent = 'All Systems Go · Ready to Build';
        } else if (data.overallStatus === 'warn') {
            els.doctorOverallIcon.textContent = '⚠️';
            els.doctorOverallTitle.textContent = 'Environment Warnings Detected';
        } else {
            els.doctorOverallIcon.textContent = '❌';
            els.doctorOverallTitle.textContent = 'Build-Breaking Issues Found';
        }
        els.doctorOverallSummary.textContent = data.summary;

        // Score pills
        let pillsHtml = `<span class="ui-badge" data-variant="success">${data.passCount} Passed</span>`;
        if (data.warnCount > 0) {
            pillsHtml += `<span class="ui-badge" data-variant="warning">${data.warnCount} Warnings</span>`;
        }
        if (data.failCount > 0) {
            pillsHtml += `<span class="ui-badge" data-variant="danger">${data.failCount} Failures</span>`;
        }
        els.doctorScorePills.innerHTML = pillsHtml;

        // Group checklist by category
        const categories = [
            { key: 'toolchain', title: 'SDK & Core Toolchain' },
            { key: 'project', title: 'Project Structure & Dependencies' },
            { key: 'android', title: 'Android Build Environment' },
            { key: 'ios', title: 'iOS Environment & Signing' },
            { key: 'credentials', title: 'Store Deployment Credentials' },
            { key: 'git', title: 'Git & Release Readiness' },
        ];

        const checks = data.checks || [];
        let html = '';

        categories.forEach(cat => {
            const catChecks = checks.filter(c => c.category === cat.key);
            if (!catChecks.length) return;

            html += `
                <div class="doctor-category-card">
                    <div class="doctor-category-header">
                        <span>${escapeHtml(cat.title)}</span>
                        <span style="font-size: 0.72rem; opacity: 0.8;">${catChecks.length} check${catChecks.length === 1 ? '' : 's'}</span>
                    </div>
                    <div>
            `;

            catChecks.forEach(c => {
                let badgeVariant = 'secondary';
                let badgeText = (c.status || '').toUpperCase();
                let statusIcon = 'check';

                if (c.status === 'pass') {
                    badgeVariant = 'success';
                    statusIcon = 'check-circle';
                } else if (c.status === 'warn') {
                    badgeVariant = 'warning';
                    statusIcon = 'alert-triangle';
                } else if (c.status === 'fail') {
                    badgeVariant = 'danger';
                    statusIcon = 'x-circle';
                } else if (c.status === 'info') {
                    badgeVariant = 'secondary';
                    statusIcon = 'info';
                }

                const hintBox = c.hint ? `
                    <div class="doctor-hint-box ${c.status === 'fail' ? 'fail' : ''}">
                        <strong>💡 Actionable Hint:</strong> ${escapeHtml(c.hint)}
                    </div>
                ` : '';

                html += `
                    <div class="doctor-check-row">
                        <div class="doctor-check-main">
                            <div class="doctor-check-name">
                                <i data-lucide="${statusIcon}" style="width:14px;height:14px;"></i>
                                <span>${escapeHtml(c.name)}</span>
                            </div>
                            <span class="ui-badge" data-variant="${badgeVariant}" style="font-size:0.68rem; text-transform:uppercase;">${badgeText}</span>
                        </div>
                        <div class="doctor-check-message">${escapeHtml(c.message)}</div>
                        ${hintBox}
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        });

        els.doctorChecklistContainer.innerHTML = html || '<div class="empty-state">No checks available.</div>';
        if (els.doctorFooterDuration) {
            els.doctorFooterDuration.textContent = `Diagnostics completed in ${data.durationMs}ms`;
        }
        if (typeof refreshIcons === 'function') refreshIcons();
    } catch (err) {
        els.doctorStatusBanner.dataset.status = 'fail';
        els.doctorOverallIcon.textContent = '❌';
        els.doctorOverallTitle.textContent = 'Diagnostic Execution Failed';
        els.doctorOverallSummary.textContent = err.message || 'Could not connect to backend';
        els.doctorChecklistContainer.innerHTML = `<div class="empty-state" style="color:var(--ui-danger);">${escapeHtml(err.message)}</div>`;
        showToast('App Doctor failed: ' + err.message, 'error');
    } finally {
        if (els.recheckDoctorBtn) els.recheckDoctorBtn.disabled = false;
    }
}

async function copyDoctorReport() {
    if (!doctorState.lastReportMarkdown) {
        showToast('No diagnostic report available to copy.');
        return;
    }
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(doctorState.lastReportMarkdown);
        } else {
            const ta = document.createElement('textarea');
            ta.value = doctorState.lastReportMarkdown;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
        showToast('Diagnostic report copied to clipboard!');
    } catch (err) {
        showToast('Could not copy report: ' + err.message);
    }
}

// Wire Doctor Events
if (els.openDoctorBtn) els.openDoctorBtn.addEventListener('click', () => openDoctorModal(state.selectedApp));
if (els.doctorPanelBtn) els.doctorPanelBtn.addEventListener('click', () => openDoctorModal(state.selectedApp));
if (els.closeDoctorModalBtn) els.closeDoctorModalBtn.addEventListener('click', closeDoctorModal);
if (els.recheckDoctorBtn) els.recheckDoctorBtn.addEventListener('click', runDoctorDiagnostics);
if (els.copyDoctorReportBtn) els.copyDoctorReportBtn.addEventListener('click', copyDoctorReport);
if (els.doctorOverlay) els.doctorOverlay.addEventListener('click', event => {
    if (event.target === els.doctorOverlay) closeDoctorModal();
});

// Attach to window
window.doctorState = doctorState;
window.openDoctorModal = openDoctorModal;
window.closeDoctorModal = closeDoctorModal;
window.runDoctorDiagnostics = runDoctorDiagnostics;
window.copyDoctorReport = copyDoctorReport;
